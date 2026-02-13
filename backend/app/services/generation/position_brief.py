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
import logging
from typing import List, Dict, Any

from ...config import get_config

logger = logging.getLogger(__name__)


class PositionBriefBuilder:
    """
    Builds a position brief for a parliamentary group from evidence chunks.

    The brief includes:
    1. Key speakers from that group
    2. Excerpts from the top evidence chunks (by authority score)

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

        # Extract key passages from each chunk
        key_passages = []
        for e in top_evidence:
            text = e.get("quote_text", "") or e.get("chunk_text", "")
            if not text:
                continue
            passage = self._truncate_at_boundary(text, self.chars_per_chunk)
            if passage:
                key_passages.append(passage)

        if not key_passages:
            return ""

        brief_lines = [
            f"POSIZIONE COMPLESSIVA DEL GRUPPO ({party}):",
            f"Principali oratori: {', '.join(speakers[:3])}",
            f"Sintesi dei {len(key_passages)} interventi più autorevoli:",
        ]

        for i, passage in enumerate(key_passages, 1):
            brief_lines.append(f"  {i}. «{passage}»")

        return "\n".join(brief_lines)
