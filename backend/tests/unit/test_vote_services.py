"""
Unit tests for votes_service.py — pure math functions only.

No Neo4j, no scipy, no numpy. Tests run in isolation from the DB.

Task 1 covers: rice_index, mean_rice (6 tests).
Task 3 adds:  test_vote_facts_empty, test_vote_coherence_empty (2 tests).
Bug-fix adds: margin-as-percentage assertions, dedup guard (4 tests).
"""
import pytest

from app.services.votes_service import rice_index, mean_rice


# ---------------------------------------------------------------------------
# rice_index
# ---------------------------------------------------------------------------

def test_rice_unanimous():
    """rice_index(10, 0) == 1.0 — perfect cohesion, all voted in favor."""
    assert rice_index(10, 0) == pytest.approx(1.0)


def test_rice_split():
    """rice_index(5, 5) == 0.0 — perfect split, zero cohesion."""
    assert rice_index(5, 5) == pytest.approx(0.0)


def test_rice_no_votes():
    """rice_index(0, 0) is None — abstain-only votes are undefined."""
    assert rice_index(0, 0) is None


def test_rice_partial():
    """rice_index(7, 3) == 0.4 — |7-3|/(7+3) = 4/10 = 0.4."""
    assert rice_index(7, 3) == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# mean_rice
# ---------------------------------------------------------------------------

def test_mean_rice_excludes_unanimous():
    """mean_rice excludes unanimous (rice==1.0) when exclude_unanimous=True.

    Input:  vote A: favor=10, against=0  → rice=1.0 (unanimous → excluded)
            vote B: favor=6,  against=4  → rice=0.2

    Expected: mean = 0.2 / 1 = 0.2
    """
    rows = [
        {"favor": 10, "against": 0},
        {"favor": 6, "against": 4},
    ]
    result = mean_rice(rows, exclude_unanimous=True)
    assert result == pytest.approx(0.2)


def test_mean_rice_empty():
    """mean_rice([]) == 0.0 — empty list returns zero without error."""
    assert mean_rice([]) == 0.0


# ---------------------------------------------------------------------------
# empty-input guards for graph functions (Task 3)
# ---------------------------------------------------------------------------

def test_vote_facts_empty():
    """get_vote_facts with empty session_ids returns [] before any DB call."""
    from app.services.votes_service import get_vote_facts
    # Pass None as neo4j — function must return before querying the DB
    result = get_vote_facts(None, [])
    assert result == []


def test_vote_coherence_empty():
    """get_vote_coherence with empty session_ids returns {} before any DB call."""
    from app.services.votes_service import get_vote_coherence
    # Pass None as neo4j — function must return before querying the DB
    result = get_vote_coherence(None, [], 19)
    assert result == {}


# ---------------------------------------------------------------------------
# Bug-fix regression: margin as percentage, Cypher dedup guard (fix 14-08)
# ---------------------------------------------------------------------------

def test_search_votes_cypher_margin_is_percentage():
    """_SEARCH_VOTES_CYPHER must compute margin as 100 * |F-A| / (F+A), not as abs count.

    Regression guard: ensures `* 100` scaling and division by expressed votes are present
    so that the returned `margin` field is a percentage [0, 100] instead of an
    absolute vote-count difference that was erroneously multiplied by 100 on the frontend.
    """
    from app.services.votes_service import _SEARCH_VOTES_CYPHER
    assert "100.0" in _SEARCH_VOTES_CYPHER, (
        "_SEARCH_VOTES_CYPHER must scale margin to a percentage with 100.0 multiplier"
    )
    # The CASE guard against division by zero must be present
    assert "CASE WHEN" in _SEARCH_VOTES_CYPHER, (
        "_SEARCH_VOTES_CYPHER margin computation must guard against division by zero"
    )


def test_search_votes_cypher_no_fanout():
    """_SEARCH_VOTES_CYPHER must deduplicate debate/act rows using collect+head.

    Regression guard: a Session with multiple Debates (and Debates with multiple acts)
    previously fanned out each Vote row — one row per (v, d, a) combination.
    The fix uses head(collect(DISTINCT ...)) to collapse to exactly one row per Vote.
    """
    from app.services.votes_service import _SEARCH_VOTES_CYPHER
    assert "collect(DISTINCT a)" in _SEARCH_VOTES_CYPHER, (
        "_SEARCH_VOTES_CYPHER must use collect(DISTINCT a) to avoid act fan-out"
    )
    assert "collect(DISTINCT d)" in _SEARCH_VOTES_CYPHER, (
        "_SEARCH_VOTES_CYPHER must use collect(DISTINCT d) to avoid debate fan-out"
    )


def test_vote_facts_cypher_no_fanout():
    """_VOTE_FACTS_CYPHER must deduplicate debate/act rows using collect+head."""
    from app.services.votes_service import _VOTE_FACTS_CYPHER
    assert "collect(DISTINCT a)" in _VOTE_FACTS_CYPHER, (
        "_VOTE_FACTS_CYPHER must use collect(DISTINCT a) to avoid act fan-out"
    )
    assert "collect(DISTINCT d)" in _VOTE_FACTS_CYPHER, (
        "_VOTE_FACTS_CYPHER must use collect(DISTINCT d) to avoid debate fan-out"
    )


def test_vote_coherence_cypher_no_fanout():
    """_VOTE_COHERENCE_CYPHER must deduplicate debate/act rows using collect+head."""
    from app.services.votes_service import _VOTE_COHERENCE_CYPHER
    assert "collect(DISTINCT d)" in _VOTE_COHERENCE_CYPHER, (
        "_VOTE_COHERENCE_CYPHER must use collect(DISTINCT d) to avoid debate fan-out"
    )
    assert "collect(DISTINCT a)" in _VOTE_COHERENCE_CYPHER, (
        "_VOTE_COHERENCE_CYPHER must use collect(DISTINCT a) to avoid act fan-out"
    )
