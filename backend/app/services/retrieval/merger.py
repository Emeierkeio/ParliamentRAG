"""
Channel merger for triple-channel retrieval using Reciprocal Rank Fusion (RRF).

Merges results from dense, sparse, and graph channels with:
- Rank-based fusion (RRF) instead of weighted similarity scores
- Diversity selection (penalize same-speaker dominance)
- Party coverage logging
"""
import logging
from typing import List, Dict, Any, Set, Optional
from collections import defaultdict

from ...config import get_config
from ..citation.sentence_extractor import compute_chunk_salience

logger = logging.getLogger(__name__)


class ChannelMerger:
    """
    Merges results from dense, sparse, and graph retrieval channels.

    Uses Reciprocal Rank Fusion (RRF) to combine channel rankings:
        rrf_score = sum(weight / (k + rank))  for each channel the item appears in

    Then applies greedy diversity selection to ensure no single speaker/party dominates.
    """

    def __init__(self):
        self.config = get_config()

    def merge(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        graph_results: List[Dict[str, Any]],
        ner_results: Optional[List[Dict[str, Any]]] = None,
        authority_scores: Optional[Dict[str, float]] = None,
        top_k: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Merge results from dense, sparse, graph, and optional NER channels using RRF.

        Args:
            dense_results: Results from dense (vector) channel
            sparse_results: Results from sparse (BM25) channel
            graph_results: Results from graph (structure) channel
            ner_results: Optional results from NER entity channel
            authority_scores: Optional speaker authority scores (unused by RRF,
                              kept for API compatibility)
            top_k: Number of final results

        Returns:
            Merged and reranked results
        """
        ner_count = len(ner_results) if ner_results else 0
        logger.info(
            f"Merging {len(dense_results)} dense + {len(sparse_results)} sparse "
            f"+ {len(graph_results)} graph"
            + (f" + {ner_count} NER" if ner_results else "")
            + " results (RRF)"
        )

        # Compute RRF scores across all channels
        scored_results = self._compute_rrf(dense_results, sparse_results, graph_results, ner_results)
        logger.info(f"After RRF deduplication: {len(scored_results)} unique results")

        # Sort by RRF score descending before diversity selection
        sorted_results = sorted(
            scored_results, key=lambda x: x.get("final_score", 0), reverse=True
        )

        # Apply greedy diversity selection
        final_results = self._select_diverse(sorted_results, top_k)

        # Log coverage statistics
        self._log_coverage(final_results)

        return final_results

    def _compute_rrf(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        graph_results: List[Dict[str, Any]],
        ner_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compute Reciprocal Rank Fusion scores for all results.

        For each evidence_id present in one or more channels:
            rrf_score = sum(weight / (k + rank))

        Results are deduplicated: if the same evidence_id appears in multiple
        channels, the best metadata (from the channel with highest contribution)
        is kept and the scores are combined.
        """
        rrf_config = self.config.retrieval.get("rrf", {})
        k = rrf_config.get("k", 60)
        dense_weight = rrf_config.get("dense_weight", 1.0)
        sparse_weight = rrf_config.get("sparse_weight", 0.8)
        graph_weight = rrf_config.get("graph_weight", 0.5)
        ner_weight = rrf_config.get("ner_weight", 0.9)

        # evidence_id -> accumulated rrf score
        rrf_scores: Dict[str, float] = defaultdict(float)
        # evidence_id -> best metadata dict (from first-seen channel)
        result_lookup: Dict[str, Dict[str, Any]] = {}

        def _process_channel(results: List[Dict[str, Any]], weight: float) -> None:
            for rank, result in enumerate(results, start=1):
                eid = result.get("evidence_id", "")
                if not eid:
                    continue
                contribution = weight / (k + rank)
                rrf_scores[eid] += contribution
                # Keep first-seen metadata (dense preferred over sparse/graph/ner)
                if eid not in result_lookup:
                    result_lookup[eid] = result

        # Process in priority order: dense > sparse > graph > ner
        _process_channel(dense_results, dense_weight)
        _process_channel(sparse_results, sparse_weight)
        _process_channel(graph_results, graph_weight)
        if ner_results:
            _process_channel(ner_results, ner_weight)

        # Build final list with RRF scores attached
        combined = []
        for eid, rrf_score in rrf_scores.items():
            result = dict(result_lookup[eid])  # Copy to avoid mutating originals

            # Compute political salience (used for diagnostics / downstream)
            salience = result.get("salience")
            if salience is None:
                text = result.get("chunk_text") or result.get("quote_text", "")
                salience = compute_chunk_salience(text)
                result["salience"] = salience

            result["rrf_score"] = rrf_score
            result["final_score"] = rrf_score  # _select_diverse reads final_score
            result["similarity"] = rrf_score   # Unify similarity for downstream use
            result["score_components"] = {
                "rrf_score": rrf_score,
                "salience": salience,
            }
            combined.append(result)

        return combined

    def _select_diverse(
        self,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Select top_k results while ensuring diversity.

        Uses a greedy approach that balances score with speaker/party diversity.
        Input must already be sorted by final_score descending.
        """
        selected: List[Dict[str, Any]] = []
        speaker_selected: Dict[str, int] = defaultdict(int)
        party_selected: Dict[str, int] = defaultdict(int)

        max_per_speaker = max(1, top_k // 10)  # Limit per speaker
        max_per_party = max(1, top_k // 3)     # Softer limit per party

        for result in results:
            if len(selected) >= top_k:
                break

            speaker_id = result.get("speaker_id", "")
            party = result.get("party", "")

            # Enforce per-speaker limit
            if speaker_selected[speaker_id] >= max_per_speaker:
                continue

            # Enforce per-party limit (allow override for very high-scoring items)
            if party_selected[party] >= max_per_party:
                if result.get("final_score", 0) < 0.8:
                    continue

            selected.append(result)
            speaker_selected[speaker_id] += 1
            party_selected[party] += 1

        return selected

    def _log_coverage(self, results: List[Dict[str, Any]]) -> None:
        """Log coverage statistics."""
        parties_covered: Set[str] = set()
        speakers_covered: Set[str] = set()
        channels: Dict[str, int] = defaultdict(int)

        for r in results:
            parties_covered.add(r.get("party", ""))
            speakers_covered.add(r.get("speaker_id", ""))
            channels[r.get("retrieval_channel", "unknown")] += 1

        all_parties = set(self.config.get_all_parties())
        missing_parties = all_parties - parties_covered

        logger.info(
            f"Coverage: {len(parties_covered)}/{len(all_parties)} parties, "
            f"{len(speakers_covered)} speakers"
        )
        if missing_parties:
            logger.warning(f"Missing parties: {missing_parties}")
        logger.info(f"Channel distribution: {dict(channels)}")
