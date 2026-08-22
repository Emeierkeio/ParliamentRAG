"""In-app feedback per strumento (issue #21).

Raccoglie micro-feedback (pollice + commento facoltativo) dal widget
FeedbackPulse del frontend. Due chiamate: il voto parte subito al click,
il commento arriva dopo se l'utente lo scrive. Nessun dato personale:
solo strumento, voto, lingua e un contesto breve (topic o chat id).
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

TOOLS = {"chat", "search", "ranking", "compass", "timeline", "explorer", "data"}
VOTES = {"up", "down"}


def _get_client():
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


class FeedbackCreate(BaseModel):
    tool: str = Field(..., max_length=20)
    vote: str = Field(..., max_length=10)
    context: Optional[str] = Field(default=None, max_length=300)
    locale: Optional[str] = Field(default=None, max_length=5)


class FeedbackComment(BaseModel):
    comment: str = Field(..., min_length=1, max_length=500)


@router.post("")
async def create_feedback(payload: FeedbackCreate):
    """Registra un voto; ritorna l'id per l'eventuale commento successivo."""
    if payload.tool not in TOOLS:
        raise HTTPException(status_code=400, detail="unknown tool")
    if payload.vote not in VOTES:
        raise HTTPException(status_code=400, detail="unknown vote")

    feedback_id = str(uuid4())
    client = _get_client()
    client.query(
        """
        CREATE (f:UserFeedback {
            id: $id, tool: $tool, vote: $vote,
            context: $context, locale: $locale,
            created_at: datetime($created_at)
        })
        """,
        {
            "id": feedback_id,
            "tool": payload.tool,
            "vote": payload.vote,
            "context": (payload.context or "").strip()[:300] or None,
            "locale": payload.locale,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    logger.info(f"[FEEDBACK] {payload.tool} {payload.vote}")
    return {"id": feedback_id}


@router.post("/{feedback_id}/comment")
async def add_comment(feedback_id: str, payload: FeedbackComment):
    """Aggiunge il commento facoltativo a un voto già registrato."""
    client = _get_client()
    rows = client.query(
        """
        MATCH (f:UserFeedback {id: $id})
        SET f.comment = $comment
        RETURN f.id AS id
        """,
        {"id": feedback_id, "comment": payload.comment.strip()[:500]},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="feedback not found")
    return {"ok": True}


@router.get("/stats")
async def feedback_stats():
    """Aggregato per strumento: voti e quanti hanno lasciato un commento."""
    client = _get_client()
    rows = client.query(
        """
        MATCH (f:UserFeedback)
        RETURN f.tool AS tool,
               sum(CASE WHEN f.vote = 'up' THEN 1 ELSE 0 END) AS up,
               sum(CASE WHEN f.vote = 'down' THEN 1 ELSE 0 END) AS down,
               sum(CASE WHEN f.comment IS NOT NULL THEN 1 ELSE 0 END) AS with_comment
        ORDER BY tool
        """
    )
    return {"tools": rows}


# ---------------------------------------------------------------------------
# Booth survey (ISWC 2026): 4 affermazioni su scala 1-5 + commento libero.
# Alimenta la parte "structured usability evaluation" della issue #21.
# ---------------------------------------------------------------------------

class BoothCreate(BaseModel):
    q1: int = Field(..., ge=1, le=5)
    q2: int = Field(..., ge=1, le=5)
    q3: int = Field(..., ge=1, le=5)
    q4: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)
    role: Optional[str] = Field(default=None, max_length=30)
    locale: Optional[str] = Field(default=None, max_length=5)


@router.post("/booth")
async def create_booth_survey(payload: BoothCreate):
    survey_id = str(uuid4())
    client = _get_client()
    client.query(
        """
        CREATE (s:BoothSurvey {
            id: $id, q1: $q1, q2: $q2, q3: $q3, q4: $q4,
            comment: $comment, role: $role, locale: $locale,
            created_at: datetime($created_at)
        })
        """,
        {
            "id": survey_id,
            "q1": payload.q1, "q2": payload.q2,
            "q3": payload.q3, "q4": payload.q4,
            "comment": (payload.comment or "").strip()[:1000] or None,
            "role": payload.role,
            "locale": payload.locale,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    logger.info(f"[BOOTH] survey {payload.q1}{payload.q2}{payload.q3}{payload.q4} role={payload.role}")
    return {"id": survey_id}


@router.get("/booth/stats")
async def booth_stats():
    client = _get_client()
    rows = client.query(
        """
        MATCH (s:BoothSurvey)
        RETURN count(s) AS n,
               avg(s.q1) AS q1_mean, avg(s.q2) AS q2_mean,
               avg(s.q3) AS q3_mean, avg(s.q4) AS q4_mean,
               sum(CASE WHEN s.comment IS NOT NULL THEN 1 ELSE 0 END) AS with_comment
        """
    )
    return rows[0] if rows else {"n": 0}
