"""
Search endpoint for parliamentary records.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import date

from fastapi import APIRouter, Query, HTTPException

from ..services.neo4j_client import Neo4jClient
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["Search"])

# Global client instance
_neo4j_client: Optional[Neo4jClient] = None


def get_client() -> Neo4jClient:
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


@router.get("/results")
async def search_results(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    deputy_id: Optional[str] = Query(None, description="Filter by deputy ID"),
    group: Optional[str] = Query(None, description="Filter by parliamentary group"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> List[Dict[str, Any]]:
    """
    Search parliamentary records.

    Searches through Chunk texts and returns matching records with metadata.
    """
    client = get_client()

    try:
        # Build the Cypher query with filters
        where_clauses = ["c.text CONTAINS $search_text"]
        params: Dict[str, Any] = {"search_text": q, "limit": limit}

        if deputy_id:
            where_clauses.append("d.id = $deputy_id")
            params["deputy_id"] = deputy_id

        if group:
            where_clauses.append("g.name = $group")
            params["group"] = group

        if start_date:
            where_clauses.append("s.date >= date($start_date)")
            params["start_date"] = start_date

        if end_date:
            where_clauses.append("s.date <= date($end_date)")
            params["end_date"] = end_date

        where_clause = " AND ".join(where_clauses)

        cypher = f"""
        MATCH (c:Chunk)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(d:Deputy)
        MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(dib:Debate)<-[:HAS_DEBATE]-(s:Session)
        OPTIONAL MATCH (d)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
        WITH c, i, d, s, dib, g
        WHERE {where_clause}
        RETURN c.id AS chunk_id,
               c.text AS text,
               i.id AS speech_id,
               toString(s.date) AS date,
               s.number AS session_number,
               dib.title AS debate_title,
               d.first_name AS first_name,
               d.last_name AS last_name,
               g.name AS group_name
        ORDER BY s.date DESC
        LIMIT $limit
        """

        with client.session() as session:
            result = session.run(cypher, **params)
            records = []
            for record in result:
                records.append({
                    "chunk_id": record["chunk_id"],
                    "text": record["text"][:500] if record["text"] else "",
                    "speech_id": record["speech_id"],
                    "date": record["date"],
                    "session_number": record["session_number"],
                    "debate_title": record["debate_title"] or "",
                    "first_name": record["first_name"] or "",
                    "last_name": record["last_name"] or "",
                    "group": record["group_name"] or "MISTO",
                })

            logger.info(f"Search for '{q}' returned {len(records)} results")
            return records

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deputies")
async def list_deputies(
    q: Optional[str] = Query(None, description="Filter by name"),
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """
    List deputies, optionally filtered by name.
    """
    client = get_client()

    try:
        if q:
            cypher = """
            MATCH (d:Deputy)
            WHERE toLower(d.first_name) CONTAINS toLower($search_text)
               OR toLower(d.last_name) CONTAINS toLower($search_text)
            RETURN d.id AS id,
                   d.first_name AS first_name,
                   d.last_name AS last_name
            ORDER BY d.last_name, d.first_name
            LIMIT $limit
            """
            params = {"search_text": q, "limit": limit}
        else:
            cypher = """
            MATCH (d:Deputy)
            RETURN d.id AS id,
                   d.first_name AS first_name,
                   d.last_name AS last_name
            ORDER BY d.last_name, d.first_name
            LIMIT $limit
            """
            params = {"limit": limit}

        with client.session() as session:
            result = session.run(cypher, **params)
            return [
                {
                    "id": record["id"],
                    "first_name": record["first_name"],
                    "last_name": record["last_name"],
                }
                for record in result
            ]

    except Exception as e:
        logger.error(f"List deputies failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups")
async def list_groups() -> List[Dict[str, Any]]:
    """
    List all parliamentary groups.
    """
    client = get_client()

    try:
        cypher = """
        MATCH (g:ParliamentaryGroup)
        OPTIONAL MATCH (d:Deputy)-[:MEMBER_OF_GROUP]->(g)
        WITH g, count(d) AS member_count
        RETURN g.name AS name,
               g.acronym AS acronym,
               member_count
        ORDER BY member_count DESC
        """

        with client.session() as session:
            result = session.run(cypher)
            return [
                {
                    "name": record["name"],
                    "acronym": record["acronym"],
                    "member_count": record["member_count"],
                }
                for record in result
            ]

    except Exception as e:
        logger.error(f"List groups failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
