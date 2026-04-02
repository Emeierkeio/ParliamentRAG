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
    """UnifiedEvidence Pydantic model must not have span_start or span_end fields."""
    from app.models.evidence import UnifiedEvidence

    assert "span_start" not in UnifiedEvidence.model_fields, (
        "UnifiedEvidence still has span_start field — remove it"
    )
    assert "span_end" not in UnifiedEvidence.model_fields, (
        "UnifiedEvidence still has span_end field — remove it"
    )


def test_citation_info_no_span_fields():
    """CitationInfo Pydantic model in query.py must not have span_start or span_end fields."""
    from app.routers.query import CitationInfo

    assert "span_start" not in CitationInfo.model_fields, (
        "CitationInfo in query.py still has span_start field — remove it"
    )
    assert "span_end" not in CitationInfo.model_fields, (
        "CitationInfo in query.py still has span_end field — remove it"
    )
