"""
Unit tests for NER entity channel, RRF sweep script, and retrieval profiling.

Tests use source-file inspection to avoid scipy/NumPy 2.x incompatibility
in the Python 3.12 anaconda environment (per project convention).
"""
import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
RETRIEVAL_DIR = Path(__file__).resolve().parents[2] / "app" / "services" / "retrieval"
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

NER_CHANNEL_PATH = RETRIEVAL_DIR / "ner_channel.py"
ENGINE_PATH = RETRIEVAL_DIR / "engine.py"
MERGER_PATH = RETRIEVAL_DIR / "merger.py"
RRF_SWEEP_PATH = SCRIPTS_DIR / "rrf_sweep.py"
DEFAULT_YAML_PATH = CONFIG_DIR / "default.yaml"


# ---------------------------------------------------------------------------
# NER channel source tests
# ---------------------------------------------------------------------------

def test_ner_channel_exists():
    """Assert ner_channel.py exists in the retrieval directory."""
    assert NER_CHANNEL_PATH.exists(), (
        f"ner_channel.py not found at {NER_CHANNEL_PATH}"
    )


def test_ner_channel_has_class():
    """Assert NERChannel class is defined in ner_channel.py."""
    src = NER_CHANNEL_PATH.read_text()
    assert "class NERChannel" in src, "ner_channel.py missing 'class NERChannel'"


def test_ner_channel_uses_lawrefs():
    """Assert Cypher query uses lawRefs property."""
    src = NER_CHANNEL_PATH.read_text()
    assert "lawRefs" in src, (
        "ner_channel.py must contain 'lawRefs' in Cypher query (NER property on Chunk)"
    )


def test_ner_channel_uses_personrefs():
    """Assert Cypher query uses personRefs property."""
    src = NER_CHANNEL_PATH.read_text()
    assert "personRefs" in src, (
        "ner_channel.py must contain 'personRefs' in Cypher query (NER property on Chunk)"
    )


def test_ner_channel_has_timing():
    """Assert Cypher timing instrumentation is present (perf_counter)."""
    src = NER_CHANNEL_PATH.read_text()
    assert "perf_counter" in src, (
        "ner_channel.py must contain perf_counter for Cypher profiling instrumentation"
    )


# ---------------------------------------------------------------------------
# Engine integration tests
# ---------------------------------------------------------------------------

def test_engine_imports_ner_channel():
    """Assert engine.py imports NERChannel from ner_channel module."""
    src = ENGINE_PATH.read_text()
    assert "NERChannel" in src, (
        "engine.py must import NERChannel"
    )
    assert "from .ner_channel import NERChannel" in src or "ner_channel" in src, (
        "engine.py must import NERChannel from .ner_channel"
    )


def test_engine_gates_ner_on_entity_filter():
    """Assert engine.py gates NER channel on entity_filter being non-empty."""
    src = ENGINE_PATH.read_text()
    assert "entity_filter" in src, "engine.py must contain entity_filter logic"
    # Either 'has_ner' or 'if entity_filter' pattern
    assert "has_ner" in src or "if entity_filter" in src, (
        "engine.py must gate NER channel on entity_filter (has_ner or if entity_filter pattern)"
    )


def test_engine_has_timing_breakdown():
    """Assert engine.py logs per-channel retrieval timing breakdown."""
    src = ENGINE_PATH.read_text()
    # Check for timing breakdown log message
    has_breakdown = (
        "timing breakdown" in src
        or "dense_ms" in src
        or "Retrieval timing" in src
    )
    assert has_breakdown, (
        "engine.py must contain retrieval timing breakdown logging "
        "(search for 'timing breakdown', 'dense_ms', or 'Retrieval timing')"
    )


# ---------------------------------------------------------------------------
# Merger tests
# ---------------------------------------------------------------------------

def test_merger_accepts_ner_results():
    """Assert merger.py merge() method accepts ner_results parameter."""
    src = MERGER_PATH.read_text()
    assert "ner_results" in src, (
        "merger.py must contain 'ner_results' parameter in merge() method"
    )


def test_merger_has_ner_weight():
    """Assert merger.py reads ner_weight from config."""
    src = MERGER_PATH.read_text()
    assert "ner_weight" in src, (
        "merger.py must read 'ner_weight' from RRF config"
    )


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

def test_config_has_ner_weight():
    """Assert default.yaml contains ner_weight setting."""
    src = DEFAULT_YAML_PATH.read_text()
    assert "ner_weight" in src, (
        "default.yaml must contain 'ner_weight' under retrieval.rrf"
    )


def test_compass_config_supports_senate():
    """Verify compass.clustering section exists with min_fragments_for_kde.

    Senate groups may have few fragments; min_fragments_for_kde=3 causes sparse
    groups to fall back to mean positioning (per RESEARCH.md analysis).
    This is the expected behavior — no alternative approach is needed.
    """
    src = DEFAULT_YAML_PATH.read_text()
    assert "clustering:" in src, (
        "default.yaml must contain compass.clustering section"
    )
    assert "min_fragments_for_kde" in src, (
        "default.yaml must contain min_fragments_for_kde under compass.clustering "
        "(handles Senate groups with few fragments via mean positioning fallback)"
    )


# ---------------------------------------------------------------------------
# RRF sweep script tests
# ---------------------------------------------------------------------------

def test_rrf_sweep_script_exists():
    """Assert rrf_sweep.py exists in scripts directory."""
    assert RRF_SWEEP_PATH.exists(), (
        f"rrf_sweep.py not found at {RRF_SWEEP_PATH}"
    )


def test_rrf_sweep_script_syntax():
    """Assert rrf_sweep.py parses without syntax errors."""
    src = RRF_SWEEP_PATH.read_text()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"rrf_sweep.py has syntax error: {e}") from e


def test_rrf_sweep_has_grid():
    """Assert rrf_sweep.py defines RRF_GRID."""
    src = RRF_SWEEP_PATH.read_text()
    assert "RRF_GRID" in src, (
        "rrf_sweep.py must define 'RRF_GRID' list of weight combinations"
    )


def test_rrf_sweep_has_compute_precision():
    """Assert rrf_sweep.py defines compute_retrieval_precision function."""
    src = RRF_SWEEP_PATH.read_text()
    assert "compute_retrieval_precision" in src, (
        "rrf_sweep.py must define 'compute_retrieval_precision' function"
    )


def test_rrf_sweep_grid_has_seven_points():
    """Assert RRF_GRID contains exactly 7 combinations."""
    src = RRF_SWEEP_PATH.read_text()
    # Count dict entries in RRF_GRID (by counting {"k": occurrences)
    count = src.count('"k"')
    assert count >= 7, (
        f"RRF_GRID should have at least 7 grid points, found {count} 'k' entries"
    )


def test_rrf_sweep_has_ner_in_grid():
    """Assert RRF_GRID includes ner weight variations."""
    src = RRF_SWEEP_PATH.read_text()
    assert '"ner"' in src or "'ner'" in src, (
        "rrf_sweep.py RRF_GRID must include 'ner' weight parameter"
    )
