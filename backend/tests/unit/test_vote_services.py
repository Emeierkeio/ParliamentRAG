"""
Unit tests for votes_service.py — pure math functions only.

No Neo4j, no scipy, no numpy. Tests run in isolation from the DB.

Task 1 covers: rice_index, mean_rice (6 tests).
Task 3 adds:  test_vote_facts_empty, test_vote_coherence_empty (2 tests).
Bug-fix adds: margin-as-percentage assertions, dedup guard (4 tests).
14-08 ext:    get_vote_individual_votes shape tests (4 tests).
14-08 label:  subject/context_label split for search_votes, facts, coherence (3 tests).
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


# ---------------------------------------------------------------------------
# get_vote_individual_votes — shape tests and Cypher contract (14-08 extension)
# ---------------------------------------------------------------------------

class _FakeNeo4j:
    """Minimal fake Neo4j client that returns a fixed row list."""

    def __init__(self, rows):
        self._rows = rows

    def query(self, cypher, params=None):
        return self._rows


def test_individual_votes_unavailable_when_no_rows():
    """get_vote_individual_votes returns available=False when neo4j returns empty list."""
    from app.services.votes_service import get_vote_individual_votes

    neo4j = _FakeNeo4j([])
    result = get_vote_individual_votes(neo4j, "fake_vote_id")

    assert result["available"] is False
    assert result["vote_id"] == "fake_vote_id"
    assert result["recorded"] == 0
    assert result["parties"] == []


def test_individual_votes_unavailable_when_deputy_id_null():
    """get_vote_individual_votes returns available=False when rows have no deputy (no IndividualVotes)."""
    from app.services.votes_service import get_vote_individual_votes

    # One row returned (vote exists) but deputy_id is None (no IndividualVote data)
    fake_row = {
        "vote_id": "v1",
        "official_total": 300,
        "deputy_id": None,
        "deputy_name": None,
        "party": "Sconosciuto",
        "outcome": None,
    }
    neo4j = _FakeNeo4j([fake_row])
    result = get_vote_individual_votes(neo4j, "v1")

    assert result["available"] is False
    assert result["recorded"] == 0
    assert result["official_total"] == 300
    assert result["parties"] == []


def test_individual_votes_grouping_by_party():
    """get_vote_individual_votes groups deputies by party and outcome correctly."""
    from app.services.votes_service import get_vote_individual_votes

    rows = [
        {"vote_id": "v1", "official_total": 10, "deputy_id": "d1",
         "deputy_name": "Mario Rossi", "party": "Partito A", "outcome": "favor"},
        {"vote_id": "v1", "official_total": 10, "deputy_id": "d2",
         "deputy_name": "Luigi Bianchi", "party": "Partito A", "outcome": "against"},
        {"vote_id": "v1", "official_total": 10, "deputy_id": "d3",
         "deputy_name": "Anna Verdi", "party": "Partito B", "outcome": "favor"},
        {"vote_id": "v1", "official_total": 10, "deputy_id": "d4",
         "deputy_name": "Carlo Neri", "party": "Partito B", "outcome": "abstain"},
    ]
    neo4j = _FakeNeo4j(rows)
    result = get_vote_individual_votes(neo4j, "v1")

    assert result["available"] is True
    assert result["vote_id"] == "v1"
    assert result["recorded"] == 4
    assert result["official_total"] == 10

    # Parties sorted alphabetically
    assert len(result["parties"]) == 2
    party_a = result["parties"][0]
    party_b = result["parties"][1]
    assert party_a["party"] == "Partito A"
    assert party_b["party"] == "Partito B"

    # Party A: 1 favor, 1 against, 0 abstained
    assert len(party_a["favor"]) == 1
    assert party_a["favor"][0]["id"] == "d1"
    assert party_a["favor"][0]["name"] == "Mario Rossi"
    assert len(party_a["against"]) == 1
    assert len(party_a["abstained"]) == 0

    # Party B: 1 favor, 0 against, 1 abstained
    assert len(party_b["favor"]) == 1
    assert len(party_b["against"]) == 0
    assert len(party_b["abstained"]) == 1
    assert party_b["abstained"][0]["id"] == "d4"


def test_individual_votes_cypher_date_scoped_membership():
    """_INDIVIDUAL_VOTES_CYPHER must use date-scoped MEMBER_OF_GROUP with start/end date guard."""
    from app.services.votes_service import _INDIVIDUAL_VOTES_CYPHER

    assert "mg.start_date <= s.date" in _INDIVIDUAL_VOTES_CYPHER, (
        "_INDIVIDUAL_VOTES_CYPHER must filter MEMBER_OF_GROUP by start_date"
    )
    assert "mg.end_date IS NULL OR mg.end_date >= s.date" in _INDIVIDUAL_VOTES_CYPHER, (
        "_INDIVIDUAL_VOTES_CYPHER must filter MEMBER_OF_GROUP by end_date (NULL or future)"
    )


def test_individual_votes_cypher_no_fanout():
    """_INDIVIDUAL_VOTES_CYPHER must collapse MEMBER_OF_GROUP fan-out via head(collect(...))."""
    from app.services.votes_service import _INDIVIDUAL_VOTES_CYPHER

    assert "head(collect(g.name))" in _INDIVIDUAL_VOTES_CYPHER, (
        "_INDIVIDUAL_VOTES_CYPHER must use head(collect(g.name)) to avoid MEMBER_OF_GROUP fan-out"
    )


# ---------------------------------------------------------------------------
# 14-08 label split: subject + context_label (search_votes, vote_facts, coherence)
# ---------------------------------------------------------------------------

def test_search_votes_cypher_has_subject_and_context_label():
    """_SEARCH_VOTES_CYPHER must expose trim(v.subject) AS subject and
    coalesce(a.title, d.title) AS context_label instead of the old single `label` field.

    Regression guard: ensures distinct label fields so the frontend can render
    specific vote object (subject) separately from debate/act context (context_label).
    """
    from app.services.votes_service import _SEARCH_VOTES_CYPHER

    assert "trim(v.subject) AS subject" in _SEARCH_VOTES_CYPHER, (
        "_SEARCH_VOTES_CYPHER must expose trim(v.subject) AS subject"
    )
    assert "context_label" in _SEARCH_VOTES_CYPHER, (
        "_SEARCH_VOTES_CYPHER must expose context_label"
    )
    # Old single label coalesce that included v.subject as final fallback must not remain
    assert "coalesce(a.title, d.title, v.subject) AS label" not in _SEARCH_VOTES_CYPHER, (
        "_SEARCH_VOTES_CYPHER must not have the old coalesce(a.title, d.title, v.subject) AS label"
    )


def test_vote_facts_cypher_has_subject():
    """_VOTE_FACTS_CYPHER must expose trim(v.subject) AS subject alongside the existing label.

    This allows direct_writer.py to build enriched prompt lines
    «context» — subject when the subject is specific (non-generic).
    """
    from app.services.votes_service import _VOTE_FACTS_CYPHER

    assert "trim(v.subject) AS subject" in _VOTE_FACTS_CYPHER, (
        "_VOTE_FACTS_CYPHER must expose trim(v.subject) AS subject"
    )
    # Existing label must remain (used for fallback and fact chips)
    assert "AS label" in _VOTE_FACTS_CYPHER, (
        "_VOTE_FACTS_CYPHER must still expose label for backward compat"
    )


def test_vote_coherence_cypher_has_subject():
    """_VOTE_COHERENCE_CYPHER must expose trim(v.subject) AS subject alongside label.

    Ensures the F1 SSE event carries per-vote specific subject for richer chat display.
    """
    from app.services.votes_service import _VOTE_COHERENCE_CYPHER

    assert "trim(v.subject) AS subject" in _VOTE_COHERENCE_CYPHER, (
        "_VOTE_COHERENCE_CYPHER must expose trim(v.subject) AS subject"
    )
    assert "AS label" in _VOTE_COHERENCE_CYPHER, (
        "_VOTE_COHERENCE_CYPHER must still expose label"
    )
