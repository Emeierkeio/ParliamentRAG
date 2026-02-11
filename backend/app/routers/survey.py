"""
Survey router for A/B blind evaluations of ParliamentRAG vs Baseline RAG.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.survey import (
    SurveyResponse,
    SurveyResponseCreate,
    SurveyWithChat,
    SurveyStats,
    SurveyListResponse,
    SURVEY_QUESTIONS,
    AB_DIMENSIONS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/surveys", tags=["surveys"])

# Data file path
DATA_DIR = Path(__file__).parent.parent.parent / "data"
SURVEYS_FILE = DATA_DIR / "surveys.json"
from ..services.neo4j_client import get_neo4j_client


def _load_surveys() -> List[dict]:
    """Load surveys from JSON file"""
    if not SURVEYS_FILE.exists():
        return []
    try:
        with open(SURVEYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading surveys: {e}")
        return []


def _save_surveys(surveys: List[dict]) -> None:
    """Save surveys to JSON file"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SURVEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(surveys, f, ensure_ascii=False, indent=2, default=str)


def _get_chat_by_id(chat_id: str) -> Optional[dict]:
    """Get a specific chat by ID from Neo4j."""
    client = get_neo4j_client()
    result = client.query("""
        MATCH (c:ChatHistory {id: $id})
        RETURN c.id AS id, c.query AS query, c.answer AS answer,
               c.timestamp AS timestamp, c.ab_assignment AS ab_assignment
    """, {"id": chat_id})
    return result[0] if result else None


def _get_ab_assignment(chat_id: str) -> Optional[Dict[str, str]]:
    """Get the A/B assignment for a chat to de-blind results."""
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
    """Convert A/B preference to system/baseline/equal."""
    if preference == "equal":
        return "equal"
    # preference is "A" or "B" - map to what A or B represents
    mapped = ab_assignment.get(preference)
    return mapped if mapped in ("system", "baseline") else "equal"


def _calculate_stats(surveys: List[dict]) -> SurveyStats:
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

    # Collect de-blinded ratings
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
        ab_assignment = _get_ab_assignment(s.get("chat_id", ""))
        if not ab_assignment:
            # Skip surveys without valid A/B assignment (old format)
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

        # Overall satisfaction
        sat_a = s.get("overall_satisfaction_a", 0)
        sat_b = s.get("overall_satisfaction_b", 0)
        if is_a_system:
            system_overall.append(sat_a)
            baseline_overall.append(sat_b)
        else:
            system_overall.append(sat_b)
            baseline_overall.append(sat_a)

        # Overall preference
        overall_p = _deblind_preference(s.get("overall_preference", "equal"), ab_assignment)
        overall_pref[overall_p] += 1

    if valid_count == 0:
        return empty_stats

    # Calculate averages
    def safe_avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    system_avg_dim = {d: safe_avg(system_ratings[d]) for d in AB_DIMENSIONS}
    baseline_avg_dim = {d: safe_avg(baseline_ratings[d]) for d in AB_DIMENSIONS}

    # Win rates
    total_pref = sum(overall_pref.values()) or 1
    system_win = round(overall_pref["system"] / total_pref * 100, 1)
    baseline_win = round(overall_pref["baseline"] / total_pref * 100, 1)
    tie = round(overall_pref["equal"] / total_pref * 100, 1)

    # Recommendation rate
    recommendations = sum(1 for s in surveys if s.get("would_recommend", False))
    recommendation_rate = round((recommendations / len(surveys)) * 100, 1)

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
        recommendation_rate=recommendation_rate,
    )


@router.get("/questions")
async def get_survey_questions():
    """Get the survey questions configuration"""
    return {"questions": SURVEY_QUESTIONS}


@router.post("", response_model=SurveyResponse)
async def create_survey(survey_data: SurveyResponseCreate):
    """Create a new A/B survey response"""

    # Verify chat exists
    chat = _get_chat_by_id(survey_data.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Check if survey already exists for this chat
    surveys = _load_surveys()
    existing = next((s for s in surveys if s.get("chat_id") == survey_data.chat_id), None)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Survey already exists for this chat. Use PUT to update."
        )

    # Create survey response
    survey = SurveyResponse(
        id=str(uuid4()),
        timestamp=datetime.now(),
        **survey_data.model_dump(),
    )

    # Save
    surveys.append(survey.model_dump())
    _save_surveys(surveys)

    logger.info(f"Survey created for chat {survey_data.chat_id}")
    return survey


