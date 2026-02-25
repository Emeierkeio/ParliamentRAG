"""
Position Brief Builder.

Generates a concise position summary for a parliamentary group
from their evidence chunks, WITHOUT requiring an LLM call.

The brief gives the sectional writer context about the group's
OVERALL stance, so citations are selected and framed correctly.
This prevents two failure modes:
1. Selecting a citation that is not the most representative
2. Selecting a citation that, read in isolation, means the opposite
   of the group's actual position
"""
import re
import logging
from typing import List, Dict, Any, Tuple

from ...config import get_config
from .reported_speech import detect_reported_speech

logger = logging.getLogger(__name__)


# --- Direction detection patterns ---
# Keyword-based approach: no LLM call, fast, deterministic.

# Patterns that signal explicit OPPOSITION to a proposal/policy
_AGAINST_PATTERNS = [
    re.compile(r'\b(?:siamo contrari|ci opponiamo|votiamo contro|voteremo contro)\b', re.IGNORECASE),
    re.compile(r'\b(?:non condividiamo|non accettiamo|non possiamo accettare|respingiamo|rifiutiamo)\b', re.IGNORECASE),
    re.compile(r'\b(?:è sbagliato|sarebbe sbagliato|non è la soluzione|non è la strada)\b', re.IGNORECASE),
    re.compile(r'\b(?:è inutile|è dannoso|è controproducente|è rischioso|è pericoloso)\b', re.IGNORECASE),
    re.compile(r'\bnon (?:introdurre|introduciamo|introdurrebbe|introduce)\b', re.IGNORECASE),
    re.compile(r'\b(?:meglio la contrattazione|meglio i contratti collettivi|la contrattazione è sufficiente)\b', re.IGNORECASE),
    re.compile(r'\b(?:parere contrario|voto contrario)\b', re.IGNORECASE),
    re.compile(r'\b(?:non sono obbligati ad introdurre|non è rimesso alla legge)\b', re.IGNORECASE),
    # Fix 5 — contrattazione collettiva vs. salario minimo legale (Lega/FdI pattern)
    re.compile(r'\b(?:contrattazione\s+collettiva)\s+(?:è|resta|rimane|deve\s+restare)\s+(?:la\s+)?(?:strada|soluzione|via|strumento)\b', re.IGNORECASE),
    re.compile(r'\b(?:lasciare|lasciamo|affidare|affidiamo)\s+(?:alla\s+)?contrattazione\b', re.IGNORECASE),
    re.compile(r'\b(?:salario\s+minimo\s+(?:per\s+legge|legale))\s+(?:non\s+è|non\s+sarebbe|non\s+può\s+essere|non\s+serve|non\s+aiuta)\b', re.IGNORECASE),
    re.compile(r'\b(?:i\s+contratti\s+collettivi?|la\s+contrattazione\s+collettiva)\s+(?:già\s+)?(?:tutelano|tutela|garantiscono|garantisce|proteggono|protegge)\b', re.IGNORECASE),
    re.compile(r'\b(?:determinazione|fissazione)\s+(?:d(?:el|i\s+un|ei)\s+salari(?:o\s+\w+)*)\s+(?:\w+\s+){0,3}(?:trattata?|affidata?|rimessa?|demandata?)\s+(?:con\s+la\s+|alla\s+)?contrattazione\b', re.IGNORECASE),
    re.compile(r'\b(?:non\s+è\s+(?:con\s+)?(?:il\s+)?salario\s+minimo\s+(?:per\s+legge\s+)?che\s+(?:si\s+)?(?:tutelano|garantiscono|aiutano|difendono))\b', re.IGNORECASE),
    re.compile(r'\b(?:rischio\s+per\s+la\s+contrattazione|compromett(?:e|ere|erebbe)\s+(?:i\s+)?contratti\s+collettivi)\b', re.IGNORECASE),
]

