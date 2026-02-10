"""
Search endpoint for parliamentary records.
Supports text search and semantic (vector) search across Speech chunks and ParliamentaryAct nodes.
"""
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Query, HTTPException

from ..services.neo4j_client import Neo4jClient
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["Search"])

# Global client instance
_neo4j_client: Optional[Neo4jClient] = None
_openai_client = None
_act_index_ensured = False


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


def _get_openai_client():
    """Get or initialize OpenAI client for embeddings."""
    global _openai_client
    if _openai_client is None:
        import openai
        settings = get_settings()
        _openai_client = openai.OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _generate_embedding(text: str) -> List[float]:
    """Generate embedding for a query using OpenAI."""
    client = _get_openai_client()
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


def _ensure_act_vector_index():
    """Create vector index on ParliamentaryAct.description_embedding if not exists."""
    global _act_index_ensured
    if _act_index_ensured:
        return
    client = get_client()
    try:
        with client.session() as session:
            session.run("""
                CREATE VECTOR INDEX act_description_embedding_index IF NOT EXISTS
                FOR (a:ParliamentaryAct) ON (a.description_embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
            """)
        _act_index_ensured = True
        logger.info("Ensured act_description_embedding_index exists")
    except Exception as e:
        logger.warning(f"Could not create act vector index: {e}")
        _act_index_ensured = True  # Don't retry on failure


