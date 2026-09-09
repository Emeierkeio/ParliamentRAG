"""Regression test for the non-streaming response model.

The synchronous path of /api/query returned HTTP 500 on every request until
2026-09-08: QueryResponse declared `experts` as a dict of a schema the
pipeline never produced. This pins the contract to the shape actually
emitted by _compute_experts (a list of per-party dicts).
"""
from app.routers.query import QueryResponse, CitationInfo


def test_query_response_accepts_pipeline_expert_shape():
    expert = {
        "id": "dep_1",
        "first_name": "Maria",
        "last_name": "Rossi",
        "group": "Fratelli d'Italia",
        "coalition": "maggioranza",
        "authority_score": 0.42,
        "relevant_speeches_count": 3,
        "score_breakdown": {"speeches": 0.4, "acts": 0.2},
    }
    resp = QueryResponse(
        text="risposta",
        citations=[],
        experts=[expert],
        compass=None,
        metadata={},
    )
    assert resp.experts[0]["group"] == "Fratelli d'Italia"


def test_citation_info_requires_string_date():
    cit = CitationInfo(
        citation_id="cit_1",
        chunk_id="leg19_sed100_chunk_1",
        quote_text="testo",
        speaker_name="Maria Rossi",
        party="Fratelli d'Italia",
        date="2024-01-15",
        span_start=0,
        span_end=5,
    )
    assert cit.date == "2024-01-15"
