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


class HistoryListResponse(BaseModel):
    """Response for history list endpoint."""
    history: List[Dict[str, Any]] = []


def _get_client():
    return get_neo4j_client()


def _ensure_constraint():
    """Create uniqueness constraint on ChatHistory.id if not exists."""
    try:
        _get_client().query(
            "CREATE CONSTRAINT chat_history_id IF NOT EXISTS FOR (c:ChatHistory) REQUIRE c.id IS UNIQUE"
        )
    except Exception as e:
        logger.debug(f"Constraint already exists or error: {e}")


# Run on import
_ensure_constraint()


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
    clean_text = _strip_markdown(chat.answer)
    chat.preview = clean_text[:100] + "..." if len(clean_text) > 100 else clean_text

    client = _get_client()

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
            compass: $compass
        })
    """, {
        "id": chat.id,
        "query": chat.query,
        "answer": chat.answer,
        "preview": chat.preview,
        "timestamp": chat.timestamp.isoformat(),
        "citations": json.dumps(chat.citations, ensure_ascii=False, default=str),
        "experts": json.dumps(chat.experts, ensure_ascii=False, default=str),
        "balance": json.dumps(chat.balance, ensure_ascii=False, default=str) if chat.balance else "",
        "compass": json.dumps(chat.compass, ensure_ascii=False, default=str) if chat.compass else "",
    })

    # Keep only last 50 chats
    client.query("""
        MATCH (c:ChatHistory)
        WITH c ORDER BY c.timestamp DESC
        SKIP 50
        DELETE c
    """)

    logger.info(f"Saved chat to history: {chat.id}, query: {chat.query[:50]}...")
    return chat


@router.get("/history/{chat_id}")
async def get_chat(chat_id: str) -> Dict[str, Any]:
    """Get a specific chat session by ID."""
    client = _get_client()
    result = client.query("""
        MATCH (c:ChatHistory {id: $id})
        RETURN c.id AS id, c.query AS query, c.answer AS answer,
               c.timestamp AS timestamp, c.citations AS citations,
               c.experts AS experts, c.balance AS balance, c.compass AS compass
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
    }


@router.delete("/history/{chat_id}")
async def delete_chat(chat_id: str) -> Dict[str, Any]:
    """Delete a chat from history."""
    client = _get_client()
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
    """Clear all chat history."""
    client = _get_client()
    result = client.query("""
        MATCH (c:ChatHistory)
        WITH c, count(*) AS count
        DELETE c
        RETURN count
    """)
    count = result[0]["count"] if result else 0
    return {"cleared": True, "count": count}
