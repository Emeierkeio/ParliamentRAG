"""
Unit tests for the evaluation service (app.services.evaluation_service).

Tests cover:
1. _compute_automated_metrics returns expected metric keys
2. _compute_baseline_authority_from_precomputed uses precomputed experts (not expert_full_lookup)
3. party_top_expert fallback used for cited deputies not in chatData.experts (bug fix #2)
4. Metric values are float type and in [0, 1] range where applicable
5. Empty evidence list returns graceful defaults (not crash)
6. _compute_aggregated averages correctly over multiple chats
"""

import math
import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Constants shared with evaluation_service
ALL_PARTIES = 10

KNOWN_PARTIES = {
    "Fratelli d'Italia",
    "Lega - Salvini Premier",
    "Forza Italia - Berlusconi Presidente - PPE",
    "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare",
    "Partito Democratico - Italia Democratica e Progressista",
    "Movimento 5 Stelle",
    "Alleanza Verdi e Sinistra",
    "Azione - Popolari Europeisti Riformatori - Renew Europe",
    "Italia Viva - Il Centro - Renew Europe",
    "Misto",
}


def _make_chat(
    chat_id: str = "chat-001",
    query: str = "test query",
    answer: str = "Test answer mentioning Fratelli d'Italia and Lega",
    citations: list | None = None,
    experts: list | None = None,
    baseline_answer: str = "",
) -> dict:
    """Build a minimal ChatHistory-like dict for testing."""
    return {
        "id": chat_id,
        "query": query,
        "answer": answer,
        "citations": citations or [],
        "experts": experts or [],
        "baseline_answer": baseline_answer,
    }


def _make_citation(
    chunk_id: str = "chunk-001",
    group: str = "Fratelli d'Italia",
    deputy_first_name: str = "Mario",
    deputy_last_name: str = "Rossi",
    full_text: str = "Some verbatim text from the source.",
) -> dict:
    return {
        "evidence_id": chunk_id,
        "group": group,
        "deputy_first_name": deputy_first_name,
        "deputy_last_name": deputy_last_name,
        "full_text": full_text,
    }


def _make_expert(
    first_name: str = "Mario",
    last_name: str = "Rossi",
    group: str = "Fratelli d'Italia",
    authority_score: float = 0.75,
) -> dict:
    return {
        "first_name": first_name,
        "last_name": last_name,
        "group": group,
        "authority_score": authority_score,
    }


# ---------------------------------------------------------------------------
# Test 1: _compute_automated_metrics returns expected metric keys
# ---------------------------------------------------------------------------

def test_compute_automated_metrics_returns_expected_keys():
    """Verify the AutomatedMetrics model contains all expected fields."""
    from app.services.evaluation_service import _compute_automated_metrics

    chat = _make_chat(
        citations=[_make_citation()],
        experts=[_make_expert()],
    )
    chunk_texts = {"chunk-001": "Some verbatim text from the source."}

    result = _compute_automated_metrics(chat, chunk_texts)

    # Check that all expected metric keys are present in the result
    assert hasattr(result, "chat_id"), "Missing chat_id"
    assert hasattr(result, "party_coverage_score"), "Missing party_coverage_score"
    assert hasattr(result, "verbatim_match_score"), "Missing verbatim_match_score"
    assert hasattr(result, "authority_utilization"), "Missing authority_utilization"
    assert hasattr(result, "authority_discrimination"), "Missing authority_discrimination"
    assert hasattr(result, "response_completeness"), "Missing response_completeness"
    assert hasattr(result, "authority_by_group"), "Missing authority_by_group"
    assert hasattr(result, "baseline_authority"), "Missing baseline_authority"
    assert hasattr(result, "baseline_authority_by_group"), "Missing baseline_authority_by_group"
    assert result.chat_id == "chat-001"


# ---------------------------------------------------------------------------
# Test 2: _compute_baseline_authority_from_precomputed uses precomputed experts
# ---------------------------------------------------------------------------

