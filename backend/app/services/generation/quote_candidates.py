"""Deterministic candidate-span extraction for the quote picker.

The picker LLM must not be the source of the final quote string: it ranks
pre-extracted candidates and the chosen text is taken verbatim from the
source. Candidates are runs of 1-2 consecutive sentences within a length
band, filtered by structural criteria that used to live only as prompt
rules (leading connectives, stenographer ellipsis, nested third-party
quotes, procedural announcements).
"""
import re
import logging
from typing import List, Optional

from .reported_speech import detect_reported_speech

logger = logging.getLogger(__name__)

MIN_CANDIDATE_CHARS = 80
MAX_CANDIDATE_CHARS = 350
MAX_CANDIDATES = 8

# Connectives/orphan complements that mark a sentence as syntactically
# dependent on the previous one — unusable as a self-contained quote.
_LEADING_CONNECTIVE = re.compile(
    r'^(?:quindi|dunque|perciò|però|perché|che|e|ed|o|ma|infatti|inoltre|'
    r'tuttavia|infine|poi|allora|cioè|anzi|eppure|pertanto|comunque|'
    r'a\s+quest[aoie]|per\s+quest[aoie]|di\s+quest[aoie]|in\s+quest[aoie])\b',
    re.IGNORECASE,
)

# Leading vocatives: transcripts open substantive sentences with them all
# the time («Signor Presidente, onorevoli colleghi, come Fratelli d'Italia
# siamo…»). Rejecting the whole sentence loses the best quotes (observed
# 2026-09-19 on "riforma sanitaria"): the vocative is stripped and the
# remainder — still an exact substring of the source — stays a candidate.
_VOCATIVE_PREFIX = re.compile(
    r'^(?:grazie,?\s+(?:signor[a]?\s+president[ea]|president[ea])[.,]?\s*|'
    r'grazie[.,]\s*|'
    r'signor[a]?\s+president[ea][.,]?\s*|'
    r'president[ea],\s*|'
    r'onorevol[ie]\s+collegh[ie](?:\s+e\s+collegh[ie])?[.,]?\s*)+',
    re.IGNORECASE,
)

# Procedural/meta-parliamentary openings: floor management, motion
# announcements — never the group's position on the topic.
_PROCEDURAL_OPENING = re.compile(
    r'^(?:ringrazio|'
    r'presentiamo\s+(?:una|la)\s+mozione|annuncio\s+il\s+voto|'
    r'dichiaro\s+(?:aperta|chiusa)|passiamo\s+(?:alla|al|all\')|'
    r'chiedo\s+di\s+(?:parlare|intervenire)|'
    r'l\'ordine\s+dei\s+lavori)',
    re.IGNORECASE,
)

_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')


def _split_sentences(text: str) -> List[str]:
    """Split into sentences without breaking inside «...» quotations."""
    # Protect guillemet spans: sentence punctuation inside a quotation must
    # not create a split point.
    protected = []
    depth = 0
    chars = []
    for ch in text:
        if ch == '«':
            depth += 1
        elif ch == '»':
            depth = max(0, depth - 1)
        if depth > 0 and ch in '.!?':
            chars.append('\x00')
            protected.append(ch)
        else:
            chars.append(ch)
    masked = ''.join(chars)
    parts = _SENTENCE_END.split(masked)
    it = iter(protected)
    return [
        ''.join(next(it) if c == '\x00' else c for c in p).strip()
        for p in parts if p.strip()
    ]


def _inside_nested_quote(text: str, start_pos: int) -> bool:
    """True when start_pos falls inside an unclosed «...» or "..." block."""
    before = text[:start_pos]
    if before.count('«') > before.count('»'):
        return True
    if before.count('“') > before.count('”'):
        return True
    return False


def _keyword_overlap(candidate: str, query_terms: set) -> int:
    if not query_terms:
        return 0
    words = set(re.findall(r'\b[a-zàèéìòù]{4,}\b', candidate.lower()))
    return len(words & query_terms)


def extract_quote_candidates(
    text: str,
    query: Optional[str] = None,
    min_chars: int = MIN_CANDIDATE_CHARS,
    max_chars: int = MAX_CANDIDATE_CHARS,
    max_candidates: int = MAX_CANDIDATES,
) -> List[str]:
    """Return candidate quote spans, each an exact substring of `text`.

    Candidates are 1-2 consecutive sentences inside the length band, in
    query-relevance order (keyword overlap, stable on ties). Returns [] when
    the text yields no structurally citable span — callers fall back to the
    legacy free-pick path.
    """
    if not text or len(text) < min_chars:
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return []

    query_terms = (
        set(re.findall(r'\b[a-zàèéìòù]{4,}\b', query.lower())) if query else set()
    )

    candidates: List[str] = []
    seen: set = set()
    for i in range(len(sentences)):
        for span in (1, 2):
            if i + span > len(sentences):
                break
            candidate = ' '.join(sentences[i:i + span]).strip()
            # Strip leading vocatives; the remainder is still a contiguous
            # span of the source, so the exact-substring property holds.
            stripped = _VOCATIVE_PREFIX.sub('', candidate)
            vocative_cut = stripped != candidate
            candidate = stripped.strip()
            if not (min_chars <= len(candidate) <= max_chars):
                continue
            if candidate in seen:
                continue
            if '…' in candidate or '[...]' in candidate:
                continue
            # Embedded guillemets: either someone else's reported words, or
            # nesting that would break the «candidate» rendering downstream.
            if '«' in candidate or '»' in candidate:
                continue
            if detect_reported_speech(candidate)["has_reported_speech"]:
                continue
            if _LEADING_CONNECTIVE.match(candidate):
                continue
            if _PROCEDURAL_OPENING.match(candidate):
                continue
            # Fragments starting with a lowercase letter usually depend on
            # a previous clause the splitter could not resolve — unless the
            # lowercase start is our own deliberate vocative cut.
            first_alpha = next((c for c in candidate if c.isalpha()), '')
            if (
                not vocative_cut
                and first_alpha and first_alpha.islower()
                and not candidate.startswith(
                    ('è', 'noi', 'non', 'il', 'la', 'lo', 'serve', 'occorre', 'bisogna')
                )
            ):
                continue
            pos = text.find(candidate)
            if pos < 0:
                continue
            if _inside_nested_quote(text, pos):
                continue
            seen.add(candidate)
            candidates.append(candidate)

    if not candidates:
        return []

    candidates.sort(key=lambda c: _keyword_overlap(c, query_terms), reverse=True)
    return candidates[:max_candidates]
