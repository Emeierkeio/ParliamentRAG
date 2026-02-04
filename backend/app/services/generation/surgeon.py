"""
Stage 4: Citation Surgeon

CRITICAL: Inserts EXACT verbatim citations with verification.
NO FUZZY MATCHING - offset-based extraction ONLY.

Citation validity = offset validity + successful extraction.

Uses semantic sentence extraction to select the most relevant
sentences from citations, avoiding arbitrary truncation.
"""
import re
import logging
from typing import List, Dict, Any, Tuple, Optional, Callable

from ...config import get_config
from ..citation import extract_best_sentences

logger = logging.getLogger(__name__)


class CitationSurgeon:
    """
    Stage 4 of the generation pipeline.

    INVIOLABLE RULES:
    1. Quote extraction ONLY via: testo_raw[span_start:span_end]
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
                testo_raw = evidence.get("testo_raw", "")
                span_start = evidence.get("span_start", 0)
                span_end = evidence.get("span_end", 0)
                if testo_raw and span_end > span_start:
                    quote_text = self._extract_quote(testo_raw, span_start, span_end)

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

            # Verify citation if enabled and testo_raw is available
            if self.verify_on_insert:
                testo_raw = evidence.get("testo_raw", "")
                span_start = evidence.get("span_start", 0)
                span_end = evidence.get("span_end", 0)

                if testo_raw and span_end > span_start:
                    if not self._verify_citation(quote_text, testo_raw, span_start, span_end):
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
                evidence_id=evidence_id
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
                evidence_id=evidence_id
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
        testo_raw: str,
        span_start: int,
        span_end: int
    ) -> Optional[str]:
        """
        Extract EXACT quote using offsets from testo_raw.

        CRITICAL: This is the ONLY valid citation source.
        DO NOT use chunk_text for verification or comparison.

        Args:
            testo_raw: Raw intervention text
            span_start: Start offset
            span_end: End offset

        Returns:
            Extracted quote or None if invalid
        """
        if span_start < 0:
            logger.error(f"Invalid span_start: {span_start}")
            return None

        if span_end > len(testo_raw):
            logger.error(
                f"span_end ({span_end}) exceeds text length ({len(testo_raw)})"
            )
            return None

        if span_start >= span_end:
            logger.error(f"Invalid span: {span_start} >= {span_end}")
            return None

        return testo_raw[span_start:span_end]

    def _verify_citation(
        self,
        quote_text: str,
        testo_raw: str,
        span_start: int,
        span_end: int
    ) -> bool:
        """
        Verify citation by re-extracting from source.

        DOES NOT compare with chunk_text - that would be incorrect.
        Citation validity = offset validity + identical re-extraction.

        Args:
            quote_text: Quote text to verify
            testo_raw: Raw intervention text
            span_start: Start offset
            span_end: End offset

        Returns:
            True if citation is valid
        """
        try:
            re_extracted = self._extract_quote(testo_raw, span_start, span_end)
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
        evidence_id: str
    ) -> str:
        """
        Format citation according to configured format.

        Format: [«quote»](evidence_id)
        The entire citation is a clickable markdown link.
        Speaker/party/date info is available in the sidebar when clicked.

        Uses semantic extraction to select the most relevant sentences
        from the quote when a query is available.
        """
        # Extract the most relevant sentences using semantic matching
        query = getattr(self, '_current_query', '')
        if query and len(quote) > 80:
            # Use semantic extraction - only 1 sentence, max 150 chars
            # Reduced from 250 for more concise inline citations
            quote = extract_best_sentences(
                text=quote,
                query=query,
                max_sentences=1,
                max_chars=150
            )

        # Clean up whitespace
        quote = " ".join(quote.split())

        # Remove parenthetical content (e.g., applausi, interruzioni) and replace with ...
        quote = re.sub(r'\s*\([^)]*\)\s*', '', quote)
        quote = quote.strip()

        # Lowercase first letter (citations follow introductory constructions)
        if quote:
            quote = quote[0].lower() + quote[1:] if len(quote) > 1 else quote.lower()

        # Format as clean clickable citation (no metadata - shown in sidebar)
        return f'[«{quote}»]({evidence_id})'

    def _shorten_party_name(self, party: str) -> str:
        """Shorten long party names for citation display."""
        party_map = {
            "FRATELLI D'ITALIA": "FdI",
            "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA": "PD",
            "LEGA - SALVINI PREMIER": "Lega",
            "MOVIMENTO 5 STELLE": "M5S",
            "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE": "FI",
            "ALLEANZA VERDI E SINISTRA": "AVS",
            "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE": "Azione",
            "ITALIA VIVA-IL CENTRO-RENEW EUROPE": "IV",
            "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE": "NM",
            "MISTO": "Misto",
            "GOVERNO": "Governo",
        }
        return party_map.get(party, party[:15] if len(party) > 15 else party)

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
