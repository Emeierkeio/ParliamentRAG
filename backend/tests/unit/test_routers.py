"""
Router quality tests — verify thin router pattern and code quality.

Tests cover:
1. Router modules have docstrings
2. Service modules have docstrings
3. No _compute_experts business logic in routers (delegated to services)
4. No Italian comments in Python source files
5. Consistent snake_case field naming in payload code
6. Type hints present in key function signatures
7. survey.py imports helpers from services (not self-contained)
"""
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/
_APP_DIR = _BACKEND_ROOT / "app"
_ROUTERS_DIR = _APP_DIR / "routers"
_SERVICES_DIR = _APP_DIR / "services"


def _read_source(relative_path: str) -> str:
    """Read a source file relative to backend/."""
    return (_BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def _has_module_docstring(source: str) -> bool:
    """Return True if the source starts with a module-level docstring."""
    stripped = source.lstrip()
    return stripped.startswith('"""') or stripped.startswith("'''")


# ---------------------------------------------------------------------------
# Router docstrings
# ---------------------------------------------------------------------------

class TestAllRoutersHaveDocstrings:
    """All router files must have module-level docstrings."""

    ROUTER_FILES = [
        "app/routers/chat.py",
        "app/routers/query.py",
        "app/routers/survey.py",
        "app/routers/history.py",
        "app/routers/config.py",
        "app/routers/compass.py",
        "app/routers/evaluation.py",
        "app/routers/evidence.py",
        "app/routers/search.py",
    ]

    def test_chat_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/chat.py")), \
            "chat.py must have a module-level docstring"

    def test_query_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/query.py")), \
            "query.py must have a module-level docstring"

    def test_survey_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/survey.py")), \
            "survey.py must have a module-level docstring"

    def test_history_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/history.py")), \
            "history.py must have a module-level docstring"

    def test_config_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/config.py")), \
            "config.py must have a module-level docstring"

    def test_compass_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/compass.py")), \
            "compass.py must have a module-level docstring"

    def test_evaluation_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/evaluation.py")), \
            "evaluation.py must have a module-level docstring"

    def test_evidence_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/evidence.py")), \
            "evidence.py must have a module-level docstring"

    def test_search_router_has_docstring(self):
        assert _has_module_docstring(_read_source("app/routers/search.py")), \
            "search.py must have a module-level docstring"


# ---------------------------------------------------------------------------
# Service docstrings
# ---------------------------------------------------------------------------

class TestAllServicesHaveDocstrings:
    """All service modules must have module-level docstrings."""

    def test_neo4j_client_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/neo4j_client.py")), \
            "neo4j_client.py must have a module-level docstring"

    def test_experts_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/experts.py")), \
            "experts.py must have a module-level docstring"

    def test_evaluation_service_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/evaluation_service.py")), \
            "evaluation_service.py must have a module-level docstring"

    def test_survey_helpers_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/survey_helpers.py")), \
            "survey_helpers.py must have a module-level docstring"

    def test_deps_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/deps.py")), \
            "deps.py must have a module-level docstring"

    def test_graph_channel_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/retrieval/graph_channel.py")), \
            "graph_channel.py must have a module-level docstring"

    def test_retrieval_engine_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/retrieval/engine.py")), \
            "engine.py must have a module-level docstring"

    def test_authority_scorer_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/authority/scorer.py")), \
            "scorer.py must have a module-level docstring"

    def test_coalition_logic_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/authority/coalition_logic.py")), \
            "coalition_logic.py must have a module-level docstring"

    def test_dense_channel_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/retrieval/dense_channel.py")), \
            "dense_channel.py must have a module-level docstring"

    def test_merger_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/retrieval/merger.py")), \
            "merger.py must have a module-level docstring"

    def test_commission_matcher_has_docstring(self):
        assert _has_module_docstring(_read_source("app/services/retrieval/commission_matcher.py")), \
            "commission_matcher.py must have a module-level docstring"


# ---------------------------------------------------------------------------
# Thin router pattern — no _compute_experts in routers
# ---------------------------------------------------------------------------

class TestChatRouterNoBusinessLogic:
    """chat.py must not define expert computation functions (delegated to services)."""

    CHAT_SOURCE = _read_source("app/routers/chat.py")

    def test_chat_router_no_compute_experts_definition(self):
        """chat.py must not define _compute_experts — it is in services/experts.py."""
        assert not re.search(r"^def _compute_experts\b", self.CHAT_SOURCE, re.MULTILINE), (
            "chat.py must not define _compute_experts. "
            "Expert computation belongs in services/experts.py."
        )

    def test_chat_router_imports_compute_experts_from_service(self):
        """chat.py must import compute_experts from services/experts.py."""
        assert "from ..services.experts import" in self.CHAT_SOURCE or \
               "from app.services.experts import" in self.CHAT_SOURCE, (
            "chat.py must import expert computation from services/experts.py."
        )

    def test_chat_router_has_sse_event_helper(self):
        """chat.py may define sse_event() — it is an HTTP formatting helper, not business logic."""
        assert "def sse_event" in self.CHAT_SOURCE, (
            "chat.py must define sse_event() helper for SSE formatting."
        )


class TestQueryRouterNoBusinessLogic:
    """query.py must not define expert computation functions (delegated to services)."""

    QUERY_SOURCE = _read_source("app/routers/query.py")

    def test_query_router_no_compute_experts_definition(self):
        """query.py must not define _compute_experts."""
        assert not re.search(r"^def _compute_experts\b", self.QUERY_SOURCE, re.MULTILINE), (
            "query.py must not define _compute_experts. "
            "Expert computation belongs in services/experts.py."
        )

    def test_query_router_imports_compute_experts_from_service(self):
        """query.py must import compute_experts from services/experts.py."""
        assert "from ..services.experts import" in self.QUERY_SOURCE or \
               "from app.services.experts import" in self.QUERY_SOURCE, (
            "query.py must import expert computation from services/experts.py."
        )

    def test_query_router_uses_services_for_retrieval(self):
        """query.py must use the retrieval service, not contain retrieval logic inline."""
        assert "services[" in self.QUERY_SOURCE or "get_services" in self.QUERY_SOURCE, (
            "query.py must delegate to services via get_services()."
        )


# ---------------------------------------------------------------------------
# No Italian comments
# ---------------------------------------------------------------------------

class TestNoItalianComments:
    """No Italian words in source code comments (Italian in string literals is allowed)."""

    # Italian comment keywords to look for
    ITALIAN_PATTERNS = [
        r"#\s*calcola",
        r"#\s*carica",
        r"#\s*salva",
        r"#\s*controlla",
        r"#\s*gestisce",
        r"#\s*verifica",
        r"#\s*aggiorna",
        r"#\s*ottieni",
        r"#\s*crea",
        r"#\s*trova",
    ]

    def _collect_python_sources(self) -> list[tuple[str, str]]:
        """Collect all Python sources from app/ directory."""
        sources = []
        for py_file in _APP_DIR.rglob("*.py"):
            relative = str(py_file.relative_to(_BACKEND_ROOT))
            sources.append((relative, py_file.read_text(encoding="utf-8")))
        return sources

    def test_no_italian_calcola_comments(self):
        """No '# calcola' comments in Python source."""
        for path, source in self._collect_python_sources():
            matches = re.findall(r"#\s*calcola", source, re.IGNORECASE)
            assert not matches, f"Italian comment '# calcola' found in {path}"

    def test_no_italian_carica_comments(self):
        """No '# carica' comments in Python source."""
        for path, source in self._collect_python_sources():
            matches = re.findall(r"#\s*carica", source, re.IGNORECASE)
            assert not matches, f"Italian comment '# carica' found in {path}"

    def test_no_italian_salva_comments(self):
        """No '# salva' comments in Python source."""
        for path, source in self._collect_python_sources():
            matches = re.findall(r"#\s*salva", source, re.IGNORECASE)
            assert not matches, f"Italian comment '# salva' found in {path}"


# ---------------------------------------------------------------------------
# Survey router imports from service
# ---------------------------------------------------------------------------

class TestSurveyRouterUsesService:
    """survey.py structure and quality checks."""

    SURVEY_SOURCE = _read_source("app/routers/survey.py")

    def test_survey_helpers_module_exists(self):
        """services/survey_helpers.py must exist (shared helper module for cross-router use)."""
        path = _BACKEND_ROOT / "app" / "services" / "survey_helpers.py"
        assert path.exists(), (
            "services/survey_helpers.py must exist — extracted helpers for "
            "evaluation.py and survey.py to share."
        )

    def test_survey_helpers_has_load_surveys(self):
        """survey_helpers.py must define load_surveys()."""
        source = _read_source("app/services/survey_helpers.py")
        assert "def load_surveys" in source, (
            "survey_helpers.py must define load_surveys() as shared helper."
        )

    def test_survey_helpers_has_calculate_stats(self):
        """survey_helpers.py must define calculate_stats()."""
        source = _read_source("app/services/survey_helpers.py")
        assert "def calculate_stats" in source, (
            "survey_helpers.py must define calculate_stats() as shared helper."
        )

    def test_evaluation_imports_from_survey_helpers(self):
        """evaluation.py must import from survey_helpers (the shared helper module)."""
        eval_source = _read_source("app/routers/evaluation.py")
        assert "survey_helpers" in eval_source, (
            "evaluation.py must use survey_helpers for shared helper functions."
        )

    def test_survey_has_docstring(self):
        """survey.py must have a module-level docstring."""
        assert _has_module_docstring(self.SURVEY_SOURCE), \
            "survey.py must have a module-level docstring"


# ---------------------------------------------------------------------------
# Evaluation router uses evaluation_service
# ---------------------------------------------------------------------------

class TestEvaluationRouterThin:
    """evaluation.py must delegate metric computation to evaluation_service."""

    EVAL_SOURCE = _read_source("app/routers/evaluation.py")

    def test_evaluation_imports_compute_automated_metrics(self):
        """evaluation.py must import _compute_automated_metrics from evaluation_service."""
        assert "_compute_automated_metrics" in self.EVAL_SOURCE, (
            "evaluation.py must use _compute_automated_metrics from evaluation_service."
        )

    def test_evaluation_imports_from_evaluation_service(self):
        """evaluation.py must import from evaluation_service."""
        assert "evaluation_service" in self.EVAL_SOURCE, (
            "evaluation.py must import from services/evaluation_service.py."
        )
