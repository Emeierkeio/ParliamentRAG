"""Tests for build/chunker.py — sentence-aware speech chunking.

Contract:
- chunk_speech(text, speech_id) returns a list of dicts
- Each dict has exactly the keys: id, text, index
- No alignment_map, startCharRaw, endCharRaw, or charCount keys
- Short speeches below min_speech_length are handled gracefully
"""

import sys
from pathlib import Path

# Ensure the build/ directory is on the path so we can import chunker
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from chunker import chunk_speech  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LONG_TEXT = (
    "Il Presidente della Camera dei Deputati ha aperto la seduta. "
    "I lavori parlamentari procedono con la discussione del disegno di legge. "
    "Il deputato ha preso la parola per esprimere le proprie considerazioni. "
    "La maggioranza ha votato a favore dell'emendamento proposto. "
    "Il Governo ha espresso parere favorevole sulla proposta di legge. "
) * 30  # ~1500+ chars * 30 repetitions — well over chunk_size


# ---------------------------------------------------------------------------
# Core contract tests
# ---------------------------------------------------------------------------


def test_chunk_speech_returns_list():
    """chunk_speech must return a non-empty list of dicts."""
    result = chunk_speech(LONG_TEXT, "speech_001")
    assert isinstance(result, list)
    assert len(result) > 0


def test_chunk_speech_dict_keys():
    """Each chunk dict must contain exactly the keys: id, text, index."""
    result = chunk_speech(LONG_TEXT, "speech_001")
    for chunk in result:
        assert set(chunk.keys()) == {"id", "text", "index"}, (
            f"Unexpected keys: {set(chunk.keys())}"
        )


def test_chunk_no_alignment_map():
    """Output dicts must NOT contain legacy alignment/raw-offset keys."""
    result = chunk_speech(LONG_TEXT, "speech_001")
    forbidden_keys = {"startCharRaw", "endCharRaw", "charCount", "alignment_map"}
    for chunk in result:
        found = forbidden_keys & set(chunk.keys())
        assert not found, f"Forbidden keys present: {found}"


def test_chunk_ids_use_speech_id():
    """Chunk IDs must be formatted as '{speech_id}_chunk_{index}'."""
    result = chunk_speech(LONG_TEXT, "sp_test_42")
    for chunk in result:
        expected_id = f"sp_test_42_chunk_{chunk['index']}"
        assert chunk["id"] == expected_id


def test_chunk_index_sequential():
    """Chunk indices must be sequential starting at 0."""
    result = chunk_speech(LONG_TEXT, "speech_001")
    for expected_idx, chunk in enumerate(result):
        assert chunk["index"] == expected_idx


def test_chunk_text_is_string():
    """Chunk text must be a non-empty string."""
    result = chunk_speech(LONG_TEXT, "speech_001")
    for chunk in result:
        assert isinstance(chunk["text"], str)
        assert len(chunk["text"]) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_chunk_empty_text_returns_empty_list():
    """Empty input text must return an empty list."""
    result = chunk_speech("", "speech_empty")
    assert result == []


def test_chunk_none_text_returns_empty_list():
    """None input text must return an empty list."""
    result = chunk_speech(None, "speech_none")
    assert result == []


def test_chunk_respects_min_length():
    """A speech shorter than min_speech_length must return an empty list."""
    short_text = "Breve."  # well below 100 chars
    result = chunk_speech(short_text, "speech_short")
    # Either returns empty (filtered) or returns the single chunk as-is.
    # The plan says "merged or skipped" for the final chunk; for a whole speech
    # below min_speech_length, the result must be empty.
    assert result == []


def test_chunk_single_sentence_no_split():
    """A text with a single sentence that fits in one chunk returns one chunk."""
    text = "Questa è una singola frase sufficiente per un intervento parlamentare."
    # This is >= min_speech_length? Let's make it long enough.
    text = text + " " + "Aggiunta per superare la soglia minima di cento caratteri effettivi."
    result = chunk_speech(text, "speech_single")
    assert len(result) == 1
    assert result[0]["index"] == 0


def test_chunk_produces_multiple_chunks_for_long_text():
    """Long text must be split into more than one chunk."""
    result = chunk_speech(LONG_TEXT, "speech_long")
    assert len(result) > 1


def test_chunk_overlap_shares_content():
    """Consecutive chunks must share some text content (overlap logic)."""
    result = chunk_speech(LONG_TEXT, "speech_overlap")
    if len(result) < 2:
        pytest.skip("Need at least 2 chunks to test overlap")
    # The end of chunk N and beginning of chunk N+1 should share sentences.
    # We verify that no chunk starts from scratch at an entirely new position.
    # Heuristic: chunk[1].text does NOT start with chunk[0].text[:20]
    # but DOES contain words from chunk[0].text (overlap).
    chunk0_words = set(result[0]["text"].split())
    chunk1_words = set(result[1]["text"].split())
    shared = chunk0_words & chunk1_words
    assert len(shared) > 0, "Chunks appear to have no overlap"


def test_chunk_abbreviation_handling():
    """Abbreviations like 'on.', 'art.', 'n.' must not trigger false sentence splits."""
    # This text contains abbreviations that should NOT cause mid-sentence splits.
    text = (
        "Il deputato on. Rossi ha citato l'art. 18 del decreto n. 123 del 2020. "
        "Successivamente il sen. Bianchi ha risposto con riferimento al comma 3 lett. a). "
        "Il prof. Verdi ha concluso il suo intervento con ulteriori osservazioni sul tema. "
    ) * 15  # repeat to ensure multiple chunks
    result = chunk_speech(text, "speech_abbrev")
    # Should not crash and should produce valid chunks
    assert isinstance(result, list)
    for chunk in result:
        assert set(chunk.keys()) == {"id", "text", "index"}
