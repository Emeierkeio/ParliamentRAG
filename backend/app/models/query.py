"""Query and response models for the Multi-View RAG system."""
from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from .evidence import UnifiedEvidence, IdeologyScore


class QueryRequest(BaseModel):
    """Request model for the /query endpoint."""
    query: str = Field(min_length=3, description="User's natural language question")
    reference_date: Optional[date] = Field(
        default=None,
        description="Reference date for temporal queries. Defaults to today."
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional filters (date range, parties, etc.)"
    )
    top_k: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Number of evidence pieces to retrieve"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Qual è la posizione dei partiti sull'immigrazione?",
                "reference_date": "2024-01-15",
                "top_k": 100
            }
        }


class PartySection(BaseModel):
    """A section of the multi-view answer for a single party."""
    party: str = Field(description="Parliamentary group name")
    coalition: str = Field(description="Coalition (maggioranza/opposizione)")
    has_evidence: bool = Field(description="Whether evidence was found for this party")
    content: str = Field(description="Generated content for this party")
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="IDs of evidence used in this section"
    )
    speaker_count: int = Field(default=0, description="Number of distinct speakers")
    ideology_position: Optional[IdeologyScore] = Field(
        default=None,
        description="Aggregate ideological position"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "party": "FRATELLI D'ITALIA",
                "coalition": "maggioranza",
                "has_evidence": True,
                "content": "Il partito sostiene una politica di...",
                "evidence_ids": ["leg19_sed123_chunk_1", "leg19_sed124_chunk_5"],
                "speaker_count": 3
            }
        }


class GovernmentSection(BaseModel):
    """Section for government members' positions."""
    has_interventions: bool = Field(
        description="Whether government members intervened on this topic"
    )
    content: str = Field(description="Generated content from government positions")
    evidence_ids: List[str] = Field(default_factory=list)
    members: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Government members who intervened"
    )


class CompassResult(BaseModel):
    """Result of ideological compass analysis."""
    fragments_analyzed: int = Field(description="Number of fragments analyzed")
    group_positions: Dict[str, IdeologyScore] = Field(
        description="Ideological position per party"
    )
    coverage: Dict[str, float] = Field(
        description="Coverage scores for left/center/right"
    )
    visualization_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data for compass visualization"
    )


class RetrievalMetadata(BaseModel):
    """Metadata about the retrieval process."""
    dense_channel_count: int = Field(description="Results from dense channel")
    graph_channel_count: int = Field(description="Results from graph channel")
    merged_count: int = Field(description="Final merged results")
    party_coverage: Dict[str, int] = Field(
        description="Number of evidence pieces per party"
    )
    processing_time_ms: float = Field(description="Total retrieval time in ms")


class MultiViewResponse(BaseModel):
    """
    Complete response for a multi-view RAG query.

    CRITICAL: All 10 parliamentary groups must have a section.
    If no evidence exists for a party, has_evidence=False and content
    contains the standard "no evidence" message.
    """
    query: str = Field(description="Original query")
    reference_date: date = Field(description="Reference date used for the query")

    # Multi-view sections - ALL 10 parties must be present
    party_sections: List[PartySection] = Field(
        min_length=10,
        max_length=10,
        description="One section per parliamentary group (all 10 required)"
    )

    # Government section
    government_section: GovernmentSection = Field(
        description="Section for government members"
    )

    # Overview/summary
    overview: str = Field(description="High-level summary integrating all views")

    # Evidence bundle
    evidence: List[UnifiedEvidence] = Field(
        description="All evidence used in the response"
    )

    # Analysis results
    compass: Optional[CompassResult] = Field(
        default=None,
        description="Ideological compass analysis"
    )

    # Metadata
    retrieval_metadata: RetrievalMetadata = Field(
        description="Information about the retrieval process"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Qual è la posizione dei partiti sull'immigrazione?",
                "reference_date": "2024-01-15",
                "party_sections": [
                    {
                        "party": "FRATELLI D'ITALIA",
                        "coalition": "maggioranza",
                        "has_evidence": True,
                        "content": "...",
                        "evidence_ids": [],
                        "speaker_count": 5
                    }
                ],
                "government_section": {
                    "has_interventions": True,
                    "content": "...",
                    "evidence_ids": [],
                    "members": []
                },
                "overview": "...",
                "evidence": [],
                "retrieval_metadata": {
                    "dense_channel_count": 150,
                    "graph_channel_count": 50,
                    "merged_count": 100,
                    "party_coverage": {},
                    "processing_time_ms": 1234.5
                }
            }
        }


# Standard message for parties without evidence
NO_EVIDENCE_MESSAGE = (
    "Nel corpus analizzato non risultano interventi rilevanti su questo tema."
)
