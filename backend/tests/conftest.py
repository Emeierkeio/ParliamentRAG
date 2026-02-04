"""
Pytest configuration and fixtures.
"""
import os
import sys
import pytest
from datetime import date

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def sample_memberships():
    """Sample group memberships for testing."""
    return [
        {
            "gruppo": "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
            "dataInizio": date(2022, 10, 13),
            "dataFine": date(2024, 1, 15),
        },
        {
            "gruppo": "FRATELLI D'ITALIA",
            "dataInizio": date(2024, 1, 16),
            "dataFine": None,
        },
    ]


@pytest.fixture
def sample_activities():
    """Sample activities for testing."""
    return [
        {"id": "act_1", "date": date(2023, 3, 15)},  # During PD membership
        {"id": "act_2", "date": date(2023, 6, 20)},  # During PD membership
        {"id": "act_3", "date": date(2024, 2, 10)},  # During FdI membership
        {"id": "act_4", "date": date(2024, 5, 1)},   # During FdI membership
    ]


@pytest.fixture
def sample_evidence():
    """Sample evidence for testing."""
    return {
        "evidence_id": "chunk_test_001",
        "doc_id": "seduta_001",
        "speech_id": "intervento_001",
        "speaker_id": "dep_001",
        "speaker_name": "Mario Rossi",
        "speaker_role": "Deputato",
        "party": "FRATELLI D'ITALIA",
        "coalition": "maggioranza",
        "date": date(2024, 1, 15),
        "chunk_text": "Questo è il testo del chunk per preview...",
        "quote_text": "Questo è la citazione esatta estratta via offset",
        "span_start": 100,
        "span_end": 150,
        "dibattito_titolo": "Discussione sulla manovra",
        "seduta_numero": 42,
        "similarity": 0.85,
        "authority_score": 0.72,
    }


@pytest.fixture
def sample_testo_raw():
    """Sample intervention text for quote extraction."""
    return (
        "Presidente, colleghi. "
        "Questo governo sta affrontando sfide importanti. "
        "Dobbiamo lavorare insieme per il bene del Paese. "
        "La manovra economica che presentiamo oggi è equilibrata e responsabile. "
        "Ringrazio tutti per l'attenzione."
    )
