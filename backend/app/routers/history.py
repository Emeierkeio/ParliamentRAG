"""
History endpoint for chat conversation history.

Stores complete chat sessions with all metadata for replay.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["History"])


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting for clean preview text."""
    # Remove headers (##, ###, etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    # Remove links [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove citation markers [CIT:...]
    text = re.sub(r'\[CIT:[^\]]+\]', '', text)
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Path to the JSON file for persistent storage
HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "chat_history.json"


class ChatHistoryItem(BaseModel):
    """A stored chat session with full response data."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    answer: str
    preview: str = ""  # Short preview for list display
    timestamp: datetime = Field(default_factory=datetime.now)

    # Full response metadata
    citations: List[Dict[str, Any]] = []
    experts: List[Dict[str, Any]] = []
    balance: Optional[Dict[str, Any]] = None
    compass: Optional[Dict[str, Any]] = None


class HistoryListResponse(BaseModel):
    """Response for history list endpoint."""
    history: List[Dict[str, Any]] = []


def _load_history() -> List[ChatHistoryItem]:
    """Load chat history from JSON file."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ChatHistoryItem(**item) for item in data]
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error loading history: {e}")
        return []


def _save_history(history: List[ChatHistoryItem]) -> None:
    """Save chat history to JSON file."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = [item.model_dump(mode="json") for item in history]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving history: {e}")


@router.get("/history")
async def get_history() -> HistoryListResponse:
    """
    Get chat history list.

    Returns simplified list for sidebar display.
    """
    _chat_history = _load_history()
    history_list = []
    for item in _chat_history:
        # Use existing preview or generate clean one
        if item.preview and not item.preview.startswith("#"):
            preview = item.preview
        else:
            clean_text = _strip_markdown(item.answer)
            preview = clean_text[:100] + "..." if len(clean_text) > 100 else clean_text
        history_list.append({
            "id": item.id,
            "query": item.query,
            "preview": preview,
            "timestamp": item.timestamp.isoformat(),
        })
    return HistoryListResponse(history=history_list)


@router.post("/history")
async def save_chat(chat: ChatHistoryItem) -> ChatHistoryItem:
    """
    Save a chat session to history.
    """
    # Generate clean preview (strip markdown)
    clean_text = _strip_markdown(chat.answer)
    chat.preview = clean_text[:100] + "..." if len(clean_text) > 100 else clean_text

    _chat_history = _load_history()
    _chat_history.insert(0, chat)  # Most recent first

    # Keep only last 50 chats
    while len(_chat_history) > 50:
        _chat_history.pop()

    _save_history(_chat_history)
    logger.info(f"Saved chat to history: {chat.id}, query: {chat.query[:50]}...")
    return chat


@router.get("/history/{chat_id}")
async def get_chat(chat_id: str) -> Dict[str, Any]:
    """
    Get a specific chat session by ID.

    Returns full data for replay including citations, experts, etc.
    """
    _chat_history = _load_history()
    for item in _chat_history:
        if item.id == chat_id:
            return {
                "id": item.id,
                "query": item.query,
                "answer": item.answer,
                "timestamp": item.timestamp.isoformat(),
                "citations": item.citations,
                "experts": item.experts,
                "balance": item.balance,
                "compass": item.compass,
            }

    raise HTTPException(status_code=404, detail="Chat not found")


@router.delete("/history/{chat_id}")
async def delete_chat(chat_id: str) -> Dict[str, Any]:
    """
    Delete a chat from history.
    """
    _chat_history = _load_history()
    original_len = len(_chat_history)
    _chat_history = [c for c in _chat_history if c.id != chat_id]

    if len(_chat_history) == original_len:
        raise HTTPException(status_code=404, detail="Chat not found")

    _save_history(_chat_history)
    return {"deleted": True, "id": chat_id}


@router.delete("/history")
async def clear_history() -> Dict[str, Any]:
    """
    Clear all chat history.
    """
    _chat_history = _load_history()
    count = len(_chat_history)
    _save_history([])
    return {"cleared": True, "count": count}