def test_compute_baseline_authority_from_precomputed_uses_stored_scores():
    """
    Verify that _compute_baseline_authority_from_precomputed returns scores
    derived only from the provided precomputed experts list, NOT from any
    expert_full_lookup (which would carry cross-query scores — bug fix #1).
    """
    from app.services.evaluation_service import _compute_baseline_authority_from_precomputed

    precomputed = [
        {"group": "Fratelli d'Italia", "authority_score": 0.80},
        {"group": "Lega - Salvini Premier", "authority_score": 0.60},
    ]
    overall, by_group = _compute_baseline_authority_from_precomputed(precomputed)

    assert overall is not None
    assert abs(overall - 0.70) < 1e-3, f"Expected 0.70, got {overall}"
    assert by_group is not None
    assert abs(by_group["Fratelli d'Italia"] - 0.80) < 1e-3
    assert abs(by_group["Lega - Salvini Premier"] - 0.60) < 1e-3


def test_compute_baseline_authority_from_precomputed_empty_returns_none():
    """Empty precomputed list should return (None, None) gracefully."""
    from app.services.evaluation_service import _compute_baseline_authority_from_precomputed

    overall, by_group = _compute_baseline_authority_from_precomputed([])
    assert overall is None
    assert by_group is None


def test_compute_automated_metrics_prefers_precomputed_baseline_experts():
    """
    When baseline_precomputed_experts is provided, _compute_automated_metrics
    must use it for baseline_authority instead of falling back to expert_full_lookup.
    This is the core of bug fix #1 (baseline authority inflation).
    """
    from app.services.evaluation_service import _compute_automated_metrics

    precomputed_bl = [
        {"group": "Fratelli d'Italia", "authority_score": 0.55},
    ]
    # Provide a conflicting expert_full_lookup with higher scores to verify
    # that precomputed wins over the fallback.
    evil_lookup = {
        ("mario", "rossi"): {"score": 0.99, "party": "Fratelli d'Italia"},
    }
    chat = _make_chat(
        citations=[_make_citation()],
        experts=[_make_expert()],
        baseline_answer="Mario Rossi from Fratelli d'Italia spoke",
    )
    chunk_texts = {"chunk-001": "Some verbatim text from the source."}

    result = _compute_automated_metrics(
        chat, chunk_texts,
        expert_full_lookup=evil_lookup,
        baseline_precomputed_experts=precomputed_bl,
    )

    assert result.baseline_authority is not None
    # Must be based on precomputed (0.55), not evil_lookup (0.99)
    assert abs(result.baseline_authority - 0.55) < 1e-3, (
        f"Expected baseline_authority ~0.55 (precomputed), got {result.baseline_authority}"
    )


# ---------------------------------------------------------------------------
# Test 3: party_top_expert fallback for cited deputies not in chatData.experts (bug fix #2)
# ---------------------------------------------------------------------------

def test_party_top_expert_fallback_for_unknown_cited_deputy():
    """
    When a citation references a deputy whose name is NOT in the experts list,
    the system should fall back to the stored top expert for that party
    (query-specific, NOT a global lookup) — bug fix #2.

    Set-up:
    - experts list has "Luigi Bianchi" for Lega with score 0.70
    - citation cites "Unknown Person" from Lega (not in experts list)
    - Expected: authority_by_group["Lega - Salvini Premier"] == 0.70 (top expert used)
    """
    from app.services.evaluation_service import _compute_automated_metrics

    experts = [_make_expert(
        first_name="Luigi", last_name="Bianchi",
        group="Lega - Salvini Premier", authority_score=0.70,
    )]
    citations = [_make_citation(
        group="Lega - Salvini Premier",
        deputy_first_name="Unknown",
        deputy_last_name="Person",
    )]
    chat = _make_chat(citations=citations, experts=experts)
    chunk_texts = {}

    result = _compute_automated_metrics(chat, chunk_texts)

    assert "Lega - Salvini Premier" in result.authority_by_group, (
        "party_top_expert fallback did not populate authority_by_group"
    )
    assert abs(result.authority_by_group["Lega - Salvini Premier"] - 0.70) < 1e-3, (
        f"Expected 0.70 from top expert fallback, got {result.authority_by_group['Lega - Salvini Premier']}"
    )


# ---------------------------------------------------------------------------
# Test 4: Metric values are float type and in [0, 1] range where applicable
# ---------------------------------------------------------------------------

