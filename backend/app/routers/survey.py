"""
Survey router for user evaluations of ParliamentRAG responses.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional
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
               c.timestamp AS timestamp
    """, {"id": chat_id})
    return result[0] if result else None


def _calculate_stats(surveys: List[dict]) -> SurveyStats:
    """Calculate aggregated statistics from surveys"""
    if not surveys:
        return SurveyStats(
            total_surveys=0,
            avg_answer_quality=0,
            avg_answer_clarity=0,
            avg_answer_completeness=0,
            avg_citations_relevance=0,
            avg_citations_accuracy=0,
            avg_balance_perception=0,
            avg_balance_fairness=0,
            avg_compass_usefulness=0,
            avg_experts_usefulness=0,
            avg_baseline_improvement=0,
            avg_authority_value=0,
            avg_citation_pipeline_value=0,
            avg_overall_satisfaction=0,
            recommendation_rate=0,
            scores_distribution={},
        )

    n = len(surveys)

    metrics = [
        "answer_quality", "answer_clarity", "answer_completeness",
        "citations_relevance", "citations_accuracy",
        "balance_perception", "balance_fairness",
        "compass_usefulness", "experts_usefulness",
        "baseline_improvement", "authority_value", "citation_pipeline_value",
        "overall_satisfaction"
    ]

    # Calculate averages
    averages = {}
    for metric in metrics:
        total = sum(s.get(metric, 0) for s in surveys)
        averages[f"avg_{metric}"] = round(total / n, 2)

    # Calculate recommendation rate
    recommendations = sum(1 for s in surveys if s.get("would_recommend", False))
    recommendation_rate = round((recommendations / n) * 100, 1)

    # Calculate score distribution
    scores_distribution = {}
    for metric in metrics:
        scores_distribution[metric] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for s in surveys:
            score = s.get(metric, 0)
            if 1 <= score <= 5:
                scores_distribution[metric][score] += 1

    return SurveyStats(
        total_surveys=n,
        recommendation_rate=recommendation_rate,
        scores_distribution=scores_distribution,
        **averages,
    )


@router.get("/questions")
async def get_survey_questions():
    """Get the survey questions configuration"""
    return {"questions": SURVEY_QUESTIONS}


@router.post("", response_model=SurveyResponse)
async def create_survey(survey_data: SurveyResponseCreate):
    """Create a new survey response"""

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
    """Get aggregated survey statistics"""
    surveys = _load_surveys()
    return _calculate_stats(surveys)


@router.get("/chats/evaluated")
async def get_evaluated_chat_ids():
    """Get list of chat IDs that have been evaluated"""
    surveys = _load_surveys()
    return {"chat_ids": [s.get("chat_id") for s in surveys]}


@router.get("/chats/pending")
async def get_pending_chats():
    """Get chats that haven't been evaluated yet"""

    surveys = _load_surveys()
    evaluated_ids = {s.get("chat_id") for s in surveys}

    # Fetch all chats from Neo4j
    client = get_neo4j_client()
    history = client.query("""
        MATCH (c:ChatHistory)
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
