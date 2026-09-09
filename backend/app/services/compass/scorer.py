"""
Ideology scorer for multi-view coverage.

Ensures balanced representation of political perspectives in retrieval and
generation. Two methods:
1. Anchor-based: parliamentary group membership as soft anchors (legacy)
2. Text-based 2D: IC-1 to IC-6 pipeline on text embeddings
"""
import logging
from typing import List, Dict, Any, Optional

from ..neo4j_client import Neo4jClient
from .anchors import AnchorManager
from .clustering import IdeologyClustering
from .pipeline import CompassPipeline
from ...models.compass import Fragment, CompassRefusalError
from ...config import get_config
from ...models.evidence import IdeologyScore

logger = logging.getLogger(__name__)

# Groups renamed mid-legislature exist in the graph under both names, because
# speech attribution is historically accurate (the group at the time of the
# speech). The compass must merge them, or the same political subject shows up
# twice on the map (two "IV" dots). Matching is by substring: the names carry
# variable suffixes and spacing.
RENAMED_GROUP_PATTERNS = [
    ("ITALIA VIVA", "ITALIA VIVA-CASA RIFORMISTA (IV-CR)"),
]


def canonical_group(party: str) -> str:
    up = (party or "").upper()
    for needle, canonical in RENAMED_GROUP_PATTERNS:
        if needle in up:
            return canonical
    return party


