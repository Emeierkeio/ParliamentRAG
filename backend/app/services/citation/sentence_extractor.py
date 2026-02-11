"""
Semantic Sentence Extractor for citations.

Extracts the most semantically relevant sentences from a text chunk
relative to a query, avoiding arbitrary truncation.

Uses a lightweight keyword-based approach for efficiency.
"""
import re
import logging
from typing import List, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class SentenceExtractor:
    """
    Extracts the most semantically relevant sentences from text.

    Uses keyword overlap scoring for fast, efficient extraction
    without requiring API calls.
    """

    # Italian stop words to ignore
    STOP_WORDS = {
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
        "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
        "e", "o", "ma", "che", "chi", "cui", "quale", "quanto",
        "questo", "quello", "codesto", "stesso", "medesimo",
        "tale", "altro", "certo", "alcuno", "nessuno", "ogni",
        "ciascuno", "tutto", "tanto", "molto", "poco", "troppo",
        "parecchio", "alquanto", "altrettanto", "più", "meno",
        "come", "dove", "quando", "perché", "se", "non", "né",
        "anche", "pure", "inoltre", "dunque", "quindi", "però",
        "essere", "avere", "fare", "dire", "potere", "dovere",
        "volere", "sapere", "venire", "andare", "stare", "dare",
        "è", "sono", "ha", "hanno", "sia", "siano", "era", "erano",
        "stato", "stata", "stati", "state", "dell", "della", "dello",
        "dei", "degli", "delle", "nel", "nella", "nello", "nei",
        "negli", "nelle", "sul", "sulla", "sullo", "sui", "sugli",
        "sulle", "al", "alla", "allo", "ai", "agli", "alle",
        "dal", "dalla", "dallo", "dai", "dagli", "dalle",
        "col", "coi", "pel", "pei"
    }

    def __init__(self, max_sentences: int = 2, min_sentence_length: int = 30):
        """
        Initialize the extractor.

        Args:
            max_sentences: Maximum number of sentences to extract
            min_sentence_length: Minimum characters for a valid sentence
        """
        self.max_sentences = max_sentences
        self.min_sentence_length = min_sentence_length

    def extract(
        self,
        text: str,
        query: str,
        max_total_chars: Optional[int] = 500
    ) -> str:
        """
        Extract the most relevant sentences from text.

        Args:
            text: Full text to extract from
            query: Query to match against
            max_total_chars: Maximum total characters (soft limit)

        Returns:
            Extracted relevant sentence(s)
        """
        if not text or not query:
            return text[:max_total_chars] if text and max_total_chars else text

        # Split into sentences
        sentences = self._split_sentences(text)

        if not sentences:
            return text[:max_total_chars] if max_total_chars else text

        # Score each sentence
        scored = self._score_sentences(sentences, query)

        # Select best sentences
        selected = self._select_best(scored, max_total_chars)

        if not selected:
            # Fallback to first sentence
            return self._clean_result(sentences[0] if sentences else text)

        result = " ".join(selected)
        return self._clean_result(result)

    def _clean_result(self, text: str) -> str:
        """Clean up the extracted text for display."""
        text = text.strip()

        # Remove leading lowercase connectors
        leading_patterns = [
            r'^(e|o|ma|che|chi|cui|dove|quando|perché|se|però|quindi|dunque|inoltre|anche|pure)\s+',
            r'^(da|di|a|con|per|tra|fra|su|in)\s+(una?|il|lo|la|i|gli|le)\s+',
        ]
        for pattern in leading_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Capitalize first letter
        if text and text[0].islower():
            text = text[0].upper() + text[1:]

        # Remove trailing incomplete phrases (ending with comma)
        if text.endswith(','):
            text = text[:-1]

        return text

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences or meaningful clauses.

        Optimized for Italian parliamentary language which tends to have
        very long sentences with multiple subordinate clauses.
        """
        # Clean up whitespace
        text = " ".join(text.split())

        # Split on sentence boundaries (. ! ?)
        pattern = r'(?<=[.!?])\s+(?=[A-Z«])'
        raw_sentences = re.split(pattern, text)

        # Filter and clean sentences
        sentences = []
        for s in raw_sentences:
            s = s.strip()
            if len(s) >= self.min_sentence_length:
                # If sentence is long, try progressive splitting
                if len(s) > 200:
                    # First try semicolons and colons
                    sub_parts = re.split(r'[;:]', s)
                    if len(sub_parts) > 1:
                        for part in sub_parts:
                            part = part.strip()
                            if len(part) >= self.min_sentence_length:
                                sentences.append(part)
                        continue

                    # Then try splitting on subordinate clauses
                    clause_parts = self._split_on_subordinates(s)
                    if clause_parts:
                        sentences.extend(clause_parts)
                        continue

                sentences.append(s)

        # If still no valid sentences or all are too long, split on commas
        if not sentences or (len(sentences) == 1 and len(sentences[0]) > 200):
            comma_parts = self._split_on_meaningful_commas(text)
            if comma_parts:
                sentences = comma_parts

        # Final fallback
        if not sentences and len(text) >= self.min_sentence_length:
            sentences = [text]

        return sentences

    def _split_on_subordinates(self, text: str) -> List[str]:
        """
        Split long sentences on Italian subordinate clause markers.

        Targets patterns like "che ha", "che sono", "il quale", etc.
        which are common in parliamentary speech.
        """
        # Pattern for subordinate clause markers followed by verb indicators
        # Match ", che " or " che " followed by common verb forms
        subordinate_pattern = r',?\s+che\s+(?=\w+(?:a|e|o|ano|ono|isce|isce)\b)'

        parts = re.split(subordinate_pattern, text, flags=re.IGNORECASE)

        if len(parts) <= 1:
            return []

        # Clean and filter parts
        result = []
        for part in parts:
            part = part.strip()
            if len(part) >= self.min_sentence_length:
                result.append(part)

        return result if len(result) > 1 else []

    def _split_on_meaningful_commas(self, text: str) -> List[str]:
        """
        Split long text on commas, keeping meaningful chunks.
        Groups comma-separated clauses into reasonable sizes.

        Optimized for 150 char citation limit - chunks target ~120 chars.
        """
        parts = text.split(',')
        if len(parts) <= 1:
            return []

        chunks = []
        current_chunk = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Add comma back for natural reading
            test_chunk = f"{current_chunk}, {part}" if current_chunk else part

            # Target ~120 chars to stay comfortably under 150 limit
            if len(test_chunk) < 120:
                # Keep building the chunk
                current_chunk = test_chunk
            else:
                # Save current chunk and start new one
                if current_chunk and len(current_chunk) >= self.min_sentence_length:
                    chunks.append(current_chunk)
                current_chunk = part

        # Don't forget the last chunk
        if current_chunk and len(current_chunk) >= self.min_sentence_length:
            chunks.append(current_chunk)

        return chunks if len(chunks) > 1 else []

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words, removing stop words."""
        # Lowercase and extract words
        words = re.findall(r'\b[a-zA-Zàèéìòù]{3,}\b', text.lower())
        # Remove stop words
        return [w for w in words if w not in self.STOP_WORDS]

    def _score_sentences(
        self,
        sentences: List[str],
        query: str
    ) -> List[Tuple[str, float, int]]:
        """
        Score sentences by relevance to query.

        Returns list of (sentence, score, original_index) tuples.
        """
        query_tokens = set(self._tokenize(query))

        if not query_tokens:
            # No meaningful query tokens, return sentences with position score
            return [(s, 1.0 / (i + 1), i) for i, s in enumerate(sentences)]

        scored = []
        for i, sentence in enumerate(sentences):
            sentence_tokens = self._tokenize(sentence)

            if not sentence_tokens:
                scored.append((sentence, 0.0, i))
                continue

            # Calculate overlap score
            sentence_set = set(sentence_tokens)
            overlap = query_tokens & sentence_set

            # Score = overlap ratio + position bonus (earlier = better)
            overlap_score = len(overlap) / len(query_tokens)
            position_bonus = 0.1 * (1.0 / (i + 1))  # Small bonus for earlier sentences

            # Density bonus - how many query words per sentence length
            density = len(overlap) / len(sentence_tokens) if sentence_tokens else 0

            total_score = overlap_score * 0.6 + density * 0.3 + position_bonus * 0.1
            scored.append((sentence, total_score, i))

        return scored

    def _select_best(
        self,
        scored: List[Tuple[str, float, int]],
        max_chars: Optional[int]
    ) -> List[str]:
        """Select the best sentences within character limit."""
        if not scored:
            return []

        # Sort by score descending
        sorted_by_score = sorted(scored, key=lambda x: x[1], reverse=True)

        selected = []
        total_chars = 0

        for sentence, score, orig_idx in sorted_by_score:
            if len(selected) >= self.max_sentences:
                break

            if max_chars and total_chars + len(sentence) > max_chars:
                # Check if we have at least one sentence
                if not selected:
                    # Truncate on the last comma before max_chars
                    truncated = self._truncate_at_boundary(sentence, max_chars)
                    selected.append((truncated, orig_idx))
                break

            selected.append((sentence, orig_idx))
            total_chars += len(sentence) + 1  # +1 for space

        # Sort by original position to maintain reading order
        selected.sort(key=lambda x: x[1])

        return [s for s, _ in selected]

    def _truncate_at_boundary(self, text: str, max_chars: int) -> str:
        """Truncate text at the last comma or semicolon before max_chars."""
        if len(text) <= max_chars:
            return text

        # Look for last comma or semicolon within limit
        truncated = text[:max_chars]
        last_comma = truncated.rfind(',')
        last_semicolon = truncated.rfind(';')
        cut_point = max(last_comma, last_semicolon)

        if cut_point > max_chars // 3:
            return truncated[:cut_point].rstrip()

        # No good boundary found - cut at last space
        last_space = truncated.rfind(' ')
        if last_space > max_chars // 3:
            return truncated[:last_space].rstrip()

        return truncated.rstrip()


# Module-level convenience function
_extractor = None

def extract_best_sentences(
    text: str,
    query: str,
    max_sentences: int = 2,
    max_chars: int = 500
) -> str:
    """
    Extract the most relevant sentences from text.

    Convenience function that uses a shared extractor instance.

    Args:
        text: Full text to extract from
        query: Query to match against
        max_sentences: Maximum sentences to extract
        max_chars: Maximum total characters

    Returns:
        Extracted relevant sentence(s)
    """
    global _extractor
    if _extractor is None or _extractor.max_sentences != max_sentences:
        _extractor = SentenceExtractor(max_sentences=max_sentences)

    return _extractor.extract(text, query, max_chars)
