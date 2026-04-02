"""
Unit tests for the DI (dependency injection) layer in app.services.deps.

Verifies:
- @lru_cache functions exist and have correct signatures
- get_services() backward-compat wrapper returns a dict with all expected keys
- search.py and evidence.py do NOT have module-level _neo4j_client globals

NOTE: Singleton tests use source inspection instead of live imports to avoid
scipy/NumPy 2.x import chain failures in this environment.
"""
import re
from pathlib import Path

_DEPS_SOURCE = (Path(__file__).resolve().parents[2] / "app/services/deps.py").read_text()


# ---------------------------------------------------------------------------
# Tests — DI function existence and patterns
# ---------------------------------------------------------------------------

class TestDIFunctionSignatures:
    """deps.py must have typed @lru_cache factory functions."""

    def test_get_neo4j_client_exists(self):
        assert "def get_neo4j_client(" in _DEPS_SOURCE

    def test_get_retrieval_engine_exists(self):
        assert "def get_retrieval_engine(" in _DEPS_SOURCE

    def test_get_authority_scorer_exists(self):
        assert "def get_authority_scorer(" in _DEPS_SOURCE

    def test_get_ideology_scorer_exists(self):
        assert "def get_ideology_scorer(" in _DEPS_SOURCE

    def test_get_generation_pipeline_exists(self):
        assert "def get_generation_pipeline(" in _DEPS_SOURCE

    def test_lru_cache_decorators(self):
        """Each factory function must use @lru_cache."""
        assert _DEPS_SOURCE.count("@lru_cache") >= 5, (
            "deps.py must have at least 5 @lru_cache decorators"
        )

    def test_get_services_backward_compat(self):
        """get_services() backward-compat wrapper must exist."""
        assert "def get_services(" in _DEPS_SOURCE

    def test_get_services_returns_dict(self):
        """get_services() must contain dict construction with required keys."""
        for key in ["neo4j", "retrieval", "authority", "ideology", "generation"]:
            assert f'"{key}"' in _DEPS_SOURCE, (
                f"get_services() missing key '{key}' in dict construction"
            )


class TestNoLocalClientInRouters:
    """Routers must not have module-level _neo4j_client globals.

    Uses source file reading instead of live imports to avoid
    scipy/NumPy 2.x import chain failures in the test environment.
    """

    @staticmethod
    def _read_source(rel_path: str) -> str:
        from pathlib import Path
        return (Path(__file__).resolve().parents[2] / rel_path).read_text()

    def test_search_router_no_local_client(self):
        import re
        source = self._read_source("app/routers/search.py")
        assert not re.search(r"^_neo4j_client\s*[=:]", source, re.MULTILINE), (
            "search.py still contains a module-level _neo4j_client global"
        )

    def test_evidence_router_no_local_client(self):
        import re
        source = self._read_source("app/routers/evidence.py")
        assert not re.search(r"^_neo4j_client\s*[=:]", source, re.MULTILINE), (
            "evidence.py still contains a module-level _neo4j_client global"
        )

    def test_search_router_uses_get_neo4j_client(self):
        source = self._read_source("app/routers/search.py")
        assert "get_neo4j_client" in source, (
            "search.py must import and use get_neo4j_client from deps"
        )

    def test_evidence_router_uses_get_neo4j_client(self):
        source = self._read_source("app/routers/evidence.py")
        assert "get_neo4j_client" in source, (
            "evidence.py must import and use get_neo4j_client from deps"
        )
