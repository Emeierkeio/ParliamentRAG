"""
Unit tests for SparseChannel BM25 retrieval.

Tests cover:
1. Returns List[Dict] with expected keys including retrieval_channel="sparse"
2. Sets similarity=0.5 (neutral) and bm25_score with original BM25 score
3. Graceful fallback when full-text index does not exist (returns empty list)
4. Empty result list when Neo4j returns no records
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_neo4j_mock(records=None):
    """Return a Neo4jClient mock whose .query() returns the given records."""
    mock = MagicMock()
    mock.query.return_value = records if records is not None else []
    return mock


def _make_fake_records(n: int = 3):
    """Return n realistic Neo4j result rows for fulltext query."""
    rows = []
    for i in range(n):
        rows.append({
            "chunk_id": f"chunk_{i}",
            "chunk_text": f"Sample text chunk {i} about parliamentary matters.",
            "bm25_score": 5.0 - i,  # Descending BM25 scores
            "speech_id": f"speech_{i}",
            "text": f"Full speech text {i}",
            "speaker_id": f"speaker_{i}",
            "speaker_first_name": "Mario",
            "speaker_last_name": f"Rossi{i}",
            "speaker_type": "Deputy",
            "party": "Fratelli d'Italia",
            "current_party": "Fratelli d'Italia",
            "session_id": f"session_{i}",
            "session_date": "2024-01-15",
            "session_number": i + 100,
            "debate_title": f"Debate {i}",
        })
    return rows


# ---------------------------------------------------------------------------
# Tests: SparseChannel.retrieve()
# ---------------------------------------------------------------------------

class TestSparseChannelRetrieve:
    """Tests for SparseChannel.retrieve() return structure."""

    def test_sparse_channel_returns_evidence_list(self):
        """retrieve() returns a list of dicts with required keys."""
        from app.services.retrieval.sparse_channel import SparseChannel

        neo4j_mock = _make_neo4j_mock(_make_fake_records(2))
        channel = SparseChannel(neo4j_mock)

        results = channel.retrieve("immigrazione", top_k=10)

        assert isinstance(results, list)
        assert len(results) == 2

        required_keys = [
            "evidence_id", "chunk_text", "similarity",
            "speaker_id", "party", "retrieval_channel",
        ]
        for key in required_keys:
            assert key in results[0], f"Missing key: {key}"

    def test_sparse_channel_sets_neutral_similarity(self):
        """Each result has similarity=0.5 (neutral) and bm25_score with original score."""
        from app.services.retrieval.sparse_channel import SparseChannel

        records = _make_fake_records(3)
        neo4j_mock = _make_neo4j_mock(records)
        channel = SparseChannel(neo4j_mock)

        results = channel.retrieve("decreto 231")

        for i, result in enumerate(results):
            assert result["similarity"] == 0.5, (
                f"Expected similarity=0.5, got {result['similarity']}"
            )
            # bm25_score must be present and equal to the original score from the record
            assert "bm25_score" in result
            assert result["bm25_score"] == records[i]["bm25_score"]

    def test_sparse_channel_sets_retrieval_channel_tag(self):
        """Each result has retrieval_channel='sparse'."""
        from app.services.retrieval.sparse_channel import SparseChannel

        neo4j_mock = _make_neo4j_mock(_make_fake_records(2))
        channel = SparseChannel(neo4j_mock)

        results = channel.retrieve("Meloni")

        for result in results:
            assert result["retrieval_channel"] == "sparse"

    def test_sparse_channel_empty_result(self):
        """retrieve() returns empty list when Neo4j returns no records."""
        from app.services.retrieval.sparse_channel import SparseChannel

        neo4j_mock = _make_neo4j_mock([])
        channel = SparseChannel(neo4j_mock)

        results = channel.retrieve("nonexistent query xyz")

        assert results == []

    def test_sparse_channel_graceful_fallback_on_missing_index(self):
        """retrieve() returns empty list when full-text index doesn't exist."""
        from app.services.retrieval.sparse_channel import SparseChannel

        # Simulate ClientError or similar when index is missing
        neo4j_mock = MagicMock()
        neo4j_mock.query.side_effect = Exception(
            "There is no such fulltext schema index: chunk_fulltext"
        )
        channel = SparseChannel(neo4j_mock)

        # Must NOT raise — should degrade gracefully
        results = channel.retrieve("immigrazione")

        assert results == []

    def test_sparse_channel_result_has_speech_and_doc_ids(self):
        """Results include speech_id, doc_id, and speaker metadata."""
        from app.services.retrieval.sparse_channel import SparseChannel

        neo4j_mock = _make_neo4j_mock(_make_fake_records(1))
        channel = SparseChannel(neo4j_mock)

        results = channel.retrieve("riforma pensioni")

        r = results[0]
        assert r["speech_id"] == "speech_0"
        assert "doc_id" in r
        assert "speaker_name" in r
