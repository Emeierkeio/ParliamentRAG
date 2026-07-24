"""
test_senate_parser.py — Unit tests for SenateStenograficoParser.

Uses the sample_session.akn fixture in build/fixtures/.
"""

import os
import sys

import pytest

# Add build/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "sample_session.akn"
)


@pytest.fixture(scope="module")
def parsed():
    """Parse the sample AKN fixture once for all tests."""
    from senate_parser import SenateStenograficoParser

    parser = SenateStenograficoParser()
    return parser.parse_xml_file(FIXTURE_PATH)


def test_parse_returns_correct_keys(parsed):
    """Returned dict must have exactly the 6 top-level keys."""
    assert set(parsed.keys()) == {
        "session",
        "debates",
        "phases",
        "speeches",
        "votes",
        "act_references",
    }


def test_session_metadata(parsed):
    """Session metadata must be extracted correctly from FRBRWork."""
    s = parsed["session"]
    assert s["id"] == "sen_leg19_sed5"
    assert s["chamber"] == "senato"
    assert s["legislature"] == 19
    assert s["number"] == 5
    assert s["year"] == 2022
    assert s["month"] == 11
    assert s["day"] == 15
    assert s["date"] == "2022-11-15"


def test_presidente_filtered(parsed):
    """No speech must have a speakingRole containing 'Presidente'."""
    for speech in parsed["speeches"]:
        role = speech.get("speakingRole") or ""
        assert "Presidente" not in role, (
            f"Speech {speech['id']} has Presidente role: {role!r}"
        )


def test_speeches_structure(parsed):
    """Every speech must have all required keys and correct deputatoId prefix."""
    required_keys = {
        "id",
        "text",
        "deputatoId",
        "cognome_nome",
        "sessionId",
        "debateId",
        "phaseId",
        "parentType",
        "parentId",
        "order",
    }
    assert len(parsed["speeches"]) > 0, "Expected at least one speech after filtering"
    for speech in parsed["speeches"]:
        missing = required_keys - set(speech.keys())
        assert not missing, f"Speech missing keys: {missing}"
        assert speech["deputatoId"].startswith("http://dati.senato.it/senatore/"), (
            f"deputatoId {speech['deputatoId']!r} must be a full senatore URI "
            "(matches Deputy.id loaded from senatori CSV)"
        )


def test_debates_and_phases(parsed):
    """InizioSeduta section must be skipped; one debate from DiscussioneArgomento."""
    # InizioSeduta should be skipped, only DiscussioneArgomento creates a debate
    assert len(parsed["debates"]) == 1
    debate = parsed["debates"][0]
    assert "sen_leg19_sed5" in debate["id"]
    # Each debate has a corresponding phase
    assert len(parsed["phases"]) == len(parsed["debates"])
    phase = parsed["phases"][0]
    assert phase["debateId"] == debate["id"]


def test_votes_and_acts_empty(parsed):
    """votes must be empty list; act_references must be empty dict."""
    assert parsed["votes"] == []
    assert parsed["act_references"] == {}
