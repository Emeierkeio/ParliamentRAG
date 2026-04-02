"""
Shared test fixtures for the Multi-View RAG backend test suite.

Provides:
- mock_neo4j: MagicMock replacing Neo4jClient for unit tests
- client: FastAPI TestClient with mocked dependencies
- sample_evidence: dict with all UnifiedEvidence fields (no span_start/span_end)
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_neo4j():
    """
    Return a MagicMock replacing Neo4jClient.

    Configured with safe defaults:
    - query() returns []
    - query_single() returns None
    - vector_search() returns []
    - close() is a no-op
    """
    mock = MagicMock()
    mock.query.return_value = []
    mock.query_single.return_value = None
    mock.vector_search.return_value = []
    mock.close.return_value = None
    return mock


@pytest.fixture
def client(mock_neo4j):
    """
    Return a FastAPI TestClient with Neo4j mocked at the module level.

    Uses patch on app.services.deps._neo4j_client to inject the mock before
    the app is started. The TestClient context manager handles startup/shutdown.
    """
    with patch("app.services.deps.get_neo4j_client", return_value=mock_neo4j):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client


@pytest.fixture
def sample_evidence():
    """
    Return a sample evidence dict with all required fields.

    Intentionally excludes span_start and span_end — these fields were
    removed from the schema in Phase 2 Plan 01.
    """
    return {
        "chunk_id": "leg19_sed123_tit00010.int00005_chunk_2",
        "chunk_text": "Questo è il testo del chunk per il retrieval.",
        "speech_id": "leg19_sed123_tit00010.int00005",
        "text": "Testo completo del discorso parlamentare.",
        "speaker_id": "d300001",
        "speaker_first_name": "Mario",
        "speaker_last_name": "Rossi",
        "speaker_type": "Deputy",
        "session_id": "leg19_sed123",
        "session_date": "2023-05-15",
        "session_number": 123,
        "debate_title": "Discussione DL immigrazione",
        "score": 0.85,
    }
