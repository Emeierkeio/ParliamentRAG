"""
Unit tests preventing cross-layer import violations.

Tests enforce the architectural boundary:
  - Routers must NOT import from other routers
  - Scripts must NOT import from routers
  - search.py must not have module-level _neo4j_client globals (Plan 02 regression check)

Run with:
    cd backend && python -m pytest tests/unit/test_import_violations.py -x -q
"""
import re
import inspect
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_source(relative_path: str) -> str:
    """Read a source file relative to the backend/ root."""
    backend_root = Path(__file__).parent.parent.parent  # backend/
    full_path = backend_root / relative_path
    return full_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# API-02: evaluation.py must not import from any router
# ---------------------------------------------------------------------------

class TestNoRouterImportsFromRouter:
    """evaluation.py must not contain cross-router imports."""

    def test_no_router_imports_from_router(self):
        source = _read_source("app/routers/evaluation.py")
        assert "from app.routers.survey" not in source, (
            "evaluation.py must not import from app.routers.survey — "
            "use app.services.survey_helpers instead"
        )

    def test_evaluation_imports_from_services_not_routers(self):
        source = _read_source("app/routers/evaluation.py")
        # Check that it now uses the service layer
        assert "survey_helpers" in source, (
            "evaluation.py should import from app.services.survey_helpers"
        )

    def test_no_cross_router_imports_in_evaluation(self):
        """evaluation.py must not import anything from app.routers (except its own router)."""
        source = _read_source("app/routers/evaluation.py")
        # Strip comments
        lines_without_comments = [
            line for line in source.splitlines()
            if not line.strip().startswith("#")
        ]
        clean = "\n".join(lines_without_comments)
        # No import of any other router
        cross_router = re.findall(r"from app\.routers\.\w+", clean)
        assert not cross_router, (
            f"evaluation.py has cross-router imports: {cross_router}"
        )


# ---------------------------------------------------------------------------
# SCR-02: seed_evaluation_topic.py must not import from routers
# ---------------------------------------------------------------------------

class TestNoScriptImportsFromRouter:
    """Script must import expert computation from services, not from routers."""

    def test_no_script_imports_from_router(self):
        source = _read_source("scripts/seed_evaluation_topic.py")
        assert "from app.routers" not in source, (
            "seed_evaluation_topic.py must not import from app.routers — "
            "use app.services.experts instead"
        )

    def test_script_imports_from_services_experts(self):
        source = _read_source("scripts/seed_evaluation_topic.py")
        assert "from app.services.experts import compute_experts" in source, (
            "seed_evaluation_topic.py should import compute_experts from app.services.experts"
        )


# ---------------------------------------------------------------------------
# Plan 02 regression: search.py must not have module-level _neo4j_client
# ---------------------------------------------------------------------------

class TestSearchNoLocalClient:
    """Verify Plan 02 fix still holds: search.py must not declare _neo4j_client globally."""

    def test_search_no_local_client(self):
        source = _read_source("app/routers/search.py")
        assert not re.search(r"^_neo4j_client\s*[=:]", source, re.MULTILINE), (
            "search.py still contains a module-level _neo4j_client global (Plan 02 regression)"
        )
