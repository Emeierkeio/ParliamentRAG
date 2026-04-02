"""
Unit tests for backend scripts DI compliance.

Verifies via source-file inspection that:
1. No script creates its own Neo4j driver (GraphDatabase.driver)
2. All scripts use the shared get_neo4j_client from app.services.deps
3. No dead Cypher properties (start_char_raw, end_char_raw) exist in scripts

Source inspection avoids the scipy/NumPy 2.x import chain broken in the
Python 3.12 anaconda environment.
"""
from pathlib import Path

_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/


def _read_script(name: str) -> str:
    """Read a script source file by name."""
    return (_BACKEND_ROOT / "scripts" / name).read_text(encoding="utf-8")


class TestNoOwnDriverCreation:
    """Scripts must not instantiate their own Neo4j GraphDatabase.driver."""

    def test_compute_baseline_no_own_driver(self):
        source = _read_script("compute_baseline_experts.py")
        assert "GraphDatabase.driver" not in source, (
            "compute_baseline_experts.py must not create its own GraphDatabase.driver — "
            "use get_neo4j_client() from app.services.deps instead"
        )

    def test_enrich_evaluation_no_own_driver(self):
        source = _read_script("enrich_evaluation_set.py")
        assert "GraphDatabase.driver" not in source, (
            "enrich_evaluation_set.py must not create its own GraphDatabase.driver — "
            "use get_neo4j_client() from app.services.deps instead"
        )

    def test_seed_evaluation_no_own_driver(self):
        source = _read_script("seed_evaluation_topic.py")
        assert "GraphDatabase.driver" not in source, (
            "seed_evaluation_topic.py must not create its own GraphDatabase.driver — "
            "use get_services() from app.services.deps instead"
        )


class TestUsesSharedClient:
    """Scripts must import from app.services.deps (shared DI)."""

    def test_compute_baseline_uses_get_neo4j_client(self):
        source = _read_script("compute_baseline_experts.py")
        assert "get_neo4j_client" in source, (
            "compute_baseline_experts.py must import and use get_neo4j_client from deps"
        )

    def test_enrich_evaluation_uses_get_neo4j_client(self):
        source = _read_script("enrich_evaluation_set.py")
        assert "get_neo4j_client" in source, (
            "enrich_evaluation_set.py must import and use get_neo4j_client from deps"
        )

    def test_seed_evaluation_uses_deps(self):
        source = _read_script("seed_evaluation_topic.py")
        assert "from app.services.deps import" in source, (
            "seed_evaluation_topic.py must import services from app.services.deps"
        )


class TestNoDeadProperties:
    """No script may reference removed Cypher properties."""

    def test_scripts_no_start_char_raw(self):
        for script_name in (
            "compute_baseline_experts.py",
            "enrich_evaluation_set.py",
            "seed_evaluation_topic.py",
        ):
            source = _read_script(script_name)
            assert "start_char_raw" not in source, (
                f"{script_name} must not reference removed property start_char_raw"
            )

    def test_scripts_no_end_char_raw(self):
        for script_name in (
            "compute_baseline_experts.py",
            "enrich_evaluation_set.py",
            "seed_evaluation_topic.py",
        ):
            source = _read_script(script_name)
            assert "end_char_raw" not in source, (
                f"{script_name} must not reference removed property end_char_raw"
            )
