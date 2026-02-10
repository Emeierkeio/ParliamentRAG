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

        # Coverage fill: find chunks for missing parties
        covered_parties = {r.get("party") for r in merged_results if r.get("party")}
        all_parties = set(self.config.get_all_parties())
        missing_parties = all_parties - covered_parties

        fill_count = 0
        if missing_parties:
            logger.info(f"Coverage fill: searching for {len(missing_parties)} missing parties: {missing_parties}")
            fill_results = self._coverage_fill(query_embedding, missing_parties)
            if fill_results:
                fill_count = len(fill_results)
                merged_results.extend(fill_results)
                logger.info(f"Coverage fill: added {fill_count} chunks for missing parties")

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

    def _coverage_fill(
        self,
        query_embedding: List[float],
        missing_parties: set,
        chunks_per_party: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fill coverage gaps by doing targeted vector search for missing parties.

        For each missing party, queries the vector index and filters results
        to only include speakers from that party.
        """
        config = get_config()
        retrieval_config = config.retrieval.get("dense_channel", {})
        index_name = retrieval_config.get("index_name", "chunk_embedding_index")

        fill_results = []

        for party in missing_parties:
            try:
                cypher = """
                CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
                YIELD node AS c, score
                WHERE score >= 0.25
                MATCH (c)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
                MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
                MATCH (speaker)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
                WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
                AND g.name = $party_name
                RETURN c.id AS chunk_id,
                       c.text AS chunk_text,
                       c.embedding AS embedding,
                       c.start_char_raw AS span_start,
                       c.end_char_raw AS span_end,
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
                LIMIT $limit
                """

                results = self.client.query(cypher, {
                    "index_name": index_name,
                    "top_k": 500,  # Search wider to find this party's chunks
                    "query_embedding": query_embedding,
                    "party_name": party,
                    "limit": chunks_per_party
                })

                if results:
                    processed = self.dense_channel._process_results(results)
                    for r in processed:
                        r["retrieval_channel"] = "coverage_fill"
                    fill_results.extend(processed)
                    logger.info(f"Coverage fill: found {len(results)} chunks for {party}")
                else:
                    logger.warning(f"Coverage fill: no chunks found for {party}")

            except Exception as e:
                logger.error(f"Coverage fill error for {party}: {e}")

        return fill_results

    def _compute_party_coverage(
        self,
        evidence_list: List[UnifiedEvidence]
    ) -> Dict[str, int]:
        """Compute number of evidence pieces per party."""
        coverage: Dict[str, int] = {}
        for e in evidence_list:
            coverage[e.party] = coverage.get(e.party, 0) + 1
        return coverage
