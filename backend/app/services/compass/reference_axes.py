"""
Reference Axes for Semantic Validation

Provides pre-defined semantic axes for validating and labeling
the PCA-discovered axes. These represent stable political dimensions
in Italian parliamentary discourse.
"""
import logging
from typing import Dict, List, Optional, Tuple, Callable
import numpy as np

logger = logging.getLogger(__name__)


# Pre-defined reference axes with Italian political dimensions
REFERENCE_AXES = {
    "pubblico_privato": {
        "name_it": "Pubblico vs Privato",
        "name_en": "Public vs Private",
        "positive": {
            "label": "Intervento pubblico",
            "terms": [
                "servizio pubblico", "stato", "nazionale", "universale",
                "gratuito", "welfare", "sanità pubblica", "scuola pubblica",
                "intervento statale", "spesa pubblica", "settore pubblico"
            ],
        },
        "negative": {
            "label": "Mercato e privato",
            "terms": [
                "privato", "mercato", "competizione", "assicurazione",
                "ticket", "privatizzazione", "liberalizzazione",
                "impresa privata", "concorrenza", "deregolamentazione"
            ],
        },
    },
    "centralismo_autonomia": {
        "name_it": "Centralismo vs Autonomia",
        "name_en": "Centralism vs Autonomy",
        "positive": {
            "label": "Centralismo",
            "terms": [
                "governo centrale", "nazionale", "unità", "coordinamento",
                "Roma", "stato centrale", "uniformità", "ministero",
                "centralizzazione", "legislazione nazionale"
            ],
        },
        "negative": {
            "label": "Autonomia territoriale",
            "terms": [
                "regioni", "autonomia", "federalismo", "territori",
                "locale", "decentramento", "sussidiarietà", "comuni",
                "autonomia differenziata", "competenze regionali"
            ],
        },
    },
    "rigore_espansione": {
        "name_it": "Rigore vs Espansione",
        "name_en": "Austerity vs Expansion",
        "positive": {
            "label": "Rigore fiscale",
            "terms": [
                "rigore", "austerità", "debito", "bilancio", "pareggio",
                "riduzione spesa", "deficit", "spending review",
                "contenimento costi", "vincoli di bilancio"
            ],
        },
        "negative": {
            "label": "Espansione fiscale",
            "terms": [
                "investimenti", "spesa pubblica", "crescita", "sviluppo",
                "fondi", "risorse", "sostegno economico", "incentivi",
                "espansione", "politica espansiva"
            ],
        },
    },
    "tradizione_progresso": {
        "name_it": "Tradizione vs Progresso",
        "name_en": "Tradition vs Progress",
        "positive": {
            "label": "Valori tradizionali",
            "terms": [
                "tradizione", "famiglia tradizionale", "valori",
                "identità", "radici", "conservazione", "patrimonio",
                "natalità", "maternità", "ruoli tradizionali"
            ],
        },
        "negative": {
            "label": "Diritti e progresso",
            "terms": [
                "diritti civili", "uguaglianza", "inclusione", "diversità",
                "parità di genere", "LGBTQ", "progressismo", "laicità",
                "autodeterminazione", "nuovi diritti"
            ],
        },
    },
    "sovranismo_europeismo": {
        "name_it": "Sovranismo vs Europeismo",
        "name_en": "Sovereignty vs Europeanism",
        "positive": {
            "label": "Sovranità nazionale",
            "terms": [
                "sovranità", "nazionale", "interesse italiano", "confini",
                "prima gli italiani", "indipendenza", "autodeterminazione",
                "identità nazionale", "patriottismo"
            ],
        },
        "negative": {
            "label": "Integrazione europea",
            "terms": [
                "Europa", "Unione Europea", "integrazione", "multilateralismo",
                "cooperazione internazionale", "trattati europei", "PNRR",
                "solidarietà europea", "fondi europei"
            ],
        },
    },
}


