"""
Unit tests for the new data endpoints in app.routers.data.

Tests GET /api/data/sessions/{id}/votes and GET /api/data/debates/{id}/acts.

The test environment uses Python 3.12 (anaconda) where scipy/NumPy 2.x is broken,
so any import that transitively loads compass.py (via app.services.deps) will fail.

Strategy:
  - Structural tests: source-file inspection only (no live imports)
  - Functional tests: pre-stub the problematic modules in sys.modules before
    importing the data router, then run FastAPI TestClient against a minimal app.
    This pattern matches the project's established approach for this environment.
"""
import re
import sys
import types
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/


def _read_source(relative_path: str) -> str:
    """Read a source file relative to backend/."""
    return (_BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def _make_mock_neo4j(return_value: list) -> MagicMock:
    mock = MagicMock()
    mock.query.return_value = return_value
    return mock


def _build_test_app_with_stubs(mock_neo4j: MagicMock):
    """
    Build a minimal FastAPI test app for the data router, injecting stubs for
    the problematic scipy/neo4j import chain.

    Steps:
    1. Create stub modules for app.services.neo4j_client and app.services.deps
       so that importing app.routers.data does not trigger scipy/pandas/neo4j.
    2. Import app.routers.data via importlib (bypassing app.routers.__init__).
    3. Override the get_neo4j_client dependency with our mock.
    """
    backend_str = str(_BACKEND_ROOT)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    # --- Stub: app.services.neo4j_client ---
    stub_client = types.ModuleType("app.services.neo4j_client")
    stub_client.Neo4jClient = MagicMock  # type stub, not called at import time
    sys.modules.setdefault("app.services.neo4j_client", stub_client)

    # --- Stub: app.services.deps ---
    stub_deps = types.ModuleType("app.services.deps")
    _get_neo4j_client_fn = MagicMock(return_value=mock_neo4j)
    stub_deps.get_neo4j_client = _get_neo4j_client_fn  # type: ignore
    sys.modules.setdefault("app.services.deps", stub_deps)

    # --- Stub: app (package) so sub-imports resolve without __init__ side-effects ---
    if "app" not in sys.modules:
        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = [str(_BACKEND_ROOT / "app")]  # type: ignore
        sys.modules["app"] = app_pkg
    if "app.services" not in sys.modules:
        svc_pkg = types.ModuleType("app.services")
        svc_pkg.__path__ = [str(_BACKEND_ROOT / "app" / "services")]  # type: ignore
        sys.modules["app.services"] = svc_pkg
    if "app.routers" not in sys.modules:
        r_pkg = types.ModuleType("app.routers")
        r_pkg.__path__ = [str(_BACKEND_ROOT / "app" / "routers")]  # type: ignore
        sys.modules["app.routers"] = r_pkg

    # --- Load app.routers.data directly ---
    module_key = "app.routers.data"
    # Remove cached version so re-runs get a fresh module
    sys.modules.pop(module_key, None)
    spec = importlib.util.spec_from_file_location(
        module_key,
        _BACKEND_ROOT / "app" / "routers" / "data.py",
    )
    data_module = importlib.util.module_from_spec(spec)
    sys.modules[module_key] = data_module
    spec.loader.exec_module(data_module)

    # --- Build minimal FastAPI app ---
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    mini_app = FastAPI()
    mini_app.include_router(data_module.router)
    # Override the dependency: FastAPI resolves it by identity of the callable
    mini_app.dependency_overrides[data_module.get_neo4j_client] = lambda: mock_neo4j

    return mini_app, data_module


# ---------------------------------------------------------------------------
# Structural tests (source inspection — no live imports)
# ---------------------------------------------------------------------------

class TestDataRouterStructure:
    """Verify data.py router structure via source inspection."""

    def test_data_py_exists(self):
        path = _BACKEND_ROOT / "app/routers/data.py"
        assert path.exists(), "backend/app/routers/data.py must exist"

    def test_contains_get_session_votes(self):
        source = _read_source("app/routers/data.py")
        assert "get_session_votes" in source, (
            "data.py must define get_session_votes endpoint"
        )

    def test_contains_get_debate_acts(self):
        source = _read_source("app/routers/data.py")
        assert "get_debate_acts" in source, (
            "data.py must define get_debate_acts endpoint"
        )

    def test_uses_get_neo4j_client_depends(self):
        source = _read_source("app/routers/data.py")
        assert re.search(r"Depends\(get_neo4j_client\)", source), (
            "data.py must use Depends(get_neo4j_client) for DI"
        )

    def test_imports_from_app_services_deps(self):
        source = _read_source("app/routers/data.py")
        assert "from app.services.deps import get_neo4j_client" in source, (
            "data.py must import get_neo4j_client from app.services.deps"
        )

    def test_main_registers_data_router(self):
        source = _read_source("app/main.py")
        assert "data_router" in source, (
            "main.py must import and register data_router"
        )

    def test_data_router_has_votes_path(self):
        source = _read_source("app/routers/data.py")
        assert "/votes" in source, (
            "data.py must define a route ending in /votes"
        )

    def test_data_router_has_acts_path(self):
        source = _read_source("app/routers/data.py")
        assert "/acts" in source, (
            "data.py must define a route ending in /acts"
        )

    def test_has_vote_relation_in_cypher(self):
        source = _read_source("app/routers/data.py")
        assert "HAS_VOTE" in source, (
            "data.py must query the HAS_VOTE relationship"
        )

    def test_has_discusses_relation_in_cypher(self):
        source = _read_source("app/routers/data.py")
        assert "DISCUSSES" in source, (
            "data.py must query the DISCUSSES relationship"
        )


# ---------------------------------------------------------------------------
# Functional tests (stub-based minimal FastAPI test app)
# ---------------------------------------------------------------------------

class TestGetSessionVotes:
    """Tests for GET /api/data/sessions/{session_id}/votes."""

    def test_get_session_votes_returns_list(self):
        """Should return 200 with vote records when Neo4j returns data."""
        from fastapi.testclient import TestClient

        sample_votes = [
            {
                "id": "vote-001",
                "number": 1,
                "type": "palese",
                "subject": "Approvazione ordine del giorno",
                "in_favor": 200,
                "against": 150,
                "abstained": 10,
                "outcome": "approvato",
                "present": 360,
                "voters": 350,
                "majority": 176,
                "on_mission": 5,
            },
        ]
        mock_neo4j = _make_mock_neo4j(sample_votes)
        mini_app, _ = _build_test_app_with_stubs(mock_neo4j)
        client = TestClient(mini_app, raise_server_exceptions=True)

        response = client.get("/api/data/sessions/session-123/votes")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "vote-001"
        assert data[0]["in_favor"] == 200
        mock_neo4j.query.assert_called_once()
        call_params = mock_neo4j.query.call_args[0][1]
        assert call_params == {"session_id": "session-123"}

    def test_get_session_votes_empty(self):
        """Should return 200 with empty list when session has no votes."""
        from fastapi.testclient import TestClient

        mock_neo4j = _make_mock_neo4j([])
        mini_app, _ = _build_test_app_with_stubs(mock_neo4j)
        client = TestClient(mini_app, raise_server_exceptions=True)

        response = client.get("/api/data/sessions/session-no-votes/votes")

        assert response.status_code == 200
        assert response.json() == []


class TestGetDebateActs:
    """Tests for GET /api/data/debates/{debate_id}/acts."""

    def test_get_debate_acts_returns_list(self):
        """Should return 200 with act records when Neo4j returns data."""
        from fastapi.testclient import TestClient

        sample_acts = [
            {
                "id": "act-001",
                "title": "Disegno di legge n. 1234",
                "is_placeholder": False,
            },
            {
                "id": "act-002",
                "title": "Mozione urgente",
                "is_placeholder": True,
            },
        ]
        mock_neo4j = _make_mock_neo4j(sample_acts)
        mini_app, _ = _build_test_app_with_stubs(mock_neo4j)
        client = TestClient(mini_app, raise_server_exceptions=True)

        response = client.get("/api/data/debates/debate-456/acts")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "act-001"
        assert data[1]["is_placeholder"] is True
        mock_neo4j.query.assert_called_once()
        call_params = mock_neo4j.query.call_args[0][1]
        assert call_params == {"debate_id": "debate-456"}

    def test_get_debate_acts_empty(self):
        """Should return 200 with empty list when debate has no acts."""
        from fastapi.testclient import TestClient

        mock_neo4j = _make_mock_neo4j([])
        mini_app, _ = _build_test_app_with_stubs(mock_neo4j)
        client = TestClient(mini_app, raise_server_exceptions=True)

        response = client.get("/api/data/debates/debate-no-acts/acts")

        assert response.status_code == 200
        assert response.json() == []
