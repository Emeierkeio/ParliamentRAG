"""
Source-file inspection tests for latency optimizations in Plan 07-02.

Uses source-file inspection (not live imports) to avoid the scipy/NumPy 2.x
import chain breakage in the Python 3.12 anaconda environment.

Verifies:
1. query.py no longer has embed_query calls (embedding reused from retrieval result)
2. chat.py no longer has embed_query calls (embedding reused from retrieval result)
3. query.py reuses retrieval_result["query_embedding"]
4. chat.py reuses retrieval_result["query_embedding"]
5. query.py runs authority + compass in parallel via asyncio.gather
6. default.yaml uses gpt-4.1-mini for all three generation stages
"""
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]  # backend/
_QUERY_SRC = (_BACKEND_ROOT / "app" / "routers" / "query.py").read_text(encoding="utf-8")
_CHAT_SRC = (_BACKEND_ROOT / "app" / "routers" / "chat.py").read_text(encoding="utf-8")
_YAML_SRC = (_BACKEND_ROOT / "config" / "default.yaml").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: query.py — no redundant embed_query call
# ---------------------------------------------------------------------------

def test_query_py_no_double_embed():
    """query.py must not call embed_query; embedding must be reused from retrieval result."""
    assert "embed_query" not in _QUERY_SRC, (
        "query.py still calls embed_query — this is a redundant embedding call. "
        "The query_embedding should be reused from retrieval_result['query_embedding']."
    )


# ---------------------------------------------------------------------------
# Test 2: chat.py — no redundant embed_query call
# ---------------------------------------------------------------------------

def test_chat_py_no_double_embed():
    """chat.py must not call embed_query; embedding must be reused from retrieval result."""
    assert "embed_query" not in _CHAT_SRC, (
        "chat.py still calls embed_query — this is a redundant embedding call. "
        "The query_embedding should be reused from retrieval_result['query_embedding']."
    )


# ---------------------------------------------------------------------------
# Test 3: query.py — uses retrieval_result["query_embedding"]
# ---------------------------------------------------------------------------

def test_query_py_uses_retrieval_result_embedding():
    """query.py must assign query_embedding from retrieval_result, not from embed_query."""
    has_double_quotes = 'retrieval_result["query_embedding"]' in _QUERY_SRC
    has_single_quotes = "retrieval_result['query_embedding']" in _QUERY_SRC
    assert has_double_quotes or has_single_quotes, (
        "query.py must read query_embedding from retrieval_result "
        "(retrieval_result[\"query_embedding\"]) to eliminate the redundant embedding call."
    )


# ---------------------------------------------------------------------------
# Test 4: chat.py — uses retrieval_result["query_embedding"]
# ---------------------------------------------------------------------------

def test_chat_py_uses_retrieval_result_embedding():
    """chat.py must assign query_embedding from retrieval_result, not from embed_query."""
    has_double_quotes = 'retrieval_result["query_embedding"]' in _CHAT_SRC
    has_single_quotes = "retrieval_result['query_embedding']" in _CHAT_SRC
    assert has_double_quotes or has_single_quotes, (
        "chat.py must read query_embedding from retrieval_result "
        "(retrieval_result[\"query_embedding\"]) to eliminate the redundant embedding call."
    )


# ---------------------------------------------------------------------------
# Test 5: query.py — authority and compass run in parallel
# ---------------------------------------------------------------------------

def test_query_py_parallel_authority_compass():
    """query.py must use asyncio.gather to run authority scoring and compass in parallel."""
    assert "asyncio.gather" in _QUERY_SRC, (
        "query.py must use asyncio.gather to execute authority scoring and compass "
        "concurrently. Currently they appear to be running sequentially."
    )


# ---------------------------------------------------------------------------
# Test 6: default.yaml — all three generation stages use gpt-4.1-mini
# ---------------------------------------------------------------------------

def test_models_are_gpt41_mini():
    """All three generation model entries must specify gpt-4.1-mini."""
    assert 'analyst: "gpt-4.1-mini"' in _YAML_SRC, (
        "default.yaml: analyst model must be gpt-4.1-mini for ~12x cost reduction vs gpt-4o"
    )
    assert 'writer: "gpt-4.1-mini"' in _YAML_SRC, (
        "default.yaml: writer model must be gpt-4.1-mini for ~12x cost reduction vs gpt-4o"
    )
    assert 'integrator: "gpt-4.1-mini"' in _YAML_SRC, (
        "default.yaml: integrator model must be gpt-4.1-mini for ~12x cost reduction vs gpt-4o"
    )
