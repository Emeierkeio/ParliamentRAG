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
from ...models.evidence import UnifiedEvidence, compute_quote_text
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
        MATCH (c)<-[:HA_CHUNK]-(i:Intervento)-[:PRONUNCIATO_DA]->(speaker)
        MATCH (i)<-[:CONTIENE_INTERVENTO]-(f:Fase)<-[:HA_FASE]-(d:Dibattito)<-[:HA_DIBATTITO]-(s:Seduta)
        OPTIONAL MATCH (speaker)-[mg:MEMBRO_GRUPPO]->(g:GruppoParlamentare)
        WHERE mg.dataInizio <= s.data AND (mg.dataFine IS NULL OR mg.dataFine >= s.data)
        RETURN c.id AS chunk_id,
               c.testo AS chunk_text,
               c.embedding AS embedding,
               c.start_char_raw AS span_start,
               c.end_char_raw AS span_end,
               c.indice AS chunk_index,
               i.id AS intervento_id,
               i.testo_raw AS testo_raw,
               speaker.id AS speaker_id,
               speaker.nome AS speaker_nome,
               speaker.cognome AS speaker_cognome,
               labels(speaker)[0] AS speaker_type,
               g.nome AS party,
               s.id AS seduta_id,
               s.data AS seduta_date,
               s.numero AS seduta_numero,
               d.titolo AS dibattito_titolo,
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

        Computes quote_text from testo_raw using offsets.
        """
        processed = []
        config = get_config()

        for row in results:
            try:
                # Extract quote using offsets - CRITICAL for citation integrity
                testo_raw = row.get("testo_raw", "")
                span_start = row.get("span_start", 0)
                span_end = row.get("span_end", 0)

                if testo_raw and span_start is not None and span_end is not None:
                    quote_text = compute_quote_text(testo_raw, span_start, span_end)
                else:
                    # Fallback to chunk_text if offsets unavailable
                    quote_text = row.get("chunk_text", "")
                    logger.warning(f"Missing offsets for chunk {row.get('chunk_id')}")

                # Determine coalition
                party = row.get("party", "MISTO")
                coalition = config.get_coalition(party) if party else "opposizione"

                # Parse date
                seduta_date = row.get("seduta_date", "")
                if seduta_date:
                    try:
                        # Handle DD/MM/YYYY format
                        date_obj = datetime.strptime(seduta_date, "%d/%m/%Y").date()
                    except ValueError:
                        date_obj = datetime.now().date()
                else:
                    date_obj = datetime.now().date()

                processed.append({
                    "evidence_id": row.get("chunk_id", ""),
                    "doc_id": row.get("seduta_id", ""),
                    "speech_id": row.get("intervento_id", ""),
                    "speaker_id": row.get("speaker_id", ""),
                    "speaker_name": f"{row.get('speaker_nome', '')} {row.get('speaker_cognome', '')}".strip(),
                    "speaker_role": row.get("speaker_type", "Deputato"),
                    "party": party or "MISTO",
                    "coalition": coalition,
                    "date": date_obj,
                    "chunk_text": row.get("chunk_text", ""),
                    "quote_text": quote_text,
                    "span_start": span_start or 0,
                    "span_end": span_end or 0,
                    "dibattito_titolo": row.get("dibattito_titolo"),
                    "seduta_numero": row.get("seduta_numero", 0),
                    "similarity": row.get("similarity", 0.0),
                    "embedding": row.get("embedding"),  # For compass PCA
                    "retrieval_channel": "dense"
                })
            except Exception as e:
                logger.error(f"Error processing result: {e}")
                continue

        return processed
