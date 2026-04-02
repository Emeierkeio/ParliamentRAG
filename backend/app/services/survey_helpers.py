"""
Shared survey helper functions.

Extracted from app.routers.survey to break the cross-router import:
  evaluation.py previously imported _load_surveys and _calculate_stats
  directly from survey.py (API-02 violation).

Both evaluation.py and survey.py now import from this module.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from app.models.survey import SurveyStats, AB_DIMENSIONS, OPTIONAL_AB_DIMS

# Path to evaluation_set.json (backend root)
_EVAL_SET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "evaluation_set.json")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Neo4j client helper (lazily resolved to avoid circular imports)
# ---------------------------------------------------------------------------

def _get_client():
    """Get Neo4j client singleton."""
    from app.services.neo4j_client import get_neo4j_client
    try:
        return get_neo4j_client()
    except RuntimeError:
        from app.config import get_settings
        from app.services.neo4j_client import init_neo4j_client
        settings = get_settings()
        return init_neo4j_client(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )


# ---------------------------------------------------------------------------
# Survey field list for Cypher queries (must stay in sync with survey.py)
# ---------------------------------------------------------------------------

_SURVEY_FIELDS = (
    "s.id AS id, s.chat_id AS chat_id, s.timestamp AS timestamp, "
    "s.overall_satisfaction_a AS overall_satisfaction_a, "
    "s.overall_satisfaction_b AS overall_satisfaction_b, "
    "s.overall_preference AS overall_preference, "
    "s.would_recommend AS would_recommend, "
    "s.feedback_positive AS feedback_positive, "
    "s.feedback_improvement AS feedback_improvement, "
    "s.evaluator_role AS evaluator_role, "
    "s.evaluation_context AS evaluation_context, "
    "s.evaluator_id AS evaluator_id, "
    "s.ab_assignment AS ab_assignment, "
    "s.baseline_authority_avg AS baseline_authority_avg, "
    "s.group_authority_votes AS group_authority_votes, "
    "s.citation_evaluations_a AS citation_evaluations_a, "
    "s.citation_evaluations_b AS citation_evaluations_b, "
    + ", ".join(f"s.{d} AS {d}" for d in AB_DIMENSIONS)
)


# ---------------------------------------------------------------------------
# Deserialization helper
# ---------------------------------------------------------------------------

def _neo4j_record_to_dict(r: dict) -> dict:
    """Convert a Neo4j SurveyEvaluation record to a plain dict compatible with SurveyResponse."""
    result = {
        "id": r["id"],
        "chat_id": r["chat_id"],
        "timestamp": r.get("timestamp", ""),
        "overall_satisfaction_a": r.get("overall_satisfaction_a", 0),
        "overall_satisfaction_b": r.get("overall_satisfaction_b", 0),
        "overall_preference": r.get("overall_preference", "equal"),
        "would_recommend": r.get("would_recommend", False),
        "feedback_positive": r.get("feedback_positive") or None,
        "feedback_improvement": r.get("feedback_improvement") or None,
        "evaluator_role": r.get("evaluator_role") or None,
        "evaluation_context": r.get("evaluation_context") or None,
        "evaluator_id": r.get("evaluator_id") or None,
        "ab_assignment": json.loads(r["ab_assignment"]) if r.get("ab_assignment") else None,
        "baseline_authority_avg": (
            r.get("baseline_authority_avg")
            if r.get("baseline_authority_avg") and r.get("baseline_authority_avg") >= 0
            else None
        ),
        "group_authority_votes": (
            json.loads(r["group_authority_votes"]) if r.get("group_authority_votes") else None
        ),
    }
    # Deserialize A/B dimensions from JSON strings
    for dim in AB_DIMENSIONS:
        raw = r.get(dim)
        if raw:
            try:
                result[dim] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                result[dim] = (
                    None if dim in OPTIONAL_AB_DIMS
                    else {"rating_a": 0, "rating_b": 0, "preference": "equal"}
                )
        else:
            result[dim] = (
                None if dim in OPTIONAL_AB_DIMS
                else {"rating_a": 0, "rating_b": 0, "preference": "equal"}
            )
    # Deserialize individual citation evaluations
    for field in ("citation_evaluations_a", "citation_evaluations_b"):
        raw = r.get(field)
        if raw:
            try:
                result[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                result[field] = []
        else:
            result[field] = []
    return result


# ---------------------------------------------------------------------------
# ChatHistory helpers (needed by _calculate_stats de-blinding)
# ---------------------------------------------------------------------------

def _get_chat_by_id(chat_id: str) -> Optional[dict]:
    """Get a specific chat's ab_assignment from Neo4j."""
    client = _get_client()
    result = client.query(
        """
        MATCH (c:ChatHistory {id: $id})
        RETURN c.id AS id, c.query AS query, c.answer AS answer,
               c.timestamp AS timestamp, c.ab_assignment AS ab_assignment
        """,
        {"id": chat_id},
    )
    return result[0] if result else None


