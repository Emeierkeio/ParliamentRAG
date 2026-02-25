"""
Evaluation router for scientific assessment of ParliamentRAG.
Computes automated metrics from stored pipeline data and combines
them with human survey evaluations for dashboard visualization.
"""

import csv
import io
import json
import logging
import math
import re
import unicodedata
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.evaluation import (
    AutomatedMetrics,
    AggregatedMetrics,
    ABComparisonStats,
    CombinedEvaluation,
    EvaluationDashboardData,
)
from app.models.survey import SurveyResponse, SurveyStats, AB_DIMENSIONS, SimpleRatingResponse
from app.routers.survey import _load_surveys, _calculate_stats, _load_evaluation_set

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])

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


def _get_client():
    """Get Neo4j client, reusing history router's pattern."""
    from ..services.neo4j_client import get_neo4j_client
    try:
        return get_neo4j_client()
    except RuntimeError:
        from ..config import get_settings
        from ..services.neo4j_client import init_neo4j_client
        settings = get_settings()
        return init_neo4j_client(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )


def _fetch_all_chats() -> List[dict]:
    """Fetch all ChatHistory nodes with full data from Neo4j."""
    client = _get_client()
    results = client.query("""
        MATCH (c:ChatHistory)
        RETURN c.id AS id, c.query AS query, c.answer AS answer,
               c.timestamp AS timestamp, c.citations AS citations,
               c.experts AS experts, c.baseline_answer AS baseline_answer
        ORDER BY c.timestamp DESC
    """)

    chats = []
    for r in results:
        chats.append({
            "id": r["id"],
            "query": r["query"],
            "answer": r.get("answer", ""),
            "timestamp": r.get("timestamp", ""),
            "citations": json.loads(r["citations"]) if r.get("citations") else [],
            "experts": json.loads(r["experts"]) if r.get("experts") else [],
            "baseline_answer": r.get("baseline_answer") or "",
        })
    return chats


def _build_expert_score_lookup(chats: List[dict]) -> dict:
    """Build a (first_name_lower, last_name_lower) → authority_score lookup from stored chat experts."""
    lookup = {}
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


def _fetch_chunk_texts(chunk_ids: List[str]) -> dict:
    """Batch-fetch chunk texts from Neo4j. Returns {chunk_id: text}."""
    if not chunk_ids:
        return {}
    client = _get_client()
    results = client.query("""
        UNWIND $ids AS cid
        MATCH (c:Chunk {id: cid})
        RETURN cid, c.text AS text
    """, {"ids": chunk_ids})
    return {r["cid"]: r.get("text", "") for r in results}


