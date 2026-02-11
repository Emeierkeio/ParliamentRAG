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
            # No sentence passed quality threshold — return empty
            # to signal that this evidence has no citable content
            return ""

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

        # Remove trailing incomplete punctuation (comma, semicolon, colon)
        text = text.rstrip(',;:')
        text = text.rstrip()

        return text

    # Common Italian verb forms for syntactic completeness check
    _VERB_AUXILIARIES = {
        'è', 'ha', 'sono', 'hanno', 'sia', 'siano', 'abbiamo',
        'era', 'erano', 'sarà', 'saranno', 'può', 'deve', 'vuole',
        'dobbiamo', 'possiamo', 'vogliamo', 'devono', 'possono',
        'vogliono', 'viene', 'vengono', 'va', 'vanno', 'sta', 'stanno',
        'risulta', 'risultano', 'sembra', 'sembrano', 'rappresenta',
    }

    # Regex for common Italian verb conjugation endings
    _VERB_ENDING_PATTERN = re.compile(
        r'\b\w+(?:amo|ano|ono|ato|uto|ito|ando|endo|isce|isce|iamo|ono'
        r'|ava|evano|iva|ivano|ò|ì|arono|irono|erà|irà|eranno|iranno'
        r'|asse|assero|esse|essero|isse|issero'
        r'|ando|endo|ato|uto|ito|ata|uta|ita|ati|uti|iti|ate|ute|ite)\b',
        re.IGNORECASE
    )

    def _has_verb(self, text: str) -> bool:
        """Check if text contains at least one Italian verb form."""
        words = set(re.findall(r'\b\w+\b', text.lower()))
        # Check auxiliaries
        if words & self._VERB_AUXILIARIES:
            return True
        # Check conjugation endings
        if self._VERB_ENDING_PATTERN.search(text):
            return True
        return False

    # Pattern to detect parliamentary speaker identification lines
    # e.g. "VANNIA GAVA, Vice Ministra dell'Ambiente e della sicurezza energetica."
    # These are headers, not citable speech content.
    _SPEAKER_ID_PATTERN = re.compile(
        r'^[A-Z\s\'.]+,'  # ALL CAPS name followed by comma
        r'\s*(?:Vice\s*)?'  # optional "Vice"
        r'(?:Ministr[oa]|Sottosegretari[oa]|President[e]|Segretari[oa]'
        r'|Relator[e]|Deputat[oa]|Senatric[e]|Senator[e]'
        r'|Capogruppo|Questore|Commissari[oa])',
        re.IGNORECASE
    )

    # Also catch short identification-only lines (name + party/role, no real content)
    _SHORT_ID_PATTERN = re.compile(
        r'^[A-Z][a-zàèéìòù]+\s+[A-Z][a-zàèéìòù]+\s*'  # "Nome Cognome"
        r'[,(]\s*(?:Vice\s*)?(?:Ministr|Sottosegretari|President|Gruppo|Partito)',
        re.IGNORECASE
    )

    def _is_speaker_identification(self, sentence: str) -> bool:
        """Detect parliamentary speaker identification headers.

        These are lines like "VANNIA GAVA, Vice Ministra dell'Ambiente..."
        that identify who is speaking but contain no citable content.
        """
        stripped = sentence.strip()
        if self._SPEAKER_ID_PATTERN.match(stripped):
            return True
        if self._SHORT_ID_PATTERN.match(stripped) and len(stripped) < 120:
            return True
        return False

    # Subordinating conjunctions that signal a dependent clause fragment
    _SUBORDINATING_CONJUNCTIONS = {
        'se', 'che', 'quando', 'dove', 'come', 'perché', 'poiché',
        'affinché', 'sebbene', 'benché', 'giacché', 'purché',
        'qualora', 'laddove', 'allorché', 'finché', 'ove',
    }

    # Dangling endings that signal truncation mid-phrase
    _DANGLING_ENDING_PATTERN = re.compile(
        r'\s+(?:per|di|a|da|in|con|su|il|lo|la|i|gli|le|un|uno|una|'
        r'al|alla|allo|del|della|dello|nel|nella|nello|'
        r'e|o|ma|che|né|se)$',
        re.IGNORECASE
    )

    def _syntactic_completeness_score(self, sentence: str) -> float:
        """
        Score syntactic completeness of a sentence.

        Returns:
            1.0: contains verb, starts with uppercase, no dangling ending
            0.7: complete but ends with dangling word
            0.5: contains verb but starts mid-clause
            0.2: subordinate clause fragment (starts with se/che/quando...)
            0.0: no verb detected (fragment)
        """
        if not self._has_verb(sentence):
            return 0.0

        stripped = sentence.strip()

        # Speaker identification headers are not citable content
        if self._is_speaker_identification(stripped):
            return 0.0

        first_word = re.match(r'\b(\w+)\b', stripped.lower())
        has_dangling = bool(self._DANGLING_ENDING_PATTERN.search(stripped))

        # Subordinate clause without main clause = very low quality
        if first_word and first_word.group(1) in self._SUBORDINATING_CONJUNCTIONS:
            return 0.2

        first_char = stripped[0] if stripped else ''
        if first_char.isupper() or first_char in '«"\'':
            return 0.7 if has_dangling else 1.0

        return 0.5

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
                # If sentence is very long, try splitting on semicolons/colons only
                # (these are strong clause boundaries that produce self-sufficient parts)
                if len(s) > 250:
                    sub_parts = re.split(r';', s)
                    if len(sub_parts) > 1:
                        valid_parts = [p.strip() for p in sub_parts
                                       if len(p.strip()) >= self.min_sentence_length
                                       and self._has_verb(p)]
                        if len(valid_parts) > 1:
                            sentences.extend(valid_parts)
                            continue

                sentences.append(s)

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

            completeness = self._syntactic_completeness_score(sentence)
            total_score = overlap_score * 0.45 + completeness * 0.25 + density * 0.2 + position_bonus * 0.1
            scored.append((sentence, total_score, i))

        return scored

    # Minimum completeness score to accept a citation.
    # Sentences below this (e.g. subordinate fragments) are skipped
    # in favour of lower-relevance but syntactically complete alternatives.
    MIN_QUALITY_SCORE = 0.15

    def _select_best(
        self,
        scored: List[Tuple[str, float, int]],
        max_chars: Optional[int]
    ) -> List[str]:
        """Select the best sentences within character limit.

        Prefers complete sentences that fit within the limit over
        truncating a longer sentence. Skips sentences whose completeness
        score is below MIN_QUALITY_SCORE when alternatives exist.
        """
        if not scored:
            return []

        # Sort by score descending
        sorted_by_score = sorted(scored, key=lambda x: x[1], reverse=True)

        # Filter out very low quality sentences if better alternatives exist
        if len(sorted_by_score) > 1:
            sorted_by_score = [
                s for s in sorted_by_score
                if s[1] >= self.MIN_QUALITY_SCORE
            ] or sorted_by_score[:1]  # keep at least one

        selected = []
        total_chars = 0

        for sentence, score, orig_idx in sorted_by_score:
            if len(selected) >= self.max_sentences:
                break

            if max_chars and total_chars + len(sentence) > max_chars:
                if not selected:
                    # Best sentence doesn't fit — try to find a shorter one
                    # that still scores well (at least 50% of best score)
                    best_score = sorted_by_score[0][1]
                    for alt_sentence, alt_score, alt_idx in sorted_by_score[1:]:
                        if alt_score >= best_score * 0.5 and len(alt_sentence) <= max_chars:
                            selected.append((alt_sentence, alt_idx))
                            total_chars += len(alt_sentence) + 1
                            break
                    # If still nothing fits, truncate as last resort
                    if not selected:
                        truncated = self._truncate_at_boundary(sentence, max_chars)
                        selected.append((truncated, orig_idx))
                break

            selected.append((sentence, orig_idx))
            total_chars += len(sentence) + 1  # +1 for space

        # Sort by original position to maintain reading order
        selected.sort(key=lambda x: x[1])

        return [s for s, _ in selected]

    def _truncate_at_boundary(self, text: str, max_chars: int) -> str:
        """Truncate text at the best natural boundary before max_chars.

        Priority: sentence boundary (.!?) > semicolon/colon > comma > space.
        This avoids producing quotes that end mid-phrase.
        """
        if len(text) <= max_chars:
            return text

        truncated = text[:max_chars]
        min_pos = max_chars // 3  # Don't cut too early

        # 1. Prefer sentence boundaries (. ! ?)
        for punct in '.!?':
            pos = truncated.rfind(punct)
            if pos > min_pos:
                return truncated[:pos + 1].rstrip()

        # 2. Try semicolons / colons (strong clause boundaries)
        for punct in ';:':
            pos = truncated.rfind(punct)
            if pos > min_pos:
                return truncated[:pos].rstrip()

        # 3. Try commas (weaker, but better than mid-word)
        pos = truncated.rfind(',')
        if pos > min_pos:
            return truncated[:pos].rstrip()

        # 4. Last resort: space
        pos = truncated.rfind(' ')
        if pos > min_pos:
            return truncated[:pos].rstrip()

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
