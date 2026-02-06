"""Authority score models for the Multi-View RAG system."""
from datetime import date
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AuthorityComponents(BaseModel):
    """Individual components that make up the authority score."""
    profession_relevance: float = Field(
        ge=0.0, le=1.0,
        description="Relevance based on profession embedding similarity"
    )
    education_relevance: float = Field(
        ge=0.0, le=1.0,
        description="Relevance based on education embedding similarity"
    )
    committee_relevance: float = Field(
        ge=0.0, le=1.0,
        description="Relevance based on committee membership"
    )
    acts_score: float = Field(
        ge=0.0, le=1.0,
        description="Score based on parliamentary acts filed"
    )
    interventions_score: float = Field(
        ge=0.0, le=1.0,
        description="Score based on interventions on topic"
    )
    role_score: float = Field(
        ge=0.0, le=1.0,
        description="Score based on institutional role"
    )

    # Raw counts for transparency
    acts_count: int = Field(default=0, description="Number of relevant acts")
    interventions_count: int = Field(default=0, description="Number of relevant interventions")
    committees: List[str] = Field(default_factory=list, description="Relevant committees")


class AuthorityScore(BaseModel):
    """
    Query-dependent authority score for a speaker.

    AuthorityScore(speaker, query, date) ∈ [0, 1]

    CRITICAL: Authority is computed dynamically per query.
    Temporal coalition logic must be respected:
    - If a deputy crosses MAGGIORANZA ↔ OPPOSIZIONE, prior authority is invalidated.
    """
    speaker_id: str = Field(description="Speaker identifier")
    speaker_name: str = Field(description="Full name")
    speaker_role: str = Field(description="Deputy or GovernmentMember")
    party: str = Field(description="Current parliamentary group")
    coalition: str = Field(description="Current coalition")

    # Final score
    score: float = Field(ge=0.0, le=1.0, description="Final authority score")

    # Component breakdown
    components: AuthorityComponents = Field(description="Score components")

    # Weights used (for transparency)
    weights_used: Dict[str, float] = Field(
        description="Weights applied to each component"
    )

    # Temporal context
    reference_date: date = Field(description="Date used for authority computation")
    coalition_changes: List[Dict] = Field(
        default_factory=list,
        description="History of coalition changes (if any)"
    )
    authority_invalidated_periods: List[Dict] = Field(
        default_factory=list,
        description="Periods where authority was invalidated due to coalition crossing"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "speaker_id": "d300001",
                "speaker_name": "Mario Rossi",
                "speaker_role": "Deputy",
                "party": "FRATELLI D'ITALIA",
                "coalition": "maggioranza",
                "score": 0.75,
                "components": {
                    "profession_relevance": 0.6,
                    "education_relevance": 0.5,
                    "committee_relevance": 0.8,
                    "acts_score": 0.7,
                    "interventions_score": 0.9,
                    "role_score": 0.3,
                    "acts_count": 15,
                    "interventions_count": 42,
                    "committees": ["I COMMISSIONE"]
                },
                "weights_used": {
                    "profession": 0.10,
                    "education": 0.10,
                    "committee": 0.20,
                    "acts": 0.25,
                    "interventions": 0.30,
                    "role": 0.05
                },
                "reference_date": "2024-01-15",
                "coalition_changes": [],
                "authority_invalidated_periods": []
            }
        }


class SpeakerAuthorityBatch(BaseModel):
    """Batch of authority scores for multiple speakers."""
    query: str = Field(description="Query used for computation")
    reference_date: date = Field(description="Reference date")
    scores: List[AuthorityScore] = Field(description="Authority scores per speaker")
    computation_time_ms: float = Field(description="Time taken to compute")