def _compute_automated_metrics(chat: dict, chunk_texts: dict) -> AutomatedMetrics:
    """Compute automated metrics from a single chat's stored data.

    Args:
        chat: Chat data dict (id, query, answer, citations, experts).
        chunk_texts: Pre-fetched {chunk_id: text} mapping for verbatim match.
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

    # 5. Authority Discrimination: std of authority_scores (higher = more selective)
    if len(auth_scores) >= 2:
        mean_a = avg_auth
        variance_a = sum((x - mean_a) ** 2 for x in auth_scores) / len(auth_scores)
        auth_discrimination = math.sqrt(variance_a)
    else:
        auth_discrimination = 0.0

    # 6. Response Completeness: how many of the 10 groups are mentioned in the answer text
    parties_in_text = _count_parties_in_text(answer)
    completeness = min(parties_in_text / ALL_PARTIES, 1.0)

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
    )


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


def _load_simple_ratings() -> List[dict]:
    """Load all SimpleRating nodes from Neo4j."""
    client = _get_client()
    results = client.query("""
        MATCH (r:SimpleRating)
        RETURN r.id AS id, r.chat_id AS chat_id, r.timestamp AS timestamp,
               r.answer_clarity AS answer_clarity,
               r.answer_quality AS answer_quality,
               r.balance_perception AS balance_perception,
               r.balance_fairness AS balance_fairness,
               r.feedback AS feedback,
               r.evaluator_id AS evaluator_id
    """)
    return [dict(r) for r in results]


@router.get("/dashboard", response_model=EvaluationDashboardData)
async def get_dashboard():
    """Get full evaluation dashboard data with automated + human metrics."""
    # Fetch all chats
    chats = _fetch_all_chats()

    # Batch-fetch chunk texts for verbatim match across all chats
    all_chunk_ids = []
    for chat in chats:
        for cit in chat.get("citations", []):
            cid = cit.get("evidence_id") or cit.get("chunk_id", "")
            if cid:
                all_chunk_ids.append(cid)
    chunk_texts = _fetch_chunk_texts(list(set(all_chunk_ids)))

    # Compute automated metrics for each chat
    metrics_map = {}
    for chat in chats:
        try:
            metrics_map[chat["id"]] = _compute_automated_metrics(chat, chunk_texts)
        except Exception as e:
            logger.warning(f"Failed to compute metrics for chat {chat['id']}: {e}")

    # Load human A/B surveys
    surveys = _load_surveys()
    survey_map = {}
    for s in surveys:
        cid = s.get("chat_id")
        if cid:
            try:
                survey_map[cid] = SurveyResponse(**s)
            except Exception:
                pass

    # Load simple Likert ratings
    simple_ratings_raw = _load_simple_ratings()
    simple_map = {}
    for r in simple_ratings_raw:
        cid = r.get("chat_id")
        if cid:
            try:
                simple_map[cid] = SimpleRatingResponse(**r)
            except Exception:
                pass

    # Build per-chat combined evaluations
    per_chat = []
    for chat in chats:
        cid = chat["id"]
        automated = metrics_map.get(cid)
        if not automated:
            continue
        per_chat.append(CombinedEvaluation(
            chat_id=cid,
            chat_query=chat.get("query", ""),
            timestamp=str(chat.get("timestamp", "")),
            automated=automated,
            human=survey_map.get(cid),
            human_simple=simple_map.get(cid),
        ))

    # Baseline metrics: prefer pre-computed baseline_metrics (written by
    # scripts/enrich_evaluation_set.py) which provide citation-based party coverage
    # and citation fidelity comparable to the system metrics.
    # Fall back to text-based detection for completeness / authority.
    from app.routers.survey import _load_evaluation_set_raw
    eval_set_raw = _load_evaluation_set_raw()
    eval_set = _load_evaluation_set()

    baseline_party_coverage_list: List[float] = []
    baseline_citation_fidelity_list: List[float] = []
    baseline_completeness_list: List[float] = []

    for entry in eval_set_raw.values():
        if isinstance(entry, str):
            entry = {"baseline_answer": entry}
        bm = entry.get("baseline_metrics")
        if bm:
            # Citation-based party coverage (from enrich_evaluation_set.py)
            if bm.get("baseline_party_coverage") is not None:
                baseline_party_coverage_list.append(bm["baseline_party_coverage"])
            if bm.get("baseline_citation_fidelity") is not None:
                baseline_citation_fidelity_list.append(bm["baseline_citation_fidelity"])

        # Text-based completeness (both sides text-based → comparable)
        baseline_text = entry.get("baseline_answer", "") if isinstance(entry, dict) else entry
        if baseline_text:
            parties_in_bl = _count_parties_in_text(baseline_text)
            baseline_completeness_list.append(min(parties_in_bl / ALL_PARTIES, 1.0))

    # Baseline authority: match deputy names in baseline text against authority scores
    expert_lookup = _build_expert_score_lookup(chats)
    baseline_authority_list: List[float] = []
    for baseline_text in eval_set.values():
        score = _compute_baseline_authority_for_text(baseline_text, expert_lookup)
        if score is not None:
            baseline_authority_list.append(score)

    # Also include any surveys that explicitly stored baseline_authority_avg
    for s in surveys:
        baa = s.get("baseline_authority_avg")
        if baa is not None and baa >= 0:
            baseline_authority_list.append(baa)

    all_metrics = list(metrics_map.values())
    automated_aggregate = _compute_aggregated(
        all_metrics,
        baseline_party_coverage_list or None,
        baseline_citation_fidelity_list or None,
        baseline_completeness_list or None,
        baseline_authority_list or None,
    )
    human_aggregate = _calculate_stats(surveys) if surveys else None

    # Compute A/B comparison stats from human aggregate
    ab_comparison = None
    if human_aggregate and human_aggregate.total_surveys > 0:
        ab_comparison = ABComparisonStats(
            total_evaluations=human_aggregate.total_surveys,
            system_win_rate=human_aggregate.system_win_rate,
            baseline_win_rate=human_aggregate.baseline_win_rate,
            tie_rate=human_aggregate.tie_rate,
            system_avg_ratings=human_aggregate.system_avg_per_dimension,
            baseline_avg_ratings=human_aggregate.baseline_avg_per_dimension,
            system_avg_overall=human_aggregate.system_avg_overall,
            baseline_avg_overall=human_aggregate.baseline_avg_overall,
            per_dimension_preference=human_aggregate.per_dimension_preference,
        )

    return EvaluationDashboardData(
        automated_aggregate=automated_aggregate,
        human_aggregate=human_aggregate,
        ab_comparison=ab_comparison,
        per_chat=per_chat,
        total_chats=len(chats),
        total_evaluated=len(survey_map),
        total_simple_rated=len(simple_map),
    )


@router.get("/metrics/{chat_id}", response_model=AutomatedMetrics)
async def get_chat_metrics(chat_id: str):
    """Compute automated metrics for a specific chat."""
    client = _get_client()
    result = client.query("""
        MATCH (c:ChatHistory {id: $id})
        RETURN c.id AS id, c.query AS query, c.answer AS answer,
               c.timestamp AS timestamp, c.citations AS citations,
               c.experts AS experts
    """, {"id": chat_id})

    if not result:
        raise HTTPException(status_code=404, detail="Chat not found")

    r = result[0]
    chat = {
        "id": r["id"],
        "query": r["query"],
        "answer": r.get("answer", ""),
        "citations": json.loads(r["citations"]) if r.get("citations") else [],
        "experts": json.loads(r["experts"]) if r.get("experts") else [],
    }

    # Fetch chunk texts only for this chat's citations
    chunk_ids = [
        cit.get("evidence_id") or cit.get("chunk_id", "")
        for cit in chat["citations"]
        if cit.get("evidence_id") or cit.get("chunk_id")
    ]
    chunk_texts = _fetch_chunk_texts(chunk_ids)

    return _compute_automated_metrics(chat, chunk_texts)


@router.get("/export/csv")
async def export_csv():
    """Export all evaluation data as CSV for paper analysis."""
    chats = _fetch_all_chats()

    # Batch fetch chunk texts for verbatim match
    all_chunk_ids = []
    for chat in chats:
        for cit in chat.get("citations", []):
            cid = cit.get("evidence_id") or cit.get("chunk_id", "")
            if cid:
                all_chunk_ids.append(cid)
    chunk_texts = _fetch_chunk_texts(list(set(all_chunk_ids)))

    surveys = _load_surveys()
    survey_map = {s.get("chat_id"): s for s in surveys if s.get("chat_id")}

    simple_ratings = _load_simple_ratings()
    simple_map = {r.get("chat_id"): r for r in simple_ratings if r.get("chat_id")}

    output = io.StringIO()
    writer = csv.writer(output)

    from app.routers.survey import _get_ab_assignment, _deblind_preference

    # A/B dimension headers
    dim_headers = []
    for dim in AB_DIMENSIONS:
        dim_headers.extend([
            f"{dim}_system", f"{dim}_baseline", f"{dim}_preference"
        ])

    # Simple rating headers
    simple_headers = [
        "simple_answer_clarity", "simple_answer_quality",
        "simple_balance_perception", "simple_balance_fairness",
        "simple_feedback",
    ]

    writer.writerow([
        "chat_id", "query", "timestamp",
        # Automated metrics
        "party_coverage", "citation_fidelity",
        "authority_utilization", "authority_discrimination", "response_completeness",
        "parties_represented", "citations_total",
        "verbatim_count", "experts_count",
        # Human A/B metrics (de-blinded)
        *dim_headers,
        "overall_satisfaction_system", "overall_satisfaction_baseline",
        "overall_preference",
        "would_recommend",
        "feedback_positive", "feedback_improvement",
        # Simple Likert rating
        *simple_headers,
    ])

    for chat in chats:
        try:
            m = _compute_automated_metrics(chat, chunk_texts)
        except Exception:
            continue

        s = survey_map.get(chat["id"], {})
        ab = _get_ab_assignment(chat["id"]) if s else None

        # De-blind A/B dimension ratings
        dim_values = []
        for dim in AB_DIMENSIONS:
            dim_data = s.get(dim, {})
            if isinstance(dim_data, dict) and ab:
                is_a_system = ab.get("A") == "system"
                r_a = dim_data.get("rating_a", "")
                r_b = dim_data.get("rating_b", "")
                pref = _deblind_preference(dim_data.get("preference", "equal"), ab) if ab else ""
                system_r = r_a if is_a_system else r_b
                baseline_r = r_b if is_a_system else r_a
                dim_values.extend([system_r, baseline_r, pref])
            else:
                dim_values.extend(["", "", ""])

        # De-blind overall satisfaction
        if ab:
            is_a_system = ab.get("A") == "system"
            sat_a = s.get("overall_satisfaction_a", "")
            sat_b = s.get("overall_satisfaction_b", "")
            overall_sys = sat_a if is_a_system else sat_b
            overall_base = sat_b if is_a_system else sat_a
            overall_pref = _deblind_preference(s.get("overall_preference", "equal"), ab)
        else:
            overall_sys = ""
            overall_base = ""
            overall_pref = ""

        # Simple rating columns
        sr = simple_map.get(chat["id"], {})
        simple_values = [
            sr.get("answer_clarity", ""),
            sr.get("answer_quality", ""),
            sr.get("balance_perception", ""),
            sr.get("balance_fairness", ""),
            sr.get("feedback", ""),
        ]

        writer.writerow([
            chat["id"],
            chat.get("query", ""),
            chat.get("timestamp", ""),
            m.party_coverage_score,
            m.verbatim_match_score,
            m.authority_utilization,
            m.authority_discrimination,
            m.response_completeness,
            m.parties_represented,
            m.citations_total,
            m.verbatim_match_count,
            m.experts_count,
            *dim_values,
            overall_sys, overall_base, overall_pref,
            s.get("would_recommend", ""),
            s.get("feedback_positive", ""),
            s.get("feedback_improvement", ""),
            *simple_values,
        ])

    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=parliament_rag_evaluation_{timestamp}.csv"
        },
    )
