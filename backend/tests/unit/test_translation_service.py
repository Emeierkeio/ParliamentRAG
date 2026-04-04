"""Unit tests for the citation translation service."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client(response_json: dict | None = None, raise_exc: Exception | None = None):
    """Return a mocked async OpenAI client."""
    client = MagicMock()

    if raise_exc is not None:
        async def _bad_create(**kwargs):
            raise raise_exc
        client.chat.completions.create = _bad_create
    else:
        payload = response_json or {"text": "Translated text", "full_text": "Translated full text"}
        choice = MagicMock()
        choice.message.content = json.dumps(payload)
        response = MagicMock()
        response.choices = [choice]

        async def _good_create(**kwargs):
            return response
        client.chat.completions.create = _good_create

    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTranslateCitationBatch:
    """Tests for translate_citation_batch."""

    def test_returns_translated_citations_with_translated_fields(self):
        """Test 1: translate_citation_batch adds translated_text and translated_full_text."""
        from app.services.translation import translate_citation_batch

        citations = [
            {"text": "Testo italiano", "full_text": "Testo completo italiano", "speaker": "Mario Rossi"},
        ]
        mock_client = _make_mock_client(
            response_json={"text": "Italian text", "full_text": "Full Italian text"}
        )

        with patch("app.services.translation.make_async_client", return_value=mock_client):
            results = asyncio.run(translate_citation_batch(citations, target_lang="en"))

        assert len(results) == 1
        assert results[0]["translated_text"] == "Italian text"
        assert results[0]["translated_full_text"] == "Full Italian text"
        assert results[0].get("is_translated") is True

    def test_preserves_original_text_and_full_text_unchanged(self):
        """Test 2: Original text and full_text fields are preserved."""
        from app.services.translation import translate_citation_batch

        citations = [
            {"text": "Testo italiano", "full_text": "Testo completo italiano", "speaker": "Mario Rossi"},
        ]
        mock_client = _make_mock_client(
            response_json={"text": "Italian text", "full_text": "Full Italian text"}
        )

        with patch("app.services.translation.make_async_client", return_value=mock_client):
            results = asyncio.run(translate_citation_batch(citations, target_lang="en"))

        assert results[0]["text"] == "Testo italiano"
        assert results[0]["full_text"] == "Testo completo italiano"
        assert results[0]["speaker"] == "Mario Rossi"

    def test_openai_failure_returns_citation_unchanged_no_exception(self):
        """Test 3: When OpenAI call fails, citation returned unchanged without translated_* fields."""
        from app.services.translation import translate_citation_batch

        citations = [
            {"text": "Testo italiano", "full_text": "Testo completo italiano"},
        ]
        mock_client = _make_mock_client(raise_exc=RuntimeError("API error"))

        with patch("app.services.translation.make_async_client", return_value=mock_client):
            results = asyncio.run(translate_citation_batch(citations, target_lang="en"))

        assert len(results) == 1
        assert "translated_text" not in results[0]
        assert "translated_full_text" not in results[0]
        assert results[0]["text"] == "Testo italiano"

    def test_empty_citation_list_returns_empty_list(self):
        """Test 4: Empty citation list returns empty list."""
        from app.services.translation import translate_citation_batch

        with patch("app.services.translation.make_async_client") as mock_factory:
            results = asyncio.run(translate_citation_batch([], target_lang="en"))

        # make_async_client should not be called for empty list
        mock_factory.assert_not_called()
        assert results == []

    def test_citation_with_no_text_field_returned_unchanged(self):
        """Test 5: Citation with no text field is returned unchanged."""
        from app.services.translation import translate_citation_batch

        citations = [
            {"speaker": "Mario Rossi", "party": "PD"},  # no text or full_text
        ]
        mock_client = _make_mock_client()

        with patch("app.services.translation.make_async_client", return_value=mock_client):
            results = asyncio.run(translate_citation_batch(citations, target_lang="en"))

        assert len(results) == 1
        assert "translated_text" not in results[0]
        assert results[0]["speaker"] == "Mario Rossi"

    def test_translation_prompt_instructs_not_to_translate_proper_nouns(self):
        """Test 6: The TRANSLATION_PROMPT contains proper noun preservation instructions."""
        from app.services.translation import TRANSLATION_PROMPT

        assert "Do not translate proper nouns" in TRANSLATION_PROMPT

    def test_italian_target_lang_returns_citations_unchanged(self):
        """Extra: target_lang='it' returns citations without calling OpenAI."""
        from app.services.translation import translate_citation_batch

        citations = [
            {"text": "Testo italiano", "full_text": "Testo completo"},
        ]

        with patch("app.services.translation.make_async_client") as mock_factory:
            results = asyncio.run(translate_citation_batch(citations, target_lang="it"))

        mock_factory.assert_not_called()
        assert results == citations
