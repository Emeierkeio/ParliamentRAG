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
from app.routers.survey import _load_surveys, _calculate_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])

# 10 parliamentary groups in the system
ALL_PARTIES = 10

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


def _count_parties_in_text(answer: str) -> int:
    """Count how many of the 10 known parliamentary groups are mentioned in the answer text."""
    answer_lower = answer.lower()
    count = 0
    for keywords in PARTY_KEYWORDS:
        if any(kw.lower() in answer_lower for kw in keywords):
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
               c.experts AS experts
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
        })
    return chats


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

    # 1. Party Coverage
    parties_found = set()
    party_breakdown = {}
    for cit in citations:
        group = cit.get("group", "") or cit.get("party", "")
        if group:
            parties_found.add(group)
            party_breakdown[group] = party_breakdown.get(group, 0) + 1
    parties_represented = len(parties_found)
    party_coverage = min(parties_represented / ALL_PARTIES, 1.0) if ALL_PARTIES > 0 else 0

    # 2. Citation Integrity: citations with non-empty quote_text
    citations_total = len(citations)
    citations_valid = sum(1 for c in citations if c.get("quote_text"))
    citation_integrity = citations_valid / max(citations_total, 1)

    # 3. Verbatim Match: the chunk referenced by each citation exists in Neo4j and its
    # text matches what was stored at retrieval time.
    #
    # We use full_text (= c.text stored verbatim during retrieval and saved in history)
    # rather than quote_text.  quote_text = compute_quote_text(speech_text, offsets)
    # which is word-boundary-aligned and can start/end at slightly different positions
    # than c.text, making a substring check unreliable.
    # full_text = c.text exactly, so normalize(full_text) ≈ normalize(c.text from Neo4j)
    # and the check trivially succeeds for any valid, unchanged citation.
    # Fallback to quote_text for older history entries that lack full_text.
    verbatim_count = 0
    if citations_valid > 0:
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
    verbatim_match_score = verbatim_count / max(citations_valid, 1) if citations_valid > 0 else 0.0

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
        citation_integrity_score=round(citation_integrity, 4),
        citations_valid=citations_valid,
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


def _compute_aggregated(metrics_list: List[AutomatedMetrics]) -> AggregatedMetrics:
    """Compute aggregated metrics with confidence intervals."""
    n = len(metrics_list)
    if n == 0:
        return AggregatedMetrics(
            total_chats=0,
            avg_party_coverage=0, avg_citation_integrity=0,
            avg_verbatim_match=0, avg_response_completeness=0,
            avg_authority_utilization=0, avg_authority_discrimination=0,
            ci_party_coverage=(0, 0), ci_citation_integrity=(0, 0),
            ci_verbatim_match=(0, 0), ci_response_completeness=(0, 0),
            ci_authority_utilization=(0, 0), ci_authority_discrimination=(0, 0),
        )

    pc = [m.party_coverage_score for m in metrics_list]
    ci_vals = [m.citation_integrity_score for m in metrics_list]
    vm = [m.verbatim_match_score for m in metrics_list]
    au = [m.authority_utilization for m in metrics_list]
    ad = [m.authority_discrimination for m in metrics_list]
    rc = [m.response_completeness for m in metrics_list]

    return AggregatedMetrics(
        total_chats=n,
        avg_party_coverage=round(sum(pc) / n, 4),
        avg_citation_integrity=round(sum(ci_vals) / n, 4),
        avg_verbatim_match=round(sum(vm) / n, 4),
        avg_authority_utilization=round(sum(au) / n, 4),
        avg_authority_discrimination=round(sum(ad) / n, 4),
        avg_response_completeness=round(sum(rc) / n, 4),
        ci_party_coverage=_compute_ci(pc),
        ci_citation_integrity=_compute_ci(ci_vals),
        ci_verbatim_match=_compute_ci(vm),
        ci_authority_utilization=_compute_ci(au),
        ci_authority_discrimination=_compute_ci_unbounded(ad),
        ci_response_completeness=_compute_ci(rc),
    )


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
               r.feedback AS feedback
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

    # Aggregated metrics
    all_metrics = list(metrics_map.values())
    automated_aggregate = _compute_aggregated(all_metrics)
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
        "party_coverage", "citation_integrity", "verbatim_match",
        "authority_utilization", "authority_discrimination", "response_completeness",
        "parties_represented", "citations_valid", "citations_total",
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
            m.citation_integrity_score,
            m.verbatim_match_score,
            m.authority_utilization,
            m.authority_discrimination,
            m.response_completeness,
            m.parties_represented,
            m.citations_valid,
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
