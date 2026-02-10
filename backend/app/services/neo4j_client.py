"""
Neo4j database client for the Multi-View RAG system.

Provides async-compatible database access with connection pooling.
"""
import logging
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


class Neo4jClient:
    """
    Neo4j database client with connection pooling.

    This client provides methods for querying the parliamentary database
    including vector search, graph traversal, and temporal queries.
    """

    _instance: Optional["Neo4jClient"] = None

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize the Neo4j client.

        Args:
            uri: Neo4j bolt URI (e.g., bolt://localhost:7689)
            user: Database username
            password: Database password
        """
        self.uri = uri
        self.user = user
        self._driver: Optional[Driver] = None

        try:
            self._driver = GraphDatabase.driver(
                uri,
                auth=(user, password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60.0,
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {uri}")
        except AuthError:
            logger.error(f"Authentication failed for Neo4j at {uri}")
            raise
        except ServiceUnavailable:
            logger.error(f"Neo4j service unavailable at {uri}")
            raise

    @classmethod
    def get_instance(
        cls,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ) -> "Neo4jClient":
        """Get or create the singleton instance."""
        if cls._instance is None:
            if uri is None or user is None or password is None:
                raise ValueError(
                    "Must provide uri, user, and password on first call"
                )
            cls._instance = cls(uri, user, password)
        return cls._instance

    @contextmanager
    def session(self, database: str = "neo4j"):
        """
        Context manager for database sessions.

        Usage:
            with client.session() as session:
                result = session.run("MATCH (n) RETURN n LIMIT 10")
        """
        session = self._driver.session(database=database)
        try:
            yield session
        finally:
            session.close()

    def query(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: str = "neo4j"
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results as a list of dicts.

        Args:
            cypher: Cypher query string
            parameters: Query parameters
            database: Database name

        Returns:
            List of result records as dictionaries
        """
        with self.session(database) as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    def query_single(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: str = "neo4j"
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a query expecting a single result.

        Args:
            cypher: Cypher query string
            parameters: Query parameters
            database: Database name

        Returns:
            Single result record or None
        """
        with self.session(database) as session:
            result = session.run(cypher, parameters or {})
            record = result.single()
            return record.data() if record else None

    def vector_search(
        self,
        index_name: str,
        query_embedding: List[float],
        top_k: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search on an index.

        CRITICAL: Uses correct Neo4j vector query syntax.
        NO MATCH clause before db.index.vector.queryNodes.

        Args:
            index_name: Name of the vector index
            query_embedding: Query embedding vector
            top_k: Number of results to return

        Returns:
            List of matched nodes with scores
        """
        # CORRECT: Direct vector query, then MATCH for related data
        cypher = """
        CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
        YIELD node AS c, score
        MATCH (c)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
        MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
        RETURN c.id AS chunk_id,
               COALESCE(c.text, c.testo) AS chunk_text,
               c.start_char_raw AS span_start,
               c.end_char_raw AS span_end,
               c.index AS chunk_index,
               i.id AS speech_id,
               i.text AS text,
               speaker.id AS speaker_id,
               speaker.first_name AS speaker_first_name,
               speaker.last_name AS speaker_last_name,
               labels(speaker)[0] AS speaker_type,
               s.id AS session_id,
               s.date AS session_date,
               s.number AS session_number,
               d.title AS debate_title,
               score
        ORDER BY score DESC
        """
        return self.query(
            cypher,
            {
                "index_name": index_name,
                "top_k": top_k,
                "query_embedding": query_embedding
            }
        )

    def get_speaker_group_at_date(
        self,
        speaker_id: str,
        target_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the parliamentary group of a speaker at a specific date.

        Args:
            speaker_id: Speaker identifier
            target_date: Date in DD/MM/YYYY format

        Returns:
            Group information or None
        """
        cypher = """
        MATCH (speaker)-[r:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WHERE speaker.id = $speaker_id
          AND r.start_date <= $target_date
          AND (r.end_date IS NULL OR r.end_date >= $target_date)
        RETURN g.name AS group,
               r.start_date AS start_date,
               r.end_date AS end_date
        LIMIT 1
        """
        return self.query_single(
            cypher,
            {"speaker_id": speaker_id, "target_date": target_date}
        )

    def get_speaker_group_history(
        self,
        speaker_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get the complete group membership history for a speaker.

        Used for coalition crossing detection in authority scoring.

        Args:
            speaker_id: Speaker identifier

        Returns:
            List of group memberships with dates
        """
        cypher = """
        MATCH (speaker)-[r:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WHERE speaker.id = $speaker_id
        RETURN g.name AS group,
               r.start_date AS start_date,
               r.end_date AS end_date
        ORDER BY r.start_date
        """
        return self.query(cypher, {"speaker_id": speaker_id})

    def get_speaker_interventions_count(
        self,
        speaker_id: str,
        keywords: Optional[List[str]] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None
    ) -> int:
        """
        Count interventions by a speaker, optionally filtered by topic.

        Args:
            speaker_id: Speaker identifier
            keywords: Optional topic keywords to filter
            date_start: Optional start date filter
            date_end: Optional end date filter

        Returns:
            Count of matching interventions
        """
        conditions = ["speaker.id = $speaker_id"]
        params: Dict[str, Any] = {"speaker_id": speaker_id}

        if keywords:
            keyword_conditions = " OR ".join(
                f"toLower(i.text) CONTAINS toLower($kw{i})"
                for i in range(len(keywords))
            )
            conditions.append(f"({keyword_conditions})")
            for i, kw in enumerate(keywords):
                params[f"kw{i}"] = kw

        if date_start:
            conditions.append("s.date >= $date_start")
            params["date_start"] = date_start

        if date_end:
            conditions.append("s.date <= $date_end")
            params["date_end"] = date_end

        where_clause = " AND ".join(conditions)

        cypher = f"""
        MATCH (i:Speech)-[:SPOKEN_BY]->(speaker)
        MATCH (i)<-[:CONTAINS_SPEECH]-()<-[:HAS_PHASE]-()<-[:HAS_DEBATE]-(s:Session)
        WHERE {where_clause}
        RETURN count(i) AS count
        """
        result = self.query_single(cypher, params)
        return result["count"] if result else 0

    def get_speaker_acts_count(
        self,
        speaker_id: str,
        keywords: Optional[List[str]] = None
    ) -> int:
        """
        Count parliamentary acts filed by a speaker.

        Args:
            speaker_id: Speaker identifier
            keywords: Optional topic keywords to filter

        Returns:
            Count of matching acts
        """
        conditions = ["speaker.id = $speaker_id"]
        params: Dict[str, Any] = {"speaker_id": speaker_id}

        if keywords:
            keyword_conditions = " OR ".join(
                f"toLower(a.title) CONTAINS toLower($kw{i}) OR "
                f"toLower(a.description) CONTAINS toLower($kw{i}) OR "
                f"toLower(a.eurovoc) CONTAINS toLower($kw{i})"
                for i in range(len(keywords))
            )
            conditions.append(f"({keyword_conditions})")
            for i, kw in enumerate(keywords):
                params[f"kw{i}"] = kw

        where_clause = " AND ".join(conditions)

        cypher = f"""
        MATCH (speaker)-[:PRIMARY_SIGNATORY|CO_SIGNATORY]->(a:ParliamentaryAct)
        WHERE {where_clause}
        RETURN count(DISTINCT a) AS count
        """
        result = self.query_single(cypher, params)
        return result["count"] if result else 0

    def verify_connectivity(self):
        """Verify database connectivity."""
        if self._driver:
            self._driver.verify_connectivity()

    def close(self):
        """Close the database connection."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed")


# Global client instance
_client: Optional[Neo4jClient] = None


def get_neo4j_client() -> Neo4jClient:
    """Get the global Neo4j client instance."""
    global _client
    if _client is None:
        raise RuntimeError(
            "Neo4j client not initialized. Call init_neo4j_client first."
        )
    return _client


def init_neo4j_client(uri: str, user: str, password: str) -> Neo4jClient:
    """Initialize the global Neo4j client."""
    global _client
    _client = Neo4jClient(uri, user, password)
    return _client
