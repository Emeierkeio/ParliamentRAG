"""
Evaluation router for scientific assessment of ParliamentRAG.

HTTP orchestration only — all metric computation is delegated to
app.services.evaluation_service. This router handles:
- Request parsing and input validation
- Service calls
- Response formatting
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import List, Optional

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
from app.services.survey_helpers import load_surveys as _load_surveys, calculate_stats as _calculate_stats
from app.services.evaluation_service import (
    _compute_automated_metrics,
    _compute_baseline_authority_from_precomputed,
    _compute_baseline_authority_full,
    _compute_aggregated,
    _count_parties_in_text,
    _build_expert_full_lookup,
    ALL_PARTIES,
    KNOWN_PARTIES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


# ---------------------------------------------------------------------------
# Data access helpers (Neo4j I/O — belongs in router layer)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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

    # Build full expert lookup for baseline per-group authority (fallback only)
    expert_full_lookup = _build_expert_full_lookup(chats)

    # Load pre-computed baseline experts from evaluation_set.json (query-specific scores).
    # These are used instead of expert_full_lookup to get comparable authority scores.
    from app.services.survey_helpers import load_evaluation_set_raw as _load_eval_set_raw_inner
    _eval_set_raw_for_experts = _load_eval_set_raw_inner()
    # Build {topic_lower: baseline_experts}, {topic_lower: authority_spread_std},
    # and {topic_lower: authority_spread_dict} for fast lookup
    _topic_to_baseline_experts: dict = {}
    _topic_to_authority_spread_std: dict = {}
    _topic_to_authority_spread: dict = {}
    for _topic, _entry in _eval_set_raw_for_experts.items():
        if isinstance(_entry, dict):
            _experts = _entry.get("baseline_experts", [])
            if _experts:
                _topic_to_baseline_experts[_topic.lower()] = _experts
            _spread = _entry.get("authority_spread")
            if _spread and _spread.get("std") is not None:
                _topic_to_authority_spread_std[_topic.lower()] = _spread["std"]
                _topic_to_authority_spread[_topic.lower()] = _spread

    def _find_baseline_experts(query: str) -> Optional[List[dict]]:
        q = query.lower()
        for topic_l, experts in _topic_to_baseline_experts.items():
            if topic_l in q or q in topic_l:
                return experts
        return None

    def _find_authority_spread_std(query: str) -> Optional[float]:
        q = query.lower()
        for topic_l, std in _topic_to_authority_spread_std.items():
            if topic_l in q or q in topic_l:
                return std
        return None

    def _find_authority_spread(query: str) -> Optional[dict]:
        q = query.lower()
        for topic_l, spread in _topic_to_authority_spread.items():
            if topic_l in q or q in topic_l:
                return spread
        return None

    # Compute automated metrics for each chat
    metrics_map = {}
    for chat in chats:
        try:
            bl_experts = _find_baseline_experts(chat.get("query", ""))
            spread_std = _find_authority_spread_std(chat.get("query", ""))
            spread_stats = _find_authority_spread(chat.get("query", ""))
            metrics_map[chat["id"]] = _compute_automated_metrics(
                chat, chunk_texts, expert_full_lookup,
                baseline_precomputed_experts=bl_experts,
                authority_spread_std=spread_std,
                authority_spread_stats=spread_stats,
            )
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
    # Reuse the already-loaded eval set (avoids a second file read).
    eval_set_raw = _eval_set_raw_for_experts

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

    # Baseline authority: prefer pre-computed query-specific experts from evaluation_set.json.
    # Fall back to text-matching with expert_full_lookup only when no pre-computed data exists.
    baseline_authority_list: List[float] = []
    all_group_baseline_from_set: dict = {}
    for entry in eval_set_raw.values():
        if isinstance(entry, str):
            entry = {"baseline_answer": entry}
        bl_experts = entry.get("baseline_experts", [])
        if bl_experts:
            overall, by_group = _compute_baseline_authority_from_precomputed(bl_experts)
        else:
            baseline_text = entry.get("baseline_answer", "")
            overall, by_group = _compute_baseline_authority_full(baseline_text, expert_full_lookup)
        if overall is not None:
            baseline_authority_list.append(overall)
        if by_group:
            for party, score in by_group.items():
                all_group_baseline_from_set.setdefault(party, []).append(score)

    # Also include any surveys that explicitly stored baseline_authority_avg
    for s in surveys:
        baa = s.get("baseline_authority_avg")
        if baa is not None and baa >= 0:
            baseline_authority_list.append(baa)

    all_metrics = list(metrics_map.values())

    # Compute avg_baseline_authority_by_group:
    # prefer per-chat breakdown (chats with stored baseline_answer), fall back to eval_set
    all_group_baseline_from_chats: dict = {}
    for m in all_metrics:
        if m.baseline_authority_by_group:
            for party, score in m.baseline_authority_by_group.items():
                all_group_baseline_from_chats.setdefault(party, []).append(score)

    merged_group_baseline = all_group_baseline_from_chats if all_group_baseline_from_chats else all_group_baseline_from_set
    avg_baseline_by_group = (
        {p: round(sum(s) / len(s), 4) for p, s in merged_group_baseline.items()}
        if merged_group_baseline else None
    )

    automated_aggregate = _compute_aggregated(
        all_metrics,
        baseline_party_coverage_list or None,
        baseline_citation_fidelity_list or None,
        baseline_completeness_list or None,
        baseline_authority_list or None,
    )
    automated_aggregate.avg_baseline_authority_by_group = avg_baseline_by_group
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
            group_authority_preference=human_aggregate.group_authority_preference,
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

    from app.services.survey_helpers import _get_ab_assignment, _deblind_preference

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
