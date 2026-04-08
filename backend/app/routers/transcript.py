"""
Transcript endpoints for the debate transcript viewer.

Read-only endpoints serving speech data from Neo4j, with LLM-generated
starter questions for the contextual chatbot.

Endpoints:
  GET /api/transcript/{debate_id}/speeches           -> all speeches in chronological order
  GET /api/transcript/{debate_id}/speech/{speech_id} -> single speech text (lazy load)
  GET /api/transcript/{debate_id}/suggestions        -> starter questions for chatbot
  POST /api/transcript/{debate_id}/chat            -> debate-scoped SSE chatbot
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.models.transcript import (
    SpeechTextResponse,
    SuggestionsResponse,
    TranscriptChatRequest,
    TranscriptResponse,
)
from app.services.deps import get_neo4j_client
from app.services.neo4j_client import Neo4jClient
from app.services import transcript_service

router = APIRouter(prefix="/api/transcript", tags=["transcript"])


@router.get("/{debate_id}/speeches")
async def get_speeches(
    debate_id: str,
    request: Request,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> TranscriptResponse:
    """Get all speeches for a debate in chronological order."""
    locale = request.headers.get("Accept-Language", "it")[:2]
    return await transcript_service.get_transcript_speeches(
        neo4j=neo4j,
        debate_id=debate_id,
        locale=locale,
    )


@router.get("/{debate_id}/speech/{speech_id}")
async def get_speech_text(
    debate_id: str,
    speech_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> SpeechTextResponse:
    """Get text of a single speech (lazy-loaded by accordion expand)."""
    return await transcript_service.get_speech_text(
        neo4j=neo4j,
        debate_id=debate_id,
        speech_id=speech_id,
    )


@router.get("/{debate_id}/suggestions")
async def get_suggestions(
    debate_id: str,
    request: Request,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> SuggestionsResponse:
    """Get 3-4 starter questions for the debate chatbot."""
    locale = request.headers.get("Accept-Language", "it")[:2]
    return await transcript_service.get_debate_suggestions(
        neo4j=neo4j,
        debate_id=debate_id,
        locale=locale,
    )


@router.post("/{debate_id}/chat")
async def debate_chat(
    debate_id: str,
    body: TranscriptChatRequest,
    request: Request,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
):
    """Debate-scoped chatbot with SSE streaming. No persistence — session-only."""
    locale = request.headers.get("Accept-Language", "it")[:2]
    history = [{"role": m.role, "content": m.content} for m in body.history]
    return StreamingResponse(
        transcript_service.debate_chat_streaming(
            debate_id=debate_id,
            query=body.query,
            history=history,
            locale=locale,
            neo4j=neo4j,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
