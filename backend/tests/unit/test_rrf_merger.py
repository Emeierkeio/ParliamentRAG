"""
Unit tests for RRF-based ChannelMerger.

Tests cover:
1. RRF scores are computed as sum(weight / (k + rank)) for each channel
2. Same evidence_id from multiple channels gets combined RRF score
3. _select_diverse is still called (diversity limits enforced)
4. Empty sparse_results does not crash — merger degrades gracefully
5. merge() accepts new 3-channel signature (dense, sparse, graph)
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(evidence_id: str, party: str = "FdI", speaker_id: str = "spk1",
                 similarity: float = 0.5, channel: str = "dense") -> dict:
    """Build a minimal retrieval result dict."""
    return {
        "evidence_id": evidence_id,
        "chunk_text": f"Text for {evidence_id}",
        "quote_text": f"Quote for {evidence_id}",
        "similarity": similarity,
        "speaker_id": speaker_id,
        "speaker_name": "Mario Rossi",
        "speaker_role": "Deputy",
        "party": party,
        "coalition": "maggioranza",
        "date": "2024-01-15",
        "retrieval_channel": channel,
        "session_number": 100,
        "debate_title": "Debate",
        "doc_id": "session_1",
        "speech_id": "speech_1",
        "embedding": None,
    }


def _make_dense(n: int, prefix: str = "d") -> list:
    parties = ["FdI", "Lega", "FI", "PD", "M5S", "AVS", "AZ", "IV", "NM", "Misto"]
    return [
        _make_result(f"{prefix}{i}", party=parties[i % len(parties)],
                     speaker_id=f"spk_{prefix}{i}", channel="dense")
        for i in range(n)
    ]


def _make_sparse(n: int, prefix: str = "s") -> list:
    parties = ["FdI", "Lega", "PD", "M5S", "AZ"]
    return [
        _make_result(f"{prefix}{i}", party=parties[i % len(parties)],
                     speaker_id=f"spk_{prefix}{i}", channel="sparse")
        for i in range(n)
    ]


def _make_graph(n: int, prefix: str = "g") -> list:
    parties = ["FdI", "PD", "M5S", "Lega", "IV"]
    return [
        _make_result(f"{prefix}{i}", party=parties[i % len(parties)],
                     speaker_id=f"spk_{prefix}{i}", channel="graph")
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests: merge() signature
# ---------------------------------------------------------------------------

class TestChannelMergerSignature:
    """merge() now accepts sparse_results as second positional argument."""

    def test_merge_accepts_three_channel_signature(self):
        """merge(dense, sparse, graph) does not raise TypeError."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()
        dense = _make_dense(5)
        sparse = _make_sparse(3)
        graph = _make_graph(3)

        result = merger.merge(dense, sparse, graph, top_k=10)

        assert isinstance(result, list)

    def test_merge_returns_list_of_dicts(self):
        """merge() returns a list of evidence dicts."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()
        result = merger.merge(_make_dense(5), _make_sparse(3), _make_graph(3), top_k=8)

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)


# ---------------------------------------------------------------------------
# Tests: RRF scoring
# ---------------------------------------------------------------------------

class TestRRFScoring:
    """RRF scores follow the rank-based fusion formula."""

    def test_rrf_merger_correct_scores(self):
        """Given known ranks, RRF scores are sum(weight / (k + rank))."""
        from app.services.retrieval.merger import ChannelMerger

        # Use a single result that appears in all 3 channels at rank 1
        shared_id = "shared_chunk"
        dense = [_make_result(shared_id, channel="dense")]
        sparse = [_make_result(shared_id, channel="sparse")]
        graph = [_make_result(shared_id, channel="graph")]

        merger = ChannelMerger()
        results = merger.merge(dense, sparse, graph, top_k=10)

        # Find the shared result
        shared = next((r for r in results if r["evidence_id"] == shared_id), None)
        assert shared is not None, "Shared chunk not found in merged results"

        # Verify rrf_score is present
        assert "rrf_score" in shared, "rrf_score key missing"
        rrf_score = shared["rrf_score"]

        # RRF formula: dense_weight/(k+1) + sparse_weight/(k+1) + graph_weight/(k+1)
        # Default k=60, dense_weight=1.0, sparse_weight=0.8, graph_weight=0.5
        k = 60
        expected = 1.0 / (k + 1) + 0.8 / (k + 1) + 0.5 / (k + 1)
        assert abs(rrf_score - expected) < 1e-6, (
            f"Expected RRF score {expected:.6f}, got {rrf_score:.6f}"
        )

    def test_rrf_merger_higher_rank_yields_higher_score(self):
        """A result ranked 1st in a channel scores higher than one ranked 5th."""
        from app.services.retrieval.merger import ChannelMerger

        # First result at rank 1, second result at rank 2 — different speakers
        dense = [
            _make_result("high_rank", speaker_id="spk_a", channel="dense"),  # rank 1
            _make_result("low_rank", speaker_id="spk_b", channel="dense"),   # rank 2
        ]
        sparse = []
        graph = []

        merger = ChannelMerger()
        # top_k large enough to avoid diversity cutoff for just 2 different speakers
        results = merger.merge(dense, sparse, graph, top_k=100)

        high = next((r for r in results if r["evidence_id"] == "high_rank"), None)
        low = next((r for r in results if r["evidence_id"] == "low_rank"), None)

        assert high is not None and low is not None
        assert high.get("rrf_score", 0) > low.get("rrf_score", 0)

    def test_rrf_merger_deduplicates(self):
        """Same evidence_id from multiple channels gets combined RRF score."""
        from app.services.retrieval.merger import ChannelMerger

        shared_id = "dup_chunk"
        unique_dense_id = "dense_only"

        dense = [_make_result(shared_id, channel="dense"),
                 _make_result(unique_dense_id, channel="dense")]
        sparse = [_make_result(shared_id, channel="sparse")]
        graph = []

        merger = ChannelMerger()
        results = merger.merge(dense, sparse, graph, top_k=10)

        # shared_id should appear ONCE
        shared_occurrences = [r for r in results if r["evidence_id"] == shared_id]
        assert len(shared_occurrences) == 1, (
            f"Expected 1 occurrence of shared_id, got {len(shared_occurrences)}"
        )

        # shared result should have higher rrf_score than dense-only result
        shared = shared_occurrences[0]
        unique = next((r for r in results if r["evidence_id"] == unique_dense_id), None)

        if unique:
            assert shared.get("rrf_score", 0) > unique.get("rrf_score", 0), (
                "Multi-channel result should outscore single-channel result at same rank"
            )


# ---------------------------------------------------------------------------
# Tests: Empty channel graceful degradation
# ---------------------------------------------------------------------------

class TestEmptyChannelGracefulDegradation:
    """Empty channels must not crash the merger."""

    def test_rrf_merger_empty_sparse(self):
        """Empty sparse_results does not crash — merger degrades gracefully."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()
        dense = _make_dense(5)
        graph = _make_graph(3)

        # Should NOT raise
        result = merger.merge(dense, [], graph, top_k=10)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_rrf_merger_all_empty_channels(self):
        """All-empty channels returns empty list without crash."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()
        result = merger.merge([], [], [], top_k=10)

        assert result == []

    def test_rrf_merger_empty_dense_and_graph(self):
        """Only sparse results still produces valid output."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()
        sparse = _make_sparse(5)

        result = merger.merge([], sparse, [], top_k=10)
        assert isinstance(result, list)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests: Diversity selection still applied
