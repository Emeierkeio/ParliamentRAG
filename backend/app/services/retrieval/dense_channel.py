"""
Dense retrieval channel using vector similarity search.

This channel performs semantic search on pre-computed chunk embeddings
using Neo4j's native vector index.

CRITICAL: Uses correct Neo4j vector query syntax.
NO MATCH clause before db.index.vector.queryNodes.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..neo4j_client import Neo4jClient
from ...models.evidence import UnifiedEvidence, compute_quote_text, normalize_speaker_name, normalize_party_name
from ...config import get_config

logger = logging.getLogger(__name__)


class DenseChannel:
    """
    Dense retrieval channel using vector similarity search.

    Performs semantic search on Chunk.embedding using Neo4j vector index.
    """

    def __init__(self, neo4j_client: Neo4jClient):
        """
        Initialize the dense retrieval channel.

        Args:
            neo4j_client: Neo4j database client
        """
        self.client = neo4j_client
        self.config = get_config()

    def retrieve(
        self,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.

        CRITICAL: Uses correct Neo4j syntax - NO MATCH before vector query.

        Args:
            query_embedding: Query embedding vector (1536 dimensions)
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score

        Returns:
            List of evidence candidates with metadata
        """
        retrieval_config = self.config.retrieval.get("dense_channel", {})
        top_k = top_k or retrieval_config.get("top_k", 200)
        threshold = similarity_threshold or retrieval_config.get("similarity_threshold", 0.3)
        index_name = retrieval_config.get("index_name", "chunk_embedding_index")

        logger.info(f"Dense channel: retrieving top {top_k} chunks (threshold={threshold})")

        # CORRECT Neo4j vector search syntax
        # NO MATCH clause before db.index.vector.queryNodes
        cypher = """
        CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
        YIELD node AS c, score
        WHERE score >= $threshold
        MATCH (c)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
        MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
        OPTIONAL MATCH (speaker)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
        AND (mg.end_date IS NULL OR mg.end_date >= date())
        RETURN c.id AS chunk_id,
               c.text AS chunk_text,
               c.embedding AS embedding,
               c.start_char_raw AS span_start,
               c.end_char_raw AS span_end,
               c.index AS chunk_index,
               i.id AS speech_id,
               i.text AS text,
               speaker.id AS speaker_id,
               speaker.first_name AS speaker_first_name,
               speaker.last_name AS speaker_last_name,
               CASE WHEN 'GovernmentMember' IN labels(speaker) THEN 'GovernmentMember' ELSE 'Deputy' END AS speaker_type,
               g.name AS party,
               s.id AS session_id,
               s.date AS session_date,
               s.number AS session_number,
               d.title AS debate_title,
               score AS similarity
        ORDER BY score DESC
        """

        results = self.client.query(
            cypher,
            {
                "index_name": index_name,
                "top_k": top_k,
                "query_embedding": query_embedding,
                "threshold": threshold
            }
        )

        logger.info(f"Dense channel: retrieved {len(results)} chunks")
        return self._process_results(results)

    def _process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process raw query results into structured evidence candidates.

        Computes quote_text from text using offsets.
        """
        processed = []
        config = get_config()

        for row in results:
            try:
                # Extract quote using offsets - CRITICAL for citation integrity
                text = row.get("text", "")
                span_start = row.get("span_start", 0)
                span_end = row.get("span_end", 0)

                if text and span_start is not None and span_end is not None and span_start < span_end:
                    quote_text = compute_quote_text(text, span_start, span_end)
                else:
                    # Fallback to chunk_text if offsets unavailable or invalid
                    quote_text = row.get("chunk_text", "") or text
                    if not quote_text:
                        logger.warning(f"Missing text for chunk {row.get('chunk_id')}")

                # Determine coalition
                # If party is NULL the speaker's current group doesn't cover
                # this session date (e.g. they switched group after the debate).
                # Skip the result — the deputy should only be cited for speeches
                # made while in their current group.
                party = row.get("party")
                speaker_role = row.get("speaker_type", "Deputy")
                if party is None and speaker_role != "GovernmentMember":
                    logger.debug(
                        f"Skipping chunk {row.get('chunk_id')}: speaker "
                        f"{row.get('speaker_last_name')} has no current group "
                        f"covering session date {row.get('session_date')}"
                    )
                    continue
                party = party or "GOVERNO"
                coalition = config.get_coalition(party) if party else "opposizione"

                # Parse date - handles both Neo4j Date objects and string formats
                session_date = row.get("session_date")
                if session_date is not None:
                    if hasattr(session_date, 'to_native'):
                        # Neo4j Date object
                        date_obj = session_date.to_native()
                    elif isinstance(session_date, str) and session_date:
                        try:
                            # Handle DD/MM/YYYY format (legacy)
                            date_obj = datetime.strptime(session_date, "%d/%m/%Y").date()
                        except ValueError:
                            date_obj = datetime.now().date()
                    else:
                        date_obj = datetime.now().date()
                else:
                    date_obj = datetime.now().date()

                processed.append({
                    "evidence_id": row.get("chunk_id", ""),
                    "doc_id": row.get("session_id", ""),
                    "speech_id": row.get("speech_id", ""),
                    "speaker_id": row.get("speaker_id", ""),
                    "speaker_name": normalize_speaker_name(row.get('speaker_first_name', ''), row.get('speaker_last_name', '')),
                    "speaker_role": row.get("speaker_type", "Deputy"),
                    "party": normalize_party_name(party),
                    "coalition": coalition,
                    "date": date_obj,
                    "chunk_text": row.get("chunk_text", ""),
                    "quote_text": quote_text,
                    "span_start": span_start or 0,
                    "span_end": span_end or 0,
                    "debate_title": row.get("debate_title"),
                    "session_number": row.get("session_number", 0),
                    "similarity": row.get("similarity", 0.0),
                    "embedding": row.get("embedding"),  # For compass PCA
                    "retrieval_channel": "dense"
                })
            except Exception as e:
                logger.error(f"Error processing result: {e}")
                continue

        return processed
