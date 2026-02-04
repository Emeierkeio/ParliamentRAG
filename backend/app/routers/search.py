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
        where_clauses = ["c.testo CONTAINS $search_text"]
        params: Dict[str, Any] = {"search_text": q, "limit": limit}

        if deputy_id:
            where_clauses.append("d.id = $deputy_id")
            params["deputy_id"] = deputy_id

        if group:
            where_clauses.append("mg.nome_gruppo = $group")
            params["group"] = group

        if start_date:
            where_clauses.append("s.data >= date($start_date)")
            params["start_date"] = start_date

        if end_date:
            where_clauses.append("s.data <= date($end_date)")
            params["end_date"] = end_date

        where_clause = " AND ".join(where_clauses)

        cypher = f"""
        MATCH (c:Chunk)<-[:HA_CHUNK]-(i:Intervento)-[:PRONUNCIATO_DA]->(d:Deputato)
        MATCH (i)<-[:CONTIENE_INTERVENTO]-(f:Fase)<-[:HA_FASE]-(dib:Dibattito)<-[:HA_DIBATTITO]-(s:Seduta)
        OPTIONAL MATCH (d)-[mg:MEMBRO_GRUPPO]->(g:GruppoParlamentare)
        WHERE mg.dataInizio <= s.data AND (mg.dataFine IS NULL OR mg.dataFine >= s.data)
        WITH c, i, d, s, dib, mg
        WHERE {where_clause}
        RETURN c.id AS chunk_id,
               c.testo AS testo,
               i.id AS intervento_id,
               toString(s.data) AS data,
               s.numero AS seduta_numero,
               dib.titolo AS dibattito_titolo,
               d.nome AS nome,
               d.cognome AS cognome,
               mg.nome_gruppo AS gruppo
        ORDER BY s.data DESC
        LIMIT $limit
        """

        with client.session() as session:
            result = session.run(cypher, **params)
            records = []
            for record in result:
                records.append({
                    "chunk_id": record["chunk_id"],
                    "testo": record["testo"][:500] if record["testo"] else "",
                    "intervento_id": record["intervento_id"],
                    "data": record["data"],
                    "seduta_numero": record["seduta_numero"],
                    "dibattito_titolo": record["dibattito_titolo"] or "",
                    "nome": record["nome"] or "",
                    "cognome": record["cognome"] or "",
                    "gruppo": record["gruppo"] or "MISTO",
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
            MATCH (d:Deputato)
            WHERE toLower(d.nome) CONTAINS toLower($search_text)
               OR toLower(d.cognome) CONTAINS toLower($search_text)
            RETURN d.id AS id,
                   d.nome AS nome,
                   d.cognome AS cognome
            ORDER BY d.cognome, d.nome
            LIMIT $limit
            """
            params = {"search_text": q, "limit": limit}
        else:
            cypher = """
            MATCH (d:Deputato)
            RETURN d.id AS id,
                   d.nome AS nome,
                   d.cognome AS cognome
            ORDER BY d.cognome, d.nome
            LIMIT $limit
            """
            params = {"limit": limit}

        with client.session() as session:
            result = session.run(cypher, **params)
            return [
                {
                    "id": record["id"],
                    "nome": record["nome"],
                    "cognome": record["cognome"],
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
        MATCH (g:GruppoParlamentare)
        OPTIONAL MATCH (d:Deputato)-[:MEMBRO_GRUPPO]->(g)
        WITH g, count(d) AS member_count
        RETURN g.nome AS nome,
               g.sigla AS sigla,
               member_count
        ORDER BY member_count DESC
        """

        with client.session() as session:
            result = session.run(cypher)
            return [
                {
                    "nome": record["nome"],
                    "sigla": record["sigla"],
                    "member_count": record["member_count"],
                }
                for record in result
            ]

    except Exception as e:
        logger.error(f"List groups failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
