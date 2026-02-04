"""
Evidence models for the Multi-View RAG system.

CRITICAL: This module implements the UnifiedEvidence schema with CLEAR SEPARATION between:
- chunk_text: used for retrieval preview (may be preprocessed)
- quote_text: VERBATIM extraction from testo_raw using offsets

Citation integrity is enforced through offset-based extraction ONLY.
NO fuzzy matching is allowed.
"""
from datetime import date as date_type
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, field_validator


class IdeologyScore(BaseModel):
    """Ideological positioning score for a fragment or speaker."""
    left: float = Field(ge=0.0, le=1.0, description="Left positioning score")
    center: float = Field(ge=0.0, le=1.0, description="Center positioning score")
    right: float = Field(ge=0.0, le=1.0, description="Right positioning score")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the score")
    method: Literal["kde", "mean_ellipse", "insufficient_data"] = Field(
        description="Method used to compute the score"
    )


class UnifiedEvidence(BaseModel):
    """
    Schema for evidence records with CLEAR SEPARATION between:
    - chunk_text: used for retrieval preview (may be preprocessed)
    - quote_text: VERBATIM extraction from testo_raw using offsets

    CRITICAL: quote_text is the ONLY valid citation source.
    Citation validity = valid offsets + verbatim extraction.
    DO NOT compare quote_text with chunk_text for verification.
    """
    # Identifiers
    evidence_id: str = Field(description="Chunk ID - unique identifier")
    doc_id: str = Field(description="Seduta ID")
    speech_id: str = Field(description="Intervento ID")
    speaker_id: str = Field(description="Deputato or MembroGoverno ID")

    # Speaker info
    speaker_name: str = Field(description="Full speaker name")
    speaker_role: Literal["Deputato", "MembroGoverno"] = Field(
        description="Speaker type"
    )
    party: str = Field(description="Parliamentary group name")
    coalition: Literal["maggioranza", "opposizione"] = Field(
        description="Coalition membership"
    )
    date: date_type = Field(description="Date of the intervention")

    # TEXT FIELDS - CLEARLY DISTINGUISHED
    chunk_text: str = Field(
        description="chunk.testo - used for retrieval/preview ONLY. "
                    "May be preprocessed. NOT valid for citation."
    )
    quote_text: str = Field(
        description="VERBATIM extraction from intervento.testo_raw[span_start:span_end]. "
                    "This is the ONLY valid citation source."
    )

    # Offset metadata for verification
    span_start: int = Field(ge=0, description="Start offset in testo_raw")
    span_end: int = Field(gt=0, description="End offset in testo_raw")

    # Context
    dibattito_titolo: Optional[str] = Field(default=None, description="Debate title")
    seduta_numero: int = Field(description="Session number")

    # Scores
    similarity: float = Field(ge=0.0, le=1.0, description="Semantic similarity score")
    authority_score: float = Field(
        ge=0.0, le=1.0, default=0.0, description="Speaker authority score"
    )
    ideology: Optional[IdeologyScore] = Field(
        default=None, description="Ideological positioning"
    )

    # Embedding for compass PCA analysis (optional, excluded from API response serialization)
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Chunk embedding vector for compass analysis",
        exclude=True  # Don't include in JSON responses (too large)
    )

    @field_validator("span_end")
    @classmethod
    def validate_span_order(cls, v: int, info) -> int:
        """Ensure span_end > span_start."""
        if "span_start" in info.data and v <= info.data["span_start"]:
            raise ValueError("span_end must be greater than span_start")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "evidence_id": "leg19_sed123_tit00010.int00005_chunk_2",
                "doc_id": "leg19_sed123",
                "speech_id": "leg19_sed123_tit00010.int00005",
                "speaker_id": "d300001",
                "speaker_name": "Mario Rossi",
                "speaker_role": "Deputato",
                "party": "FRATELLI D'ITALIA",
                "coalition": "maggioranza",
                "date": "2023-05-15",
                "chunk_text": "Preview text for retrieval...",
                "quote_text": "Exact verbatim quote from testo_raw",
                "span_start": 1523,
                "span_end": 1687,
                "dibattito_titolo": "Discussione DL immigrazione",
                "seduta_numero": 123,
                "similarity": 0.85,
                "authority_score": 0.72,
                "ideology": {
                    "left": 0.1,
                    "center": 0.3,
                    "right": 0.6,
                    "confidence": 0.8,
                    "method": "kde"
                }
            }
        }


def compute_quote_text(intervento_testo_raw: str, span_start: int, span_end: int) -> str:
    """
    Extract EXACT quote using offsets. This is the ONLY valid method.

    CRITICAL: This function extracts verbatim text from the source.
    NEVER compare the result with chunk.testo for verification.
    Citation validity = valid offsets + successful extraction.

    Args:
        intervento_testo_raw: The raw intervention text
        span_start: Start offset (inclusive)
        span_end: End offset (exclusive)

    Returns:
        Verbatim extracted quote

    Raises:
        ValueError: If offsets are invalid
    """
    if span_start < 0:
        raise ValueError(f"span_start must be non-negative, got {span_start}")
    if span_end > len(intervento_testo_raw):
        raise ValueError(
            f"span_end ({span_end}) exceeds text length ({len(intervento_testo_raw)})"
        )
    if span_start >= span_end:
        raise ValueError(
            f"span_start ({span_start}) must be less than span_end ({span_end})"
        )

    return intervento_testo_raw[span_start:span_end]


def verify_citation_integrity(
    quote_or_evidence,
    intervento_testo_raw: str,
    span_start: Optional[int] = None,
    span_end: Optional[int] = None
) -> bool:
    """
    Verify citation is valid by re-extracting from source.

    CRITICAL: This DOES NOT compare with chunk_text - that would be incorrect.
    Verification is done by re-extraction only.

    Can be called in two ways:
    1. verify_citation_integrity(evidence, testo_raw) - with UnifiedEvidence object
    2. verify_citation_integrity(quote_text, testo_raw, start, end) - with individual params

    Args:
        quote_or_evidence: Either an UnifiedEvidence object or a quote string
        intervento_testo_raw: The raw intervention text
        span_start: Start offset (required if quote_or_evidence is a string)
        span_end: End offset (required if quote_or_evidence is a string)

    Returns:
        True if re-extraction matches stored/provided quote_text
    """
    try:
        # Check if first argument is an UnifiedEvidence object
        if isinstance(quote_or_evidence, UnifiedEvidence):
            evidence = quote_or_evidence
            re_extracted = intervento_testo_raw[evidence.span_start:evidence.span_end]
            return re_extracted == evidence.quote_text
        else:
            # Individual parameters provided
            if span_start is None or span_end is None:
                raise ValueError("span_start and span_end required when quote is a string")
            quote_text = quote_or_evidence
            re_extracted = intervento_testo_raw[span_start:span_end]
            return re_extracted == quote_text
    except (IndexError, ValueError):
        return False


class EvidenceBundle(BaseModel):
    """Collection of evidence records for a query response."""
    query: str = Field(description="Original query")
    total_retrieved: int = Field(description="Total evidence pieces retrieved")
    evidence: List[UnifiedEvidence] = Field(description="List of evidence records")
    retrieval_channels: dict = Field(
        default_factory=dict,
        description="Metadata about retrieval channels used"
    )