def test_metric_values_are_floats_in_range():
    """All [0,1]-constrained metrics must be floats between 0 and 1."""
    from app.services.evaluation_service import _compute_automated_metrics

    # Provide multiple citations from different parties to get non-trivial values
    citations = [
        _make_citation(chunk_id=f"c{i}", group=p, deputy_first_name="A", deputy_last_name="B")
        for i, p in enumerate(list(KNOWN_PARTIES)[:3])
    ]
    experts = [
        _make_expert(first_name="A", last_name="B", group=p, authority_score=0.5)
        for p in list(KNOWN_PARTIES)[:3]
    ]
    chat = _make_chat(citations=citations, experts=experts)
    chunk_texts = {}

    result = _compute_automated_metrics(chat, chunk_texts)

    bounded_metrics = {
        "party_coverage_score": result.party_coverage_score,
        "verbatim_match_score": result.verbatim_match_score,
        "authority_utilization": result.authority_utilization,
        "response_completeness": result.response_completeness,
    }
    for name, value in bounded_metrics.items():
        assert isinstance(value, float), f"{name} should be float, got {type(value)}"
        assert 0.0 <= value <= 1.0, f"{name}={value} is out of [0, 1] range"

    assert isinstance(result.authority_discrimination, float)
    assert result.authority_discrimination >= 0.0


# ---------------------------------------------------------------------------
# Test 5: Empty evidence returns graceful defaults (not crash)
# ---------------------------------------------------------------------------

def test_empty_evidence_returns_defaults():
    """
    A chat with no citations and no experts should return a valid AutomatedMetrics
    with all-zero values, not raise an exception.
    Uses an empty answer to also get response_completeness == 0.
    """
    from app.services.evaluation_service import _compute_automated_metrics

    chat = _make_chat(citations=[], experts=[], answer="")
    chunk_texts = {}

    result = _compute_automated_metrics(chat, chunk_texts)

    assert result.party_coverage_score == 0.0
    assert result.verbatim_match_score == 0.0
    assert result.authority_utilization == 0.0
    assert result.authority_discrimination == 0.0
    assert result.response_completeness == 0.0
    assert result.parties_represented == 0
    assert result.citations_total == 0
    assert result.authority_by_group == {}


# ---------------------------------------------------------------------------
# Test 6: _compute_aggregated averages correctly over multiple chats
# ---------------------------------------------------------------------------

def test_compute_aggregated_averages_correctly():
    """
    _compute_aggregated should produce simple averages of metric values
    across multiple AutomatedMetrics instances.
    """
    from app.services.evaluation_service import _compute_automated_metrics, _compute_aggregated

    # Build two minimal chats with known metric outcomes
    # Chat A: 2 parties cited → party_coverage = 2/10 = 0.2
    chat_a = _make_chat(
        chat_id="a",
        citations=[
            _make_citation(chunk_id="c1", group="Fratelli d'Italia"),
            _make_citation(chunk_id="c2", group="Lega - Salvini Premier"),
        ],
        experts=[
            _make_expert(group="Fratelli d'Italia", authority_score=0.60),
            _make_expert(
                first_name="Luigi", last_name="Bianchi",
                group="Lega - Salvini Premier", authority_score=0.80,
            ),
        ],
    )
    # Chat B: 0 parties cited → party_coverage = 0.0
    chat_b = _make_chat(chat_id="b", citations=[], experts=[])

    chunk_texts: dict = {}
    metrics_a = _compute_automated_metrics(chat_a, chunk_texts)
    metrics_b = _compute_automated_metrics(chat_b, chunk_texts)

    aggregated = _compute_aggregated([metrics_a, metrics_b])

    # avg_party_coverage should be (0.2 + 0.0) / 2 = 0.1
    expected_avg = (metrics_a.party_coverage_score + metrics_b.party_coverage_score) / 2
    assert abs(aggregated.avg_party_coverage - expected_avg) < 1e-3, (
        f"Expected avg_party_coverage {expected_avg}, got {aggregated.avg_party_coverage}"
    )
    assert aggregated.total_chats == 2

    # CIs should be tuples of length 2
    assert isinstance(aggregated.ci_party_coverage, tuple)
    assert len(aggregated.ci_party_coverage) == 2


# ---------------------------------------------------------------------------
# Sanity: no import from app.routers in the service module
# ---------------------------------------------------------------------------

def test_no_router_imports_in_evaluation_service():
    """
    The evaluation_service module must not import from app.routers.
    Cross-router imports are the architectural violation this plan fixes.
    """
    import ast
    import inspect
    import app.services.evaluation_service as svc_module

    source = inspect.getsource(svc_module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("app.routers"), (
                    f"evaluation_service imports from router: {node.module}"
                )
