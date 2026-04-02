"""
Evaluation metric computation service.

Extracted from app.routers.evaluation to separate business logic from HTTP
orchestration. All metric computation lives here; the router delegates to
these functions.

Historical bug fixes preserved verbatim:
  Bug fix #1 (baseline authority inflation) — _compute_baseline_authority_from_precomputed
  Bug fix #2 (detail/survey inconsistency)  — party_top_expert fallback in _compute_automated_metrics
  Bug fix #3 (wrong experts panel)          — lives in query.py (post-generation SSE patch)
"""

import math
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from app.models.evaluation import AutomatedMetrics, AggregatedMetrics

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 10 parliamentary groups in the system
ALL_PARTIES = 10

# Known parliamentary groups — Governo is excluded from party coverage count
KNOWN_PARTIES = {
    "Fratelli d'Italia",
    "Lega - Salvini Premier",
    "Forza Italia - Berlusconi Presidente - PPE",
    "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare",
    "Partito Democratico - Italia Democratica e Progressista",
    "Movimento 5 Stelle",
    "Alleanza Verdi e Sinistra",
    "Azione - Popolari Europeisti Riformatori - Renew Europe",
    "Italia Viva - Il Centro - Renew Europe",
    "Misto",
}

# Keyword sets for each group — at least one keyword must appear in the answer text
PARTY_KEYWORDS: List[List[str]] = [
    ["Fratelli d'Italia", "Fratelli d'Italia", "FdI"],
    ["Lega"],
    ["Forza Italia"],
    ["Noi Moderati"],
    ["Partito Democratico", "PD"],
    ["Movimento 5 Stelle", "M5S"],
    ["Azione"],
    ["Italia Viva"],
    ["Alleanza Verdi", "AVS", "Verdi e Sinistra"],
    ["Misto"],
]


# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------

