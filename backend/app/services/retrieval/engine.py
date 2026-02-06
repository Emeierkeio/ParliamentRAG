"""
Main retrieval engine orchestrating dual-channel retrieval.

Coordinates dense and graph channels, applies authority scoring,
and returns unified evidence records.
"""
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import date

import openai

from ..neo4j_client import Neo4jClient
from .dense_channel import DenseChannel
from .graph_channel import GraphChannel
from .merger import ChannelMerger
from ...models.evidence import UnifiedEvidence
from ...config import get_config, get_settings

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """
    Main retrieval engine for dual-channel evidence retrieval.

    Orchestrates:
    1. Query embedding generation
    2. Dense channel retrieval (vector search)
    3. Graph channel retrieval (metadata/structure)
    4. Channel merging with authority weighting
    5. Evidence record creation
    """

    def __init__(self, neo4j_client: Neo4jClient):
        """
        Initialize the retrieval engine.

        Args:
            neo4j_client: Neo4j database client
        """
        self.client = neo4j_client
        self.dense_channel = DenseChannel(neo4j_client)
        self.graph_channel = GraphChannel(neo4j_client)
        self.merger = ChannelMerger()
        self.config = get_config()
        self.settings = get_settings()

        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(api_key=self.settings.openai_api_key)

    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query using OpenAI.

        Args:
            query: Query text

        Returns:
            Embedding vector (1536 dimensions)
        """
        llm_config = self.config.load_config().get("llm", {})
        model = llm_config.get("embedding_model", "text-embedding-3-small")

        response = self.openai_client.embeddings.create(
            input=query,
            model=model
        )

        return response.data[0].embedding

    def retrieve_sync(
        self,
        query: str,
        top_k: int = 100,
        authority_scores: Optional[Dict[str, float]] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform dual-channel retrieval (synchronous version).

        OPTIMIZED: Dense and Graph channels run IN PARALLEL using ThreadPoolExecutor.

        Args:
            query: User query
            top_k: Number of results to return
            authority_scores: Optional pre-computed authority scores
            date_start: Optional date filter start
            date_end: Optional date filter end

        Returns:
            Dictionary with evidence list and metadata
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        start_time = time.time()

        # Generate query embedding
        logger.info(f"Generating embedding for query: {query[:50]}...")
        query_embedding = self.embed_query(query)

        # Run both channels IN PARALLEL
        logger.info("Running dense and graph channels in parallel...")

        def run_dense():
            return self.dense_channel.retrieve(
                query_embedding=query_embedding,
                top_k=top_k * 2  # Over-retrieve for merging
            )

        def run_graph():
            return self.graph_channel.retrieve(
                query=query,
                query_embedding=query_embedding,
                date_start=date_start,
                date_end=date_end
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            dense_future = executor.submit(run_dense)
            graph_future = executor.submit(run_graph)

            dense_results = dense_future.result()
            graph_results = graph_future.result()

        logger.info(f"Channels complete: dense={len(dense_results)}, graph={len(graph_results)}")

        # Merge channels
        logger.info("Merging channels...")
        merged_results = self.merger.merge(
            dense_results=dense_results,
            graph_results=graph_results,
            authority_scores=authority_scores,
            top_k=top_k
        )

        # Convert to UnifiedEvidence
        evidence_list = self._to_evidence_records(merged_results)

        # Compute metadata
        processing_time = (time.time() - start_time) * 1000
        party_coverage = self._compute_party_coverage(evidence_list)

        return {
            "evidence": evidence_list,
            "metadata": {
                "dense_channel_count": len(dense_results),
                "graph_channel_count": len(graph_results),
                "merged_count": len(merged_results),
                "party_coverage": party_coverage,
                "processing_time_ms": processing_time
            }
        }

    async def retrieve(
        self,
        query: str,
        top_k: int = 100,
        authority_scores: Optional[Dict[str, float]] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform dual-channel retrieval (async wrapper).

        Note: This is kept for backwards compatibility but the actual
        work is done synchronously in retrieve_sync().

        Args:
            query: User query
            top_k: Number of results to return
            authority_scores: Optional pre-computed authority scores
            date_start: Optional date filter start
            date_end: Optional date filter end

        Returns:
            Dictionary with evidence list and metadata
        """
        return self.retrieve_sync(
            query=query,
            top_k=top_k,
            authority_scores=authority_scores,
            date_start=date_start,
            date_end=date_end
        )

    def _to_evidence_records(
        self,
        results: List[Dict[str, Any]]
    ) -> List[UnifiedEvidence]:
        """Convert raw results to UnifiedEvidence records."""
        evidence_list = []

        for r in results:
            try:
                evidence = UnifiedEvidence(
                    evidence_id=r.get("evidence_id", ""),
                    doc_id=r.get("doc_id", ""),
                    speech_id=r.get("speech_id", ""),
                    speaker_id=r.get("speaker_id", ""),
                    speaker_name=r.get("speaker_name", ""),
                    speaker_role=r.get("speaker_role", "Deputy"),
                    party=r.get("party", "MISTO"),
                    coalition=r.get("coalition", "opposizione"),
                    date=r.get("date", date.today()),
                    chunk_text=r.get("chunk_text", ""),
                    quote_text=r.get("quote_text", ""),
                    span_start=r.get("span_start", 0),
                    span_end=r.get("span_end", 0),
                    debate_title=r.get("debate_title"),
                    session_number=r.get("session_number", 0),
                    similarity=r.get("similarity", 0.0),
                    authority_score=r.get("authority_score", 0.0),
                    embedding=r.get("embedding")  # For compass PCA
                )
                evidence_list.append(evidence)
            except Exception as e:
                logger.error(f"Error creating evidence record: {e}")
                continue

        return evidence_list

    def _compute_party_coverage(
        self,
        evidence_list: List[UnifiedEvidence]
    ) -> Dict[str, int]:
        """Compute number of evidence pieces per party."""
        coverage: Dict[str, int] = {}
        for e in evidence_list:
            coverage[e.party] = coverage.get(e.party, 0) + 1
        return coverage
