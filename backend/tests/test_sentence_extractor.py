"""Unit tests for SentenceExtractor._clean_result.

The word-level trim replaced a character-level loop on 2026-09-08: leading
fragments (no early verb, lowercase start) are dropped up to the first
capitalized word, and words are never split mid-token.
"""
from app.services.citation.sentence_extractor import SentenceExtractor


def _clean(text):
    return SentenceExtractor()._clean_result(text)


def test_drops_leading_fragment_up_to_first_capitalized_word():
    assert _clean("europeo e del Mediterraneo serve un impegno comune") == (
        "Mediterraneo serve un impegno comune"
    )


def test_never_splits_a_word_mid_token():
    cleaned = _clean("continuo e determinato per l'Italia serve coraggio")
    assert "talia" not in cleaned.split()[0]


def test_removes_leading_connector():
    cleaned = _clean("e quindi Serve una risposta")
    assert not cleaned.startswith("e ")
    assert cleaned.endswith("Serve una risposta")


def test_removes_lowercase_comma_continuation():
    assert _clean("internazionale, Serve una risposta").startswith("Serve")


def test_keeps_text_starting_with_verb():
    text = "Serve una risposta immediata del Parlamento"
    assert _clean(text) == text