def _normalize_for_verbatim(text: str) -> str:
    """Normalize text for verbatim match comparison.

    Strips differences caused by:
    - Unicode normalization (accents, ligatures)
    - Case differences
    - Punctuation
    - Whitespace inconsistencies
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_apostrophes(text: str) -> str:
    """Normalise all apostrophe/quote variants to a plain ASCII apostrophe.

    LLM outputs often use typographic apostrophes (U+2019 '\u2019', U+2018 '\u2018')
    or prime signs (U+02BC) while the PARTY_KEYWORDS list uses straight apostrophes.
    NFKC normalisation doesn't collapse these, so we do it explicitly.
    """
    for char in ("\u2019", "\u2018", "\u02BC", "\u0060", "\u00B4"):
        text = text.replace(char, "'")
    return text


def _count_parties_in_text(answer: str) -> int:
    """Count how many of the 10 known parliamentary groups are mentioned in the answer text."""
    answer_norm = _normalize_apostrophes(unicodedata.normalize("NFKC", answer)).lower()
    count = 0
    for keywords in PARTY_KEYWORDS:
        if any(_normalize_apostrophes(kw).lower() in answer_norm for kw in keywords):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Expert lookup builders
# ---------------------------------------------------------------------------

def _build_expert_score_lookup(chats: List[dict]) -> dict:
    """Build a (first_name_lower, last_name_lower) → authority_score lookup from stored chat experts."""
    lookup: dict = {}
    for chat in chats:
        for expert in chat.get("experts", []):
            fn = (expert.get("first_name") or "").strip().lower()
            ln = (expert.get("last_name") or "").strip().lower()
            score = expert.get("authority_score") or expert.get("total_score") or 0
            if fn and ln and score:
                key = (fn, ln)
                # Keep the max score seen for this deputy across all chats
                if key not in lookup or score > lookup[key]:
                    lookup[key] = score
    return lookup


def _build_expert_full_lookup(chats: List[dict]) -> dict:
    """Build a (first_name_lower, last_name_lower) → {score, party} lookup from stored chat experts."""
    lookup: dict = {}
    for chat in chats:
        for expert in chat.get("experts", []):
            fn = (expert.get("first_name") or "").strip().lower()
            ln = (expert.get("last_name") or "").strip().lower()
            score = expert.get("authority_score") or expert.get("total_score") or 0
            party = expert.get("party") or expert.get("group") or ""
            if fn and ln and score:
                key = (fn, ln)
                if key not in lookup or score > lookup[key]["score"]:
                    lookup[key] = {"score": score, "party": party}
    return lookup


# ---------------------------------------------------------------------------
# Baseline authority computation
# ---------------------------------------------------------------------------

def _compute_baseline_authority_full(
    baseline_text: str,
    expert_full_lookup: dict,
) -> tuple:
    """
    Match deputies in baseline_text using the full expert lookup.
    Returns (overall_avg, {party: avg_score}) or (None, None) if no matches.

    Matching strategy (in order, stops at first match per expert):
    1. Full "fn ln" or "ln fn" substring match.
    2. ln as a whole word (works for single-word surnames).
    3. Last word of ln as whole word (handles compound surnames like "Elena Boschi" → "Boschi").
    4. fn as whole word (last resort for short texts citing just a first name, rare).
    """
    if not baseline_text or not expert_full_lookup:
        return None, None
    text_lower = baseline_text.lower()
    party_scores: dict = {}
    all_matched_scores: list = []

    for (fn, ln), info in expert_full_lookup.items():
        score = info["score"]
        party = info["party"]
        matched = False

        if f"{fn} {ln}" in text_lower or f"{ln} {fn}" in text_lower:
            matched = True
        elif len(ln) >= 4 and re.search(r'\b' + re.escape(ln) + r'\b', text_lower):
            matched = True
        elif " " in ln:
            # Compound surname: try just the last word (e.g. "elena boschi" → "boschi")
            last_word = ln.rsplit(" ", 1)[-1]
            if len(last_word) >= 4 and re.search(r'\b' + re.escape(last_word) + r'\b', text_lower):
                matched = True

        if matched:
            all_matched_scores.append(score)
            if party:
                party_scores.setdefault(party, []).append(score)

    if not all_matched_scores:
        return None, None

    overall = round(sum(all_matched_scores) / len(all_matched_scores), 4)
    by_group = {p: round(sum(s) / len(s), 4) for p, s in party_scores.items()} or None
    return overall, by_group


def _compute_baseline_authority_from_precomputed(
    baseline_experts: List[dict],
) -> tuple:
    """
    Compute baseline authority from pre-computed experts (query-specific scores).
    These experts already have authority scores computed with the specific query embedding,
    so they are directly comparable to the system's per-chat authority_by_group.
    Returns (overall_avg, {party: avg_score}) or (None, None) if no data.
    """
    if not baseline_experts:
        return None, None
    party_scores: dict = {}
    all_scores: list = []
    for e in baseline_experts:
        score = e.get("authority_score", 0) or 0
        party = e.get("group", "") or e.get("party", "")
        if score > 0:
            all_scores.append(score)
            if party:
                party_scores.setdefault(party, []).append(score)
    if not all_scores:
        return None, None
    overall = round(sum(all_scores) / len(all_scores), 4)
    by_group = {p: round(sum(s) / len(s), 4) for p, s in party_scores.items()} or None
    return overall, by_group


def _compute_baseline_authority_for_text(baseline_text: str, expert_lookup: dict) -> Optional[float]:
    """
    Estimate the average authority score of deputies mentioned in a baseline text.
    Uses the pre-computed expert score lookup from existing chat data.
    Returns None if no deputies could be matched.

    Matching strategy (in order):
    1. Full "first_name last_name" or "last_name first_name" substring match.
    2. Surname-only word-boundary match (fallback, because Italian parliamentary text
       typically uses only surnames: "onorevole Rossi", "il deputato Bianchi").
       Surnames shorter than 4 characters are excluded to avoid false positives.
    """
    if not baseline_text or not expert_lookup:
        return None
    text_lower = baseline_text.lower()
    matched_scores = []
    for (fn, ln), score in expert_lookup.items():
        if f"{fn} {ln}" in text_lower or f"{ln} {fn}" in text_lower:
            matched_scores.append(score)
        elif len(ln) >= 4 and re.search(r'\b' + re.escape(ln) + r'\b', text_lower):
            matched_scores.append(score)
    if not matched_scores:
        return None
    return sum(matched_scores) / len(matched_scores)


# ---------------------------------------------------------------------------
# Confidence interval helpers
# ---------------------------------------------------------------------------

def _compute_ci(values: List[float], confidence: float = 0.95) -> Tuple[float, float]:
    """Compute confidence interval using t-distribution approximation."""
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (values[0], values[0])

    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std_err = math.sqrt(variance / n)

    # t-value approximation for 95% CI
    t_val = 2.0 if n < 30 else 1.96
    margin = t_val * std_err

    return (round(max(0, mean - margin), 4), round(min(1, mean + margin), 4))


def _compute_ci_unbounded(values: List[float]) -> Tuple[float, float]:
    """Compute CI without upper bound clamping (for authority_discrimination)."""
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (values[0], values[0])

    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std_err = math.sqrt(variance / n)
    t_val = 2.0 if n < 30 else 1.96
    margin = t_val * std_err

    return (round(max(0, mean - margin), 4), round(mean + margin, 4))


# ---------------------------------------------------------------------------
# Core metric computation
# ---------------------------------------------------------------------------

def _compute_automated_metrics(
    chat: dict,
    chunk_texts: dict,
    expert_full_lookup: Optional[dict] = None,
    baseline_precomputed_experts: Optional[List[dict]] = None,
    authority_spread_std: Optional[float] = None,
    authority_spread_stats: Optional[dict] = None,
) -> AutomatedMetrics:
    """Compute automated metrics from a single chat's stored data.

    Args:
        chat: Chat data dict (id, query, answer, citations, experts, baseline_answer).
        chunk_texts: Pre-fetched {chunk_id: text} mapping for verbatim match.
        expert_full_lookup: Optional full expert lookup for baseline per-group authority (fallback).
        baseline_precomputed_experts: Optional pre-computed baseline experts with query-specific
            authority scores (preferred over expert_full_lookup for accurate comparison).
        authority_spread_std: Optional pre-computed std dev of ALL deputies' scores for this topic
            (from compute_topic_authority_spread.py). When present, used directly as
            authority_discrimination instead of the cited-experts std dev.
        authority_spread_stats: Optional full spread stats dict (stored verbatim in result).
    """
    chat_id = chat["id"]
    citations = chat.get("citations", [])
    experts = chat.get("experts", [])
    answer = chat.get("answer", "")

    # 1. Party Coverage — only count known parliamentary groups (excludes "Governo")
    parties_found = set()
    party_breakdown = {}
    for cit in citations:
        group = cit.get("group", "") or cit.get("party", "")
        if group and group in KNOWN_PARTIES:
            parties_found.add(group)
            party_breakdown[group] = party_breakdown.get(group, 0) + 1
    parties_represented = len(parties_found)
    party_coverage = min(parties_represented / ALL_PARTIES, 1.0) if ALL_PARTIES > 0 else 0

    # 2. Citation Fidelity: verbatim_count / citations_total
    # Unified metric: a citation passes only if it has text AND that text appears verbatim
    # in the source chunk.  Denominator is citations_total so missing quote_text also fails.
    citations_total = len(citations)
    verbatim_count = 0
    for cit in citations:
        chunk_id = cit.get("evidence_id") or cit.get("chunk_id", "")
        if not chunk_id:
            continue
        stored_text = cit.get("full_text", "") or cit.get("quote_text", "")
        if not stored_text:
            continue
        chunk_text = chunk_texts.get(chunk_id, "")
        if not chunk_text:
            continue
        norm_stored = _normalize_for_verbatim(stored_text)
        norm_chunk = _normalize_for_verbatim(chunk_text)
        if norm_stored == norm_chunk or norm_stored in norm_chunk or norm_chunk in norm_stored:
            verbatim_count += 1
    verbatim_match_score = verbatim_count / max(citations_total, 1) if citations_total > 0 else 0.0

    # 4. Authority Utilization: mean authority_score of cited experts
    auth_scores = [
        e.get("authority_score", 0) or e.get("total_score", 0)
        for e in experts
        if e.get("authority_score") or e.get("total_score")
    ]
    avg_auth = sum(auth_scores) / len(auth_scores) if auth_scores else 0.0

    # 4b. Per-group authority breakdown (system) — from the authority scores of deputies
    # ACTUALLY CITED in the answer, not the top-retrieved expert per party.
    # Strategy:
    #   1. Build a (first_name, last_name) → score lookup from this chat's query-specific experts.
    #   2. Also build a party → (fn, ln, score) lookup for the stored top expert per party.
    #   3. For each citation, look up the cited deputy's score by name.
    #   4. Fallback to the stored top expert for that party (query-specific, NOT global max).
    #      This ensures authority_by_group is always based on query-specific scores and
    #      stays consistent with the survey panel which also uses chatData.experts.
    expert_name_lookup: dict = {}
    party_top_expert: dict = {}  # party → (fn, ln, score) for query-specific fallback
    for e in experts:
        fn = (e.get("first_name") or "").strip().lower()
        ln = (e.get("last_name") or "").strip().lower()
        score = e.get("authority_score", 0) or e.get("total_score", 0)
        party = e.get("group") or e.get("party") or ""
        if fn and ln and score:
            expert_name_lookup[(fn, ln)] = score
            if party and party not in party_top_expert:
                party_top_expert[party] = (fn, ln, score)

    group_cited_deputies: dict = {}  # {party: {(fn, ln): score}}
    for cit in citations:
        g = cit.get("group", "") or cit.get("party", "")
        if not g:
            continue
        fn = (cit.get("deputy_first_name") or "").strip().lower()
        ln = (cit.get("deputy_last_name") or "").strip().lower()
        if not fn and not ln:
            continue
        score = expert_name_lookup.get((fn, ln))
        if score is None:
            # Fallback: use the stored top expert for this party (query-specific).
            # Never use expert_full_lookup here — it carries scores from other queries,
            # which would make authority_by_group inconsistent with the survey panel.
            top = party_top_expert.get(g)
            if top:
                fn, ln, score = top
        if score:
            group_cited_deputies.setdefault(g, {})[(fn, ln)] = score

    authority_by_group = {
        p: round(sum(scores.values()) / len(scores), 4)
        for p, scores in group_cited_deputies.items()
        if scores
    }

    # 5. Authority Discrimination (Authority Spread):
    # Prefer pre-computed std across ALL deputies for this topic (from
    # compute_topic_authority_spread.py), which gives a meaningful signal about
    # how much authority scores vary across the full parliament on that topic.
    # Falls back to cited-experts std when no pre-computed data is available.
    if authority_spread_std is not None:
        auth_discrimination = authority_spread_std
    elif len(auth_scores) >= 2:
        mean_a = avg_auth
        variance_a = sum((x - mean_a) ** 2 for x in auth_scores) / len(auth_scores)
        auth_discrimination = math.sqrt(variance_a)
    else:
        auth_discrimination = 0.0

    # 6. Response Completeness: how many of the 10 groups are mentioned in the answer text
    parties_in_text = _count_parties_in_text(answer)
    completeness = min(parties_in_text / ALL_PARTIES, 1.0)

    # 7. Baseline authority (per-chat, per-group)
    # Prefer pre-computed baseline experts (query-specific scores) for an accurate
    # apples-to-apples comparison with the system's authority_by_group.
    # Fall back to expert_full_lookup text-matching only when no pre-computed data exists.
    baseline_authority = None
    baseline_authority_by_group = None
    if baseline_precomputed_experts:
        baseline_authority, baseline_authority_by_group = _compute_baseline_authority_from_precomputed(
            baseline_precomputed_experts
        )
    else:
        baseline_text = chat.get("baseline_answer", "")
        if baseline_text and expert_full_lookup:
            baseline_authority, baseline_authority_by_group = _compute_baseline_authority_full(
                baseline_text, expert_full_lookup
            )

    return AutomatedMetrics(
        chat_id=chat_id,
        party_coverage_score=round(party_coverage, 4),
        parties_represented=parties_represented,
        parties_total=ALL_PARTIES,
        party_breakdown=party_breakdown,
        citations_total=citations_total,
        verbatim_match_score=round(verbatim_match_score, 4),
        verbatim_match_count=verbatim_count,
        authority_utilization=round(avg_auth, 4),
        experts_count=len(experts),
        authority_discrimination=round(auth_discrimination, 4),
        response_completeness=round(completeness, 4),
        authority_by_group=authority_by_group,
        baseline_authority=baseline_authority,
        baseline_authority_by_group=baseline_authority_by_group,
        authority_spread_stats=authority_spread_stats,
    )


def _compute_aggregated(
    metrics_list: List[AutomatedMetrics],
    baseline_party_coverage_list: Optional[List[float]] = None,
    baseline_citation_fidelity_list: Optional[List[float]] = None,
    baseline_completeness_list: Optional[List[float]] = None,
    baseline_authority_list: Optional[List[float]] = None,
) -> AggregatedMetrics:
    """Compute aggregated metrics with confidence intervals."""
    n = len(metrics_list)
    if n == 0:
        return AggregatedMetrics(
            total_chats=0,
            avg_party_coverage=0,
            avg_verbatim_match=0, avg_response_completeness=0,
            avg_authority_utilization=0, avg_authority_discrimination=0,
            ci_party_coverage=(0, 0),
            ci_verbatim_match=(0, 0), ci_response_completeness=(0, 0),
            ci_authority_utilization=(0, 0), ci_authority_discrimination=(0, 0),
        )

    pc = [m.party_coverage_score for m in metrics_list]
    vm = [m.verbatim_match_score for m in metrics_list]
    au = [m.authority_utilization for m in metrics_list]
    ad = [m.authority_discrimination for m in metrics_list]
    rc = [m.response_completeness for m in metrics_list]

    result = AggregatedMetrics(
        total_chats=n,
        avg_party_coverage=round(sum(pc) / n, 4),
        avg_verbatim_match=round(sum(vm) / n, 4),
        avg_authority_utilization=round(sum(au) / n, 4),
        avg_authority_discrimination=round(sum(ad) / n, 4),
        avg_response_completeness=round(sum(rc) / n, 4),
        ci_party_coverage=_compute_ci(pc),
        ci_verbatim_match=_compute_ci(vm),
        ci_authority_utilization=_compute_ci(au),
        ci_authority_discrimination=_compute_ci_unbounded(ad),
        ci_response_completeness=_compute_ci(rc),
    )

    # Baseline comparison metrics (optional, pre-computed by enrich_evaluation_set.py)
    if baseline_party_coverage_list and len(baseline_party_coverage_list) > 0:
        bpc_n = len(baseline_party_coverage_list)
        result.avg_baseline_party_coverage = round(sum(baseline_party_coverage_list) / bpc_n, 4)
        result.ci_baseline_party_coverage = _compute_ci(baseline_party_coverage_list)

    if baseline_citation_fidelity_list and len(baseline_citation_fidelity_list) > 0:
        bcf_n = len(baseline_citation_fidelity_list)
        result.avg_baseline_citation_fidelity = round(sum(baseline_citation_fidelity_list) / bcf_n, 4)
        result.ci_baseline_citation_fidelity = _compute_ci(baseline_citation_fidelity_list)

    if baseline_completeness_list and len(baseline_completeness_list) > 0:
        bn = len(baseline_completeness_list)
        result.avg_baseline_response_completeness = round(sum(baseline_completeness_list) / bn, 4)
        result.ci_baseline_response_completeness = _compute_ci(baseline_completeness_list)

    if baseline_authority_list and len(baseline_authority_list) > 0:
        ban = len(baseline_authority_list)
        result.avg_baseline_authority = round(sum(baseline_authority_list) / ban, 4)
        result.ci_baseline_authority = _compute_ci(baseline_authority_list)

    return result
