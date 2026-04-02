"""Sentence-aware speech chunker for ParliamentRAG.

Splits a preprocessed speech text into overlapping chunk dicts, each
containing only the minimal properties needed by the pipeline::

    {"id": "<speech_id>_chunk_<index>", "text": "...", "index": <int>}

No legacy offset fields — just the minimal three keys: id, text, index.

Usage::

    from chunker import chunk_speech
    from build_config import BuildConfig

    chunks = chunk_speech(text, speech_id="sp_001")
    # or with custom config:
    chunks = chunk_speech(text, speech_id="sp_001", config=BuildConfig(chunk_size=800))
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from build_config import BuildConfig

# ---------------------------------------------------------------------------
# Sentence splitting — abbreviation-aware
# ---------------------------------------------------------------------------

# Split pattern: capture punctuation + whitespace so we can re-attach it.
_SENTENCE_SPLIT = re.compile(r'([.!?]\s+)')

# Abbreviations that should NOT trigger a sentence boundary even though
# they end with punctuation followed by whitespace.
_ABBREV_PATTERN = re.compile(
    r'\b(?:On|Sen|Prof|Dott|Avv|Sig|Sigg|lett|cfr|art|comma|n|pag|V|B|on|onn|Onn|pagg)\.$'
)


def _split_sentences(text: str) -> list[str]:
    """Split *text* into a list of sentences using abbreviation-aware rules.

    The splitter re-attaches punctuation to the preceding token and skips
    common Italian parliamentary abbreviations (e.g. "on.", "art.", "n.").

    Args:
        text: Preprocessed speech text (single-space-normalised).

    Returns:
        Non-empty list of sentence strings, or empty list if *text* is blank.
    """
    parts = _SENTENCE_SPLIT.split(text)

    sentences: list[str] = []
    current = ""

    # parts alternates: [text, punct+space, text, punct+space, ...]
    i = 0
    while i < len(parts):
        text_part = parts[i]
        punct_part = parts[i + 1] if i + 1 < len(parts) else ""

        combined = current + text_part + punct_part

        if punct_part and _ABBREV_PATTERN.search((current + text_part).rstrip()):
            # Abbreviation — do not split here; keep accumulating.
            current = combined
        else:
            sentence = combined.strip()
            if sentence:
                sentences.append(sentence)
            current = ""

        i += 2  # skip the captured delimiter (counted separately by split)

    # Any trailing text not followed by punctuation.
    if current.strip():
        sentences.append(current.strip())

    return [s for s in sentences if s]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_speech(
    text: str | None,
    speech_id: str,
    config: BuildConfig | None = None,
) -> list[dict]:
    """Split preprocessed speech text into overlapping chunks.

    Args:
        text: Preprocessed speech text (no raw text, no alignment).
              Returns ``[]`` if *None* or empty.
        speech_id: Parent speech ID used to generate chunk IDs.
        config: Build configuration.  Defaults to ``BuildConfig()``.

    Returns:
        List of chunk dicts, each with keys: ``id``, ``text``, ``index``.
        Returns an empty list when *text* is shorter than
        ``config.min_speech_length``.
    """
    if not text:
        return []

    cfg = config if config is not None else BuildConfig()

    # Skip speeches that are too short to be meaningful.
    if len(text) < cfg.min_speech_length:
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[dict] = []
    chunk_index = 0
    sentence_pos = 0  # index into sentences[]

    while sentence_pos < len(sentences):
        # ----------------------------------------------------------------
        # Build the current chunk greedily: keep adding sentences until
        # adding the next one would exceed chunk_size (unless the chunk
        # is still empty — always include at least one sentence).
        # ----------------------------------------------------------------
        current_sentences: list[str] = []
        current_length = 0

        j = sentence_pos
        while j < len(sentences):
            sentence = sentences[j]
            if current_length + len(sentence) <= cfg.chunk_size or not current_sentences:
                current_sentences.append(sentence)
                current_length += len(sentence)
                j += 1
            else:
                break

        chunk_text = " ".join(current_sentences)

        # ----------------------------------------------------------------
        # Handle the final chunk: if it is very short, merge it into the
        # previous chunk rather than emitting a tiny orphan.
        # ----------------------------------------------------------------
        if (
            j == len(sentences)
            and len(chunk_text) < cfg.min_speech_length
            and chunks
        ):
            # Append to the last chunk instead of creating a new one.
            prev = chunks[-1]
            chunks[-1] = {
                "id": prev["id"],
                "text": prev["text"] + " " + chunk_text,
                "index": prev["index"],
            }
            break

        chunks.append(
            {
                "id": f"{speech_id}_chunk_{chunk_index}",
                "text": chunk_text,
                "index": chunk_index,
            }
        )
        chunk_index += 1

        # ----------------------------------------------------------------
        # All sentences consumed — we are done.
        # ----------------------------------------------------------------
        if j == len(sentences):
            break

        # ----------------------------------------------------------------
        # Overlap: step back so that the next chunk starts with the last
        # few sentences of this chunk (up to chunk_overlap characters).
        # ----------------------------------------------------------------
        overlap_length = 0
        new_sentence_pos = j
        while new_sentence_pos > sentence_pos + 1:
            prev_sentence = sentences[new_sentence_pos - 1]
            if overlap_length + len(prev_sentence) <= cfg.chunk_overlap:
                overlap_length += len(prev_sentence)
                new_sentence_pos -= 1
            else:
                # Even if we cannot fit it entirely, take at least one
                # overlap sentence to avoid completely disjoint chunks.
                if overlap_length == 0:
                    new_sentence_pos -= 1
                break

        # Guard against infinite loops: always advance at least one sentence.
        sentence_pos = new_sentence_pos if new_sentence_pos != j else j

    return chunks
