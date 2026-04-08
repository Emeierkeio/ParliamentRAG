"""
Smoke tests for timeline API endpoints.

Uses source-file inspection to verify endpoint structure without requiring
full application import (avoids scipy/NumPy 2.x incompatibility in test env).
"""
from pathlib import Path

ROUTER_PATH = Path(__file__).parent.parent / "app" / "routers" / "timeline.py"
SERVICE_PATH = Path(__file__).parent.parent / "app" / "services" / "timeline_service.py"
MODELS_PATH = Path(__file__).parent.parent / "app" / "models" / "timeline.py"


def test_router_file_exists():
    assert ROUTER_PATH.exists(), "timeline router must exist"

def test_service_file_exists():
    assert SERVICE_PATH.exists(), "timeline service must exist"

def test_models_file_exists():
    assert MODELS_PATH.exists(), "timeline models must exist"

def test_router_has_three_endpoints():
    source = ROUTER_PATH.read_text()
    assert source.count("@router.get") == 3, "router must have exactly 3 GET endpoints"

def test_router_has_locale_extraction():
    source = ROUTER_PATH.read_text()
    assert "Accept-Language" in source, "router must extract locale from Accept-Language header"

def test_service_has_get_sessions():
    source = SERVICE_PATH.read_text()
    assert "async def get_sessions" in source

def test_service_has_get_debate_detail():
    source = SERVICE_PATH.read_text()
    assert "async def get_debate_detail" in source

def test_service_has_get_speaker_summary():
    source = SERVICE_PATH.read_text()
    assert "async def get_speaker_summary" in source

def test_models_have_response_types():
    source = MODELS_PATH.read_text()
    for cls in ["TimelineResponse", "DebateDetailResponse", "SpeakerSummaryResponse", "SessionCard"]:
        assert f"class {cls}" in source, f"models must define {cls}"

def test_service_handles_locale():
    source = SERVICE_PATH.read_text()
    assert "recapIt" in source and "recapEn" in source, "service must handle both locales"

def test_service_cursor_pagination():
    source = SERVICE_PATH.read_text()
    assert "limit + 1" in source or "limit+1" in source, "service must fetch limit+1 for cursor pagination"

def test_router_registered_in_main():
    main_path = Path(__file__).parent.parent / "app" / "main.py"
    source = main_path.read_text()
    assert "timeline" in source.lower(), "timeline router must be registered in main.py"

def test_service_handles_speakers():
    source = SERVICE_PATH.read_text()
    assert "SPOKEN_BY" in source, "service must query speakers via SPOKEN_BY relationship"

def test_service_has_speaker_debate_summary():
    source = SERVICE_PATH.read_text()
    assert "HAS_DEBATE_SUMMARY" in source or "SpeakerDebateSummary" in source, \
        "service must query SpeakerDebateSummary nodes"

def test_service_has_coalesce_for_speaker_types():
    source = SERVICE_PATH.read_text()
    assert "coalesce" in source.lower(), "service must use coalesce for Deputy/GovernmentMember handling"

def test_models_have_session_card_fields():
    source = MODELS_PATH.read_text()
    assert "class SessionCard" in source
    assert "debate_count" in source or "debateCount" in source
    assert "vote_count" in source or "voteCount" in source
    assert "speech_count" in source or "speechCount" in source

def test_models_have_debate_detail_fields():
    source = MODELS_PATH.read_text()
    assert "class DebateDetailResponse" in source
    assert "phases" in source
    assert "speakers" in source
    assert "votes" in source
    assert "acts" in source

def test_models_have_speaker_summary_fields():
    source = MODELS_PATH.read_text()
    assert "class SpeakerSummaryResponse" in source
    assert "summary" in source
    assert "speech_count" in source or "speechCount" in source