class ReferenceAxesRegistry:
    """
    Registry for reference semantic axes.

    Provides methods to validate PCA-discovered axes against
    pre-defined political dimensions and suggest labels.
    """

    def __init__(
        self,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        similarity_threshold: float = 0.25
    ):
        """
        Initialize the registry.

        Args:
            embedding_fn: Function to compute embeddings. If None, uses
                          simple term matching instead of semantic similarity.
            similarity_threshold: Minimum cosine similarity for axis matching.
        """
        self.embedding_fn = embedding_fn
        self.similarity_threshold = similarity_threshold
        self._embeddings_cache: Dict[str, np.ndarray] = {}

    def _compute_pole_embedding(self, terms: List[str]) -> Optional[np.ndarray]:
        """Compute mean embedding for a pole's terms."""
        if self.embedding_fn is None:
            return None

        embeddings = []
        for term in terms:
            if term in self._embeddings_cache:
                embeddings.append(self._embeddings_cache[term])
            else:
                try:
                    emb = np.array(self.embedding_fn(term))
                    self._embeddings_cache[term] = emb
                    embeddings.append(emb)
                except Exception as e:
                    logger.warning(f"Failed to embed term '{term}': {e}")

        if not embeddings:
            return None

        return np.mean(embeddings, axis=0)

    def validate_axis(
        self,
        axis_vector: np.ndarray,
        positive_texts: List[str],
        negative_texts: List[str]
    ) -> Optional[Tuple[str, str, float]]:
        """
        Validate an axis against reference axes.

        Args:
            axis_vector: The PCA axis vector [D]
            positive_texts: Texts from the positive pole
            negative_texts: Texts from the negative pole

        Returns:
            Tuple of (axis_key, pole_alignment, similarity) if match found,
            None otherwise. pole_alignment is 'aligned' or 'inverted'.
        """
        if self.embedding_fn is None:
            # Fall back to term matching
            return self._validate_by_terms(positive_texts, negative_texts)

        best_match = None
        best_similarity = 0.0

        for axis_key, axis_def in REFERENCE_AXES.items():
            pos_emb = self._compute_pole_embedding(axis_def["positive"]["terms"])
            neg_emb = self._compute_pole_embedding(axis_def["negative"]["terms"])

            if pos_emb is None or neg_emb is None:
                continue

            # Reference axis direction
            ref_direction = pos_emb - neg_emb
            ref_direction = ref_direction / (np.linalg.norm(ref_direction) + 1e-8)

            # Compare with PCA axis
            axis_norm = axis_vector / (np.linalg.norm(axis_vector) + 1e-8)
            similarity = float(np.dot(ref_direction, axis_norm))

            abs_similarity = abs(similarity)
            if abs_similarity > best_similarity and abs_similarity >= self.similarity_threshold:
                best_similarity = abs_similarity
                alignment = "aligned" if similarity > 0 else "inverted"
                best_match = (axis_key, alignment, abs_similarity)

        return best_match

    def _validate_by_terms(
        self,
        positive_texts: List[str],
        negative_texts: List[str]
    ) -> Optional[Tuple[str, str, float]]:
        """
        Validate axis by counting term occurrences in pole texts.

        This is a fallback when embedding function is not available.
        """
        pos_text = " ".join(positive_texts).lower()
        neg_text = " ".join(negative_texts).lower()

        best_match = None
        best_score = 0.0

        for axis_key, axis_def in REFERENCE_AXES.items():
            # Count positive terms
            pos_terms = axis_def["positive"]["terms"]
            neg_terms = axis_def["negative"]["terms"]

            # Check alignment
            pos_in_pos = sum(1 for t in pos_terms if t.lower() in pos_text)
            neg_in_neg = sum(1 for t in neg_terms if t.lower() in neg_text)
            aligned_score = (pos_in_pos + neg_in_neg) / (len(pos_terms) + len(neg_terms))

            # Check inverse alignment
            pos_in_neg = sum(1 for t in pos_terms if t.lower() in neg_text)
            neg_in_pos = sum(1 for t in neg_terms if t.lower() in pos_text)
            inverted_score = (pos_in_neg + neg_in_pos) / (len(pos_terms) + len(neg_terms))

            if aligned_score > best_score and aligned_score >= self.similarity_threshold:
                best_score = aligned_score
                best_match = (axis_key, "aligned", aligned_score)
            elif inverted_score > best_score and inverted_score >= self.similarity_threshold:
                best_score = inverted_score
                best_match = (axis_key, "inverted", inverted_score)

        return best_match

    def get_axis_labels(
        self,
        axis_key: str,
        alignment: str
    ) -> Tuple[str, str]:
        """
        Get positive and negative labels for an axis.

        Args:
            axis_key: Key from REFERENCE_AXES
            alignment: 'aligned' or 'inverted'

        Returns:
            Tuple of (positive_label, negative_label)
        """
        if axis_key not in REFERENCE_AXES:
            return ("Polo (+)", "Polo (-)")

        axis_def = REFERENCE_AXES[axis_key]

        if alignment == "aligned":
            return (
                axis_def["positive"]["label"],
                axis_def["negative"]["label"]
            )
        else:
            return (
                axis_def["negative"]["label"],
                axis_def["positive"]["label"]
            )

    def get_axis_terms(
        self,
        axis_key: str,
        alignment: str
    ) -> Tuple[List[str], List[str]]:
        """
        Get terms for positive and negative poles.

        Returns:
            Tuple of (positive_terms, negative_terms)
        """
        if axis_key not in REFERENCE_AXES:
            return ([], [])

        axis_def = REFERENCE_AXES[axis_key]

        if alignment == "aligned":
            return (
                axis_def["positive"]["terms"],
                axis_def["negative"]["terms"]
            )
        else:
            return (
                axis_def["negative"]["terms"],
                axis_def["positive"]["terms"]
            )

    @staticmethod
    def get_all_axis_names() -> List[str]:
        """Get all available reference axis names."""
        return list(REFERENCE_AXES.keys())

    @staticmethod
    def get_axis_description(axis_key: str) -> Optional[Dict]:
        """Get full description of a reference axis."""
        return REFERENCE_AXES.get(axis_key)
