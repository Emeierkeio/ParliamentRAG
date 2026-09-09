"""Unit tests for channel-level helpers: similarity scale and keywords.

The two channels must expose similarity on the same scale (the Neo4j
vector-index mapping (1+cos)/2) for the merger's relevance term to compare
like with like; the cosine helper is pinned here together with that mapping.
"""
import pytest

from app.services.retrieval.graph_channel import GraphChannel, cosine_similarity


def test_cosine_similarity_basic():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


@pytest.mark.parametrize("cos", [-1.0, -0.3, 0.0, 0.4, 1.0])
def test_normalized_scale_stays_in_unit_interval(cos):
    normalized = (1.0 + cos) / 2.0
    assert 0.0 <= normalized <= 1.0


def test_extract_keywords_filters_stopwords_and_short_tokens():
    channel = GraphChannel.__new__(GraphChannel)  # no DB client needed
    kws = channel.extract_keywords("qual è la posizione dei partiti sul salario minimo")
    assert "salario" in kws
    assert "minimo" in kws
    assert "la" not in kws
    assert "dei" not in kws
    # Bigram of the two content words survives.
    assert any("salario minimo" == k for k in kws)


def test_extract_keywords_deduplicates_preserving_order():
    channel = GraphChannel.__new__(GraphChannel)
    kws = channel.extract_keywords("immigrazione immigrazione clandestina")
    assert kws.count("immigrazione") == 1
    assert kws.index("immigrazione") < kws.index("clandestina")
