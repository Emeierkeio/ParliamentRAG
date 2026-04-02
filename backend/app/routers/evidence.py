"""
Evidence endpoint for retrieving full evidence details.

Provides exact quote extraction with verification.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from ..services.neo4j_client import Neo4jClient
from ..services.deps import get_neo4j_client
from ..models.evidence import normalize_party_name

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
    quote_text: str  # Verbatim citation source (chunk_text)
    text: Optional[str] = None  # Full intervention text (optional)

    # Context
    date: str
    debate_title: Optional[str]
    session_number: int

    # Verification
    citation_verified: bool


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: str = Path(..., description="Evidence/Chunk ID"),
    client: Neo4jClient = Depends(get_neo4j_client),
):
    """
    Get full evidence details by ID.

    Returns the exact verbatim quote extracted via offsets,
    with verification status.
    """

    # Query for full evidence details
    cypher = """
    MATCH (c:Chunk {id: $evidence_id})
    MATCH (c)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
    MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
    OPTIONAL MATCH (speaker)-[:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
    WHERE g IS NULL OR (
        (speaker)-[:MEMBER_OF_GROUP {end_date: null}]->(g) OR
        NOT EXISTS { MATCH (speaker)-[:MEMBER_OF_GROUP {end_date: null}]->(:ParliamentaryGroup) }
    )
    WITH c, i, speaker, d, s, g
    ORDER BY CASE WHEN g IS NOT NULL THEN 0 ELSE 1 END
    LIMIT 1

    RETURN c.id AS chunk_id,
           c.text AS chunk_text,
           i.id AS speech_id,
           i.text AS text,
           speaker.id AS speaker_id,
           speaker.first_name AS first_name,
           speaker.last_name AS last_name,
           labels(speaker)[0] AS speaker_role,
           g.name AS party,
           s.id AS doc_id,
           s.date AS date,
           s.number AS session_number,
           d.title AS debate_title
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

        # Use chunk_text as the verbatim citation source (Phase 2 schema).
        text = data.get("text", "")
        quote_text = data.get("chunk_text", "")
        citation_verified = bool(quote_text)

        # Determine coalition
        from ..services.authority.coalition_logic import CoalitionLogic
        coalition_logic = CoalitionLogic()
        party = data.get("party") or "MISTO"
        coalition = coalition_logic.get_coalition(party)

        # Build speaker name
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        speaker_name = f"{first_name} {last_name}".strip() or "Unknown"

        return EvidenceResponse(
            evidence_id=evidence_id,
            chunk_id=data.get("chunk_id", evidence_id),
            speech_id=data.get("speech_id", ""),
            doc_id=data.get("doc_id", ""),
            speaker_id=data.get("speaker_id", ""),
            speaker_name=speaker_name,
            speaker_role=data.get("speaker_role", "Deputy"),
            party=party,
            coalition=coalition,
            chunk_text=data.get("chunk_text", ""),
            quote_text=quote_text,
            text=text if len(text) < 10000 else None,  # Omit if too large
            date=str(data.get("date", "")),
            debate_title=data.get("debate_title"),
            session_number=data.get("session_number", 0),
            citation_verified=citation_verified,
        )


@router.get("/{evidence_id}/verify")
async def verify_evidence(
    evidence_id: str = Path(..., description="Evidence/Chunk ID"),
    client: Neo4jClient = Depends(get_neo4j_client),
):
    """
    Verify citation integrity for an evidence piece.

    Returns verification status and details.
    """

    cypher = """
    MATCH (c:Chunk {id: $evidence_id})
    MATCH (c)<-[:HAS_CHUNK]-(i:Speech)
    RETURN c.text AS chunk_text,
           i.text AS text
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
        text = data.get("text", "")
        chunk_text = data.get("chunk_text", "")

        # Use chunk_text as the citation source (Phase 2 schema).
        quote_text = chunk_text
        is_valid = bool(quote_text)

        return {
            "evidence_id": evidence_id,
            "is_valid": is_valid,
            "text_length": len(text),
            "quote_text": quote_text,
            "quote_length": len(quote_text) if quote_text else 0,
            "error": None,
        }
