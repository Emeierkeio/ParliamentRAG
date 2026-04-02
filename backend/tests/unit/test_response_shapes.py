"""
Response shape tests — verify API responses match the frontend contract.

Strategy: source-file inspection for structural tests (no live imports),
to avoid the scipy/NumPy 2.x incompatibility in the anaconda environment.

Tests verify:
1. UnifiedEvidence Pydantic model field presence (source inspection)
2. EvidenceResponse shape from evidence.py router
3. Search response shape from search.py router
4. Evaluation dashboard response shape from evaluation.py router
5. QueryResponse model fields
"""
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/


def _read_source(relative_path: str) -> str:
    """Read a source file relative to backend/."""
    return (_BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# UnifiedEvidence model shape
# ---------------------------------------------------------------------------

class TestUnifiedEvidenceFields:
    """Verify UnifiedEvidence has required fields and excludes removed ones."""

    EVIDENCE_MODEL_SOURCE = _read_source("app/models/evidence.py")

    def test_unified_evidence_has_chunk_id_equiv(self):
        """UnifiedEvidence must have evidence_id (serves as chunk_id)."""
        assert "evidence_id" in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must have 'evidence_id' field (acts as chunk_id)."
        )

    def test_unified_evidence_has_chunk_text(self):
        """UnifiedEvidence must have chunk_text."""
        assert "chunk_text" in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must have 'chunk_text' field."
        )

    def test_unified_evidence_has_speech_id(self):
        """UnifiedEvidence must have speech_id."""
        assert "speech_id" in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must have 'speech_id' field."
        )

    def test_unified_evidence_has_text_field(self):
        """UnifiedEvidence must have text field (full speech text)."""
        assert re.search(r"\btext\b\s*:", self.EVIDENCE_MODEL_SOURCE), (
            "UnifiedEvidence must have 'text' field for full speech text."
        )

    def test_unified_evidence_has_speaker_id(self):
        """UnifiedEvidence must have speaker_id."""
        assert "speaker_id" in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must have 'speaker_id' field."
        )

    def test_unified_evidence_has_speaker_role(self):
        """UnifiedEvidence must have speaker_role (maps to speaker_type in responses)."""
        assert "speaker_role" in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must have 'speaker_role' field."
        )

    def test_unified_evidence_has_score(self):
        """UnifiedEvidence must have similarity score."""
        assert "similarity" in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must have 'similarity' field (score for retrieval ranking)."
        )

    def test_unified_evidence_no_span_start(self):
        """UnifiedEvidence must NOT have span_start (removed in Phase 2 schema)."""
        assert "span_start" not in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must not have 'span_start' field — removed in Phase 2 schema."
        )

    def test_unified_evidence_no_span_end(self):
        """UnifiedEvidence must NOT have span_end (removed in Phase 2 schema)."""
        assert "span_end" not in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must not have 'span_end' field — removed in Phase 2 schema."
        )

    def test_unified_evidence_no_start_char_raw(self):
        """UnifiedEvidence must NOT have start_char_raw (removed in Phase 2 schema)."""
        assert "start_char_raw" not in self.EVIDENCE_MODEL_SOURCE, (
            "UnifiedEvidence must not have 'start_char_raw' — removed in Phase 2 schema."
        )


# ---------------------------------------------------------------------------
# EvidenceResponse shape (evidence.py router)
# ---------------------------------------------------------------------------

class TestEvidenceResponseShape:
    """Verify EvidenceResponse model has expected fields."""

    EVIDENCE_ROUTER_SOURCE = _read_source("app/routers/evidence.py")

    def test_evidence_response_has_chunk_id(self):
        """EvidenceResponse must have chunk_id field."""
        assert "chunk_id" in self.EVIDENCE_ROUTER_SOURCE, (
            "EvidenceResponse must have 'chunk_id' field."
        )

    def test_evidence_response_has_speech_id(self):
        """EvidenceResponse must have speech_id field."""
        assert "speech_id" in self.EVIDENCE_ROUTER_SOURCE, (
            "EvidenceResponse must have 'speech_id' field."
        )

    def test_evidence_response_has_speaker_id(self):
        """EvidenceResponse must have speaker_id field."""
        assert "speaker_id" in self.EVIDENCE_ROUTER_SOURCE, (
            "EvidenceResponse must have 'speaker_id' field."
        )

    def test_evidence_response_has_chunk_text(self):
        """EvidenceResponse must have chunk_text field."""
        assert "chunk_text" in self.EVIDENCE_ROUTER_SOURCE, (
            "EvidenceResponse must have 'chunk_text' field."
        )

    def test_evidence_response_has_speaker_name(self):
        """EvidenceResponse must have speaker_name field."""
        assert "speaker_name" in self.EVIDENCE_ROUTER_SOURCE, (
            "EvidenceResponse must have 'speaker_name' field."
        )

    def test_evidence_endpoint_uses_get_neo4j_client(self):
        """Evidence router must use Depends(get_neo4j_client) for DB access."""
        assert re.search(r"Depends\s*\(\s*get_neo4j_client\s*\)", self.EVIDENCE_ROUTER_SOURCE), (
            "evidence.py must use Depends(get_neo4j_client) for dependency injection."
        )

    def test_evidence_response_model_defined(self):
        """EvidenceResponse Pydantic model must be defined in evidence.py."""
        assert "class EvidenceResponse" in self.EVIDENCE_ROUTER_SOURCE, (
            "evidence.py must define 'EvidenceResponse' Pydantic model."
        )


