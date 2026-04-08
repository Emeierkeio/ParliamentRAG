"""
Pydantic v2 models for the transcript API endpoints.

Provides response shapes for the three transcript endpoints:
  - GET /api/transcript/{debate_id}/speeches        -> TranscriptResponse
  - GET /api/transcript/{debate_id}/speech/{id}     -> SpeechTextResponse
  - GET /api/transcript/{debate_id}/suggestions     -> SuggestionsResponse
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class TranscriptSpeechRow(BaseModel):
    """One speech occurrence in chronological order for transcript viewer."""

    speech_id: str
    phase_id: str
    phase_title: str
    speaker_id: str
    first_name: str
    last_name: str
    party: Optional[str] = None
    speaking_role: Optional[str] = None
    is_government_member: bool = False


class TranscriptResponse(BaseModel):
    """All speeches for a debate, chronologically ordered."""

    debate_id: str
    debate_title: str
    session_date: str          # ISO date string for breadcrumb
    session_id: str            # For breadcrumb link
    chamber: str               # "camera" or "senato"
    speeches: list[TranscriptSpeechRow]


class SpeechTextResponse(BaseModel):
    """Text content of a single speech (lazy-loaded on accordion expand)."""

    speech_id: str
    text: str


class SuggestionsResponse(BaseModel):
    """Starter questions for the debate chatbot."""

    questions: list[str]
