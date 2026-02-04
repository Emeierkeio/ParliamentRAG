"""
Ideology scorer for multi-view coverage.

PURPOSE: Ensure balanced representation of political perspectives in retrieval
and generation.

Methods:
1. Anchor-based: Use parliamentary group membership as SOFT anchors (legacy)
2. Text-based 2D: Use PCA on text embeddings via IC-1 to IC-6 pipeline (new)
"""
import logging
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

from ..neo4j_client import Neo4jClient
from .anchors import AnchorManager
from .clustering import IdeologyClustering
from .pipeline import CompassPipeline
from ...models.compass import Fragment, CompassRefusalError
from ...config import get_config
from ...models.evidence import IdeologyScore

logger = logging.getLogger(__name__)


class IdeologyScorer:
    """
    Computes ideological positions for multi-view coverage.

    NOT used for:
    - Discovering ideology from scratch
    - Political analysis or classification
    - Definitive position labeling

    USED for:
    - Ensuring all perspectives are represented
    - Balancing retrieval across political spectrum
    - Labeling evidence for multi-view generation
    """

    def __init__(self, neo4j_client: Neo4jClient):
        self.client = neo4j_client
        self.config = get_config()
        self.anchor_manager = AnchorManager()

        # Get clustering config
        compass_config = self.config.load_config().get("compass", {})
        clustering_config = compass_config.get("clustering", {})

        self.clustering = IdeologyClustering(
            bandwidth=clustering_config.get("kde_bandwidth", "scott")
        )

        self.min_fragments_for_kde = clustering_config.get("min_fragments_for_kde", 3)

    def score_evidence(
        self,
        evidence: Dict[str, Any]
    ) -> IdeologyScore:
        """
        Compute ideology score for a piece of evidence.

        Args:
            evidence: Evidence dictionary with party field

        Returns:
            IdeologyScore with left/center/right scores and confidence
        """
        party = evidence.get("party", "MISTO")

        # Get position from anchors
        position, confidence = self.anchor_manager.get_position_for_group(party)

        # Convert to numeric
        numeric_position = self.anchor_manager.position_to_numeric(position)

        # Compute multi-view scores
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

    def score_evidence_batch(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> List[IdeologyScore]:
        """
        Compute ideology scores for multiple evidence pieces.
        """
        return [self.score_evidence(e) for e in evidence_list]

    def compute_coverage_metrics(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute multi-view coverage metrics for evidence set.

        Returns metrics showing how well the evidence covers
        different political perspectives.
        """
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

        # Count by party
        party_counts: Dict[str, int] = {}
        position_counts = {"left": 0, "center": 0, "right": 0}

        for evidence in evidence_list:
            party = evidence.get("party", "MISTO")
            party_counts[party] = party_counts.get(party, 0) + 1

            # Get position for party
            position, _ = self.anchor_manager.get_position_for_group(party)
            position_counts[position] += 1

        # Compute balance score
        # Perfect balance = 1.0, complete imbalance = 0.0
        total = sum(position_counts.values())
        if total > 0:
            ideal = total / 3
            deviations = [abs(count - ideal) for count in position_counts.values()]
            max_deviation = 2 * ideal * 3  # Maximum possible deviation
            actual_deviation = sum(deviations)
            balance_score = 1.0 - (actual_deviation / max_deviation)
        else:
            balance_score = 0.0

        # Find missing positions
        missing = [pos for pos, count in position_counts.items() if count == 0]

        return {
            "total_evidence": len(evidence_list),
            "party_coverage": party_counts,
            "position_coverage": position_counts,
            "balance_score": balance_score,
            "missing_positions": missing,
        }

    def rebalance_evidence(
        self,
        evidence_list: List[Dict[str, Any]],
        target_count: int
    ) -> List[Dict[str, Any]]:
        """
        Rebalance evidence to improve multi-view coverage.

        Prioritizes under-represented positions while maintaining
        relevance ordering.

        Args:
            evidence_list: List of evidence with scores
            target_count: Target number of evidence pieces

        Returns:
            Rebalanced list with better position coverage
        """
        if len(evidence_list) <= target_count:
            return evidence_list

        # Group by position
        by_position: Dict[str, List[Dict]] = {
            "left": [],
            "center": [],
            "right": [],
        }

        for evidence in evidence_list:
            party = evidence.get("party", "MISTO")
            position, _ = self.anchor_manager.get_position_for_group(party)
            by_position[position].append(evidence)

        # Sort each group by relevance
        for position in by_position:
            by_position[position].sort(
                key=lambda x: x.get("similarity", 0) + x.get("authority_score", 0),
                reverse=True
            )

        # Distribute target count across positions
        per_position = target_count // 3
        remainder = target_count % 3

        selected = []

        # Select from each position
        for i, position in enumerate(["left", "center", "right"]):
            count = per_position + (1 if i < remainder else 0)
            available = by_position[position]

            # Take up to count from this position
            selected.extend(available[:count])

        # If we have room, add more from any position (by score)
        remaining = target_count - len(selected)
        if remaining > 0:
            # Collect remaining evidence
            all_remaining = []
            for position in by_position:
                count_taken = per_position + (1 if ["left", "center", "right"].index(position) < remainder else 0)
                all_remaining.extend(by_position[position][count_taken:])

            # Sort by score and take remaining
            all_remaining.sort(
                key=lambda x: x.get("similarity", 0) + x.get("authority_score", 0),
                reverse=True
            )
            selected.extend(all_remaining[:remaining])

        return selected

    def get_anchor_centroids(
        self,
        query_embedding: List[float]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get centroid information for each anchor position.

        This can be used for visualization or debugging.
        """
        centroids = {}

        for position in ["left", "center", "right"]:
            groups = self.anchor_manager.get_anchor_groups(position)

            centroids[position] = {
                "groups": groups,
                "confidence": self.anchor_manager._load_anchors()[position]["confidence"],
            }

        return centroids

    def compute_2d_text_positions(
        self,
        evidence_list: List[Dict[str, Any]],
        query: str = ""
    ) -> Dict[str, Any]:
        """
        Compute 2D positions for evidence using the IC-1 to IC-6 pipeline.

        This method uses weighted PCA with advanced features:
        - IC-1: Weighted PCA (inverse group frequency)
        - IC-2: SCR confidence + Z-score normalization
        - IC-3: KDE clustering for group centroids
        - IC-4: Eigendecomposition for dispersion ellipses
        - IC-5: Evidence binding to axis poles
        - IC-6: TF-IDF axis labeling

        Args:
            evidence_list: List of evidence dictionaries with 'embedding' field
            query: Original query string for metadata

        Returns:
            Dictionary compatible with frontend CompassCard component
        """
        # Convert evidence to Fragment objects
        fragments = self._evidence_to_fragments(evidence_list)

        if len(fragments) < 3:
            logger.warning(f"Only {len(fragments)} fragments, need at least 3 for PCA")
            return self._fallback_compass_data(evidence_list)

        # Run the IC-1 to IC-6 pipeline
        try:
            compass_config = self.config.load_config().get("compass", {})
            pipeline = CompassPipeline(compass_config)
            result = pipeline.run(fragments, query=query)

            # Convert to frontend-compatible format
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
        """Convert evidence dictionaries to Fragment objects for pipeline."""
        import json

        fragments = []

        for e in evidence_list:
            emb = e.get("embedding")
            if emb is None:
                continue

            # Handle string embeddings (JSON)
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except (json.JSONDecodeError, TypeError):
                    continue

            if not emb or len(emb) == 0:
                continue

            fragments.append(Fragment(
                id=e.get("evidence_id", f"frag_{len(fragments)}"),
                group_id=e.get("party", "MISTO"),
                speaker_id=e.get("speaker_id", ""),
                embedding=emb,
                text=e.get("chunk_text", ""),
                date=str(e.get("date", "")),
            ))

        return fragments

    def _pipeline_result_to_dict(self, result) -> Dict[str, Any]:
        """Convert CompassAnalysisResponse to frontend-compatible dict."""
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
        """
        Fallback when not enough data for PCA or pipeline fails.
        Uses anchor-based positioning instead.
        """
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

            # Add jitter for visualization
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