def _search_speeches_text(
    client: Neo4jClient,
    q: str,
    limit: int,
    deputy_id: Optional[str] = None,
    group: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Text search on Speech chunks."""
    where_clauses = ["toLower(c.text) CONTAINS toLower($search_text)"]
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
    MATCH (c:Chunk)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(d)
    WHERE (d:Deputy OR d:GovernmentMember)
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
           CASE WHEN 'GovernmentMember' IN labels(d) THEN 'Governo' ELSE coalesce(g.name, 'MISTO') END AS group_name
    ORDER BY s.date DESC
    LIMIT $limit
    """

    with client.session() as session:
        result = session.run(cypher, **params)
        records = []
        for record in result:
            records.append({
                "type": "speech",
                "id": record["chunk_id"],
                "text": record["text"][:500] if record["text"] else "",
                "date": record["date"],
                "session_number": record["session_number"],
                "debate_title": record["debate_title"] or "",
                "first_name": record["first_name"] or "",
                "last_name": record["last_name"] or "",
                "group": record["group_name"] or "MISTO",
                "act_type": None,
                "act_title": None,
                "act_number": None,
                "destinatario": None,
                "eurovoc": None,
                "score": None,
                "match_type": "text",
            })
        return records


def _search_acts_text(
    client: Neo4jClient,
    q: str,
    limit: int,
    deputy_id: Optional[str] = None,
    group: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Text search on ParliamentaryAct title and description."""
    where_clauses = [
        "(toLower(a.titolo) CONTAINS toLower($search_text) OR toLower(a.descrizione) CONTAINS toLower($search_text))"
    ]
    params: Dict[str, Any] = {"search_text": q, "limit": limit}

    if deputy_id:
        where_clauses.append("d.id = $deputy_id")
        params["deputy_id"] = deputy_id

    if start_date:
        where_clauses.append("a.dataPresentazione >= $start_date_act")
        params["start_date_act"] = start_date.replace("-", "")
    if end_date:
        where_clauses.append("a.dataPresentazione <= $end_date_act")
        params["end_date_act"] = end_date.replace("-", "")

    where_clause = " AND ".join(where_clauses)

    # Group filter handled separately since it's on the signatory's group
    group_filter = ""
    if group:
        group_filter = "WHERE g.name = $group"
        params["group"] = group

    cypher = f"""
    MATCH (d)-[:PRIMARY_SIGNATORY]->(a:ParliamentaryAct)
    WHERE (d:Deputy OR d:GovernmentMember)
    AND {where_clause}
    OPTIONAL MATCH (d)-[:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
    {group_filter}
    RETURN a.uri AS act_uri,
           a.tipo AS act_type,
           a.titolo AS act_title,
           a.descrizione AS description,
           a.dataPresentazione AS date_raw,
           a.numero AS act_number,
           a.destinatario AS destinatario,
           a.eurovoc AS eurovoc,
           d.first_name AS first_name,
           d.last_name AS last_name,
           coalesce(g.name, 'MISTO') AS group_name
    ORDER BY a.dataPresentazione DESC
    LIMIT $limit
    """

    with client.session() as session:
        result = session.run(cypher, **params)
        records = []
        for record in result:
            # Format date from YYYYMMDD to YYYY-MM-DD
            date_raw = record["date_raw"] or ""
            formatted_date = ""
            if len(date_raw) == 8:
                formatted_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
            else:
                formatted_date = date_raw

            records.append({
                "type": "act",
                "id": record["act_uri"] or "",
                "text": (record["description"] or "")[:500],
                "date": formatted_date,
                "session_number": None,
                "debate_title": None,
                "first_name": record["first_name"] or "",
                "last_name": record["last_name"] or "",
                "group": record["group_name"] or "MISTO",
                "act_type": record["act_type"] or "",
                "act_title": record["act_title"] or "",
                "act_number": record["act_number"] or "",
                "destinatario": record["destinatario"] or "",
                "eurovoc": record["eurovoc"] or "",
                "score": None,
                "match_type": "text",
            })
        return records


def _search_speeches_semantic(
    client: Neo4jClient,
    embedding: List[float],
    limit: int,
    threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """Semantic search on Speech chunks using vector index."""
    cypher = """
    CALL db.index.vector.queryNodes('chunk_embedding_index', $top_k, $embedding)
    YIELD node AS c, score
    WHERE score >= $threshold
    MATCH (c)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(d)
    WHERE (d:Deputy OR d:GovernmentMember)
    MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(dib:Debate)<-[:HAS_DEBATE]-(s:Session)
    OPTIONAL MATCH (d)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
    WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
    RETURN c.id AS chunk_id,
           c.text AS text,
           i.id AS speech_id,
           toString(s.date) AS date,
           s.number AS session_number,
           dib.title AS debate_title,
           d.first_name AS first_name,
           d.last_name AS last_name,
           CASE WHEN 'GovernmentMember' IN labels(d) THEN 'Governo' ELSE coalesce(g.name, 'MISTO') END AS group_name,
           score
    ORDER BY score DESC
    LIMIT $limit
    """

    results = client.query(cypher, {
        "top_k": limit * 2,
        "embedding": embedding,
        "threshold": threshold,
        "limit": limit,
    })

    records = []
    for r in results:
        records.append({
            "type": "speech",
            "id": r["chunk_id"],
            "text": r["text"][:500] if r.get("text") else "",
            "date": r["date"],
            "session_number": r["session_number"],
            "debate_title": r["debate_title"] or "",
            "first_name": r["first_name"] or "",
            "last_name": r["last_name"] or "",
            "group": r["group_name"] or "MISTO",
            "act_type": None,
            "act_title": None,
            "act_number": None,
            "destinatario": None,
            "eurovoc": None,
            "score": round(r["score"], 4),
            "match_type": "semantic",
        })
    return records


def _search_acts_semantic(
    client: Neo4jClient,
    embedding: List[float],
    limit: int,
    threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """Semantic search on ParliamentaryAct using vector index."""
    _ensure_act_vector_index()

    cypher = """
    CALL db.index.vector.queryNodes('act_description_embedding_index', $top_k, $embedding)
    YIELD node AS a, score
    WHERE score >= $threshold
    OPTIONAL MATCH (d)-[:PRIMARY_SIGNATORY]->(a)
    WHERE (d:Deputy OR d:GovernmentMember)
    OPTIONAL MATCH (d)-[:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
    RETURN a.uri AS act_uri,
           a.tipo AS act_type,
           a.titolo AS act_title,
           a.descrizione AS description,
           a.dataPresentazione AS date_raw,
           a.numero AS act_number,
           a.destinatario AS destinatario,
           a.eurovoc AS eurovoc,
           d.first_name AS first_name,
           d.last_name AS last_name,
           coalesce(g.name, 'MISTO') AS group_name,
           score
    ORDER BY score DESC
    LIMIT $limit
    """

    results = client.query(cypher, {
        "top_k": limit * 2,
        "embedding": embedding,
        "threshold": threshold,
        "limit": limit,
    })

    records = []
    for r in results:
        date_raw = r.get("date_raw") or ""
        formatted_date = ""
        if len(date_raw) == 8:
            formatted_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        else:
            formatted_date = date_raw

        records.append({
            "type": "act",
            "id": r["act_uri"] or "",
            "text": (r.get("description") or "")[:500],
            "date": formatted_date,
            "session_number": None,
            "debate_title": None,
            "first_name": r.get("first_name") or "",
            "last_name": r.get("last_name") or "",
            "group": r.get("group_name") or "MISTO",
            "act_type": r.get("act_type") or "",
            "act_title": r.get("act_title") or "",
            "act_number": r.get("act_number") or "",
            "destinatario": r.get("destinatario") or "",
            "eurovoc": r.get("eurovoc") or "",
            "score": round(r["score"], 4),
            "match_type": "semantic",
        })
    return records


@router.get("/results")
async def search_results(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    deputy_id: Optional[str] = Query(None, description="Filter by deputy ID"),
    group: Optional[str] = Query(None, description="Filter by parliamentary group"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    search_type: str = Query("text", description="Search type: text, semantic, hybrid"),
) -> List[Dict[str, Any]]:
    """
    Search parliamentary records (Speech chunks + ParliamentaryAct).

    - text: exact text matching
    - semantic: vector similarity search
    - hybrid: both text and semantic combined
    """
    client = get_client()
    all_results: List[Dict[str, Any]] = []

    try:
        half_limit = max(limit // 2, 20)

        # Text search
        if search_type in ("text", "hybrid"):
            speech_text = _search_speeches_text(client, q, half_limit, deputy_id, group, start_date, end_date)
            act_text = _search_acts_text(client, q, half_limit, deputy_id, group, start_date, end_date)
            all_results.extend(speech_text)
            all_results.extend(act_text)

        # Semantic search
        if search_type in ("semantic", "hybrid"):
            try:
                embedding = _generate_embedding(q)
                speech_sem = _search_speeches_semantic(client, embedding, half_limit)
                act_sem = _search_acts_semantic(client, embedding, half_limit)
                all_results.extend(speech_sem)
                all_results.extend(act_sem)
            except Exception as e:
                logger.error(f"Semantic search failed: {e}")
                # Fall back to text-only if semantic fails
                if search_type == "semantic":
                    speech_text = _search_speeches_text(client, q, half_limit, deputy_id, group, start_date, end_date)
                    act_text = _search_acts_text(client, q, half_limit, deputy_id, group, start_date, end_date)
                    all_results.extend(speech_text)
                    all_results.extend(act_text)

        # Deduplicate by id
        seen = set()
        unique_results = []
        for r in all_results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique_results.append(r)

        # Sort: semantic results first (by score desc), then text results (by date desc)
        def sort_key(r):
            if r["score"] is not None:
                return (0, -r["score"])
            return (1, r.get("date") or "")

        unique_results.sort(key=sort_key)

        # Limit
        unique_results = unique_results[:limit]

        logger.info(f"Search '{q}' (type={search_type}): {len(unique_results)} results")
        return unique_results

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
