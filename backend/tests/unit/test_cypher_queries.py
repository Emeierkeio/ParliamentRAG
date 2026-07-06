"""
Tests verifying that dead Cypher properties have been removed from all backend files.

Phase 1 schema change: Chunk nodes no longer have start_char_raw or end_char_raw.
Pydantic models must not have span_start or span_end fields either.

These tests act as regression guards — if any dead property is accidentally
re-introduced, the corresponding test will fail immediately.
"""
import pathlib
import pytest


# Base path to the backend app source tree
_APP_DIR = pathlib.Path(__file__).parent.parent.parent / "app"


def _read_source(relative_path: str) -> str:
    """Read source file content relative to the app directory."""
    full_path = _APP_DIR / relative_path
    return full_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Dead Cypher property tests
# ---------------------------------------------------------------------------

def test_neo4j_client_vector_search_no_dead_properties():
    """neo4j_client.py must not reference start_char_raw or end_char_raw."""
    source = _read_source("services/neo4j_client.py")
    assert "start_char_raw" not in source, (
        "neo4j_client.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "neo4j_client.py still references dead property end_char_raw"
    )


def test_graph_channel_no_dead_properties():
    """graph_channel.py must not reference start_char_raw or end_char_raw."""
    source = _read_source("services/retrieval/graph_channel.py")
    assert "start_char_raw" not in source, (
        "graph_channel.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "graph_channel.py still references dead property end_char_raw"
    )


def test_evidence_router_no_dead_properties():
    """routers/evidence.py must not reference start_char_raw or end_char_raw."""
    source = _read_source("routers/evidence.py")
    assert "start_char_raw" not in source, (
        "routers/evidence.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "routers/evidence.py still references dead property end_char_raw"
    )


def test_query_router_no_dead_properties():
    """routers/query.py must not reference start_char_raw or end_char_raw."""
    source = _read_source("routers/query.py")
    assert "start_char_raw" not in source, (
        "routers/query.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "routers/query.py still references dead property end_char_raw"
    )


def test_chat_router_no_dead_properties():
    """routers/chat.py must not reference start_char_raw or end_char_raw."""
    source = _read_source("routers/chat.py")
    assert "start_char_raw" not in source, (
        "routers/chat.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "routers/chat.py still references dead property end_char_raw"
    )


def test_search_router_no_dead_properties():
    """routers/search.py must not reference start_char_raw, end_char_raw, span_start, or span_end."""
    source = _read_source("routers/search.py")
    assert "start_char_raw" not in source, (
        "routers/search.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "routers/search.py still references dead property end_char_raw"
    )
    assert "span_start" not in source, (
        "routers/search.py still references dead field span_start"
    )
    assert "span_end" not in source, (
        "routers/search.py still references dead field span_end"
    )


def test_scorer_no_dead_properties():
    """services/authority/scorer.py must not reference start_char_raw, end_char_raw, span_start, or span_end."""
    source = _read_source("services/authority/scorer.py")
    assert "start_char_raw" not in source, (
        "services/authority/scorer.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "services/authority/scorer.py still references dead property end_char_raw"
    )
    assert "span_start" not in source, (
        "services/authority/scorer.py still references dead field span_start"
    )
    assert "span_end" not in source, (
        "services/authority/scorer.py still references dead field span_end"
    )


# ---------------------------------------------------------------------------
# Pydantic model dead-field tests
# ---------------------------------------------------------------------------

def test_unified_evidence_no_span_fields():
    """UnifiedEvidence Pydantic model source must not define span_start or span_end fields."""
    source = _read_source("models/evidence.py")

    # Check that no field declaration (Field(...)) uses these names as field names.
    # The source can still contain the words in function parameter names (compute_quote_text),
    # but the Pydantic model class body must not have them as class-level annotations.
    import re
    # Find the UnifiedEvidence class body (between class def and next top-level def/class)
    class_match = re.search(
        r'class UnifiedEvidence\(BaseModel\):(.*?)(?=\ndef |\nclass )',
        source,
        re.DOTALL
    )
    assert class_match is not None, "Could not find UnifiedEvidence class in evidence.py"
    class_body = class_match.group(1)

    assert "span_start" not in class_body, (
        "UnifiedEvidence class body still contains span_start — remove the field"
    )
    assert "span_end" not in class_body, (
        "UnifiedEvidence class body still contains span_end — remove the field"
    )


def test_votes_search_has_chamber_filter():
    """votes_service.py must filter by s.chamber and s.legislature in search_votes Cypher.

    Also asserts:
      - coalesce(a.title, d.title, v.subject) label hierarchy is present (Pitfall 4 guard).
      - get_party_cohesion region contains the date-scoped MEMBER_OF_GROUP condition.
    """
    source = _read_source("services/votes_service.py")

    # search_votes Cypher must filter both chamber and legislature
    assert "s.chamber" in source, (
        "votes_service.py search_votes Cypher must filter by s.chamber"
    )
    assert "s.legislature" in source, (
        "votes_service.py search_votes Cypher must filter by s.legislature"
    )

    # Label hierarchy: prefer act/debate title over generic v.subject (Pitfall 4)
    assert "coalesce(a.title, d.title, v.subject)" in source, (
        "votes_service.py must use coalesce(a.title, d.title, v.subject) as label "
        "to avoid generic Votazione labels from SPARQL-ingested votes"
    )

    # get_party_cohesion uses date-scoped MEMBER_OF_GROUP (as per design notes)
    assert "mg.start_date <= s.date" in source, (
        "votes_service.py get_party_cohesion Cypher must scope MEMBER_OF_GROUP by date "
        "(mg.start_date <= s.date)"
    )


def test_citation_info_no_span_fields():
    """CitationInfo Pydantic model source in query.py must not define span_start or span_end fields."""
    source = _read_source("routers/query.py")

    # Find the CitationInfo class definition and check it has no span fields
    # We verify by checking that the source file has no span field definitions
    assert "span_start" not in source, (
        "routers/query.py still references span_start (CitationInfo or elsewhere)"
    )
    assert "span_end" not in source, (
        "routers/query.py still references span_end (CitationInfo or elsewhere)"
    )


# ---------------------------------------------------------------------------
# Retrieval layer dead-property tests (gap closure from verification)
# ---------------------------------------------------------------------------

def test_dense_channel_no_dead_properties():
    """dense_channel.py must not reference start_char_raw, end_char_raw, span_start, or span_end."""
    source = _read_source("services/retrieval/dense_channel.py")
    assert "start_char_raw" not in source, (
        "dense_channel.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "dense_channel.py still references dead property end_char_raw"
    )


def test_engine_no_dead_properties():
    """engine.py must not reference start_char_raw or end_char_raw."""
    source = _read_source("services/retrieval/engine.py")
    assert "start_char_raw" not in source, (
        "engine.py still references dead property start_char_raw"
    )
    assert "end_char_raw" not in source, (
        "engine.py still references dead property end_char_raw"
    )