def _get_ab_assignment(chat_id: str) -> Optional[Dict[str, str]]:
    """Get the A/B assignment for a chat (for de-blinding legacy records)."""
    chat = _get_chat_by_id(chat_id)
    if not chat or not chat.get("ab_assignment"):
        return None
    ab = chat["ab_assignment"]
    if isinstance(ab, str):
        try:
            return json.loads(ab)
        except (json.JSONDecodeError, TypeError):
            return None
    return ab


def _deblind_preference(preference: str, ab_assignment: Dict[str, str]) -> str:
    """Convert A/B label to 'system' / 'baseline' / 'equal'."""
    if preference == "equal":
        return "equal"
    mapped = ab_assignment.get(preference)
    return mapped if mapped in ("system", "baseline") else "equal"


# ---------------------------------------------------------------------------
# Evaluation set helpers
# ---------------------------------------------------------------------------

def load_evaluation_set_raw() -> dict:
    """Load raw evaluation_set.json (values may be str or dict)."""
    try:
        path = os.path.normpath(_EVAL_SET_PATH)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"evaluation_set.json not found at {_EVAL_SET_PATH}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load evaluation_set.json: {e}")
        return {}


# ---------------------------------------------------------------------------
# Public API: load and aggregate surveys
# ---------------------------------------------------------------------------

def load_surveys() -> List[dict]:
    """Load all A/B surveys from Neo4j. Returns list of dicts compatible with SurveyResponse."""
    client = _get_client()
    results = client.query(
        f"""
        MATCH (s:SurveyEvaluation)
        RETURN {_SURVEY_FIELDS}
        ORDER BY s.timestamp DESC
        """
    )
    return [_neo4j_record_to_dict(r) for r in results]