# Patterns that signal explicit SUPPORT for a proposal/policy
_PRO_PATTERNS = [
    re.compile(r'\b(?:siamo favorevoli|siamo d\'accordo|sosteniamo|appoggiamo|approviamo)\b', re.IGNORECASE),
    re.compile(r'\b(?:votiamo a favore|voteremo a favore|voto favorevole)\b', re.IGNORECASE),
    re.compile(r'\b(?:è necessario introdurre|occorre introdurre|bisogna introdurre|serve introdurre)\b', re.IGNORECASE),
    re.compile(r'\b(?:proponiamo|chiediamo|auspichiamo)\s+(?:il|la|un|una|che)\b', re.IGNORECASE),
    re.compile(r'\b(?:è fondamentale|è indispensabile|è doveroso|è urgente)\b', re.IGNORECASE),
    re.compile(r'\b(?:un diritto|diritto fondamentale|diritto dei lavoratori)\b', re.IGNORECASE),
    re.compile(r'\b(?:soglia di dignità|salario dignitoso|retribuzione dignitosa|vita dignitosa)\b', re.IGNORECASE),
    re.compile(r'\b(?:parere favorevole|voto favorevole)\b', re.IGNORECASE),
    re.compile(r'\b(?:9 euro|nove euro)\b', re.IGNORECASE),
]

# Patterns that signal a CONDITIONAL/NUANCED position
_CONDITIONAL_PATTERNS = [
    re.compile(r'\b(?:a condizione che|purché|a patto che|subordinatamente)\b', re.IGNORECASE),
    re.compile(r'\b(?:ci asterremo|ci asteniamo|astensione)\b', re.IGNORECASE),
    re.compile(r'\b(?:ma bisogna|tuttavia|però occorre|pur riconoscendo)\b', re.IGNORECASE),
    re.compile(r'\b(?:non sufficiente da sola|non basta|non è sufficiente)\b', re.IGNORECASE),
]


def _detect_direction(texts: List[str]) -> Tuple[str, int, int, int]:
    """
    Scan all text passages and count PRO / CONTRO / CONDIZIONALE signal hits.

    Returns:
        (label, pro_hits, against_hits, conditional_hits)
        label is one of: "FAVOREVOLE", "CONTRARIO", "CONDIZIONALE", "NON DETERMINATO"
    """
    pro_hits = 0
    against_hits = 0
    cond_hits = 0

    for text in texts:
        for p in _PRO_PATTERNS:
            if p.search(text):
                pro_hits += 1
        for p in _AGAINST_PATTERNS:
            if p.search(text):
                against_hits += 1
        for p in _CONDITIONAL_PATTERNS:
            if p.search(text):
                cond_hits += 1

    if against_hits == 0 and pro_hits == 0 and cond_hits == 0:
        return "NON DETERMINATO", pro_hits, against_hits, cond_hits

    # Conditional is definitive only when no clear PRO/AGAINST majority
    if cond_hits > 0 and abs(pro_hits - against_hits) <= 1:
        return "CONDIZIONALE", pro_hits, against_hits, cond_hits

    if against_hits > pro_hits:
        return "CONTRARIO", pro_hits, against_hits, cond_hits
    if pro_hits > against_hits:
        return "FAVOREVOLE", pro_hits, against_hits, cond_hits

    # Tie with conditional signals → ambiguous
    if cond_hits > 0:
        return "CONDIZIONALE", pro_hits, against_hits, cond_hits

    return "NON DETERMINATO", pro_hits, against_hits, cond_hits


