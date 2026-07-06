"""
Unit tests for vote-based compass: party×vote matrix encoding, PCA shape, cache TTL.

Imports ONLY numpy and the vote_pipeline module (no scipy, no DB).

The anaconda Python 3.12 environment has a NumPy 2.x/scipy incompatibility.
The compass package __init__ imports pipeline.py → scipy.stats which crashes.
We pre-stub scipy submodules in sys.modules (established project pattern,
see test_new_endpoints.py and test_routers.py comments) so that the compass
package __init__ can be imported without triggering scipy's broken lazy-load chain.
"""
import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Pre-stub scipy submodules BEFORE any compass package import.
# This must happen at module level so it runs before the next import block.
# ---------------------------------------------------------------------------
_scipy_stats_mock = types.ModuleType("scipy.stats")
_scipy_optimize_mock = types.ModuleType("scipy.optimize")
_scipy_sparse_mock = types.ModuleType("scipy.sparse")
for _name in ("scipy.stats", "scipy.optimize", "scipy.sparse",
              "scipy.stats._stats_py", "scipy.stats.qmc",
              "scipy.sparse._csgraph", "scipy.sparse.linalg"):
    sys.modules.setdefault(_name, types.ModuleType(_name))

# Stub the compass submodules that import scipy so the package __init__
# doesn't crash when we import vote_pipeline.
for _mod_name in (
    "app.services.compass.scorer",
    "app.services.compass.anchors",
    "app.services.compass.clustering",
    "app.services.compass.pipeline",
    "app.services.compass.reference_axes",
    "app.services.compass.axis_labeling",
):
    sys.modules.setdefault(_mod_name, types.ModuleType(_mod_name))

# Provide the symbols that compass.__init__ re-exports, as MagicMock stubs.
sys.modules["app.services.compass.scorer"].IdeologyScorer = MagicMock()  # type: ignore[attr-defined]
sys.modules["app.services.compass.anchors"].AnchorManager = MagicMock()  # type: ignore[attr-defined]
sys.modules["app.services.compass.clustering"].IdeologyClustering = MagicMock()  # type: ignore[attr-defined]
sys.modules["app.services.compass.pipeline"].CompassPipeline = MagicMock()  # type: ignore[attr-defined]
sys.modules["app.services.compass.reference_axes"].ReferenceAxesRegistry = MagicMock()  # type: ignore[attr-defined]
sys.modules["app.services.compass.reference_axes"].REFERENCE_AXES = {}  # type: ignore[attr-defined]
sys.modules["app.services.compass.axis_labeling"].AxisLabeler = MagicMock()  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Now the real imports — numpy only + vote_pipeline
# ---------------------------------------------------------------------------
import numpy as np
import time

from app.services.compass.vote_pipeline import (
    build_party_vote_matrix,
    pca_2d,
    get_vote_compass,
    VOTE_COMPASS_TTL_SECONDS,
    _vote_compass_cache,
)
import app.services.compass.vote_pipeline as _vp_module


# ---------------------------------------------------------------------------
# test_party_vote_matrix
# ---------------------------------------------------------------------------