# ---------------------------------------------------------------------------
# Search response shape (search.py router)
# ---------------------------------------------------------------------------

class TestSearchResponseShape:
    """Verify search.py router returns expected shape."""

    SEARCH_SOURCE = _read_source("app/routers/search.py")

    def test_search_endpoint_exists(self):
        """Search router must define a search endpoint."""
        assert re.search(r"@router\.(get|post)", self.SEARCH_SOURCE), (
            "search.py must define at least one router endpoint."
        )

    def test_search_results_has_results_key(self):
        """Search response must contain a 'results' key."""
        assert '"results"' in self.SEARCH_SOURCE or "'results'" in self.SEARCH_SOURCE, (
            "search.py must include 'results' key in response."
        )

    def test_search_results_has_score_field(self):
        """Search records must include 'score' field."""
        assert '"score"' in self.SEARCH_SOURCE or "'score'" in self.SEARCH_SOURCE, (
            "search.py must include 'score' field in result records."
        )

    def test_search_results_has_text_field(self):
        """Search records must include 'text' field."""
        assert '"text"' in self.SEARCH_SOURCE or "'text'" in self.SEARCH_SOURCE, (
            "search.py must include 'text' field in result records."
        )

    def test_search_uses_get_neo4j_client(self):
        """Search router must use get_neo4j_client for DB access."""
        assert "get_neo4j_client" in self.SEARCH_SOURCE, (
            "search.py must import and use get_neo4j_client."
        )


# ---------------------------------------------------------------------------
# Evaluation dashboard response shape (evaluation.py router)
# ---------------------------------------------------------------------------

class TestEvaluationDashboardShape:
    """Verify evaluation.py router returns the expected top-level dashboard keys."""

    EVAL_SOURCE = _read_source("app/routers/evaluation.py")

    def test_evaluation_router_has_dashboard_endpoint(self):
        """Evaluation router must have a /dashboard endpoint."""
        assert "dashboard" in self.EVAL_SOURCE, (
            "evaluation.py must define a /dashboard endpoint."
        )

    def test_evaluation_dashboard_returns_chats(self):
        """Dashboard response must include chat-level data."""
        # Dashboard returns chats list or similar structure
        assert "chats" in self.EVAL_SOURCE or "chat_evaluations" in self.EVAL_SOURCE, (
            "evaluation.py dashboard must include chat data."
        )

    def test_evaluation_dashboard_returns_aggregated(self):
        """Dashboard response must include aggregated metrics."""
        assert "aggregated" in self.EVAL_SOURCE, (
            "evaluation.py dashboard must include 'aggregated' metrics."
        )

    def test_evaluation_imports_from_service(self):
        """evaluation.py must import metric computation from evaluation_service."""
        assert "from app.services.evaluation_service import" in self.EVAL_SOURCE or \
               "from ..services.evaluation_service import" in self.EVAL_SOURCE, (
            "evaluation.py must import from evaluation_service (thin router pattern)."
        )

    def test_evaluation_has_module_docstring(self):
        """evaluation.py must have a module docstring."""
        stripped = self.EVAL_SOURCE.lstrip()
        assert stripped.startswith('"""'), (
            "evaluation.py must have a module-level docstring."
        )


# ---------------------------------------------------------------------------
# QueryResponse model (query.py)
# ---------------------------------------------------------------------------

class TestQueryResponseShape:
    """Verify QueryResponse model fields in query.py."""

    QUERY_SOURCE = _read_source("app/routers/query.py")

    def test_query_response_has_text(self):
        """QueryResponse must have 'text' field."""
        assert re.search(r"\btext\b\s*:", self.QUERY_SOURCE), (
            "query.py QueryResponse must have 'text' field."
        )

    def test_query_response_has_citations(self):
        """QueryResponse must have 'citations' field."""
        assert "citations" in self.QUERY_SOURCE, (
            "query.py QueryResponse must have 'citations' field."
        )

    def test_query_response_has_experts(self):
        """QueryResponse must have 'experts' field."""
        assert "experts" in self.QUERY_SOURCE, (
            "query.py QueryResponse must have 'experts' field."
        )

    def test_query_response_has_metadata(self):
        """QueryResponse must have 'metadata' field."""
        assert "metadata" in self.QUERY_SOURCE, (
            "query.py QueryResponse must have 'metadata' field."
        )