@router.put("/{chat_id}", response_model=SurveyResponse)
async def update_survey(chat_id: str, survey_data: SurveyResponseCreate):
    """Update an existing survey response"""

    surveys = _load_surveys()
    survey_index = next(
        (i for i, s in enumerate(surveys) if s.get("chat_id") == chat_id),
        None
    )

    if survey_index is None:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Update survey
    existing = surveys[survey_index]
    updated = SurveyResponse(
        id=existing.get("id"),
        timestamp=datetime.now(),
        **survey_data.model_dump(),
    )

    surveys[survey_index] = updated.model_dump()
    _save_surveys(surveys)

    logger.info(f"Survey updated for chat {chat_id}")
    return updated


@router.get("/{chat_id}", response_model=SurveyResponse)
async def get_survey_by_chat(chat_id: str):
    """Get survey for a specific chat"""

    surveys = _load_surveys()
    survey = next((s for s in surveys if s.get("chat_id") == chat_id), None)

    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    return SurveyResponse(**survey)


@router.get("", response_model=SurveyListResponse)
async def list_surveys(
    include_stats: bool = Query(True, description="Include aggregated statistics"),
    limit: int = Query(50, ge=1, le=200, description="Maximum surveys to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List all surveys with optional statistics"""

    surveys = _load_surveys()

    # Get chat IDs from surveys
    chat_ids = [s.get("chat_id") for s in surveys if s.get("chat_id")]

    # Fetch chats from Neo4j
    chat_lookup = {}
    if chat_ids:
        client = get_neo4j_client()
        results = client.query("""
            MATCH (c:ChatHistory) WHERE c.id IN $ids
            RETURN c.id AS id, c.query AS query, c.preview AS preview, c.timestamp AS timestamp
        """, {"ids": chat_ids})
        chat_lookup = {r["id"]: r for r in results}

    # Build response with chat metadata
    surveys_with_chat = []
    for s in surveys:
        chat = chat_lookup.get(s.get("chat_id"))
        if chat:
            surveys_with_chat.append(
                SurveyWithChat(
                    survey=SurveyResponse(**s),
                    chat_query=chat.get("query", ""),
                    chat_preview=chat.get("preview", ""),
                    chat_timestamp=chat.get("timestamp", datetime.now()),
                )
            )

    # Sort by timestamp descending
    surveys_with_chat.sort(key=lambda x: x.survey.timestamp, reverse=True)

    # Apply pagination
    total = len(surveys_with_chat)
    paginated = surveys_with_chat[offset : offset + limit]

    # Calculate stats if requested
    stats = _calculate_stats(surveys) if include_stats else None

    return SurveyListResponse(
        surveys=paginated,
        total=total,
        stats=stats,
    )


@router.delete("/{chat_id}")
async def delete_survey(chat_id: str):
    """Delete a survey"""

    surveys = _load_surveys()
    original_len = len(surveys)
    surveys = [s for s in surveys if s.get("chat_id") != chat_id]

    if len(surveys) == original_len:
        raise HTTPException(status_code=404, detail="Survey not found")

    _save_surveys(surveys)
    logger.info(f"Survey deleted for chat {chat_id}")

    return {"message": "Survey deleted", "chat_id": chat_id}


@router.get("/stats/summary", response_model=SurveyStats)
async def get_stats_summary():
    """Get aggregated survey statistics (de-blinded)"""
    surveys = _load_surveys()
    return _calculate_stats(surveys)


@router.get("/chats/evaluated")
async def get_evaluated_chat_ids():
    """Get list of chat IDs that have been evaluated"""
    surveys = _load_surveys()
    return {"chat_ids": [s.get("chat_id") for s in surveys]}


@router.get("/chats/pending")
async def get_pending_chats():
    """Get chats that haven't been evaluated yet (only those with baseline)"""

    surveys = _load_surveys()
    evaluated_ids = {s.get("chat_id") for s in surveys}

    # Fetch all chats from Neo4j - only those with baseline_answer
    client = get_neo4j_client()
    history = client.query("""
        MATCH (c:ChatHistory)
        WHERE c.baseline_answer IS NOT NULL AND c.baseline_answer <> ''
        RETURN c.id AS id, c.query AS query, c.preview AS preview, c.timestamp AS timestamp
        ORDER BY c.timestamp DESC
    """)

    pending = [
        {
            "id": c["id"],
            "query": c["query"],
            "preview": c.get("preview", ""),
            "timestamp": c.get("timestamp", ""),
        }
        for c in history
        if c["id"] not in evaluated_ids
    ]

    return {"pending": pending, "total": len(pending)}
