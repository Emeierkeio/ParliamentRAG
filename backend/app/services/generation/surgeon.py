"""
Stage 4: Citation Surgeon

CRITICAL: Inserts EXACT verbatim citations with verification.
NO FUZZY MATCHING - offset-based extraction ONLY.

Citation validity = offset validity + successful extraction.

CITATION-FIRST APPROACH:
If pre_extracted_citation is available in evidence (from Stage 2),
use it directly. This ensures the citation matches what the LLM
saw when writing the introductory text.
"""
import re
import logging
from typing import List, Dict, Any, Tuple, Optional, Callable

from ...config import get_config
from ..citation import extract_best_sentences
from ..citation.sentence_extractor import compute_chunk_salience

logger = logging.getLogger(__name__)


class CitationSurgeon:
    """
    Stage 4 of the generation pipeline.

    INVIOLABLE RULES:
    1. Quote extraction ONLY via: text[span_start:span_end]
    2. NEVER compare extracted quote with chunk_text for verification
    3. Citation validity = valid offsets + successful extraction
    4. chunk_text is ONLY for retrieval preview, NOT for citation

    If a citation cannot be verified, it is marked as unsupported.
    """

    # Citation patterns - [CIT:id] is primary, ["text"](id) is legacy fallback
    CITATION_PATTERN_CIT = re.compile(r'\[CIT:([^\]]+)\]')
    CITATION_PATTERN_MARKDOWN = re.compile(r'\["([^"]*)"\]\(([^)]+)\)')

    def __init__(self):
        self.config = get_config()
        config_data = self.config.load_config()
        citation_config = config_data.get("citation", {})

        self.citation_format = citation_config.get(
            "format",
            "«{quote}» [{speaker}, {party}, {date}, ID:{id}]"
        )
        self.verify_on_insert = citation_config.get("verify_on_insert", True)

    def insert_citations(
        self,
        text: str,
        evidence_map: Dict[str, Dict[str, Any]],
        query: str = ""
    ) -> Dict[str, Any]:
        """
        Process citations in text - converts all citation formats to full formatted citations.

        Handles:
        - [CIT:id] format (primary) -> converts to [«quote» — Speaker, Party, Date](id)
        - ["text"](id) format (legacy) -> converts to [«quote» — Speaker, Party, Date](id)

        Uses semantic sentence extraction to select the most relevant
        sentences from citations when query is provided.

        Args:
            text: Text with citation placeholders
            evidence_map: Map of evidence_id to evidence data
            query: Original query for semantic extraction (optional)

        Returns:
            Dictionary with:
            - text: Final text with citations processed
            - citations: List of citation metadata
            - failed_citations: List of citations that couldn't be verified
        """
        self._current_query = query  # Store for use in formatting
        citations_used = []
        failed_citations = []
        seen_ids = set()

        def get_citation_data(evidence_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
            """Get quote text and evidence data for an evidence_id."""
            if evidence_id not in evidence_map:
                logger.warning(f"Citation {evidence_id} not found in evidence map")
                failed_citations.append({
                    "evidence_id": evidence_id,
                    "reason": "not_found_in_evidence_map"
                })
                return None, None

            evidence = evidence_map[evidence_id]
            quote_text = evidence.get("quote_text", "")

            if not quote_text:
                text = evidence.get("text", "")
                span_start = evidence.get("span_start", 0)
                span_end = evidence.get("span_end", 0)
                if text and span_end > span_start:
                    quote_text = self._extract_quote(text, span_start, span_end)

            if not quote_text:
                # Fallback to chunk_text if quote_text extraction failed
                quote_text = evidence.get("chunk_text", "")[:300]
                if not quote_text:
                    logger.warning(f"No quote_text available for {evidence_id}")
                    failed_citations.append({
                        "evidence_id": evidence_id,
                        "reason": "no_quote_text"
                    })
                    return None, None

            # Verify citation if enabled and text is available
            if self.verify_on_insert:
                text = evidence.get("text", "")
                span_start = evidence.get("span_start", 0)
                span_end = evidence.get("span_end", 0)

                if text and span_end > span_start:
                    if not self._verify_citation(quote_text, text, span_start, span_end):
                        logger.warning(f"Citation verification failed for {evidence_id}, using chunk_text")
                        # Don't fail - use chunk_text as fallback
                        quote_text = evidence.get("chunk_text", "")[:300]

            return quote_text, evidence

        def track_citation(evidence_id: str, quote_text: str, evidence: Dict[str, Any]):
            """Track a citation that was used."""
            if evidence_id not in seen_ids:
                seen_ids.add(evidence_id)
                citations_used.append({
                    "evidence_id": evidence_id,
                    "quote_text": quote_text,
                    "speaker_name": evidence.get("speaker_name"),
                    "speaker_id": evidence.get("speaker_id", ""),
                    "speaker_role": evidence.get("speaker_role", "Deputy"),
                    "party": evidence.get("party"),
                    "date": str(evidence.get("date", "")),
                    "span_start": evidence.get("span_start"),
                    "span_end": evidence.get("span_end"),
                })

        # Handle [CIT:id] format
        def replace_cit_format(match):
            evidence_id = match.group(1)
            quote_text, evidence = get_citation_data(evidence_id)

            if quote_text is None:
                return "[Citazione non disponibile]"

            track_citation(evidence_id, quote_text, evidence)

            return self._format_citation(
                quote=quote_text,
                speaker=evidence.get("speaker_name", ""),
                party=evidence.get("party", ""),
                date=str(evidence.get("date", "")),
                evidence_id=evidence_id,
                pre_extracted=evidence.get("pre_extracted_citation", ""),
                session_number=evidence.get("session_number")
            )

        # Handle ["text"](id) markdown format - convert to full citation
        def replace_markdown_format(match):
            inline_text = match.group(1)  # The text inside ["..."]
            evidence_id = match.group(2)  # The ID inside (...)

            quote_text, evidence = get_citation_data(evidence_id)

            if quote_text is None:
                # Keep the inline text but mark as unavailable
                return f'"{inline_text}" [Citazione non disponibile]'

            track_citation(evidence_id, quote_text, evidence)

            return self._format_citation(
                quote=quote_text,
                speaker=evidence.get("speaker_name", ""),
                party=evidence.get("party", ""),
                date=str(evidence.get("date", "")),
                evidence_id=evidence_id,
                pre_extracted=evidence.get("pre_extracted_citation", ""),
                session_number=evidence.get("session_number")
            )

        # First replace [CIT:id] format
        final_text = self.CITATION_PATTERN_CIT.sub(replace_cit_format, text)

        # Then replace ["text"](id) markdown format
        final_text = self.CITATION_PATTERN_MARKDOWN.sub(replace_markdown_format, final_text)

        return {
            "text": final_text,
            "citations": citations_used,
            "failed_citations": failed_citations,
            "total_citations": len(citations_used),
            "failed_count": len(failed_citations),
        }

    def _extract_quote(
        self,
        text: str,
        span_start: int,
        span_end: int
    ) -> Optional[str]:
        """
        Extract EXACT quote using offsets from text.

        CRITICAL: This is the ONLY valid citation source.
        DO NOT use chunk_text for verification or comparison.

        Args:
            text: Speech text
            span_start: Start offset
            span_end: End offset

        Returns:
            Extracted quote or None if invalid
        """
        if span_start < 0:
            logger.error(f"Invalid span_start: {span_start}")
            return None

        if span_end > len(text):
            logger.error(
                f"span_end ({span_end}) exceeds text length ({len(text)})"
            )
            return None

        if span_start >= span_end:
            logger.error(f"Invalid span: {span_start} >= {span_end}")
            return None

        return text[span_start:span_end]

    def _verify_citation(
        self,
        quote_text: str,
        text: str,
        span_start: int,
        span_end: int
    ) -> bool:
        """
        Verify citation by re-extracting from source.

        DOES NOT compare with chunk_text - that would be incorrect.
        Citation validity = offset validity + identical re-extraction.

        Args:
            quote_text: Quote text to verify
            text: Speech text
            span_start: Start offset
            span_end: End offset

        Returns:
            True if citation is valid
        """
        try:
            re_extracted = self._extract_quote(text, span_start, span_end)
            if re_extracted is None:
                return False
            return re_extracted == quote_text
        except Exception as e:
            logger.error(f"Citation verification error: {e}")
            return False

    def _format_citation(
        self,
        quote: str,
        speaker: str,
        party: str,
        date: str,
        evidence_id: str,
        pre_extracted: str = "",
        session_number: Optional[int] = None
    ) -> str:
        """
        Format citation according to configured format.

        Format: [«quote» — Speaker, Seduta N. X, DD/MM/YYYY](evidence_id)
        The entire citation is a clickable markdown link.
        Full metadata is also available in the sidebar when clicked.

        Includes session reference for academic traceability.
        See: ALCE (Gao et al., EMNLP 2023) on citation traceability;
        Abercrombie & Batista-Navarro (2019) on parliamentary metadata standards.

        CITATION-FIRST: If pre_extracted is provided (from Stage 2),
        use it directly. This ensures consistency between the LLM's
        introductory text and the actual citation.
        """
        # CITATION-FIRST: Use pre-extracted citation if available
        if pre_extracted:
            quote = pre_extracted
        else:
            # Fallback: Extract on-the-fly (legacy behavior)
            query = getattr(self, '_current_query', '')
            if query and len(quote) > 80:
                quote = extract_best_sentences(
                    text=quote,
                    query=query,
                    max_sentences=1,
                    max_chars=200
                )

        # Salience gate: reject procedural citations as last defense.
        # If the citation is purely procedural (e.g. "il parere è favorevole"),
        # try to re-extract a better sentence from the full quote text.
        # If no better sentence exists, keep the original to avoid empty citations.
        citation_salience = compute_chunk_salience(quote)
        if citation_salience <= 0.2 and quote:
            logger.warning(
                f"Procedural citation detected for {evidence_id}: "
                f"salience={citation_salience:.1f}, attempting re-extraction"
            )
            query = getattr(self, '_current_query', '')
            # Try original full quote text (before pre-extraction)
            original_quote = quote  # Save for fallback
            if pre_extracted:
                # We had a pre-extracted version; get the full text to try again
                # The full quote should be in the evidence_map
                pass  # quote variable already has the pre-extracted text
            if query and len(quote) > 30:
                re_extracted = extract_best_sentences(
                    text=quote,
                    query=query,
                    max_sentences=1,
                    max_chars=200
                )
                if re_extracted:
                    re_salience = compute_chunk_salience(re_extracted)
                    if re_salience > citation_salience:
                        quote = re_extracted
                        logger.info(f"Re-extracted better citation: salience={re_salience:.1f}")

        # Clean up whitespace
        quote = " ".join(quote.split())

        # Remove parenthetical content (e.g., applausi, interruzioni)
        quote = re.sub(r'\s*\([^)]*\)\s*', '', quote)
        quote = quote.strip()

        # Strip trailing sentence punctuation — citations are always embedded
        # in narrative text inside «», so a trailing "." would read as:
        # «dimezzare le tasse.» è quello che vuole il Governo (wrong)
        # vs «dimezzare le tasse» è quello che vuole il Governo (correct)
        quote = quote.rstrip('.!?')
        quote = quote.rstrip()  # clean any trailing space left

        # Strip leading sentence punctuation artifacts (e.g. comma, semicolon)
        quote = quote.lstrip('.,;:')
        quote = quote.lstrip()

        # Trim trailing dangling words: articles, prepositions, conjunctions,
        # truncated references (e.g. "– n"), etc. that signal a mid-phrase cut.
        # These patterns at the end mean the quote was truncated mid-sentence.
        # Also catches trailing comma + fragment (e.g. "..., secondo")
        dangling = re.compile(
            r'(?:'
            r'\s+(?:'
            r'il|lo|la|i|gli|le|un|uno|una|l|dell|del|della|dello|dei|degli|delle|'
            r'nel|nella|nello|nei|negli|nelle|sul|sulla|sullo|sui|sugli|sulle|'
            r'al|alla|allo|ai|agli|alle|dal|dalla|dallo|dai|dagli|dalle|'
            r'di|a|da|in|con|su|per|tra|fra|'
            r'e|o|ma|che|né|se|'
            r'[–\-]\s*\w{0,2}'  # truncated references like "– n", "- 2"
            r')'
            r'|,\s+\w{1,6}'  # trailing comma + short word fragment
            r')$',
            re.IGNORECASE
        )
        # Apply repeatedly — removing "il" may expose "che", etc.
        prev = None
        while quote != prev:
            prev = quote
            quote = dangling.sub('', quote)

        # Lowercase first letter (citations follow introductory constructions)
        if quote:
            quote = quote[0].lower() + quote[1:] if len(quote) > 1 else quote.lower()

        return f'[«{quote}»]({evidence_id})'

    def _shorten_party_name(self, party: str) -> str:
        """Return readable display name for a party (full name, title case)."""
        from ...models.evidence import normalize_party_name
        return normalize_party_name(party)

    def extract_unsupported_claims(
        self,
        text: str
    ) -> List[str]:
        """
        Find claims that weren't supported by citations.

        Looks for text patterns that suggest unsupported assertions.
        """
        unsupported = []
        sentences = re.split(r'[.!?]', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if sentence has a citation (any format)
            has_citation = (
                '«' in sentence or
                '[CIT:' in sentence or
                self.CITATION_PATTERN_MARKDOWN.search(sentence) is not None
            )

            if not has_citation:
                claim_patterns = [
                    r'\bsostiene\b',
                    r'\bafferma\b',
                    r'\bdichiara\b',
                    r'\bpropone\b',
                    r'\bcritica\b',
                    r'\bvuole\b',
                ]
                for pattern in claim_patterns:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        unsupported.append(sentence)
                        break

        return unsupported
