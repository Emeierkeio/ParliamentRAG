"""
Unit tests for votes_service.py — pure math functions only.

No Neo4j, no scipy, no numpy. Tests run in isolation from the DB.

Task 1 covers: rice_index, mean_rice (6 tests).
Task 3 adds:  test_vote_facts_empty, test_vote_coherence_empty (2 tests).
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
