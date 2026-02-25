"""
Main retrieval engine orchestrating dual-channel retrieval.

Coordinates dense and graph channels, applies authority scoring,
and returns unified evidence records.
"""
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import date

import openai

from ..neo4j_client import Neo4jClient
from ...key_pool import make_client
from .dense_channel import DenseChannel
from .graph_channel import GraphChannel
from .merger import ChannelMerger
from .query_rewriter import QueryRewriter
from ...models.evidence import UnifiedEvidence
from ...config import get_config, get_settings
from ..citation.sentence_extractor import compute_chunk_salience

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
        self.query_rewriter = QueryRewriter()
        self.config = get_config()
        self.settings = get_settings()

        # Initialize OpenAI client
        self.openai_client = make_client()

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

        # Rewrite short/ambiguous queries before retrieval.
        # The rewritten query is used for embedding + graph keyword search;
        # the original query is kept for logging and UI display.
        retrieval_query = self.query_rewriter.rewrite(query)

        # Generate query embedding
        logger.info(f"Generating embedding for query: {query[:50]}...")
        query_embedding = self.embed_query(retrieval_query)

        # Run both channels IN PARALLEL
        logger.info("Running dense and graph channels in parallel...")

        def run_dense():
            return self.dense_channel.retrieve(
                query_embedding=query_embedding,
                top_k=top_k * 2  # Over-retrieve for merging
            )

        def run_graph():
            return self.graph_channel.retrieve(
                query=retrieval_query,
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

        # Expand to neighboring chunks when a more politically salient
        # adjacent chunk exists for the same speech
        merged_results = self._expand_neighbors(merged_results)

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
        Perform dual-channel retrieval (async).

        Runs retrieve_sync() in a thread-pool executor so the event loop
        is never blocked while embedding or querying the DB.

        Args:
            query: User query
            top_k: Number of results to return
            authority_scores: Optional pre-computed authority scores
            date_start: Optional date filter start
            date_end: Optional date filter end

        Returns:
            Dictionary with evidence list and metadata
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.retrieve_sync(
                query=query,
                top_k=top_k,
                authority_scores=authority_scores,
                date_start=date_start,
                date_end=date_end,
            ),
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
                    text=r.get("text", ""),  # Full speech text for sentence expansion
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

    # Threshold below which span_start is considered "early in speech"
    # (i.e., the chunk is likely an introduction, not a position statement).
    # Speeches where the first meaningful position appears after ~500 chars
    # are common in Italian parliamentary debate.
    _EARLY_SPEECH_SPAN_THRESHOLD = 600

    def _expand_neighbors(
        self,
        results: List[Dict[str, Any]],
        salience_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Expand to neighboring chunks when they have higher political salience.

        For each retrieved chunk with low salience, checks the previous and
        next chunks via the NEXT relationship. If a neighbor has higher
        political salience, it replaces the original chunk.

        EARLY-SPEECH EXPANSION: chunks whose span_start is below
        _EARLY_SPEECH_SPAN_THRESHOLD are also considered for next-chunk
        expansion even if their salience is above the threshold, because
        early chunks tend to be introductory (topic contextualisation) and
        the position statement is typically in the following chunk.
        """
        if not results:
            return results

        # Compute salience for all current chunks
        for r in results:
            text = r.get("chunk_text") or r.get("quote_text", "")
            r["salience"] = compute_chunk_salience(text)

        # Candidates for expansion:
        # 1. Low-salience chunks (original logic)
        # 2. Early-in-speech chunks (new: span_start < threshold)
        #    Early chunks are introductory even when salience is medium-high
        #    because they mention the topic ("parliamo di salario minimo") which
        #    triggers opinion patterns but contain no actual position statement.
        low_salience = [r for r in results if r.get("salience", 0) < salience_threshold]
        early_speech = [
            r for r in results
            if r.get("span_start", 9999) < self._EARLY_SPEECH_SPAN_THRESHOLD
            and r not in low_salience  # avoid duplicates in the candidate set
        ]
        candidates = low_salience + early_speech

        if not candidates:
            logger.info("Neighbor expansion: all chunks above salience threshold and not early-speech, skipping")
            return results

        # Collect chunk IDs to expand
        chunk_ids = [r.get("evidence_id") for r in candidates if r.get("evidence_id")]
        if not chunk_ids:
            return results

        logger.info(
            f"Neighbor expansion: checking neighbors for {len(chunk_ids)} chunks "
            f"({len(low_salience)} low-salience, {len(early_speech)} early-speech)"
        )

        try:
            cypher = """
            UNWIND $chunk_ids AS cid
            MATCH (c:Chunk {id: cid})
            OPTIONAL MATCH (prev:Chunk)-[:NEXT]->(c)
            OPTIONAL MATCH (c)-[:NEXT]->(next:Chunk)
            MATCH (c)<-[:HAS_CHUNK]-(i:Speech)
            RETURN cid,
                   prev.id AS prev_id, prev.text AS prev_text,
                   prev.start_char_raw AS prev_start, prev.end_char_raw AS prev_end,
                   next.id AS next_id, next.text AS next_text,
                   next.start_char_raw AS next_start, next.end_char_raw AS next_end,
                   i.text AS speech_text
            """
            neighbor_rows = self.client.query(cypher, {"chunk_ids": chunk_ids})
        except Exception as e:
            logger.error(f"Neighbor expansion query failed: {e}")
            return results

        # Build lookup: chunk_id -> neighbor info
        neighbor_map = {}
        for row in neighbor_rows:
            neighbor_map[row["cid"]] = row

        # Existing evidence IDs to avoid duplicates
        existing_ids = {r.get("evidence_id") for r in results}

        # Track early-speech IDs for special handling
        early_speech_ids = {r.get("evidence_id") for r in early_speech}

        replaced = 0
        appended = 0
        for r in results:
            eid = r.get("evidence_id")
            if eid not in neighbor_map:
                continue

            is_low_salience = r.get("salience", 0) < salience_threshold
            is_early_speech = eid in early_speech_ids

            if not is_low_salience and not is_early_speech:
                continue

            row = neighbor_map[eid]
            current_salience = r.get("salience", 0)

            if is_low_salience:
                # Original logic: replace if a neighbor has higher salience
                best_replacement = None
                best_salience = current_salience

                if row.get("prev_text") and row.get("prev_id") not in existing_ids:
                    prev_salience = compute_chunk_salience(row["prev_text"])
                    if prev_salience > best_salience:
                        best_salience = prev_salience
                        best_replacement = ("prev", row)

                if row.get("next_text") and row.get("next_id") not in existing_ids:
                    next_salience = compute_chunk_salience(row["next_text"])
                    if next_salience > best_salience:
                        best_salience = next_salience
                        best_replacement = ("next", row)

                if best_replacement:
                    direction, nrow = best_replacement
                    prefix = "prev" if direction == "prev" else "next"
                    new_id = nrow.get(f"{prefix}_id")
                    new_text = nrow.get(f"{prefix}_text")
                    new_start = nrow.get(f"{prefix}_start", 0)
                    new_end = nrow.get(f"{prefix}_end", 0)
                    speech_text = nrow.get("speech_text", "")

                    from ...models.evidence import compute_quote_text
                    if speech_text and new_start is not None and new_end is not None and new_start < new_end:
                        new_quote = compute_quote_text(speech_text, new_start, new_end)
                    else:
                        new_quote = new_text

                    r["evidence_id"] = new_id
                    r["chunk_text"] = new_text
                    r["quote_text"] = new_quote
                    r["span_start"] = new_start or 0
                    r["span_end"] = new_end or 0
                    r["salience"] = best_salience
                    existing_ids.add(new_id)
                    replaced += 1

            elif is_early_speech:
                # Early-speech logic: APPEND the next chunk as additional evidence
                # rather than replacing, so the original chunk is still retrievable
                # (it may contain relevant keyword matches).
                # Only append if the next chunk has meaningfully higher salience.
                next_id = row.get("next_id")
                next_text = row.get("next_text")
                if not next_text or not next_id or next_id in existing_ids:
                    continue

                next_salience = compute_chunk_salience(next_text)
                # Append only if next chunk is more opinionated than current
                if next_salience <= current_salience:
                    continue

                next_start = row.get("next_start", 0)
                next_end = row.get("next_end", 0)
                speech_text = row.get("speech_text", "")

                from ...models.evidence import compute_quote_text
                if speech_text and next_start is not None and next_end is not None and next_start < next_end:
                    next_quote = compute_quote_text(speech_text, next_start, next_end)
                else:
                    next_quote = next_text

                # Clone the parent evidence record with the next chunk's data,
                # keeping speaker/party/date/authority metadata.
                neighbor_evidence = dict(r)
                neighbor_evidence["evidence_id"] = next_id
                neighbor_evidence["chunk_text"] = next_text
                neighbor_evidence["quote_text"] = next_quote
                neighbor_evidence["span_start"] = next_start or 0
                neighbor_evidence["span_end"] = next_end or 0
                neighbor_evidence["salience"] = next_salience
                neighbor_evidence["retrieval_channel"] = "neighbor_expansion"
                # Give a slight similarity boost to surface it near its parent
                neighbor_evidence["similarity"] = r.get("similarity", 0.0) * 0.95

                results.append(neighbor_evidence)
                existing_ids.add(next_id)
                appended += 1
                logger.info(
                    f"Early-speech expansion: appended next chunk {next_id} "
                    f"(parent={eid}, salience {current_salience:.2f}→{next_salience:.2f})"
                )

        logger.info(
            f"Neighbor expansion: replaced {replaced}/{len(low_salience)} low-salience chunks, "
            f"appended {appended}/{len(early_speech)} early-speech next chunks"
        )
        return results

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
                # Normalize party name to match DB storage format:
                # DB stores uppercase with no spaces around hyphens (e.g. "ITALIA VIVA-IL CENTRO-RENEW EUROPE")
                # Config uses display names with spaces (e.g. "Italia Viva - Il Centro - Renew Europe")
                normalized_party = party.upper().replace(" - ", "-").replace("- ", "-").replace(" -", "-")

                cypher = """
                CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
                YIELD node AS c, score
                WHERE score >= 0.15
                MATCH (c)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
                MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
                // Solo membri ATTUALI del partito: la membership deve essere
                // attiva sia alla data del discorso che oggi.
                MATCH (speaker)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
                WHERE toLower(g.name) = toLower($party_name)
                AND mg.start_date <= s.date
                AND (mg.end_date IS NULL OR mg.end_date >= s.date)
                AND (mg.end_date IS NULL OR mg.end_date >= date())
                // Partito attuale (per calcolo party_changed in _process_results)
                OPTIONAL MATCH (speaker)-[mg_now:MEMBER_OF_GROUP]->(g_now:ParliamentaryGroup)
                WHERE mg_now.end_date IS NULL
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
                       g_now.name AS current_party,
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
                    "party_name": normalized_party,
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
