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

async def translate_response_text(
    text: str,
    target_lang: str = "en",
) -> str:
    """Translate the generated Italian markdown response text to *target_lang*.

    Preserves markdown formatting, citation links ``[text](leg19_...)``,
    and proper nouns (party names, people names, session numbers).
    On failure returns the original text unchanged.
    """
    if target_lang == "it" or not text:
        return text

    client = make_async_client()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional translator from Italian to English.\n"
                        "Translate the following Italian parliamentary markdown text to English.\n"
                        "RULES:\n"
                        "- Preserve ALL markdown formatting (##, **, «», bullet points, etc.)\n"
                        "- Preserve ALL citation links exactly as-is: e.g. [some text](leg19_abc) — do NOT modify the link target inside parentheses\n"
                        "- Preserve proper nouns: party names, people names, place names, dates, session numbers\n"
                        "- Maintain formal parliamentary register\n"
                        "- Return ONLY the translated text, nothing else"
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        translated = response.choices[0].message.content
        return translated if translated else text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Response text translation failed; returning original. Error: %s", exc)
        return text


async def translate_compass_axes(
    compass_data: dict,
    target_lang: str = "en",
) -> dict:
    """Translate compass axis labels to *target_lang*.

    The *compass_data* dict has an ``axes`` dict with keys like ``"x"`` and
    ``"y"``, each containing ``positive_label`` and ``negative_label`` strings.
    On failure returns the original data unchanged.
    """
    if target_lang == "it" or not compass_data:
        return compass_data

    axes = compass_data.get("axes")
    if not axes:
        return compass_data

    # Collect all labels to translate in one call
    labels_to_translate = {}
    for axis_key, axis_val in axes.items():
        if isinstance(axis_val, dict):
            for label_key in ("positive_label", "negative_label"):
                val = axis_val.get(label_key, "")
                if val:
                    labels_to_translate[f"{axis_key}.{label_key}"] = val

    if not labels_to_translate:
        return compass_data

    client = make_async_client()
    try:
        prompt = (
            "Translate these Italian political compass axis labels to English.\n"
            "Preserve proper nouns. Return ONLY valid JSON with the same keys.\n\n"
            + json.dumps(labels_to_translate, ensure_ascii=False)
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = response.choices[0].message.content
        translated = json.loads(raw)

        # Apply translations back
        result = {**compass_data, "axes": {**axes}}
        for compound_key, translated_val in translated.items():
            parts = compound_key.split(".", 1)
            if len(parts) == 2:
                axis_key, label_key = parts
                if axis_key in result["axes"] and isinstance(result["axes"][axis_key], dict):
                    result["axes"][axis_key] = {**result["axes"][axis_key], label_key: translated_val}
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("Compass axes translation failed; returning original. Error: %s", exc)
        return compass_data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TRANSLATE_SYS = (
    "Translate the following Italian parliamentary text to English. "
    "Preserve proper nouns (names, parties, dates, session numbers). "
    "Return ONLY the translation."
)


async def _translate_text(client, text: str, max_tokens: int = 2000) -> str:
    """Translate a single text string. Returns original on failure."""
    if not text:
        return ""
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _TRANSLATE_SYS},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or text


async def _translate_one(citation: dict, client) -> dict:
    """Translate a single citation's short text (preview).

    Only translates 'text' (the short preview, ~100-300 chars).
    full_text (entire speech, up to 11k chars) is NOT translated eagerly —
    it would take 5-10s per citation and hit rate limits. The frontend
    shows the original Italian in the modal with an ORIGINAL label.
    """
    text = citation.get("text", "")

    if not text:
        return citation

    try:
        translated_text = await _translate_text(client, text)

        return {
            **citation,
            "translated_text": translated_text,
            "is_translated": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Translation failed for citation; returning original. Error: %s", exc)
        return citation
