"""
Evidence models for the Multi-View RAG system.

CRITICAL: This module implements the UnifiedEvidence schema with CLEAR SEPARATION between:
- chunk_text: used for retrieval preview (may be preprocessed)
- quote_text: VERBATIM extraction from text using offsets

Citation integrity is enforced through offset-based extraction ONLY.
NO fuzzy matching is allowed.
"""
from datetime import date as date_type
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, field_validator


# ── Name normalisation (deterministic, applied at retrieval time) ────────────

PARTY_DISPLAY_NAMES: dict[str, str] = {
    "FRATELLI D'ITALIA": "Fratelli d'Italia",
    "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA": "Partito Democratico - Italia Democratica e Progressista",
    "LEGA - SALVINI PREMIER": "Lega - Salvini Premier",
    "MOVIMENTO 5 STELLE": "Movimento 5 Stelle",
    "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE": "Forza Italia - Berlusconi Presidente - PPE",
    "ALLEANZA VERDI E SINISTRA": "Alleanza Verdi e Sinistra",
    "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE": "Azione - Popolari Europeisti Riformatori - Renew Europe",
    "ITALIA VIVA-IL CENTRO-RENEW EUROPE": "Italia Viva - Il Centro - Renew Europe",
    "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE": "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare",
    "MISTO": "Misto",
    "GOVERNO": "Governo",
}


def normalize_speaker_name(first_name: str, last_name: str) -> str:
    """Return speaker name in title case (e.g. 'Mario Rossi')."""
    full = f"{first_name} {last_name}".strip()
    return full.title() if full else ""


def normalize_party_name(raw_party: str) -> str:
    """Map DB party name (UPPERCASE) to readable display name."""
    return PARTY_DISPLAY_NAMES.get(raw_party, raw_party.title() if raw_party else "Misto")


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
    - quote_text: VERBATIM extraction from text using offsets

    CRITICAL: quote_text is the ONLY valid citation source.
    Citation validity = valid offsets + verbatim extraction.
    DO NOT compare quote_text with chunk_text for verification.
    """
    # Identifiers
    evidence_id: str = Field(description="Chunk ID - unique identifier")
    doc_id: str = Field(description="Session ID")
    speech_id: str = Field(description="Speech ID")
    speaker_id: str = Field(description="Deputy or GovernmentMember ID")

    # Speaker info
    speaker_name: str = Field(description="Full speaker name")
    speaker_role: Literal["Deputy", "GovernmentMember"] = Field(
        description="Speaker type"
    )
    party: str = Field(description="Parliamentary group name")
    coalition: Literal["maggioranza", "opposizione", "governo"] = Field(
        description="Coalition membership"
    )
    date: date_type = Field(description="Date of the intervention")

    # TEXT FIELDS - CLEARLY DISTINGUISHED
    chunk_text: str = Field(
        description="chunk.text - used for retrieval/preview ONLY. "
                    "May be preprocessed. NOT valid for citation."
    )
    quote_text: str = Field(
        description="VERBATIM extraction from speech.text[span_start:span_end]. "
                    "This is the ONLY valid citation source."
    )

    # Offset metadata for verification
    span_start: int = Field(ge=0, description="Start offset in text")
    span_end: int = Field(gt=0, description="End offset in text")

    # Context
    debate_title: Optional[str] = Field(default=None, description="Debate title")
    session_number: int = Field(description="Session number")

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

    # Full speech text — excluded from API responses but needed by CitationSurgeon
    # to expand mid-sentence chunk boundaries back to the sentence start.
    text: str = Field(
        default="",
        description="Full speech text (speech.text). Used by CitationSurgeon for "
                    "sentence-boundary expansion when chunk starts mid-sentence.",
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
                "speaker_role": "Deputy",
                "party": "FRATELLI D'ITALIA",
                "coalition": "maggioranza",
                "date": "2023-05-15",
                "chunk_text": "Preview text for retrieval...",
                "quote_text": "Exact verbatim quote from text",
                "span_start": 1523,
                "span_end": 1687,
                "debate_title": "Discussione DL immigrazione",
                "session_number": 123,
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


def compute_quote_text(speech_text: str, span_start: int, span_end: int) -> str:
    """
    Extract quote using offsets, with automatic clamping and word-boundary alignment.

    This function:
    1. Clamps offsets to valid text bounds
    2. Extends start backward to the nearest word boundary (space or start of text)
    3. Extends end forward to the nearest word boundary (space or end of text)

    Args:
        speech_text: The raw speech text
        span_start: Start offset (inclusive)
        span_end: End offset (exclusive)

    Returns:
        Extracted quote aligned to word boundaries

    Raises:
        ValueError: If offsets are completely invalid (negative end, start > end after clamping)
    """
    text_len = len(speech_text)

    # Handle empty text
    if text_len == 0:
        return ""

    # Clamp offsets to valid bounds
    span_start = max(0, span_start)
    span_end = min(text_len, span_end)

    # Validate after clamping
    if span_start >= span_end:
        raise ValueError(
            f"Invalid span after clamping: start={span_start}, end={span_end}"
        )

    # Extend start backward to word boundary (find previous space or start of text)
    while span_start > 0 and speech_text[span_start] != ' ' and speech_text[span_start - 1] != ' ':
        span_start -= 1

    # Skip leading space if we landed on one
    if span_start < text_len and speech_text[span_start] == ' ':
        span_start += 1

    # Extend end forward to word boundary (find next space or end of text)
    while span_end < text_len and speech_text[span_end - 1] != ' ' and speech_text[span_end] != ' ':
        span_end += 1

    # Strip trailing space if we landed before one
    while span_end > span_start and speech_text[span_end - 1] == ' ':
        span_end -= 1

    return speech_text[span_start:span_end]


def verify_citation_integrity(
    quote_or_evidence,
    speech_text: str,
    span_start: Optional[int] = None,
    span_end: Optional[int] = None
) -> bool:
    """
    Verify citation is valid by re-extracting from source.

    CRITICAL: This DOES NOT compare with chunk_text - that would be incorrect.
    Verification is done by re-extraction only.

    Can be called in two ways:
    1. verify_citation_integrity(evidence, text) - with UnifiedEvidence object
    2. verify_citation_integrity(quote_text, text, start, end) - with individual params

    Args:
        quote_or_evidence: Either an UnifiedEvidence object or a quote string
        speech_text: The raw speech text
        span_start: Start offset (required if quote_or_evidence is a string)
        span_end: End offset (required if quote_or_evidence is a string)

    Returns:
        True if re-extraction matches stored/provided quote_text
    """
    try:
        # Check if first argument is an UnifiedEvidence object
        if isinstance(quote_or_evidence, UnifiedEvidence):
            evidence = quote_or_evidence
            re_extracted = speech_text[evidence.span_start:evidence.span_end]
            return re_extracted == evidence.quote_text
        else:
            # Individual parameters provided
            if span_start is None or span_end is None:
                raise ValueError("span_start and span_end required when quote is a string")
            quote_text = quote_or_evidence
            re_extracted = speech_text[span_start:span_end]
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
