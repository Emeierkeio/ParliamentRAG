"""
Unit tests for the DI (dependency injection) layer in app.services.deps.

Verifies:
- @lru_cache functions return the same singleton object on repeated calls
- get_services() backward-compat wrapper returns a dict with all expected keys
- search.py and evidence.py do NOT have module-level _neo4j_client globals
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings_mock():
    """Return a mock Settings object with required Neo4j fields."""
    s = MagicMock()
    s.neo4j_uri = "bolt://localhost:7687"
    s.neo4j_user = "neo4j"
    s.neo4j_password = "test"
    return s


def _clear_all_caches():
    """Clear all lru_cache caches in deps to prevent cross-test pollution."""
    from app.services import deps
    deps.get_neo4j_client.cache_clear()
    deps.get_retrieval_engine.cache_clear()
    deps.get_authority_scorer.cache_clear()
    deps.get_ideology_scorer.cache_clear()
    deps.get_generation_pipeline.cache_clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetNeo4jClientSingleton:
    """get_neo4j_client() must return the same object on repeated calls."""

    def setup_method(self):
        _clear_all_caches()

    def teardown_method(self):
        _clear_all_caches()

    def test_get_neo4j_client_returns_singleton(self):
        with patch("app.services.deps.get_settings", return_value=_make_settings_mock()):
            with patch("app.services.deps.Neo4jClient") as MockClient:
                MockClient.return_value = MagicMock()
                from app.services.deps import get_neo4j_client
                first = get_neo4j_client()
                second = get_neo4j_client()
                assert first is second, "get_neo4j_client() must return the same singleton"
                # Constructor called exactly once
                assert MockClient.call_count == 1


class TestGetRetrievalEngineSingleton:
    """get_retrieval_engine() must return the same object on repeated calls."""

    def setup_method(self):
        _clear_all_caches()

    def teardown_method(self):
        _clear_all_caches()

    def test_get_retrieval_engine_returns_singleton(self):
        mock_neo4j = MagicMock()
        with patch("app.services.deps.get_settings", return_value=_make_settings_mock()):
            with patch("app.services.deps.Neo4jClient", return_value=mock_neo4j):
                with patch("app.services.deps.RetrievalEngine") as MockEngine:
                    MockEngine.return_value = MagicMock()
                    from app.services.deps import get_retrieval_engine
                    first = get_retrieval_engine()
                    second = get_retrieval_engine()
                    assert first is second, "get_retrieval_engine() must return the same singleton"
                    assert MockEngine.call_count == 1


class TestGetServicesBackwardCompat:
    """get_services() must return a dict with all required service keys."""

    def setup_method(self):
        _clear_all_caches()

    def teardown_method(self):
        _clear_all_caches()

    def test_get_services_backward_compat(self):
        with patch("app.services.deps.get_settings", return_value=_make_settings_mock()):
            with patch("app.services.deps.Neo4jClient", return_value=MagicMock()):
                with patch("app.services.deps.RetrievalEngine", return_value=MagicMock()):
                    with patch("app.services.deps.AuthorityScorer", return_value=MagicMock()):
                        with patch("app.services.deps.IdeologyScorer", return_value=MagicMock()):
                            with patch("app.services.deps.GenerationPipeline", return_value=MagicMock()):
                                from app.services.deps import get_services
                                services = get_services()
                                assert isinstance(services, dict), "get_services() must return a dict"
                                required_keys = {"neo4j", "retrieval", "authority", "ideology", "generation"}
                                assert required_keys == set(services.keys()), (
                                    f"get_services() missing keys: {required_keys - set(services.keys())}"
                                )


class TestNoLocalClientInRouters:
    """Routers must not have module-level _neo4j_client globals."""

    def test_search_router_no_local_client(self):
        import inspect
        import app.routers.search as search_module
        source = inspect.getsource(search_module)
        # The module must not declare a module-level _neo4j_client variable.
        # A bare assignment like `_neo4j_client: Optional[...] = None` or
        # `_neo4j_client = None` would match; an import containing the
        # substring (e.g. `get_neo4j_client`) is allowed.
        import re
        assert not re.search(r"^_neo4j_client\s*[=:]", source, re.MULTILINE), (
            "search.py still contains a module-level _neo4j_client global"
        )

    def test_evidence_router_no_local_client(self):
        import inspect
        import app.routers.evidence as evidence_module
        source = inspect.getsource(evidence_module)
        import re
        assert not re.search(r"^_neo4j_client\s*[=:]", source, re.MULTILINE), (
            "evidence.py still contains a module-level _neo4j_client global"
        )

    def test_search_router_uses_get_neo4j_client(self):
        import inspect
        import app.routers.search as search_module
        source = inspect.getsource(search_module)
        assert "get_neo4j_client" in source, (
            "search.py must import and use get_neo4j_client from deps"
        )

    def test_evidence_router_uses_get_neo4j_client(self):
        import inspect
        import app.routers.evidence as evidence_module
        source = inspect.getsource(evidence_module)
        assert "get_neo4j_client" in source, (
            "evidence.py must import and use get_neo4j_client from deps"
        )