class IdeologyScorer:
    """
    Compute ideological positions for multi-view coverage.

    Used to ensure all perspectives are represented and to label evidence for
    multi-view generation — not for ideology discovery or definitive
    political classification.
    """

    def __init__(self, neo4j_client: Neo4jClient):
        self.client = neo4j_client
        self.config = get_config()
        self.anchor_manager = AnchorManager()
        self.clustering = IdeologyClustering()

    def score_evidence(
        self,
        evidence: Dict[str, Any]
    ) -> IdeologyScore:
        """Compute the anchor-based left/center/right score for one evidence dict."""
        party = evidence.get("party", "MISTO")

        position, confidence = self.anchor_manager.get_position_for_group(party)
        numeric_position = self.anchor_manager.position_to_numeric(position)
        scores = self.clustering.compute_multi_view_scores(
            numeric_position, confidence
        )

        return IdeologyScore(
            left=scores["left"],
            center=scores["center"],
            right=scores["right"],
            confidence=confidence,
            method="anchor"
        )

    def compute_coverage_metrics(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Measure how well an evidence set covers the political spectrum."""
        if not evidence_list:
            return {
                "total_evidence": 0,
                "party_coverage": {},
                "position_coverage": {
                    "left": 0,
                    "center": 0,
                    "right": 0,
                },
                "balance_score": 0.0,
                "missing_positions": ["left", "center", "right"],
            }

        party_counts: Dict[str, int] = {}
        position_counts = {"left": 0, "center": 0, "right": 0}

        for evidence in evidence_list:
            party = evidence.get("party", "MISTO")
            party_counts[party] = party_counts.get(party, 0) + 1

            position, _ = self.anchor_manager.get_position_for_group(party)
            position_counts[position] += 1

        # Balance score: 1.0 = perfectly even split, 0.0 = complete imbalance.
        total = sum(position_counts.values())
        if total > 0:
            ideal = total / 3
            deviations = [abs(count - ideal) for count in position_counts.values()]
            max_deviation = 2 * ideal * 3
            actual_deviation = sum(deviations)
            balance_score = 1.0 - (actual_deviation / max_deviation)
        else:
            balance_score = 0.0

        missing = [pos for pos, count in position_counts.items() if count == 0]

        return {
            "total_evidence": len(evidence_list),
            "party_coverage": party_counts,
            "position_coverage": position_counts,
            "balance_score": balance_score,
            "missing_positions": missing,
        }

    def compute_2d_text_positions(
        self,
        evidence_list: List[Dict[str, Any]],
        query: str = ""
    ) -> Dict[str, Any]:
        """
        Compute 2D positions for evidence via the IC-1 to IC-6 pipeline.

        Args:
            evidence_list: Evidence dictionaries with an 'embedding' field
            query: Original query string for metadata

        Returns:
            Dictionary compatible with the frontend CompassCard component
        """
        fragments = self._evidence_to_fragments(evidence_list)

        # Exclude unclassified groups (config compass.unclassified, e.g. Misto):
        # the mixed group aggregates unrelated components, so a single centroid
        # would be meaningless in the compass.
        excluded_groups = {
            g.strip().lower()
            for g in self.config.load_config().get("compass", {}).get("unclassified", [])
        } | {"misto"}
        fragments = [f for f in fragments if f.group_id.strip().lower() not in excluded_groups]

        if len(fragments) < 3:
            logger.warning(f"Only {len(fragments)} fragments, need at least 3 for PCA")
            return self._fallback_compass_data(evidence_list)

        try:
            full_config = self.config.load_config()
            compass_config = full_config.get("compass", {})

            # Semantic anchored axes (default): readable poles generated for
            # the query. Any failure falls back to the PCA path, never breaks
            # the compass.
            semantic_axes = None
            if query and compass_config.get("axis_method", "semantic") == "semantic":
                try:
                    from .semantic_axes import SemanticAxisGenerator
                    semantic_axes = SemanticAxisGenerator(full_config).generate(query)
                except Exception as e:
                    logger.warning(f"Semantic axes failed, falling back to PCA: {e}")

            # LLM stance scoring (default): positions from what each speaker
            # argues, not from embedding similarity to the pole texts (which
            # tracks vocabulary, not stance — rebuttals land on the wrong
            # side). Any failure falls back to embedding projection.
            stance_scores = None
            if semantic_axes is not None and compass_config.get("stance", {}).get("enabled", True):
                try:
                    from .stance import StanceClassifier
                    stance_scores = StanceClassifier(full_config).classify(
                        fragments, semantic_axes)
                except Exception as e:
                    logger.warning(
                        f"Stance classification failed, falling back to "
                        f"embedding projection: {e}")

            pipeline = CompassPipeline(compass_config)
            result = pipeline.run(
                fragments, query=query, semantic_axes=semantic_axes,
                stance_scores=stance_scores)

            return self._pipeline_result_to_dict(result)

        except CompassRefusalError as e:
            logger.warning(f"Compass refused: {e.code} - {e.message}")
            return self._fallback_compass_data(evidence_list, warning=e.message)
        except Exception as e:
            logger.error(f"Compass pipeline failed: {e}")
            return self._fallback_compass_data(evidence_list, warning=str(e))

    def _evidence_to_fragments(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> List[Fragment]:
        """Convert evidence dictionaries to Fragment objects for the pipeline."""
        import json

        fragments = []

        for e in evidence_list:
            emb = e.get("embedding")
            if emb is None:
                continue

            # Embeddings may arrive as JSON strings from the DB.
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except (json.JSONDecodeError, TypeError):
                    continue

            if not emb or len(emb) == 0:
                continue

            fragments.append(Fragment(
                id=e.get("evidence_id", f"frag_{len(fragments)}"),
                group_id=canonical_group(e.get("party", "MISTO")),
                speaker_id=e.get("speaker_id", ""),
                embedding=emb,
                text=e.get("chunk_text", ""),
                date=str(e.get("date", "")),
            ))

        return fragments

    def _pipeline_result_to_dict(self, result) -> Dict[str, Any]:
        """Convert CompassAnalysisResponse to a frontend-compatible dict."""
        return {
            "groups": [
                {
                    "group_id": g.group_id,
                    "position_x": round(g.position_x, 3),
                    "position_y": round(g.position_y, 3),
                    "dispersion": {
                        "center_x": round(g.dispersion.center_x, 3),
                        "center_y": round(g.dispersion.center_y, 3),
                        "radius_x": round(g.dispersion.radius_x, 3),
                        "radius_y": round(g.dispersion.radius_y, 3),
                        "rotation": round(g.dispersion.rotation, 1),
                    },
                    "stats": g.stats,
                    "core_evidence_ids": g.core_evidence_ids[:5],
                }
                for g in result.groups
            ],
            "scatter_sample": result.scatter_sample,
            "axes": {
                name: {
                    "index": axis.index,
                    "positive_pole_fragments": axis.positive_pole_fragments[:10],
                    "negative_pole_fragments": axis.negative_pole_fragments[:10],
                    "label": axis.positive_side.label if axis.positive_side else f"Asse {axis.index + 1}",
                    "description": axis.positive_side.explanation if axis.positive_side else "",
                    "positive_side": {
                        "label": axis.positive_side.label if axis.positive_side else "+",
                        "explanation": axis.positive_side.explanation if axis.positive_side else "",
                        "keywords": axis.positive_side.keywords[:5] if axis.positive_side else [],
                        "fragments": axis.positive_side.fragments[:3] if axis.positive_side else [],
                    } if axis.positive_side else None,
                    "negative_side": {
                        "label": axis.negative_side.label if axis.negative_side else "-",
                        "explanation": axis.negative_side.explanation if axis.negative_side else "",
                        "keywords": axis.negative_side.keywords[:5] if axis.negative_side else [],
                        "fragments": axis.negative_side.fragments[:3] if axis.negative_side else [],
                    } if axis.negative_side else None,
                }
                for name, axis in result.axes.items()
            },
            "meta": {
                "method": "weighted_pca_pipeline",
                "axis_method": result.meta.axis_method,
                "explained_variance_ratio": result.meta.explained_variance_ratio,
                "total_variance_explained": result.meta.total_variance_explained,
                "n_evidence": result.meta.n_evidence,
                "dimensionality": result.meta.dimensionality,
                "is_stable": result.meta.is_stable,
                "warnings": result.meta.warnings,
                "query": result.meta.query,
            },
        }

    def _default_axis_info(self) -> Dict[str, Any]:
        """Return default axis info when PCA cannot determine axes."""
        return {
            "x": {
                "index": 0,
                "positive_pole_fragments": [],
                "negative_pole_fragments": [],
                "label": "Asse principale",
                "description": "Dati insufficienti",
                "positive_side": {"label": "+", "explanation": "", "keywords": [], "fragments": []},
                "negative_side": {"label": "-", "explanation": "", "keywords": [], "fragments": []},
            },
            "y": {
                "index": 1,
                "positive_pole_fragments": [],
                "negative_pole_fragments": [],
                "label": "Asse secondario",
                "description": "Dati insufficienti",
                "positive_side": {"label": "+", "explanation": "", "keywords": [], "fragments": []},
                "negative_side": {"label": "-", "explanation": "", "keywords": [], "fragments": []},
            },
        }

    def _fallback_compass_data(
        self,
        evidence_list: List[Dict[str, Any]],
        warning: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build anchor-based compass data when the pipeline fails or data is too thin."""
        import random

        groups = []
        scatter_sample = []
        party_counts: Dict[str, int] = {}

        for e in evidence_list:
            party = e.get("party", "MISTO")
            party_counts[party] = party_counts.get(party, 0) + 1

        for party, count in party_counts.items():
            position, confidence = self.anchor_manager.get_position_for_group(party)
            numeric_pos = self.anchor_manager.position_to_numeric(position)

            # Jitter so co-anchored groups don't overlap in the chart.
            x = numeric_pos + (random.random() - 0.5) * 0.6
            y = (random.random() - 0.5) * 1.0

            groups.append({
                "group_id": party,
                "position_x": round(x, 3),
                "position_y": round(y, 3),
                "dispersion": {
                    "center_x": round(x, 3),
                    "center_y": round(y, 3),
                    "radius_x": 0.4,
                    "radius_y": 0.3,
                    "rotation": 0.0,
                },
                "stats": {
                    "n_fragments": count,
                    "confidence": round(confidence, 2),
                },
                "core_evidence_ids": [],
            })

        for e in evidence_list[:50]:
            party = e.get("party", "MISTO")
            position, _ = self.anchor_manager.get_position_for_group(party)
            numeric_pos = self.anchor_manager.position_to_numeric(position)

            scatter_sample.append({
                "x": round(numeric_pos + (random.random() - 0.5) * 0.8, 3),
                "y": round((random.random() - 0.5) * 0.6, 3),
                "group_id": party,
                "text": e.get("chunk_text", "")[:100],
                "evidence_id": e.get("evidence_id", ""),
            })

        warning_msg = warning or "Dati insufficienti per analisi PCA, usato posizionamento anchor"

        return {
            "groups": groups,
            "scatter_sample": scatter_sample,
            "axes": self._default_axis_info(),
            "meta": {
                "method": "anchor_fallback",
                "explained_variance_ratio": [0.0, 0.0],
                "total_variance_explained": 0.0,
                "n_evidence": len(evidence_list),
                "dimensionality": 1,
                "is_stable": False,
                "warnings": [warning_msg],
            },
        }
