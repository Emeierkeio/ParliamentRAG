"""
History endpoint for chat conversation history.

Stores complete chat sessions in Neo4j for persistence across deploys.
"""
import json
import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.neo4j_client import get_neo4j_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["History"])


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting for clean preview text."""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\[CIT:[^\]]+\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class ChatHistoryItem(BaseModel):
    """A stored chat session with full response data."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    answer: str
    preview: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)

    citations: List[Dict[str, Any]] = []
    experts: List[Dict[str, Any]] = []
    balance: Optional[Dict[str, Any]] = None
    compass: Optional[Dict[str, Any]] = None

    # A/B Baseline comparison fields (optional for backwards compatibility)
    baseline_answer: Optional[str] = None
    ab_assignment: Optional[Dict[str, str]] = None  # e.g. {"A": "system", "B": "baseline"}


class HistoryListResponse(BaseModel):
    """Response for history list endpoint."""
    history: List[Dict[str, Any]] = []


def _get_client():
    try:
        return get_neo4j_client()
    except RuntimeError:
        # Global client not initialized yet - create and register it
        from ..config import get_settings
        from ..services.neo4j_client import Neo4jClient, init_neo4j_client
        settings = get_settings()
        return init_neo4j_client(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )


def ensure_constraint():
    """Create uniqueness constraint on ChatHistory.id if not exists."""
    try:
        _get_client().query(
            "CREATE CONSTRAINT chat_history_id IF NOT EXISTS FOR (c:ChatHistory) REQUIRE c.id IS UNIQUE"
        )
    except Exception as e:
        logger.debug(f"Constraint already exists or error: {e}")


@router.get("/history")
async def get_history() -> HistoryListResponse:
    """Get chat history list for sidebar display."""
    client = _get_client()
    results = client.query("""
        MATCH (c:ChatHistory)
        RETURN c.id AS id, c.query AS query, c.preview AS preview,
               c.timestamp AS timestamp
        ORDER BY c.timestamp DESC
        LIMIT 50
    """)

    history_list = []
    for r in results:
        history_list.append({
            "id": r["id"],
            "query": r["query"],
            "preview": r.get("preview", ""),
            "timestamp": r["timestamp"],
        })
    return HistoryListResponse(history=history_list)


@router.post("/history")
async def save_chat(chat: ChatHistoryItem) -> ChatHistoryItem:
    """Save a chat session to history."""
    try:
        logger.info(f"[HISTORY-SAVE] === Saving chat to history ===")
        logger.info(f"[HISTORY-SAVE] chat.id={chat.id}")
        logger.info(f"[HISTORY-SAVE] chat.query='{chat.query[:80]}...'")
        logger.info(f"[HISTORY-SAVE] chat.answer length={len(chat.answer)}")
        logger.info(f"[HISTORY-SAVE] chat.baseline_answer: type={type(chat.baseline_answer).__name__}, value={repr(chat.baseline_answer[:200]) if chat.baseline_answer else repr(chat.baseline_answer)}")
        logger.info(f"[HISTORY-SAVE] chat.ab_assignment: type={type(chat.ab_assignment).__name__}, value={chat.ab_assignment}")

        clean_text = _strip_markdown(chat.answer)
        chat.preview = clean_text[:100] + "..." if len(clean_text) > 100 else clean_text

        client = _get_client()

        # Serialize with size limits to avoid Neo4j property size issues
        citations_json = json.dumps(chat.citations, ensure_ascii=False, default=str)
        experts_json = json.dumps(chat.experts, ensure_ascii=False, default=str)
        balance_json = json.dumps(chat.balance, ensure_ascii=False, default=str) if chat.balance else ""
        compass_json = json.dumps(chat.compass, ensure_ascii=False, default=str) if chat.compass else ""
        ab_assignment_json = json.dumps(chat.ab_assignment, ensure_ascii=False) if chat.ab_assignment else ""

        baseline_value = (chat.baseline_answer or "")[:50000]
        logger.info(f"[HISTORY-SAVE] Neo4j params: baseline_answer='{baseline_value[:100]}...' (len={len(baseline_value)}), ab_assignment='{ab_assignment_json}'")

        client.query("""
            CREATE (c:ChatHistory {
                id: $id,
                query: $query,
                answer: $answer,
                preview: $preview,
                timestamp: $timestamp,
                citations: $citations,
                experts: $experts,
                balance: $balance,
                compass: $compass,
                baseline_answer: $baseline_answer,
                ab_assignment: $ab_assignment
            })
        """, {
            "id": chat.id,
            "query": chat.query,
            "answer": chat.answer[:50000],  # Limit answer size
            "preview": chat.preview,
            "timestamp": chat.timestamp.isoformat(),
            "citations": citations_json,
            "experts": experts_json,
            "balance": balance_json,
            "compass": compass_json,
            "baseline_answer": baseline_value,
            "ab_assignment": ab_assignment_json,
        })

        # Verify what was actually saved
        verify = client.query("""
            MATCH (c:ChatHistory {id: $id})
            RETURN c.baseline_answer AS baseline_answer, c.ab_assignment AS ab_assignment
        """, {"id": chat.id})
        if verify:
            logger.info(f"[HISTORY-SAVE] VERIFICATION: Neo4j baseline_answer='{str(verify[0].get('baseline_answer', ''))[:100]}...', ab_assignment='{verify[0].get('ab_assignment', '')}'")
        else:
            logger.warning(f"[HISTORY-SAVE] VERIFICATION FAILED: Could not find chat {chat.id} after save!")

        # Keep only last 50 chats
        client.query("""
            MATCH (c:ChatHistory)
            WITH c ORDER BY c.timestamp DESC
            SKIP 50
            DELETE c
        """)

        logger.info(f"[HISTORY-SAVE] Saved chat to history: {chat.id}, query: {chat.query[:50]}...")
        return chat
    except Exception as e:
        logger.error(f"Failed to save chat to history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save chat: {str(e)}")