def test_party_vote_matrix():
    """Encoding: favor > against → 1.0; against > favor → 0.0; equal (incl. favor==against==0) → 0.5."""
    rows = [
        {"party": "A", "vote_id": "v1", "favor": 10, "against": 0, "abstain": 0},
        {"party": "B", "vote_id": "v1", "favor": 0, "against": 8, "abstain": 0},
        {"party": "C", "vote_id": "v1", "favor": 5, "against": 5, "abstain": 0},  # tie → 0.5
        {"party": "A", "vote_id": "v2", "favor": 0, "against": 0, "abstain": 0},  # total==0 → 0.5
        {"party": "B", "vote_id": "v2", "favor": 3, "against": 7, "abstain": 0},  # against > favor → 0.0
        {"party": "C", "vote_id": "v2", "favor": 0, "against": 0, "abstain": 4},  # only abstain, equal → 0.5
    ]

    matrix, parties, votes = build_party_vote_matrix(rows)

    # parties and votes are sorted
    assert parties == sorted(set(r["party"] for r in rows))
    assert votes == sorted(set(r["vote_id"] for r in rows))

    pa = parties.index("A")
    pb = parties.index("B")
    pc = parties.index("C")
    v1 = votes.index("v1")
    v2 = votes.index("v2")

    # A on v1: favor=10, against=0 → 1.0
    assert matrix[pa, v1] == 1.0
    # B on v1: favor=0, against=8 → 0.0
    assert matrix[pb, v1] == 0.0
    # C on v1: favor==against (5==5) → 0.5
    assert matrix[pc, v1] == 0.5
    # A on v2: total==0 → default 0.5 (continue branch)
    assert matrix[pa, v2] == 0.5
    # B on v2: against > favor → 0.0
    assert matrix[pb, v2] == 0.0
    # C on v2: only abstain (favor=0 == against=0) → 0.5
    assert matrix[pc, v2] == 0.5

    assert matrix.shape == (3, 2)
    assert matrix.dtype.kind == "f"


# ---------------------------------------------------------------------------
# test_pca_shape
# ---------------------------------------------------------------------------

def test_pca_shape():
    """coords.shape == (n_parties, 2) and sum(variance_explained) <= 1.0 + 1e-9."""
    n_parties = 5
    n_votes = 10
    rng = np.random.default_rng(42)
    matrix = rng.random((n_parties, n_votes))

    coords, variance_explained = pca_2d(matrix)

    assert coords.shape == (n_parties, 2), f"Expected shape ({n_parties}, 2), got {coords.shape}"
    assert sum(variance_explained) <= 1.0 + 1e-9, (
        f"variance_explained sum {sum(variance_explained)} > 1 + 1e-9"
    )


def test_pca_shape_guard_too_small():
    """Guard: matrix with < 2 rows returns zeros and empty variance list."""
    matrix = np.array([[0.5, 1.0, 0.0]])  # 1 row, 3 cols

    coords, variance_explained = pca_2d(matrix)

    assert coords.shape == (1, 2)
    assert variance_explained == []
    assert np.all(coords == 0)


# ---------------------------------------------------------------------------
# test_compass_cache
# ---------------------------------------------------------------------------

def test_compass_cache(monkeypatch):
    """Two get_vote_compass calls within TTL invoke _compute_vote_compass only once."""
    call_count = {"n": 0}

    fake_result = {
        "available": True,
        "legislature": 19,
        "chamber": "camera",
        "parties": [],
        "variance_explained": [],
    }

    def fake_compute(legislature, chamber, neo4j):
        call_count["n"] += 1
        return fake_result

    monkeypatch.setattr(_vp_module, "_compute_vote_compass", fake_compute)
    _vote_compass_cache.clear()

    # First call — must hit _compute_vote_compass
    result1 = get_vote_compass(19, "camera", neo4j=None)
    assert call_count["n"] == 1

    # Second call within TTL — must return cached result without recomputing
    result2 = get_vote_compass(19, "camera", neo4j=None)
    assert call_count["n"] == 1, "Cache miss: _compute_vote_compass called twice within TTL"

    assert result1 is result2 or result1 == result2


def test_compass_cache_expires(monkeypatch):
    """After TTL expiry, cache recomputes."""
    call_count = {"n": 0}

    fake_result = {
        "available": True,
        "legislature": 19,
        "chamber": "senato",
        "parties": [],
        "variance_explained": [],
    }

    def fake_compute(legislature, chamber, neo4j):
        call_count["n"] += 1
        return fake_result

    monkeypatch.setattr(_vp_module, "_compute_vote_compass", fake_compute)
    _vote_compass_cache.clear()
    monkeypatch.setattr(_vp_module, "VOTE_COMPASS_TTL_SECONDS", 0)

    get_vote_compass(19, "senato", neo4j=None)
    assert call_count["n"] == 1

    time.sleep(0.01)

    get_vote_compass(19, "senato", neo4j=None)
    assert call_count["n"] == 2, "Cache should have expired and recomputed"
