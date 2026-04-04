"""Citation translation service.

Translates Italian parliamentary speech excerpts to a target language using
OpenAI, with parallel asyncio.gather and graceful fallback on failure.
"""

import asyncio
import json
import logging

from ..key_pool import make_async_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

TRANSLATION_PROMPT = (
    "Translate the following Italian parliamentary speech excerpts to English.\n"
    "Preserve formal parliamentary register. Do not translate proper nouns\n"
    "(speaker names, party names, place names, dates, session numbers).\n"
    'Return ONLY valid JSON: {{"text": "...", "full_text": "..."}}\n\n'
    "text: {text}\n"
    "full_text: {full_text}"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def translate_citation_batch(
    citations: list[dict],
    target_lang: str = "en",
) -> list[dict]:
    """Translate a batch of citations to *target_lang*.

    Args:
        citations: List of citation dicts, each may have ``text`` and
            ``full_text`` fields.
        target_lang: BCP-47 language code.  Only ``"en"`` triggers
            translation; all other values return *citations* unchanged.

    Returns:
        List of dicts where each entry is the original citation potentially
        augmented with ``translated_text``, ``translated_full_text``, and
        ``is_translated=True``.  On failure the original citation is returned
        without any ``translated_*`` keys.
    """
    if target_lang == "it" or not citations:
        return citations

    client = make_async_client()
    raw_results = await asyncio.gather(
        *[_translate_one(c, client) for c in citations],
        return_exceptions=True,
    )

    output: list[dict] = []
    for original, result in zip(citations, raw_results):
        if isinstance(result, Exception):
            logger.warning("Translation failed for citation; returning original. Error: %s", result)
            output.append(original)
        else:
            output.append(result)  # type: ignore[arg-type]
    return output


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _translate_one(citation: dict, client) -> dict:
    """Translate a single citation dict.

    Returns the original citation unchanged on any exception.
    """
    text = citation.get("text", "")
    full_text = citation.get("full_text", "")

    if not text and not full_text:
        return citation

    prompt = TRANSLATION_PROMPT.format(text=text, full_text=full_text)

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = response.choices[0].message.content
        result = json.loads(raw)
        return {
            **citation,
            "translated_text": result.get("text", ""),
            "translated_full_text": result.get("full_text", ""),
            "is_translated": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Translation failed for citation; returning original. Error: %s", exc)
        return citation
