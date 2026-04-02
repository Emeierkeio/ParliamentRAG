"""
Data endpoints for Phase 1 schema nodes.

Exposes Vote nodes (Session -[:HAS_VOTE]-> Vote) and parliamentary act links
(Debate -[:DISCUSSES]-> ParliamentaryAct) that were added during Phase 1 but
had no API surface until now.
"""
from typing import Any

from fastapi import APIRouter, Depends

from app.services.deps import get_neo4j_client
from app.services.neo4j_client import Neo4jClient

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/sessions/{session_id}/votes")
async def get_session_votes(
    session_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> list[dict[str, Any]]:
    """Get all votes for a session."""
    cypher = """
    MATCH (s:Session {id: $session_id})-[:HAS_VOTE]->(v:Vote)
    RETURN v.id AS id,
           v.number AS number,
           v.type AS type,
           v.subject AS subject,
           v.inFavor AS in_favor,
           v.against AS against,
           v.abstained AS abstained,
           v.outcome AS outcome,
           v.present AS present,
           v.voters AS voters,
           v.majority AS majority,
           v.onMission AS on_mission
    ORDER BY v.number
    """
    return neo4j.query(cypher, {"session_id": session_id})


@router.get("/debates/{debate_id}/acts")
async def get_debate_acts(
    debate_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> list[dict[str, Any]]:
    """Get all parliamentary acts discussed in a debate."""
    cypher = """
    MATCH (d:Debate {id: $debate_id})-[:DISCUSSES]->(a:ParliamentaryAct)
    RETURN a.id AS id,
           a.title AS title,
           a.isPlaceholder AS is_placeholder
    ORDER BY a.title
    """
    return neo4j.query(cypher, {"debate_id": debate_id})
