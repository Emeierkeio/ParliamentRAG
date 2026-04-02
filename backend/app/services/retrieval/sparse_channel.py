"""
Sparse retrieval channel using Neo4j full-text index (BM25).

This channel performs keyword-based search on Chunk.text using the
Lucene full-text index with an Italian analyzer (or standard fallback).

Key design choices:
- similarity is set to 0.5 (neutral sentinel) for all results;
  the raw BM25 score is preserved in bm25_score for diagnostics.
- Rank position (not raw BM25 score) is used by the RRF merger.
- If the full-text index does not exist, returns [] gracefully.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..neo4j_client import Neo4jClient
from ...models.evidence import normalize_speaker_name, normalize_party_name
from ...config import get_config

logger = logging.getLogger(__name__)


class SparseChannel:
    """
    Sparse retrieval channel using Neo4j full-text index (BM25 via Lucene).

    Queries the chunk_fulltext index and returns evidence dicts in the
    same format as DenseChannel, so the RRF merger can treat all channels
    uniformly.
    """

    def __init__(self, neo4j_client: Neo4jClient):
        """
        Initialize the sparse retrieval channel.

        Args:
            neo4j_client: Neo4j database client
        """
        self.client = neo4j_client
        self.config = get_config()

    def retrieve(
        self,
        query_text: str,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25 full-text search via Neo4j Lucene index.

        Args:
            query_text: Raw query string (keywords)
            top_k: Number of results to return

        Returns:
            List of evidence candidates with metadata.
            Returns [] if index does not exist or query fails.
        """
        retrieval_config = self.config.retrieval.get("sparse_channel", {})
        top_k = top_k or retrieval_config.get("top_k", 100)
        index_name = retrieval_config.get("index_name", "chunk_fulltext")

        logger.info(f"Sparse channel: querying '{query_text[:50]}...' top_k={top_k}")

        # Escape Lucene special characters to avoid syntax errors
        escaped_query = self._escape_lucene(query_text)

        cypher = """
        CALL db.index.fulltext.queryNodes($index_name, $query_text)
        YIELD node AS c, score
        WITH c, score
        LIMIT $top_k
        MATCH (c)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
        MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
        OPTIONAL MATCH (speaker)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= date())
        OPTIONAL MATCH (speaker)-[mg_now:MEMBER_OF_GROUP]->(g_now:ParliamentaryGroup)
        WHERE mg_now.end_date IS NULL
        RETURN c.id AS chunk_id,
               c.text AS chunk_text,
               score AS bm25_score,
               i.id AS speech_id,
               i.text AS text,
               speaker.id AS speaker_id,
               speaker.first_name AS speaker_first_name,
               speaker.last_name AS speaker_last_name,
               CASE WHEN 'GovernmentMember' IN labels(speaker) THEN 'GovernmentMember' ELSE 'Deputy' END AS speaker_type,
               g.name AS party,
               g_now.name AS current_party,
               s.id AS session_id,
               s.date AS session_date,
               s.number AS session_number,
               d.title AS debate_title
        ORDER BY bm25_score DESC
        """

        try:
            results = self.client.query(
                cypher,
                {
                    "index_name": index_name,
                    "query_text": escaped_query,
                    "top_k": top_k,
                }
            )
            logger.info(f"Sparse channel: retrieved {len(results)} chunks")
            return self._process_results(results)

        except Exception as e:
            # Graceful degradation: index may not exist yet (first build,
            # or running against a DB without the full-text index)
            logger.warning(
                f"Sparse channel: query failed (index may not exist): {e}. "
                "Returning empty list."
            )
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert raw Neo4j records to structured evidence dicts.

        Sets similarity=0.5 (neutral — rank position drives RRF, not raw score).
        Preserves bm25_score for diagnostics.
        """
        processed = []
        config = get_config()

        for row in results:
            try:
                party = row.get("party")
                current_party_raw = row.get("current_party")
                speaker_role = row.get("speaker_type", "Deputy")

                if party is None and speaker_role != "GovernmentMember":
                    logger.debug(
                        f"Skipping chunk {row.get('chunk_id')}: no historical group "
                        f"for speaker {row.get('speaker_last_name')} at {row.get('session_date')}"
                    )
                    continue

                if speaker_role == "GovernmentMember":
                    party = party or "GOVERNO"
                    coalition = "governo"
                    party_changed = False
                    current_party_display = None
                else:
                    coalition = config.get_coalition(party) if party else "opposizione"
                    historical_display = normalize_party_name(party)
                    current_party_display = (
                        normalize_party_name(current_party_raw)
                        if current_party_raw else None
                    )
                    party_changed = bool(
                        current_party_display and current_party_display != historical_display
                    )

                # Parse session date
                session_date = row.get("session_date")
                if session_date is not None:
                    if hasattr(session_date, 'to_native'):
                        date_obj = session_date.to_native()
                    elif isinstance(session_date, str) and session_date:
                        try:
                            date_obj = datetime.strptime(session_date, "%Y-%m-%d").date()
                        except ValueError:
                            try:
                                date_obj = datetime.strptime(session_date, "%d/%m/%Y").date()
                            except ValueError:
                                date_obj = datetime.now().date()
                    else:
                        date_obj = datetime.now().date()
                else:
                    date_obj = datetime.now().date()

                chunk_text = row.get("chunk_text", "")
                text = row.get("text", "")

                processed.append({
                    "evidence_id": row.get("chunk_id", ""),
                    "doc_id": row.get("session_id", ""),
                    "speech_id": row.get("speech_id", ""),
                    "speaker_id": row.get("speaker_id", ""),
                    "speaker_name": normalize_speaker_name(
                        row.get("speaker_first_name", ""),
                        row.get("speaker_last_name", "")
                    ),
                    "speaker_role": speaker_role,
                    "party": normalize_party_name(party),
                    "coalition": coalition,
                    "party_changed": party_changed,
                    "current_party": current_party_display if party_changed else None,
                    "date": date_obj,
                    "chunk_text": chunk_text,
                    "quote_text": chunk_text,
                    "text": text,
                    "debate_title": row.get("debate_title"),
                    "session_number": row.get("session_number", 0),
                    # Neutral similarity — RRF uses rank, not raw BM25 score
                    "similarity": 0.5,
                    # Preserve original BM25 score for diagnostics
                    "bm25_score": row.get("bm25_score", 0.0),
                    "embedding": None,
                    "retrieval_channel": "sparse",
                })

            except Exception as e:
                logger.error(f"Sparse channel: error processing result: {e}")
                continue

        return processed

    @staticmethod
    def _escape_lucene(query: str) -> str:
        """
        Escape Lucene special characters in query string.

        Prevents query parse errors for inputs containing +, -, /, etc.
        """
        special_chars = r'+-&|!(){}[]^"~*?:\/'
        escaped = []
        for char in query:
            if char in special_chars:
                escaped.append(f"\\{char}")
            else:
                escaped.append(char)
        return "".join(escaped)