@router.get("/history/{chat_id}")
async def get_chat(chat_id: str) -> Dict[str, Any]:
    """Get a specific chat session by ID."""
    client = _get_client()
    result = client.query("""
        MATCH (c:ChatHistory {id: $id})
        RETURN c.id AS id, c.query AS query, c.answer AS answer,
               c.timestamp AS timestamp, c.citations AS citations,
               c.experts AS experts, c.balance AS balance, c.compass AS compass,
               c.baseline_answer AS baseline_answer, c.ab_assignment AS ab_assignment
    """, {"id": chat_id})

    if not result:
        raise HTTPException(status_code=404, detail="Chat not found")

    r = result[0]
    return {
        "id": r["id"],
        "query": r["query"],
        "answer": r["answer"],
        "timestamp": r["timestamp"],
        "citations": json.loads(r["citations"]) if r.get("citations") else [],
        "experts": json.loads(r["experts"]) if r.get("experts") else [],
        "balance": json.loads(r["balance"]) if r.get("balance") else None,
        "compass": json.loads(r["compass"]) if r.get("compass") else None,
        "baseline_answer": r.get("baseline_answer") or None,
        "ab_assignment": json.loads(r["ab_assignment"]) if r.get("ab_assignment") else None,
    }


@router.delete("/history/{chat_id}")
async def delete_chat(chat_id: str) -> Dict[str, Any]:
    """Delete a chat from history and its associated survey."""
    client = _get_client()
    # Delete associated survey if any
    client.query("""
        MATCH (s:SurveyEvaluation {chat_id: $id})
        DELETE s
    """, {"id": chat_id})
    result = client.query("""
        MATCH (c:ChatHistory {id: $id})
        DELETE c
        RETURN count(*) AS deleted
    """, {"id": chat_id})

    if not result or result[0]["deleted"] == 0:
        raise HTTPException(status_code=404, detail="Chat not found")

    return {"deleted": True, "id": chat_id}


@router.delete("/history")
async def clear_history() -> Dict[str, Any]:
    """Clear all chat history and associated surveys."""
    client = _get_client()
    # Delete all surveys first
    client.query("MATCH (s:SurveyEvaluation) DELETE s")
    result = client.query("""
        MATCH (c:ChatHistory)
        WITH c, count(*) AS count
        DELETE c
        RETURN count
    """)
    count = result[0]["count"] if result else 0
    return {"cleared": True, "count": count}
