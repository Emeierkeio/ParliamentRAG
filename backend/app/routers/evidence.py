"""
Evidence endpoint for retrieving full evidence details.

Provides exact quote extraction with verification.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from ..services.neo4j_client import Neo4jClient
from ..models.evidence import compute_quote_text, verify_citation_integrity
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/evidence", tags=["Evidence"])


class EvidenceResponse(BaseModel):
    """Full evidence response with exact quote."""
    evidence_id: str
    chunk_id: str
    speech_id: str
    doc_id: str

    # Speaker info
    speaker_id: str
    speaker_name: str
    speaker_role: str
    party: str
    coalition: str

    # Text content
    chunk_text: str  # Preview text
    quote_text: str  # EXACT verbatim quote
    testo_raw: Optional[str] = None  # Full intervention text (optional)

    # Offsets
    span_start: int
    span_end: int

    # Context
    date: str
    dibattito_titolo: Optional[str]
    seduta_numero: int

    # Verification
    citation_verified: bool


# Service instance
_neo4j_client: Optional[Neo4jClient] = None


def get_neo4j():
    """Get or initialize Neo4j client."""
    global _neo4j_client
    if _neo4j_client is None:
        settings = get_settings()
        _neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )
    return _neo4j_client


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: str = Path(..., description="Evidence/Chunk ID")
):
    """
    Get full evidence details by ID.

    Returns the exact verbatim quote extracted via offsets,
    with verification status.
    """
    client = get_neo4j()

    # Query for full evidence details
    cypher = """
    MATCH (c:Chunk {id: $evidence_id})
    MATCH (c)<-[:HA_CHUNK]-(i:Intervento)-[:PRONUNCIATO_DA]->(speaker)
    MATCH (i)<-[:CONTIENE_INTERVENTO]-(f:Fase)<-[:HA_FASE]-(d:Dibattito)<-[:HA_DIBATTITO]-(s:Seduta)
    OPTIONAL MATCH (speaker)-[:MEMBRO_GRUPPO]->(g:GruppoParlamentare)
    WHERE g IS NULL OR (
        (speaker)-[:MEMBRO_GRUPPO {dataFine: null}]->(g) OR
        NOT EXISTS { MATCH (speaker)-[:MEMBRO_GRUPPO {dataFine: null}]->(:GruppoParlamentare) }
    )
    WITH c, i, speaker, d, s, g
    ORDER BY CASE WHEN g IS NOT NULL THEN 0 ELSE 1 END
    LIMIT 1

    RETURN c.id AS chunk_id,
           c.testo AS chunk_text,
           c.start_char_raw AS span_start,
           c.end_char_raw AS span_end,
           i.id AS speech_id,
           i.testo_raw AS testo_raw,
           speaker.id AS speaker_id,
           speaker.nome AS nome,
           speaker.cognome AS cognome,
           labels(speaker)[0] AS speaker_role,
           g.nome AS party,
           s.id AS doc_id,
           s.data AS date,
           s.numero AS seduta_numero,
           d.titolo AS dibattito_titolo
    """

    with client.session() as session:
        result = session.run(cypher, evidence_id=evidence_id)
        record = result.single()

        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Evidence {evidence_id} not found"
            )

        data = dict(record)

        # Extract exact quote using offsets
        testo_raw = data.get("testo_raw", "")
        span_start = data.get("span_start", 0)
        span_end = data.get("span_end", 0)

        try:
            quote_text = compute_quote_text(testo_raw, span_start, span_end)
            citation_verified = verify_citation_integrity(
                quote_text, testo_raw, span_start, span_end
            )
        except ValueError as e:
            logger.error(f"Quote extraction failed for {evidence_id}: {e}")
            quote_text = data.get("chunk_text", "")[:200]  # Fallback to chunk preview
            citation_verified = False

        # Determine coalition
        from ..services.authority.coalition_logic import CoalitionLogic
        coalition_logic = CoalitionLogic()
        party = data.get("party") or "MISTO"
        coalition = coalition_logic.get_coalition(party)

        # Build speaker name
        nome = data.get("nome", "")
        cognome = data.get("cognome", "")
        speaker_name = f"{nome} {cognome}".strip() or "Unknown"

        return EvidenceResponse(
            evidence_id=evidence_id,
            chunk_id=data.get("chunk_id", evidence_id),
            speech_id=data.get("speech_id", ""),
            doc_id=data.get("doc_id", ""),
            speaker_id=data.get("speaker_id", ""),
            speaker_name=speaker_name,
            speaker_role=data.get("speaker_role", "Deputato"),
            party=party,
            coalition=coalition,
            chunk_text=data.get("chunk_text", ""),
            quote_text=quote_text,
            testo_raw=testo_raw if len(testo_raw) < 10000 else None,  # Omit if too large
            span_start=span_start,
            span_end=span_end,
            date=str(data.get("date", "")),
            dibattito_titolo=data.get("dibattito_titolo"),
            seduta_numero=data.get("seduta_numero", 0),
            citation_verified=citation_verified,
        )


@router.get("/{evidence_id}/verify")
async def verify_evidence(
    evidence_id: str = Path(..., description="Evidence/Chunk ID")
):
    """
    Verify citation integrity for an evidence piece.

    Returns verification status and details.
    """
    client = get_neo4j()

    cypher = """
    MATCH (c:Chunk {id: $evidence_id})
    MATCH (c)<-[:HA_CHUNK]-(i:Intervento)
    RETURN c.testo AS chunk_text,
           c.start_char_raw AS span_start,
           c.end_char_raw AS span_end,
           i.testo_raw AS testo_raw
    """

    with client.session() as session:
        result = session.run(cypher, evidence_id=evidence_id)
        record = result.single()

        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Evidence {evidence_id} not found"
            )

        data = dict(record)
        testo_raw = data.get("testo_raw", "")
        span_start = data.get("span_start", 0)
        span_end = data.get("span_end", 0)

        # Verify
        try:
            quote_text = compute_quote_text(testo_raw, span_start, span_end)
            is_valid = True
            error = None
        except ValueError as e:
            quote_text = None
            is_valid = False
            error = str(e)

        return {
            "evidence_id": evidence_id,
            "is_valid": is_valid,
            "span_start": span_start,
            "span_end": span_end,
            "testo_raw_length": len(testo_raw),
            "quote_text": quote_text,
            "quote_length": len(quote_text) if quote_text else 0,
            "error": error,
        }
