"""
Semantic Coherence Validator.

Verifies that introductory text matches citation content semantically.
Uses lightweight keyword-based approach (no API calls) for fast validation.

This is a critical component for ensuring citation integrity:
- The text that introduces a citation must reflect its actual content
- A positive intro ("elogia", "sostiene") cannot introduce a negative quote
- Keyword overlap ensures topical alignment
"""
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CoherenceValidator:
    """
    Validates semantic coherence between intro text and citations.

    Uses keyword overlap scoring for fast validation without API calls.

    Example:
        validator = CoherenceValidator(min_coherence_score=0.2)

        result = validator.validate_coherence(
            intro_text="Il deputato critica la gestione sanitaria",
            quote_text="il sistema sanitario è in crisi per mancanza di fondi"
        )

        if not result["is_coherent"]:
            print(f"Warning: {result['warning']}")
    """

    # Italian stop words to filter out
    STOP_WORDS = {
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
        "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
        "e", "o", "ma", "che", "non", "anche", "come", "questo",
        "quello", "essere", "avere", "fare", "dire", "dovere",
        "potere", "volere", "sapere", "andare", "venire", "stare",
        "del", "della", "dei", "delle", "dello", "degli", "al",
        "alla", "ai", "alle", "allo", "agli", "dal", "dalla",
        "nel", "nella", "nei", "nelle", "nello", "negli", "sul",
        "sulla", "sui", "sulle", "sullo", "sugli", "col", "coi",
        "sono", "sia", "stato", "stata", "stati", "state", "hanno",
        "ha", "ho", "hai", "abbiamo", "avete", "era", "erano",
        "sarà", "saranno", "si", "ci", "vi", "ne", "mi", "ti",
        "loro", "lui", "lei", "noi", "voi", "se", "quando", "dove",
        "perché", "perche", "quindi", "però", "pero", "dunque",
        "così", "cosi", "poi", "già", "gia", "ancora", "sempre",
        "mai", "molto", "poco", "più", "piu", "meno", "tutto",
        "tutti", "tutte", "ogni", "qualche", "alcuni", "alcune",
        "altro", "altri", "altre", "quale", "quali", "quanto",
        "quanti", "quante", "chi", "cosa", "cui", "proprio"
    }

    # Positive sentiment indicators (praise, support)
    POSITIVE_INDICATORS = {
        "sostiene", "difende", "elogia", "promuove", "appoggia",
        "approva", "plaude", "apprezza", "condivide", "supporta",
        "conferma", "ribadisce", "valorizza", "esalta", "celebra"
    }

    # Negative sentiment indicators (criticism, opposition)
    NEGATIVE_INDICATORS = {
        "critica", "denuncia", "contesta", "attacca", "respinge",
        "oppone", "condanna", "stigmatizza", "deplora", "lamenta",
        "controbatte", "rifiuta", "contrasta", "rigetta", "boccia"
    }

    def __init__(self, min_coherence_score: float = 0.2):
        """
        Initialize validator.

        Args:
            min_coherence_score: Minimum score for text to be considered coherent (0.0-1.0)
        """
        self.min_coherence_score = min_coherence_score

    def validate_coherence(
        self,
        intro_text: str,
        quote_text: str
    ) -> Dict[str, Any]:
        """
        Validate semantic coherence between intro and quote.

        Args:
            intro_text: The introductory text before the citation
            quote_text: The actual citation text

        Returns:
            Dictionary with:
            - is_coherent: Boolean indicating if texts are coherent
            - score: Keyword overlap score (0.0-1.0)
            - overlap_keywords: List of matching keywords
            - sentiment_mismatch: Boolean if sentiments contradict
            - warning: Optional warning message
        """
        # Tokenize
        intro_tokens = self._tokenize(intro_text)
        quote_tokens = self._tokenize(quote_text)

        if not intro_tokens or not quote_tokens:
            return {
                "is_coherent": True,  # Can't validate, assume OK
                "score": 0.0,
                "warning": "Empty tokens - cannot validate",
                "intro_tokens": len(intro_tokens),
                "quote_tokens": len(quote_tokens),
                "overlap_keywords": [],
                "sentiment_mismatch": False
            }

        # Keyword overlap score
        intro_set = set(intro_tokens)
        quote_set = set(quote_tokens)
        overlap = intro_set & quote_set

        # Calculate Jaccard-like score
        union_size = len(intro_set | quote_set)
        overlap_score = len(overlap) / union_size if union_size > 0 else 0

        # Check for sentiment contradiction
        intro_sentiment = self._detect_sentiment(intro_text)
        quote_sentiment = self._detect_sentiment(quote_text)

        sentiment_mismatch = (
            intro_sentiment is not None and
            quote_sentiment is not None and
            intro_sentiment != quote_sentiment
        )

        # Final coherence decision
        is_coherent = overlap_score >= self.min_coherence_score and not sentiment_mismatch

        result = {
            "is_coherent": is_coherent,
            "score": round(overlap_score, 3),
            "overlap_keywords": list(overlap)[:10],
            "intro_sentiment": intro_sentiment,
            "quote_sentiment": quote_sentiment,
            "sentiment_mismatch": sentiment_mismatch
        }

        if sentiment_mismatch:
            result["warning"] = f"Sentiment mismatch: intro={intro_sentiment}, quote={quote_sentiment}"
            logger.warning(f"Coherence: Sentiment mismatch detected - intro={intro_sentiment}, quote={quote_sentiment}")

        elif overlap_score < self.min_coherence_score:
            result["warning"] = f"Low keyword overlap: {overlap_score:.2f} < {self.min_coherence_score}"
            logger.warning(f"Coherence: Low overlap score {overlap_score:.2f}")

        return result

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize and filter Italian text.

        Args:
            text: Input text

        Returns:
            List of meaningful tokens (no stop words, min 3 chars)
        """
        # Extract words with Italian accented characters
        words = re.findall(r'\b[a-zA-ZàèéìòùÀÈÉÌÒÙ]{3,}\b', text.lower())
        return [w for w in words if w not in self.STOP_WORDS]

    def _detect_sentiment(self, text: str) -> Optional[str]:
        """
        Detect positive/negative sentiment indicators in text.

        Args:
            text: Input text

        Returns:
            "positive", "negative", or None if mixed/neutral
        """
        text_lower = text.lower()

        has_positive = any(ind in text_lower for ind in self.POSITIVE_INDICATORS)
        has_negative = any(ind in text_lower for ind in self.NEGATIVE_INDICATORS)

        if has_positive and not has_negative:
            return "positive"
        elif has_negative and not has_positive:
            return "negative"
        else:
            return None  # Mixed or neutral

    def validate_all_citations(
        self,
        text_with_citations: str,
        evidence_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate all citations in a text.

        Args:
            text_with_citations: Text with [CIT:id] placeholders
            evidence_map: Map of evidence_id to evidence data

        Returns:
            Validation report with:
            - total_citations: Number of citations found
            - coherent_citations: Number passing coherence check
            - incoherent_citations: Number failing
            - all_coherent: Boolean
            - details: List of per-citation results
        """
        results = []

        # Find all citations with their context
        # Match sentence containing [CIT:id]
        pattern = r'([^.!?]*\[CIT:([^\]]+)\][^.!?]*[.!?]?)'
        matches = re.findall(pattern, text_with_citations)

        for full_match, evidence_id in matches:
            if evidence_id not in evidence_map:
                results.append({
                    "evidence_id": evidence_id,
                    "is_coherent": False,
                    "warning": "Evidence not found in map"
                })
                continue

            evidence = evidence_map[evidence_id]
            quote_text = evidence.get("quote_text") or evidence.get("chunk_text", "")

            # Extract intro (text before [CIT:])
            parts = full_match.split(f"[CIT:{evidence_id}]")
            intro = parts[0].strip() if parts else ""

            validation = self.validate_coherence(intro, quote_text)
            validation["evidence_id"] = evidence_id
            validation["intro_text"] = intro[:100] + "..." if len(intro) > 100 else intro
            validation["quote_preview"] = quote_text[:100] + "..." if len(quote_text) > 100 else quote_text

            results.append(validation)

        # Summary
        coherent_count = sum(1 for r in results if r.get("is_coherent", False))

        return {
            "total_citations": len(results),
            "coherent_citations": coherent_count,
            "incoherent_citations": len(results) - coherent_count,
            "all_coherent": coherent_count == len(results),
            "average_score": (
                sum(r.get("score", 0) for r in results) / len(results)
                if results else 0
            ),
            "details": results
        }

    def get_incoherent_citations(
        self,
        validation_report: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract only incoherent citations from a validation report.

        Args:
            validation_report: Report from validate_all_citations()

        Returns:
            List of incoherent citation details
        """
        return [
            detail for detail in validation_report.get("details", [])
            if not detail.get("is_coherent", True)
        ]