# ---------------------------------------------------------------------------

class TestDiversitySelection:
    """_select_diverse is called and enforces per-speaker limits."""

    def test_rrf_merger_preserves_diversity_selection(self):
        """Per-speaker limit is enforced in final output."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()

        # Create 50 results all from the same speaker/party
        same_speaker_results = [
            _make_result(f"chunk_{i}", party="FdI", speaker_id="spk_dominant",
                         channel="dense")
            for i in range(50)
        ]
        # top_k=20 → max_per_speaker = 20 // 10 = 2
        result = merger.merge(same_speaker_results, [], [], top_k=20)

        dominant_count = sum(1 for r in result if r.get("speaker_id") == "spk_dominant")
        # Should be limited to at most max_per_speaker (2)
        assert dominant_count <= 2, (
            f"Expected <=2 results from dominant speaker, got {dominant_count}"
        )

    def test_rrf_merger_final_score_set_for_select_diverse(self):
        """final_score is set equal to rrf_score for _select_diverse to use."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()
        dense = _make_dense(3)

        result = merger.merge(dense, [], [], top_k=10)

        for r in result:
            assert "final_score" in r, "final_score missing"
            assert "rrf_score" in r, "rrf_score missing"
            assert r["final_score"] == r["rrf_score"], (
                f"final_score ({r['final_score']}) != rrf_score ({r['rrf_score']})"
            )