class PositionBriefBuilder:
    """
    Builds a position brief for a parliamentary group from evidence chunks.

    The brief includes:
    1. Estimated direction: FAVOREVOLE / CONTRARIO / CONDIZIONALE
    2. Key speakers from that group
    3. Excerpts from the top evidence chunks (by authority score)

    This is injected into the sectional writer prompt so the LLM
    understands the group's overall position before selecting citations.
    """

    def __init__(self):
        config = get_config()
        config_data = config.load_config()
        brief_config = config_data.get("generation", {}).get("position_brief", {})

        self.enabled = brief_config.get("enabled", True)
        self.max_chunks = brief_config.get("max_chunks", 5)
        self.chars_per_chunk = brief_config.get("chars_per_chunk", 200)

    @staticmethod
    def _truncate_at_boundary(text: str, max_chars: int) -> str:
        """Truncate text at a natural sentence/clause boundary."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        min_pos = max_chars // 3
        for punct in '.;!?':
            pos = truncated.rfind(punct)
            if pos > min_pos:
                return truncated[:pos + 1].rstrip()
        pos = truncated.rfind(',')
        if pos > min_pos:
            return truncated[:pos].rstrip()
        pos = truncated.rfind(' ')
        if pos > min_pos:
            return truncated[:pos].rstrip()
        return truncated.rstrip()

    def build_brief(
        self,
        evidence: List[Dict[str, Any]],
        party: str,
    ) -> str:
        """
        Build a position brief from the party's evidence.

        Args:
            evidence: Evidence list sorted by authority_score (descending)
            party: Party name

        Returns:
            Formatted position brief string (Italian), or "" if disabled/empty
        """
        if not self.enabled or not evidence:
            return ""

        top_evidence = evidence[:self.max_chunks]

        # Collect unique speakers (preserve order)
        speakers = []
        seen_speakers: set = set()
        for e in top_evidence:
            name = e.get("speaker_name", "")
            if name and name not in seen_speakers:
                speakers.append(name)
                seen_speakers.add(name)

        # Extract key passages from each chunk, annotating reported speech
        key_passages = []
        full_texts = []  # full text for direction detection (not truncated)
        reported_speech_count = 0
        reported_speech_opening_count = 0
        for e in top_evidence:
            text = e.get("quote_text", "") or e.get("chunk_text", "")
            if not text:
                continue
            full_texts.append(text)
            passage = self._truncate_at_boundary(text, self.chars_per_chunk)
            if passage:
                key_passages.append(passage)

            # Use pre-annotated result if available, otherwise run detection
            rs_info = e.get("reported_speech") or detect_reported_speech(text)
            if rs_info.get("has_reported_speech"):
                reported_speech_count += 1
                if rs_info.get("opening_is_reported"):
                    reported_speech_opening_count += 1

        if not key_passages:
            return ""

        # Detect direction from full texts
        direction, pro_hits, against_hits, cond_hits = _detect_direction(full_texts)

        logger.info(
            f"[POSITION_BRIEF] {party}: direction={direction} "
            f"(pro={pro_hits}, contro={against_hits}, cond={cond_hits})"
        )

        # Build direction label with visual emphasis for the LLM
        if direction == "CONTRARIO":
            direction_label = "⛔ CONTRARIO alla proposta/politica"
        elif direction == "FAVOREVOLE":
            direction_label = "✅ FAVOREVOLE alla proposta/politica"
        elif direction == "CONDIZIONALE":
            direction_label = "⚠️ CONDIZIONALE / SFUMATO (né puramente pro né puramente contro)"
        else:
            direction_label = "❓ NON DETERMINATO dai testi disponibili"

        brief_lines = [
            f"POSIZIONE COMPLESSIVA DEL GRUPPO ({party}):",
            f"Orientamento stimato: {direction_label}",
            f"⚠️ ATTENZIONE: scegli una citazione COERENTE con l'orientamento sopra.",
            f"   Se l'orientamento è CONTRARIO, NON citare frasi che sembrano difendere la proposta.",
            f"   Se l'orientamento è FAVOREVOLE, NON citare frasi che sembrano attaccarla.",
            f"Principali oratori: {', '.join(speakers[:3])}",
        ]

        # Fix 3 — Reported speech warning
        if reported_speech_count > 0:
            warning_level = "🚨 ALTA PRIORITÀ" if reported_speech_opening_count > 0 else "⚠️ ATTENZIONE"
            brief_lines.append(
                f"{warning_level} — DISCORSO RIPORTATO: {reported_speech_count} dei "
                f"{len(top_evidence)} testi analizzati contengono citazioni di ALTRI soggetti "
                f"(avversari, colleghi, media) riportate dal deputato per confutarle o rispondervi."
            )
            if reported_speech_opening_count > 0:
                brief_lines.append(
                    f"   ⛔ {reported_speech_opening_count} testo/i INIZIANO con discorso riportato: "
                    f"massimo rischio di inversione di posizione. "
                    f"La posizione VERA del gruppo è nella RISPOSTA del deputato, "
                    f"NON nelle parole altrui che vengono citate."
                )

        brief_lines.append(f"Sintesi dei {len(key_passages)} interventi più autorevoli:")

        for i, passage in enumerate(key_passages, 1):
            brief_lines.append(f"  {i}. «{passage}»")

        return "\n".join(brief_lines)
