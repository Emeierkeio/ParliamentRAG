"""
TF-IDF axis labeling.

Generates interpretable labels for compass axes from the terms that
distinguish one pole from the other.
"""
import logging
import math
from collections import Counter
from typing import List, Tuple

logger = logging.getLogger(__name__)


# Procedural stoplist for Italian parliamentary language.
PROCEDURAL_STOPLIST = {
    # Parliamentary procedure
    "signor", "signora", "presidente", "ministro", "sottosegretario",
    "governo", "legge", "articolo", "comma", "emendamento",
    "camera", "senato", "seduta", "resoconto", "voto", "votazione",
    "discussione", "approvazione", "decreto", "disegno", "proposta",
    "relatore", "commissione", "aula", "maggioranza", "opposizione",
    "gruppo", "parlamentare", "deputato", "onorevole", "collega",

    # Common verbs and connectors
    "essere", "avere", "fare", "dire", "potere", "dovere", "volere",
    "anno", "oggi", "ieri", "domani", "sempre", "mai", "molto",
    "poco", "tanto", "tutto", "nulla", "cosa", "modo", "parte",
    "tempo", "punto", "caso", "fatto", "volta", "momento",

    # Numbers and common words
    "primo", "secondo", "terzo", "uno", "due", "tre", "quattro",
    "cinque", "dieci", "cento", "mille", "milione", "miliardo",
    "euro", "percentuale", "numero", "dato", "cifra",

    # Generic political terms (too common to be distinctive)
    "italia", "italiano", "italiana", "italiani", "paese", "nazione",
    "politica", "politico", "politici", "pubblico", "pubblici",
    "cittadino", "cittadini", "popolo", "gente", "persona", "persone",
}


class AxisLabeler:
    """
    Generates interpretable labels for PCA axes using TF-IDF.

    Analyzes text from pole fragments to identify distinctive terms
    that characterize each pole of an axis.
    """

    def __init__(
        self,
        nlp_model: str = "it_core_news_sm",
        top_terms: int = 3,
        min_term_length: int = 3
    ):
        """
        Initialize the labeler.

        Args:
            nlp_model: Spacy model name for Italian NLP
            top_terms: Number of top terms to use for label
            min_term_length: Minimum character length for terms
        """
        self.nlp_model = nlp_model
        self.top_terms = top_terms
        self.min_term_length = min_term_length
        self._nlp = None

    @property
    def nlp(self):
        """Lazy-load spacy model."""
        if self._nlp is None:
            try:
                import spacy
                self._nlp = spacy.load(self.nlp_model)
                logger.info(f"Loaded spacy model: {self.nlp_model}")
            except Exception as e:
                logger.warning(f"Failed to load spacy model: {e}")
                self._nlp = None
        return self._nlp

    def label_pole(
        self,
        focus_texts: List[str],
        contrast_texts: List[str]
    ) -> Tuple[str, List[str]]:
        """
        Generate label and keywords for one pole of an axis.

        Uses TF-IDF ranking where:
        - TF (term frequency) is computed on focus texts
        - IDF-like contrast is computed against the opposite pole

        Args:
            focus_texts: Texts from the pole to label
            contrast_texts: Texts from the opposite pole

        Returns:
            Tuple of (label_string, list_of_keywords)
        """
        focus_lemmas = self._extract_lemmas(focus_texts)
        contrast_lemmas = self._extract_lemmas(contrast_texts)

        if not focus_lemmas:
            return "Polo semantico", []

        focus_counts = Counter(focus_lemmas)
        contrast_counts = Counter(contrast_lemmas)

        total_focus = sum(focus_counts.values())
        total_contrast = sum(contrast_counts.values()) + 1  # add-one smoothing

        # Discriminative score: TF on the focus pole times the log ratio of
        # smoothed frequencies, penalizing terms common in the opposite pole.
        scores = {}
        for term, count in focus_counts.items():
            tf = count / total_focus
            contrast_freq = (contrast_counts.get(term, 0) + 1) / total_contrast
            focus_freq = (count + 1) / (total_focus + 1)
            scores[term] = tf * math.log(focus_freq / contrast_freq)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        top_keywords = [term for term, _ in ranked[:self.top_terms * 3]]
        label_terms = [term for term, _ in ranked[:self.top_terms]]
        label = " / ".join(label_terms) if label_terms else "Polo semantico"

        return label, top_keywords

    def _extract_lemmas(self, texts: List[str]) -> List[str]:
        """
        Extract filtered lemmas from texts.

        Filters for:
        - NOUN, ADJ, PROPN parts of speech
        - Minimum length
        - Not in procedural stoplist
        """
        if not texts:
            return []

        full_text = " ".join(texts)

        if self.nlp is not None:
            return self._extract_with_spacy(full_text)
        else:
            return self._extract_simple(full_text)

    def _extract_with_spacy(self, text: str) -> List[str]:
        """Extract lemmas using spacy NLP."""
        lemmas = []

        # Process in chunks to stay under spacy's max document length.
        max_length = 100000
        for i in range(0, len(text), max_length):
            chunk = text[i:i + max_length]

            try:
                doc = self.nlp(chunk)

                for token in doc:
                    if token.pos_ not in {"NOUN", "ADJ", "PROPN"}:
                        continue

                    lemma = token.lemma_.lower()

                    if len(lemma) < self.min_term_length:
                        continue
                    if lemma in PROCEDURAL_STOPLIST:
                        continue
                    if token.is_stop:
                        continue
                    if token.is_punct:
                        continue
                    if lemma.isdigit():
                        continue

                    lemmas.append(lemma)

            except Exception as e:
                logger.warning(f"Spacy processing error: {e}")
                continue

        return lemmas

    def _extract_simple(self, text: str) -> List[str]:
        """Tokenize without lemmatization, as fallback when spacy is unavailable."""
        import re

        words = re.findall(r'\b[a-zA-ZàèéìòùÀÈÉÌÒÙ]+\b', text.lower())

        lemmas = []
        for word in words:
            if len(word) < self.min_term_length:
                continue
            if word in PROCEDURAL_STOPLIST:
                continue
            if word.isdigit():
                continue
            lemmas.append(word)

        return lemmas
