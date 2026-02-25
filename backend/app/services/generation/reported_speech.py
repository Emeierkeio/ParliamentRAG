"""
Reported Speech Detector.

Identifies parliamentary speech chunks where the speaker is primarily
quoting another person's words (opponents, ministers, media) to refute,
contextualize, or respond to them.

This is distinct from first-person statements and requires special
handling to avoid selecting the quoted content as the speaker's own
position — a common failure mode in citation extraction.

Example failure:
  Nisini (Lega) cites Gribaudo (PD): «per il centrodestra vengono prima i
  corrotti, vengono prima gli evasori». The system must NOT treat this as
  Lega's position on salario minimo.
"""
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

# Strong patterns: high confidence of reported speech, especially at the
# beginning of a chunk (opening_is_reported).
_STRONG_PATTERNS = [
    # "ieri/oggi la collega/il collega X ha dichiarato che..."
    re.compile(
        r'\b(?:ieri|oggi|l\'altro\s+ieri)\s+'
        r'(?:la\s+collega|il\s+collega|l\'onorevole|l\'on\.|il\s+collega|la\s+collega)\s+'
        r'\w+\s+ha\s+\w+\s+che\b',
        re.IGNORECASE,
    ),
    # "X ha dichiarato che per [partito/gruppo]..."
    re.compile(
        r'\b\w+\s+ha\s+(?:dichiarato|affermato|detto)\s+che\s+per\s+(?:il|la|i|lo)\b',
        re.IGNORECASE,
    ),
    # "il collega/la collega X ha [verbo] che..." (general parliamentary citation)
    re.compile(
        r'\b(?:la\s+collega|il\s+collega)\s+\w+\s+ha\s+\w+\s+che\b',
        re.IGNORECASE,
    ),
]

# Regular patterns: moderate confidence, requires at least one match.
_REGULAR_PATTERNS = [
    # "X ha dichiarato/affermato/detto/sostenuto che..."
    re.compile(
        r'\b(?:ha|hanno|aveva|avevano)\s+'
        r'(?:dichiarato|affermato|detto|sostenuto|asserito|proclamato|annunciato|comunicato|ribadito)\s+'
        r'che\b',
        re.IGNORECASE,
    ),
    # "come ha detto/dichiarato/affermato X"
    re.compile(
        r'\bcome\s+ha\s+(?:detto|dichiarato|affermato|sostenuto)\b',
        re.IGNORECASE,
    ),
    # "secondo X" / "stando a X" where X is a noun phrase
    re.compile(
        r'\b(?:secondo|stando\s+a)\s+(?:il|la|lo|i|gli|le|un|una|l\'|l\')\b',
        re.IGNORECASE,
    ),
    # "l'onorevole / l'on. X ha [verb]"
    re.compile(
        r'\b(?:l\'onorevole|l\'on\.)\s+\w+\s+ha\s+\w+\b',
        re.IGNORECASE,
    ),
    # Inline attribution before guillemets: "X ha detto: «" or "X: «"
    re.compile(r'\w+\s*:\s*«', re.IGNORECASE),
]

# Attribution + inline guillemet (very strong signal)
_ATTRIBUTED_INLINE_QUOTE = re.compile(
    r'(?:\w+\s+){1,5}(?:ha\s+)?'
    r'(?:dichiarato|affermato|detto|sostenuto|scritto|twittato)\s+'
    r'(?:che\s+)?«',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_reported_speech(text: str) -> Dict[str, Any]:
    """
    Detect if a text chunk primarily contains reported speech from another
    person (i.e. the speaker is quoting someone else's words).

    Args:
        text: The chunk text (quote_text or chunk_text from evidence).

    Returns:
        dict with:
        - has_reported_speech (bool)
        - confidence (float 0.0–1.0)
        - matched_patterns (list[str]): descriptions of matched patterns
        - opening_is_reported (bool): True if the chunk BEGINS with
          reported speech (first 300 chars), strongest signal of all
    """
    if not text or len(text) < 20:
        return {
            "has_reported_speech": False,
            "confidence": 0.0,
            "matched_patterns": [],
            "opening_is_reported": False,
        }

    matched: List[str] = []
    confidence = 0.0
    opening_is_reported = False
    opening_text = text[:300]

    # 1. Strong patterns — check opening
    for pat in _STRONG_PATTERNS:
        if pat.search(opening_text):
            label = f"strong_opening:{pat.pattern[:60]}"
            matched.append(label)
            confidence = max(confidence, 0.90)
            opening_is_reported = True
            logger.debug(f"[REPORTED_SPEECH] Strong match: {label}")

    # 2. Regular patterns — check full text
    for pat in _REGULAR_PATTERNS:
        if pat.search(text):
            label = f"regular:{pat.pattern[:60]}"
            matched.append(label)
            confidence = max(confidence, 0.60)

    # 3. Attributed inline quote (strong signal)
    m = _ATTRIBUTED_INLINE_QUOTE.search(text)
    if m:
        matched.append("attributed_inline_quote")
        confidence = max(confidence, 0.85)
        if m.start() < 200:
            opening_is_reported = True
            confidence = max(confidence, 0.90)

    has_reported = confidence >= 0.60

    return {
        "has_reported_speech": has_reported,
        "confidence": round(confidence, 2),
        "matched_patterns": matched,
        "opening_is_reported": opening_is_reported,
    }


def annotate_evidence_with_reported_speech(
    evidence_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Annotate each evidence chunk with reported-speech detection results.

    Mutates evidence in-place by adding/updating the 'reported_speech' key.
    Returns the same list for convenience (suitable for chaining).

    Logs a warning for each chunk where reported speech is detected so that
    the pipeline log provides visibility into which chunks are flagged.
    """
    flagged = 0
    for e in evidence_list:
        text = e.get("quote_text", "") or e.get("chunk_text", "")
        result = detect_reported_speech(text)
        e["reported_speech"] = result
        if result["has_reported_speech"]:
            flagged += 1
            logger.warning(
                f"[REPORTED_SPEECH] Chunk {e.get('evidence_id', '?')} "
                f"({e.get('speaker_name', '?')}) flagged "
                f"(confidence={result['confidence']:.2f}, "
                f"opening={result['opening_is_reported']}): "
                f"{text[:120]!r}"
            )

    if flagged:
        logger.info(
            f"[REPORTED_SPEECH] {flagged}/{len(evidence_list)} chunks flagged as reported speech"
        )

    return evidence_list
