"""
Pydantic v2 models for the timeline API endpoints.

Provides response shapes for the three timeline endpoints:
  - GET /api/timeline            → TimelineResponse
  - GET /api/timeline/debates/{id} → DebateDetailResponse
  - GET /api/timeline/speakers/{debateId}/{speakerId} → SpeakerSummaryResponse
"""
from typing import Optional

from pydantic import BaseModel


class DebateSummary(BaseModel):
    """Lightweight debate entry nested inside a SessionCard."""

    id: str
    title: str
    speech_count: int


class SessionCard(BaseModel):
    """One parliamentary session shown in the timeline list."""

    id: str
    date: str                        # ISO date string "2026-04-07"
    chamber: str                     # "camera" or "senato"
    number: int
    recap: Optional[str] = None      # None if not yet generated
    debate_count: int
    vote_count: int
    speech_count: int
    debates: list[DebateSummary]


class TimelineResponse(BaseModel):
    """Paginated list of sessions for GET /api/timeline."""

    sessions: list[SessionCard]
    next_cursor: Optional[str] = None  # ISO date of the last session in this page
    has_more: bool


class PhaseInfo(BaseModel):
    """A single debate phase with speech count."""

    id: str
    title: str
    phase_type: Optional[str] = None
    speech_count: int


class VoteInfo(BaseModel):
    """One roll-call vote attached to a session."""

    id: str
    number: int
    subject: Optional[str] = None
    outcome: Optional[str] = None
    in_favor: Optional[int] = None
    against: Optional[int] = None
    abstained: Optional[int] = None


class ActInfo(BaseModel):
    """Parliamentary act discussed in a debate."""

    id: str
    title: Optional[str] = None
    type: Optional[str] = None


class SpeakerInfo(BaseModel):
    """One speaker in a debate, listed chronologically."""

    id: str
    first_name: str
    last_name: str
    party: Optional[str] = None
    speaking_role: Optional[str] = None
    is_government_member: bool = False
    speech_count: int
    phases: list[str]  # Phase titles where this speaker participated


class DebateDetailResponse(BaseModel):
    """Full debate detail for GET /api/timeline/debates/{id}."""

    id: str
    title: str
    recap: Optional[str] = None
    phases: list[PhaseInfo]
    speakers: list[SpeakerInfo]
    votes: list[VoteInfo]
    acts: list[ActInfo]


class SpeechText(BaseModel):
    """Full text of a single speech in a debate."""

    id: str
    text: str
    phase_title: Optional[str] = None


class SpeakerSummaryResponse(BaseModel):
    """Speaker speeches and optional AI summary for GET /api/timeline/speakers/{debateId}/{speakerId}."""

    summary: Optional[str] = None
    speech_count: int
    phases: list[str]
    speeches: list[SpeechText] = []
