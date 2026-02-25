"""
Semantic Coherence Validator.

Verifies that introductory text matches citation content semantically.

Two-tier validation approach:
1. Primary: Embedding cosine similarity (OpenAI text-embedding-3-small)
2. Fallback: Keyword-based Jaccard overlap (no API calls)

Grounded in:
- SummaC (Laban et al., TACL 2022): NLI-based models outperform lexical
  overlap for inconsistency detection in summarization
- BERTScore (Zhang et al., ICLR 2020): contextual embedding matching
  captures paraphrasing that Jaccard ignores

This is a critical component for ensuring citation integrity:
- The text that introduces a citation must reflect its actual content
- A positive intro ("elogia", "sostiene") cannot introduce a negative quote
- Semantic similarity ensures topical alignment beyond keyword overlap
"""
import re
import logging
from typing import Dict, Any, List, Optional

import numpy as np
import openai

from ...config import get_settings
from ...key_pool import make_client
from .reported_speech import detect_reported_speech

logger = logging.getLogger(__name__)


class CoherenceValidator:
    """
    Validates semantic coherence between intro text and citations.

    Primary method: embedding cosine similarity (threshold 0.6)
    Fallback method: Jaccard keyword overlap (threshold 0.2)

    Example:
        validator = CoherenceValidator(min_coherence_score=0.6)

        result = validator.validate_coherence(
            intro_text="Il deputato critica la gestione sanitaria",
            quote_text="il sistema sanitario è in crisi per mancanza di fondi"
        )

        if not result["is_coherent"]:
            print(f"Warning: {result['warning']}")
    """

    # Italian stop words to filter out (for Jaccard fallback)
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

    def __init__(
        self,
        min_coherence_score: float = 0.6,
        method: str = "embedding"
    ):
        """
        Initialize validator.

        Args:
            min_coherence_score: Minimum score for coherence (0.0-1.0).
                For embedding method: 0.6 recommended.
                For jaccard method: 0.2 recommended.
            method: "embedding" (primary) or "jaccard" (fallback/legacy)
        """
        self.min_coherence_score = min_coherence_score
        self.method = method
        self._embedding_available = None  # Lazy check
        self._client = None

    def _get_client(self) -> openai.OpenAI:
        """Lazy-init OpenAI client."""
        if self._client is None:
            self._client = make_client()
        return self._client

    def _embedding_similarity(self, text_a: str, text_b: str) -> Optional[float]:
        """Compute cosine similarity between embeddings of two texts.

        Returns None if embedding API is unavailable.
        """
        try:
            client = self._get_client()
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=[text_a, text_b]
            )
            vec_a = np.array(response.data[0].embedding, dtype=np.float32)
            vec_b = np.array(response.data[1].embedding, dtype=np.float32)

            # Normalize and compute cosine similarity
            norm_a = np.linalg.norm(vec_a)
            norm_b = np.linalg.norm(vec_b)
            if norm_a == 0 or norm_b == 0:
                return 0.0

            return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
        except Exception as exc:
            logger.warning(f"Embedding coherence check failed: {exc}")
            self._embedding_available = False
            return None

    def _jaccard_similarity(self, text_a: str, text_b: str) -> float:
        """Compute Jaccard keyword overlap (fallback method)."""
        tokens_a = set(self._tokenize(text_a))
        tokens_b = set(self._tokenize(text_b))

        if not tokens_a or not tokens_b:
            return 0.0

        overlap = tokens_a & tokens_b
        union_size = len(tokens_a | tokens_b)
        return len(overlap) / union_size if union_size > 0 else 0.0

    # Patterns that signal the INTRO is framing a party as PRO
    _INTRO_PRO_SIGNALS = re.compile(
        r'\b(?:si\s+esprime?\s+a\s+favore|sostien[ei]\s+la\s+necessità|è\s+favorevole|'
        r'appoggia|sostien[ei]|propone|auspica|chiede|ritiene\s+necessario|difende\s+la\s+proposta|'
        r'supporta|promuove|plaude|approva)\b',
        re.IGNORECASE,
    )

    # Patterns that signal the INTRO is framing a party as AGAINST
    _INTRO_AGAINST_SIGNALS = re.compile(
        r'\b(?:si\s+oppone|è\s+contrario|contesta|critica|respinge|rifiuta|denuncia|'
        r'condanna|stigmatizza|boccia|rigetta|controbatte|contrasta)\b',
        re.IGNORECASE,
    )

    def _stance_alignment_check(
        self,
        intro_text: str,
        quote_text: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Check whether the INTRO's attributed stance matches the evidence.

        When the evidence chunk contains reported speech (speaker quoting an
        opponent), the semantic embedding similarity will still be high
        (both texts are topically related) but the stance may be inverted.

        This check applies a penalty when:
        1. The intro attributes a PRO stance to the party, AND
        2. The evidence chunk shows strong reported-speech signals (the
           quoted content belongs to an opponent, not the speaker).

        Returns a dict with:
        - has_stance_issue: bool
        - penalty: float to subtract from the coherence score
        - reason: str
        """
        result = {
            "has_stance_issue": False,
            "penalty": 0.0,
            "reason": "",
        }

        if not intro_text or not quote_text:
            return result

        # Use pre-annotated info if available (from evidence dict), else run detection
        if evidence is not None:
            rs_info = evidence.get("reported_speech") or detect_reported_speech(quote_text)
        else:
            rs_info = detect_reported_speech(quote_text)

        if not rs_info.get("has_reported_speech"):
            return result

        # Evidence contains reported speech — check if intro claims a PRO stance
        intro_is_pro = bool(self._INTRO_PRO_SIGNALS.search(intro_text))
        intro_is_against = bool(self._INTRO_AGAINST_SIGNALS.search(intro_text))

        if intro_is_pro and not intro_is_against:
            # Intro says PRO, but quote is reported speech → possible inversion
            penalty = 0.30 if rs_info.get("opening_is_reported") else 0.15
            result["has_stance_issue"] = True
            result["penalty"] = penalty
            result["reason"] = (
                f"Intro attributes PRO stance but evidence contains reported speech "
                f"(confidence={rs_info['confidence']:.2f}, "
                f"opening={rs_info['opening_is_reported']}). "
                f"Score penalty: -{penalty:.2f}"
            )
            logger.warning(
                f"[STANCE_CHECK] Possible stance inversion: intro=PRO but evidence "
                f"has reported speech (confidence={rs_info['confidence']:.2f}). "
                f"Penalty: -{penalty:.2f}. Intro: '{intro_text[:80]}'"
            )

        return result

    def validate_coherence(
        self,
        intro_text: str,
        quote_text: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate semantic coherence between intro and quote.

        Uses embedding cosine similarity as primary method,
        falls back to Jaccard if embeddings unavailable.

        Args:
            intro_text: The introductory text before the citation
            quote_text: The actual citation text

        Returns:
            Dictionary with:
            - is_coherent: Boolean indicating if texts are coherent
            - score: Similarity score (0.0-1.0)
            - method: "embedding" or "jaccard"
            - sentiment_mismatch: Boolean if sentiments contradict
            - warning: Optional warning message
        """
        if not intro_text or not quote_text:
            return {
                "is_coherent": True,
                "score": 0.0,
                "method": "none",
                "warning": "Empty text - cannot validate",
                "overlap_keywords": [],
                "sentiment_mismatch": False,
                "stance_issue": False,
            }

        # Check sentiment mismatch (always, regardless of method)
        intro_sentiment = self._detect_sentiment(intro_text)
        quote_sentiment = self._detect_sentiment(quote_text)
        sentiment_mismatch = (
            intro_sentiment is not None and
            quote_sentiment is not None and
            intro_sentiment != quote_sentiment
        )

        # Compute similarity score
        score = 0.0
        method_used = self.method
        overlap_keywords = []

        if self.method == "embedding" and self._embedding_available is not False:
            embedding_score = self._embedding_similarity(intro_text, quote_text)
            if embedding_score is not None:
                score = embedding_score
                method_used = "embedding"
            else:
                # Fallback to Jaccard
                score = self._jaccard_similarity(intro_text, quote_text)
                method_used = "jaccard"
                # Adjust threshold for Jaccard
                overlap_keywords = list(
                    set(self._tokenize(intro_text)) &
                    set(self._tokenize(quote_text))
                )[:10]
        else:
            score = self._jaccard_similarity(intro_text, quote_text)
            method_used = "jaccard"
            overlap_keywords = list(
                set(self._tokenize(intro_text)) &
                set(self._tokenize(quote_text))
            )[:10]

        # Fix 4 — Stance alignment check (reported speech penalty)
        # Applied AFTER base similarity so that a topically-similar but
        # directionally-inverted citation is penalised even when embedding
        # similarity is above threshold.
        stance_result = self._stance_alignment_check(intro_text, quote_text, evidence)
        if stance_result["has_stance_issue"]:
            score = max(0.0, score - stance_result["penalty"])

        # Determine threshold based on method
        if method_used == "embedding":
            threshold = self.min_coherence_score  # 0.6 for embedding
        else:
            threshold = 0.2  # Original Jaccard threshold

        # Final coherence decision
        is_coherent = score >= threshold and not sentiment_mismatch

        result = {
            "is_coherent": is_coherent,
            "score": round(score, 3),
            "method": method_used,
            "threshold": threshold,
            "overlap_keywords": overlap_keywords,
            "intro_sentiment": intro_sentiment,
            "quote_sentiment": quote_sentiment,
            "sentiment_mismatch": sentiment_mismatch,
            "stance_issue": stance_result["has_stance_issue"],
            "stance_penalty": stance_result["penalty"],
        }

        if stance_result["has_stance_issue"]:
            result["warning"] = stance_result["reason"]
        elif sentiment_mismatch:
            result["warning"] = (
                f"Sentiment mismatch: intro={intro_sentiment}, "
                f"quote={quote_sentiment}"
            )
            logger.warning(
                f"Coherence: Sentiment mismatch detected - "
                f"intro={intro_sentiment}, quote={quote_sentiment}"
            )
        elif not is_coherent:
            result["warning"] = (
                f"Low {method_used} score: {score:.2f} < {threshold}"
            )
            logger.warning(
                f"Coherence: Low {method_used} score {score:.2f} "
                f"(threshold {threshold})"
            )

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

            # Pass evidence dict so _stance_alignment_check can use pre-annotated
            # reported_speech info (set by annotate_evidence_with_reported_speech
            # in write_sections) instead of re-running detection from scratch.
            validation = self.validate_coherence(intro, quote_text, evidence=evidence)
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
