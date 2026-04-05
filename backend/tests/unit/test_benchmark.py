"""
Smoke tests for the benchmark pipeline script and related engine changes.

Uses source-file inspection (not live imports) to avoid the scipy/NumPy 2.x
import chain breakage in the Python 3.12 anaconda environment.

Verifies:
1. benchmark_pipeline.py parses without syntax errors
2. PRICE_TABLE constant is present
3. All 7 required metrics are captured
4. Script loads evaluation_set.json
5. engine.py retrieve_sync return dict contains the "query_embedding" key
6. baseline_before_opt.json exists (pre-optimization snapshot captured)
"""
import ast
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]  # backend/
_BENCHMARK_SRC = (_BACKEND_ROOT / "scripts" / "benchmark_pipeline.py").read_text(encoding="utf-8")
_ENGINE_SRC = (_BACKEND_ROOT / "app" / "services" / "retrieval" / "engine.py").read_text(encoding="utf-8")
_BASELINE_PATH = _BACKEND_ROOT / "benchmark_results" / "baseline_before_opt.json"


# ---------------------------------------------------------------------------
# Test 1: Syntax
# ---------------------------------------------------------------------------

def test_benchmark_script_syntax():
    """benchmark_pipeline.py must parse without SyntaxError."""
    # Will raise SyntaxError on failure, which pytest catches as an error
    tree = ast.parse(_BENCHMARK_SRC)
    assert tree is not None, "AST parse returned None unexpectedly"


# ---------------------------------------------------------------------------
# Test 2: PRICE_TABLE
# ---------------------------------------------------------------------------

def test_benchmark_has_price_table():
    """PRICE_TABLE dict must be present in benchmark_pipeline.py."""
    assert "PRICE_TABLE" in _BENCHMARK_SRC, (
        "benchmark_pipeline.py must define PRICE_TABLE with per-model pricing"
    )


# ---------------------------------------------------------------------------
# Test 3: All metric names captured
# ---------------------------------------------------------------------------

def test_benchmark_captures_all_metrics():
    """All 7 required metric names must appear in benchmark_pipeline.py."""
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


# ---------------------------------------------------------------------------
# Test 4: Loads evaluation_set.json
# ---------------------------------------------------------------------------

def test_benchmark_loads_evaluation_set():
    """benchmark_pipeline.py must reference evaluation_set.json."""
    assert "evaluation_set.json" in _BENCHMARK_SRC, (
        "benchmark_pipeline.py must load evaluation_set.json as the topic source"
    )


# ---------------------------------------------------------------------------
# Test 5: engine.py returns query_embedding
# ---------------------------------------------------------------------------

def test_engine_returns_query_embedding():
    """
    retrieve_sync return dict in engine.py must contain the 'query_embedding' key.

    Checks that the string 'query_embedding' appears in the return dict
    (source-level: the key assignment pattern).
    """
    # The key must appear as a string constant in the AST
    tree = ast.parse(_ENGINE_SRC)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "query_embedding":
            found = True
            break

    assert found, (
        "engine.py retrieve_sync return dict must include 'query_embedding' key "
        "so callers can reuse the embedding without re-computing it"
    )


# ---------------------------------------------------------------------------
# Test 6: Baseline snapshot exists
# ---------------------------------------------------------------------------

def test_baseline_before_opt_exists():
    """
    backend/benchmark_results/baseline_before_opt.json must exist.

    Confirms the pre-optimization baseline metrics were captured
    (or a placeholder was written if services were unavailable).
    """
    assert _BASELINE_PATH.exists(), (
        f"baseline_before_opt.json not found at {_BASELINE_PATH}. "
        "Run: python scripts/benchmark_pipeline.py --output benchmark_results/baseline_before_opt.json"
    )
    assert _BASELINE_PATH.stat().st_size > 10, (
        "baseline_before_opt.json appears empty — benchmark may not have run"
    )