def calculate_stats(surveys: List[dict]) -> SurveyStats:
    """Calculate aggregated A/B statistics with de-blinding."""
    empty_stats = SurveyStats(
        total_surveys=0,
        system_avg_per_dimension={d: 0.0 for d in AB_DIMENSIONS},
        baseline_avg_per_dimension={d: 0.0 for d in AB_DIMENSIONS},
        system_avg_overall=0.0,
        baseline_avg_overall=0.0,
        system_win_rate=0.0,
        baseline_win_rate=0.0,
        tie_rate=0.0,
        per_dimension_preference={d: {"system": 0, "baseline": 0, "equal": 0} for d in AB_DIMENSIONS},
        recommendation_rate=0.0,
    )

    if not surveys:
        return empty_stats

    system_ratings: Dict[str, List[float]] = {d: [] for d in AB_DIMENSIONS}
    baseline_ratings: Dict[str, List[float]] = {d: [] for d in AB_DIMENSIONS}
    system_overall: List[float] = []
    baseline_overall: List[float] = []
    per_dim_pref: Dict[str, Dict[str, int]] = {
        d: {"system": 0, "baseline": 0, "equal": 0} for d in AB_DIMENSIONS
    }
    overall_pref = {"system": 0, "baseline": 0, "equal": 0}
    valid_count = 0

    for s in surveys:
        ab_assignment = s.get("ab_assignment") or _get_ab_assignment(s.get("chat_id", ""))
        if not ab_assignment:
            continue

        valid_count += 1
        is_a_system = ab_assignment.get("A") == "system"

        for dim in AB_DIMENSIONS:
            dim_data = s.get(dim, {})
            if isinstance(dim_data, dict):
                rating_a = dim_data.get("rating_a", 0)
                rating_b = dim_data.get("rating_b", 0)
                pref = dim_data.get("preference", "equal")

                if is_a_system:
                    system_ratings[dim].append(rating_a)
                    baseline_ratings[dim].append(rating_b)
                else:
                    system_ratings[dim].append(rating_b)
                    baseline_ratings[dim].append(rating_a)

                deblinded_pref = _deblind_preference(pref, ab_assignment)
                per_dim_pref[dim][deblinded_pref] += 1

        sat_a = s.get("overall_satisfaction_a", 0)
        sat_b = s.get("overall_satisfaction_b", 0)
        if is_a_system:
            system_overall.append(sat_a)
            baseline_overall.append(sat_b)
        else:
            system_overall.append(sat_b)
            baseline_overall.append(sat_a)

        overall_p = _deblind_preference(s.get("overall_preference", "equal"), ab_assignment)
        overall_pref[overall_p] += 1

    # Aggregate per-group authority votes (de-blinded)
    group_auth_pref: Dict[str, Dict[str, int]] = {}
    for s in surveys:
        ab_assign = s.get("ab_assignment") or _get_ab_assignment(s.get("chat_id", ""))
        if not ab_assign:
            continue
        is_a_sys = ab_assign.get("A") == "system"
        votes = s.get("group_authority_votes")
        if not isinstance(votes, dict):
            continue
        for gkey, vote in votes.items():
            if gkey not in group_auth_pref:
                group_auth_pref[gkey] = {"system": 0, "equal": 0, "baseline": 0}
            if vote == 0:
                group_auth_pref[gkey]["equal"] += 1
            elif vote == -1:
                group_auth_pref[gkey]["system" if is_a_sys else "baseline"] += 1
            elif vote == 1:
                group_auth_pref[gkey]["baseline" if is_a_sys else "system"] += 1

    if valid_count == 0:
        return empty_stats

    def safe_avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    system_avg_dim = {d: safe_avg(system_ratings[d]) for d in AB_DIMENSIONS}
    baseline_avg_dim = {d: safe_avg(baseline_ratings[d]) for d in AB_DIMENSIONS}

    total_pref = sum(overall_pref.values()) or 1
    system_win = round(overall_pref["system"] / total_pref * 100, 1)
    baseline_win = round(overall_pref["baseline"] / total_pref * 100, 1)
    tie = round(overall_pref["equal"] / total_pref * 100, 1)

    valid_surveys = [
        s for s in surveys
        if s.get("ab_assignment") or _get_ab_assignment(s.get("chat_id", ""))
    ]
    recommendations = sum(1 for s in valid_surveys if s.get("would_recommend", False))
    recommendation_rate = (
        round((recommendations / len(valid_surveys)) * 100, 1) if valid_surveys else 0.0
    )

    return SurveyStats(
        total_surveys=valid_count,
        system_avg_per_dimension=system_avg_dim,
        baseline_avg_per_dimension=baseline_avg_dim,
        system_avg_overall=safe_avg(system_overall),
        baseline_avg_overall=safe_avg(baseline_overall),
        system_win_rate=system_win,
        baseline_win_rate=baseline_win,
        tie_rate=tie,
        per_dimension_preference=per_dim_pref,
        group_authority_preference=group_auth_pref if group_auth_pref else None,
        recommendation_rate=recommendation_rate,
    )


# ---------------------------------------------------------------------------
# Backward-compatible aliases for code that still uses the private names
# ---------------------------------------------------------------------------

_load_surveys = load_surveys
_calculate_stats = calculate_stats
_load_evaluation_set_raw = load_evaluation_set_raw
