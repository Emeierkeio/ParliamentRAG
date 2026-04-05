"""
Comprehensive Phase 7 pipeline optimization validation test suite.

Acts as a final checklist — a single file that confirms every Phase 7
optimization is in place via source-file inspection (no live imports).

Tests:
  Model optimization (tests 1-3)
  Latency optimization (tests 4-7)
  Retrieval optimization (tests 8-12)
  Benchmark infrastructure (tests 13-16)
  Compass (test 17)
  Neo4j profiling (tests 18-19)

Convention: uses Path(__file__).resolve().parent.parent.parent for all
path computation (backend root = three levels up from this file).
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[2]  # backend/

_YAML_SRC = (_BACKEND_ROOT / "config" / "default.yaml").read_text(encoding="utf-8")
_ENGINE_SRC = (_BACKEND_ROOT / "app" / "services" / "retrieval" / "engine.py").read_text(encoding="utf-8")
_MERGER_SRC = (_BACKEND_ROOT / "app" / "services" / "retrieval" / "merger.py").read_text(encoding="utf-8")
_NER_SRC = (_BACKEND_ROOT / "app" / "services" / "retrieval" / "ner_channel.py").read_text(encoding="utf-8")
_QUERY_SRC = (_BACKEND_ROOT / "app" / "routers" / "query.py").read_text(encoding="utf-8")
_CHAT_SRC = (_BACKEND_ROOT / "app" / "routers" / "chat.py").read_text(encoding="utf-8")
_BENCHMARK_SRC = (_BACKEND_ROOT / "scripts" / "benchmark_pipeline.py").read_text(encoding="utf-8")

_NER_CHANNEL_PATH = _BACKEND_ROOT / "app" / "services" / "retrieval" / "ner_channel.py"
_BENCHMARK_PATH = _BACKEND_ROOT / "scripts" / "benchmark_pipeline.py"
_RRF_SWEEP_PATH = _BACKEND_ROOT / "scripts" / "rrf_sweep.py"
_BASELINE_PATH = _BACKEND_ROOT / "benchmark_results" / "baseline_before_opt.json"


# ===========================================================================
# MODEL OPTIMIZATION TESTS
# ===========================================================================

def test_all_models_are_mini():
    """All three generation stages must use gpt-4.1-mini (analyst, writer, integrator)."""
    assert 'analyst: "gpt-4.1-mini"' in _YAML_SRC, (
        "default.yaml: analyst model must be gpt-4.1-mini (~12x cost reduction vs gpt-4o)"
    )
    assert 'writer: "gpt-4.1-mini"' in _YAML_SRC, (
        "default.yaml: writer model must be gpt-4.1-mini (~12x cost reduction vs gpt-4o)"
    )
    assert 'integrator: "gpt-4.1-mini"' in _YAML_SRC, (
        "default.yaml: integrator model must be gpt-4.1-mini (~12x cost reduction vs gpt-4o)"
    )


def test_embedding_model_unchanged():
    """Embedding model must remain text-embedding-3-small (must NOT have been changed)."""
    assert 'embedding_model: "text-embedding-3-small"' in _YAML_SRC, (
        "default.yaml: embedding_model must be text-embedding-3-small — "
        "changing this would invalidate all cached embeddings in Neo4j"
    )


def test_query_rewriter_model_unchanged():
    """Query rewriting model must remain gpt-4o-mini (NOT changed to gpt-4.1-mini)."""
    assert 'model: "gpt-4o-mini"' in _YAML_SRC, (
        "default.yaml: query_rewriting model must remain gpt-4o-mini — "
        "it was intentionally kept separate from the generation stage model swap"
    )


# ===========================================================================
# LATENCY OPTIMIZATION TESTS
# ===========================================================================

def test_no_embed_query_in_routers():
    """Neither query.py nor chat.py must call embed_query (embedding is reused from retrieval)."""
    query_calls = _QUERY_SRC.count("embed_query")
    chat_calls = _CHAT_SRC.count("embed_query")
    total = query_calls + chat_calls
    assert total == 0, (
        f"Found {query_calls} embed_query call(s) in query.py and "
        f"{chat_calls} call(s) in chat.py. "
        "Embedding must be reused from retrieval_result['query_embedding'] "
        "to eliminate ~300ms duplicate embed_query call."
    )


def test_query_embedding_reused():
    """query.py must read query_embedding from retrieval_result dict (not recompute it)."""
    has_double_quotes = 'retrieval_result["query_embedding"]' in _QUERY_SRC
    has_single_quotes = "retrieval_result['query_embedding']" in _QUERY_SRC
    assert has_double_quotes or has_single_quotes, (
        "query.py must assign query_embedding from retrieval_result dict "
        "(retrieval_result[\"query_embedding\"]) to avoid duplicate embedding computation."
    )


def test_authority_compass_parallel():
    """query.py must run authority scoring and compass in parallel via asyncio.gather."""
    assert "asyncio.gather" in _QUERY_SRC, (
        "query.py must use asyncio.gather to execute authority scoring and compass "
        "concurrently — they have no mutual dependency, so sequential execution wastes time."
    )


def test_engine_returns_query_embedding():
    """engine.py retrieve_sync return dict must contain the 'query_embedding' key."""
    assert '"query_embedding"' in _ENGINE_SRC, (
        "engine.py retrieve_sync return dict must include 'query_embedding' key "
        "so callers can reuse the embedding without re-computing it."
    )


# ===========================================================================
# RETRIEVAL OPTIMIZATION TESTS
# ===========================================================================

def test_ner_channel_module_exists():
    """ner_channel.py must exist in the retrieval directory."""
    assert _NER_CHANNEL_PATH.exists(), (
        f"ner_channel.py not found at {_NER_CHANNEL_PATH}. "
        "The NER entity retrieval channel (Plan 07-03) must be created."
    )


def test_ner_channel_integrated_in_engine():
    """engine.py must import and instantiate NERChannel."""
    assert "NERChannel" in _ENGINE_SRC, (
        "engine.py must import NERChannel from ner_channel module."
    )
    assert "ner_channel" in _ENGINE_SRC, (
        "engine.py must instantiate self.ner_channel = NERChannel(...) "
        "to activate the 4th retrieval channel."
    )


def test_ner_channel_gated():
    """engine.py must gate NER channel execution on entity_filter being non-empty."""
    assert "entity_filter" in _ENGINE_SRC, (
        "engine.py must implement entity_filter logic for NER gating."
    )
    # NER must only run conditionally — either via has_ner flag or if entity_filter check
    has_gate = "has_ner" in _ENGINE_SRC or "if entity_filter" in _ENGINE_SRC
    assert has_gate, (
        "engine.py must gate NER channel on entity_filter (has_ner or if entity_filter). "
        "NER must never fire for generic queries — it adds latency and only helps entity queries."
    )


def test_merger_supports_4_channels():
    """merger.py must accept ner_results parameter in the merge() signature."""
    assert "ner_results" in _MERGER_SRC, (
        "merger.py merge() method must accept 'ner_results' parameter "
        "to support the 4th NER entity retrieval channel."
    )


def test_config_has_ner_weight():
    """default.yaml must define ner_weight under retrieval.rrf."""
    assert "ner_weight" in _YAML_SRC, (
        "default.yaml must contain 'ner_weight' under retrieval.rrf "
        "to control the NER entity channel's contribution in RRF fusion."
    )


# ===========================================================================
# BENCHMARK INFRASTRUCTURE TESTS
# ===========================================================================

def test_benchmark_script_exists():
    """benchmark_pipeline.py must exist in the scripts directory."""
    assert _BENCHMARK_PATH.exists(), (
        f"benchmark_pipeline.py not found at {_BENCHMARK_PATH}. "
        "The pipeline benchmark harness (Plan 07-01) must be created."
    )


def test_rrf_sweep_script_exists():
    """rrf_sweep.py must exist in the scripts directory."""
    assert _RRF_SWEEP_PATH.exists(), (
        f"rrf_sweep.py not found at {_RRF_SWEEP_PATH}. "
        "The RRF weight sweep script (Plan 07-03) must be created."
    )


def test_benchmark_captures_all_metrics():
    """benchmark_pipeline.py must capture all 7 required metric names."""
    required_metrics = [
        "latency_total_s",
        "latency_retrieval_s",
        "latency_generation_s",
        "cost_estimate_usd",
        "citation_count",
        "parties_covered",
        "section_completeness",
    ]
    for metric in required_metrics:
        assert metric in _BENCHMARK_SRC, (
            f"benchmark_pipeline.py must capture metric '{metric}'"
        )


def test_baseline_before_opt_captured():
    """benchmark_results/baseline_before_opt.json must exist (pre-optimization baseline saved)."""
    assert _BASELINE_PATH.exists(), (
        f"baseline_before_opt.json not found at {_BASELINE_PATH}. "
        "Run: python scripts/benchmark_pipeline.py "
        "--output benchmark_results/baseline_before_opt.json"
    )
    assert _BASELINE_PATH.stat().st_size > 10, (
        "baseline_before_opt.json appears empty — benchmark may not have completed."
    )


# ===========================================================================
# COMPASS TESTS
# ===========================================================================

def test_compass_config_has_kde_settings():
    """default.yaml must contain min_fragments_for_kde to support sparse Senate groups."""
    assert "min_fragments_for_kde" in _YAML_SRC, (
        "default.yaml must contain 'min_fragments_for_kde' under compass.clustering. "
        "Senate groups often have few fragments; this setting controls the KDE fallback "
        "to mean positioning for sparse groups."
    )


# ===========================================================================
# NEO4J PROFILING TESTS
# ===========================================================================

def test_ner_channel_has_cypher_timing():
    """ner_channel.py must use perf_counter for Cypher execution timing."""
    assert "perf_counter" in _NER_SRC, (
        "ner_channel.py must contain perf_counter for Cypher profiling instrumentation. "
        "This enables Neo4j query latency monitoring."
    )


def test_engine_has_retrieval_timing_breakdown():
    """engine.py must log per-channel retrieval timing breakdown."""
    has_breakdown = (
        "timing breakdown" in _ENGINE_SRC
        or "dense_ms" in _ENGINE_SRC
        or "Retrieval timing" in _ENGINE_SRC
    )
    assert has_breakdown, (
        "engine.py must contain retrieval timing breakdown logging "
        "(search for 'timing breakdown', 'dense_ms', or 'Retrieval timing'). "
        "This is required for Neo4j Cypher profiling."
    )
