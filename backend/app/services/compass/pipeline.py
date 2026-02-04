"""
Compass Pipeline - IC-1 to IC-6 Implementation

Implements the complete ideological compass analysis pipeline:
- IC-1: Axis Discovery (Weighted PCA)
- IC-2: Projection (SCR confidence + Z-score normalization)
- IC-3: Group Clustering (KDE or mean)
- IC-4: Dispersion (Eigendecomposition ellipses)
- IC-5: Evidence Binding (extreme fragments per pole)
- IC-6: Interpretability (TF-IDF axis labeling)
"""
import logging
import random
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
from scipy import stats

from ...models.compass import (
    Fragment,
    ProjectedFragment,
    AxisDefinition,
    AxisSideDescription,
    DispersionEllipse,
    GroupPosition,
    CompassMetadata,
    CompassAnalysisResponse,
    CompassRefusalError,
)
from ...config import get_config

logger = logging.getLogger(__name__)


class CompassPipeline:
    """
    Complete IC-1 to IC-6 pipeline for ideological compass analysis.

    Uses weighted PCA to discover semantic axes from parliamentary
    speech embeddings, with validation and interpretability features.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize pipeline with configuration.

        Args:
            config: Optional config dict. If None, loads from default.yaml
        """
        if config is None:
            app_config = get_config()
            config = app_config.load_config().get("compass", {})
        self.config = config

        # Configuration parameters with defaults
        self.max_weight_per_fragment = config.get("max_weight_per_fragment", 0.05)
        self.pc2_pc1_ratio_threshold = config.get("pc2_pc1_ratio_threshold", 0.40)
        self.min_variance_explained = config.get("min_variance_explained", 0.05)
        self.z_score_clip_threshold = config.get("z_score_clip_threshold", 4.0)
        self.scr_confidence_threshold = config.get("scr_confidence_threshold", 0.15)
        self.min_fragments_for_kde = config.get("min_fragments_for_kde", 3)
        self.scatter_sample_size = config.get("scatter_sample_size", 200)
        self.scatter_random_seed = config.get("scatter_random_seed", 42)
        self.pole_purity_threshold = config.get("pole_purity_threshold", 0.30)
        self.tfidf_top_terms = config.get("tfidf_top_terms", 3)

        # Lazy-loaded labeler
        self._axis_labeler = None

    def run(
        self,
        fragments: List[Fragment],
        query: str = ""
    ) -> CompassAnalysisResponse:
        """
        Run the complete IC-1 to IC-6 pipeline.

        Args:
            fragments: List of Fragment objects with embeddings
            query: Original query string for metadata

        Returns:
            CompassAnalysisResponse with all analysis results

        Raises:
            CompassRefusalError: If analysis cannot produce reliable results
        """
        warnings = []

        # Check minimum fragments
        if len(fragments) < 3:
            return self._fallback_response(fragments, query, "Insufficient data (< 3 fragments)")

        # IC-1: Axis Discovery (Weighted PCA)
        try:
            axes, mu, evr = self._ic1_axis_discovery(fragments)
        except Exception as e:
            logger.error(f"IC-1 failed: {e}")
            return self._fallback_response(fragments, query, f"PCA failed: {e}")

        # Dimensionality decision
        dimensionality = self._decide_dimensionality(evr)
        if dimensionality == 1:
            warnings.append("ONE_DIMENSIONAL_MODE: PC2/PC1 ratio < 0.40")

        # Validation
        total_var = sum(evr[:2]) if len(evr) >= 2 else evr[0]
        if total_var < self.min_variance_explained:
            warnings.append(f"WEAK_SIGNAL: Variance explained {total_var:.2%} < {self.min_variance_explained:.0%}")

        # IC-2: Projection
        projected = self._ic2_projection(fragments, axes, mu, dimensionality)

        # IC-3: Group Clustering
        groups = self._ic3_group_clustering(projected, dimensionality)

        # IC-4: Dispersion Ellipses
        groups = self._ic4_dispersion(groups, projected)

        # IC-5: Evidence Binding
        axis_defs = self._ic5_evidence_binding(axes, evr, projected, dimensionality)

        # IC-6: Axis Labeling (optional, requires spacy)
        axis_defs = self._ic6_interpretability(axis_defs, fragments, projected)

        # Build scatter sample
        scatter_sample = self._build_scatter_sample(projected, dimensionality)

        # Stability check
        is_stable = (
            len(fragments) >= 10 and
            total_var >= self.min_variance_explained and
            len(groups) >= 2
        )

        return CompassAnalysisResponse(
            meta=CompassMetadata(
                query=query,
                dimensionality=dimensionality,
                explained_variance_ratio=evr[:2].tolist() if len(evr) >= 2 else [evr[0], 0.0],
                total_variance_explained=float(total_var),
                n_evidence=len(fragments),
                is_stable=is_stable,
                warnings=warnings,
            ),
            axes={
                "x": axis_defs[0],
                "y": axis_defs[1] if dimensionality == 2 else AxisDefinition(
                    index=1,
                    explained_variance=0.0,
                    positive_pole_fragments=[],
                    negative_pole_fragments=[],
                ),
            },
            groups=groups,
            scatter_sample=scatter_sample,
        )

    def _ic1_axis_discovery(
        self,
        fragments: List[Fragment]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        IC-1: Axis Discovery using Weighted PCA.

        Uses inverse group frequency weighting to prevent large groups
        from dominating the analysis.

        Args:
            fragments: List of fragments with embeddings

        Returns:
            Tuple of (axes [2, D], mean [D], explained_variance_ratio [K])
        """
        embeddings = np.array([f.embedding for f in fragments])
        group_ids = [f.group_id for f in fragments]

        # Compute inverse frequency weights per group
        group_counts = Counter(group_ids)
        n_groups = len(group_counts)

        weights = []
        for gid in group_ids:
            w = 1.0 / (group_counts[gid] * n_groups)
            weights.append(min(w, self.max_weight_per_fragment))

        weights = np.array(weights)
        weights /= weights.sum()  # Normalize to sum to 1

        # Weighted mean
        mu = np.average(embeddings, axis=0, weights=weights)
        X_centered = embeddings - mu

        # Weighted SVD
        X_weighted = np.sqrt(weights)[:, np.newaxis] * X_centered
        U, S, Vt = np.linalg.svd(X_weighted, full_matrices=False)

        # Principal components (rows of Vt)
        axes = Vt[:2]  # [2, D]

        # Explained variance ratio
        total_var = np.sum(S ** 2)
        evr = (S ** 2) / total_var if total_var > 0 else np.zeros_like(S)

        # Deterministic orientation based on skewness
        for i in range(min(2, len(axes))):
            proj = X_centered @ axes[i]
            skewness = np.mean(proj ** 3)
            if skewness < 0:
                axes[i] *= -1

        logger.info(
            f"IC-1: Weighted PCA computed. "
            f"EVR=[{evr[0]:.3f}, {evr[1]:.3f}], "
            f"n_fragments={len(fragments)}, n_groups={n_groups}"
        )

        return axes, mu, evr

    def _decide_dimensionality(self, evr: np.ndarray) -> int:
        """
        Decide whether to use 1D or 2D visualization.

        Uses PC2/PC1 ratio threshold.
        """
        if len(evr) < 2 or evr[0] == 0:
            return 1

        ratio = evr[1] / evr[0]
        if ratio < self.pc2_pc1_ratio_threshold:
            logger.info(f"IC-1: 1D mode (PC2/PC1 ratio {ratio:.3f} < {self.pc2_pc1_ratio_threshold})")
            return 1
        return 2

    def _ic2_projection(
        self,
        fragments: List[Fragment],
        axes: np.ndarray,
        mu: np.ndarray,
        dimensionality: int
    ) -> List[ProjectedFragment]:
        """
        IC-2: Project fragments to PCA space with SCR confidence.

        Computes Subspace Contribution Ratio (SCR) as confidence measure
        and applies Z-score normalization with soft clipping.
        """
        projected = []

        for f in fragments:
            x_c = np.array(f.embedding) - mu
            raw_coords = x_c @ axes.T  # [2]

            # SCR (Subspace Contribution Ratio)
            x_c_norm = np.linalg.norm(x_c)
            proj_norm = np.linalg.norm(raw_coords)
            scr = (proj_norm ** 2) / (x_c_norm ** 2) if x_c_norm > 0 else 0

            projected.append(ProjectedFragment(
                fragment_id=f.id,
                group_id=f.group_id,
                raw_coordinates=tuple(raw_coords),
                confidence=scr,
                text=f.text,
            ))

        # Z-score normalization
        all_raw = np.array([p.raw_coordinates for p in projected])
        mean_coords = all_raw.mean(axis=0)
        std_coords = all_raw.std(axis=0)
        std_coords = np.where(std_coords < 1e-8, 1.0, std_coords)  # Avoid division by zero

        for p in projected:
            scaled = (np.array(p.raw_coordinates) - mean_coords) / std_coords

            # Soft clipping with tanh beyond threshold
            threshold = self.z_score_clip_threshold
            scaled = np.where(
                np.abs(scaled) > threshold,
                threshold * np.tanh(scaled / threshold),
                scaled
            )

            # In 1D mode, set Y to 0
            if dimensionality == 1:
                scaled[1] = 0.0

            p.coordinates = tuple(scaled)

            # Mark outliers
            p.is_outlier = p.confidence < self.scr_confidence_threshold

        logger.info(f"IC-2: Projected {len(projected)} fragments, "
                   f"{sum(1 for p in projected if p.is_outlier)} outliers")

        return projected

    def _ic3_group_clustering(
        self,
        projected: List[ProjectedFragment],
        dimensionality: int
    ) -> List[GroupPosition]:
        """
        IC-3: Cluster fragments by group and find centroids.

        Uses KDE for groups with >= 3 points, mean for smaller groups.
        """
        # Group by party
        groups_map: Dict[str, List[ProjectedFragment]] = {}
        for p in projected:
            if p.group_id not in groups_map:
                groups_map[p.group_id] = []
            groups_map[p.group_id].append(p)

        positions = []

        for group_id, group_frags in groups_map.items():
            # Filter out outliers for centroid computation
            valid_frags = [p for p in group_frags if not p.is_outlier]
            if not valid_frags:
                valid_frags = group_frags  # Fallback to all if all are outliers

            coords = np.array([p.coordinates for p in valid_frags])
            n_frags = len(valid_frags)

            if n_frags >= self.min_fragments_for_kde and dimensionality == 2:
                # KDE for 2D with enough points
                try:
                    centroid = self._kde_peak_2d(coords)
                except Exception:
                    centroid = coords.mean(axis=0)
            elif n_frags >= self.min_fragments_for_kde and dimensionality == 1:
                # KDE for 1D
                try:
                    kde = stats.gaussian_kde(coords[:, 0])
                    x_grid = np.linspace(coords[:, 0].min(), coords[:, 0].max(), 100)
                    peak_idx = np.argmax(kde(x_grid))
                    centroid = np.array([x_grid[peak_idx], 0.0])
                except Exception:
                    centroid = np.array([coords[:, 0].mean(), 0.0])
            else:
                # Simple mean
                centroid = coords.mean(axis=0)

            # Compute mean confidence
            mean_confidence = np.mean([p.confidence for p in valid_frags])

            positions.append(GroupPosition(
                group_id=group_id,
                position_x=float(centroid[0]),
                position_y=float(centroid[1]) if dimensionality == 2 else 0.0,
                dispersion=DispersionEllipse(
                    center_x=float(centroid[0]),
                    center_y=float(centroid[1]) if dimensionality == 2 else 0.0,
                    radius_x=0.1,
                    radius_y=0.1,
                    rotation=0.0,
                ),
                stats={
                    "n_fragments": len(group_frags),
                    "n_valid": n_frags,
                    "confidence": float(mean_confidence),
                },
                core_evidence_ids=[],
            ))

        logger.info(f"IC-3: Clustered {len(positions)} groups")
        return positions

    def _kde_peak_2d(self, coords: np.ndarray) -> np.ndarray:
        """Find KDE peak in 2D space."""
        from scipy.optimize import minimize

        kde = stats.gaussian_kde(coords.T)

        def neg_density(x):
            return -kde(x.reshape(-1, 1))[0]

        # Start from mean
        x0 = coords.mean(axis=0)
        result = minimize(neg_density, x0, method='L-BFGS-B')

        return result.x

    def _ic4_dispersion(
        self,
        groups: List[GroupPosition],
        projected: List[ProjectedFragment]
    ) -> List[GroupPosition]:
        """
        IC-4: Compute dispersion ellipses using eigendecomposition.

        Uses weighted covariance matrix based on SCR confidence.
        """
        proj_by_group = {}
        for p in projected:
            if p.group_id not in proj_by_group:
                proj_by_group[p.group_id] = []
            proj_by_group[p.group_id].append(p)

        for group in groups:
            group_points = proj_by_group.get(group.group_id, [])
            valid_points = [p for p in group_points if not p.is_outlier]

            if len(valid_points) < 2:
                # Minimal ellipse for sparse groups
                group.dispersion = DispersionEllipse(
                    center_x=group.position_x,
                    center_y=group.position_y,
                    radius_x=0.1,
                    radius_y=0.1,
                    rotation=0.0,
                )
                continue

            coords = np.array([p.coordinates for p in valid_points])
            weights = np.array([p.confidence for p in valid_points])

            # Normalize weights
            weights = weights / weights.sum() if weights.sum() > 0 else np.ones_like(weights) / len(weights)

            # Weighted mean (should match centroid)
            mean = np.average(coords, axis=0, weights=weights)

            # Weighted covariance
            centered = coords - mean
            cov = np.cov(centered.T, aweights=weights)

            # Ensure cov is 2D
            if cov.ndim == 0:
                cov = np.array([[cov, 0], [0, cov]])
            elif cov.shape == (2,):
                cov = np.diag(cov)

            # Eigendecomposition
            try:
                eigenvalues, eigenvectors = np.linalg.eigh(cov)
                eigenvalues = np.maximum(eigenvalues, 1e-6)  # Avoid negative

                # Chi2 scaling for 50% mass containment
                chi2_scale = 1.386

                radius_x = np.sqrt(eigenvalues[1]) * chi2_scale
                radius_y = np.sqrt(eigenvalues[0]) * chi2_scale
                rotation = np.degrees(np.arctan2(eigenvectors[1, 1], eigenvectors[0, 1]))

            except Exception as e:
                logger.warning(f"Eigendecomposition failed for {group.group_id}: {e}")
                radius_x = np.std(coords[:, 0]) * 1.386
                radius_y = np.std(coords[:, 1]) * 1.386 if coords.shape[1] > 1 else 0.1
                rotation = 0.0

            group.dispersion = DispersionEllipse(
                center_x=float(mean[0]),
                center_y=float(mean[1]),
                radius_x=float(radius_x),
                radius_y=float(radius_y),
                rotation=float(rotation),
            )

        logger.info(f"IC-4: Computed dispersion for {len(groups)} groups")
        return groups

    def _ic5_evidence_binding(
        self,
        axes: np.ndarray,
        evr: np.ndarray,
        projected: List[ProjectedFragment],
        dimensionality: int
    ) -> List[AxisDefinition]:
        """
        IC-5: Bind evidence fragments to axis poles.

        Identifies extreme fragments on each axis for interpretability.
        """
        axis_defs = []

        for i in range(dimensionality):
            # Sort by coordinate on this axis
            sorted_frags = sorted(projected, key=lambda p: p.coordinates[i])

            # Top 50 at each pole (or 10% of total, whichever is smaller)
            n_pole = min(50, max(3, len(sorted_frags) // 10))

            negative_pole = [p.fragment_id for p in sorted_frags[:n_pole]]
            positive_pole = [p.fragment_id for p in sorted_frags[-n_pole:]]

            axis_defs.append(AxisDefinition(
                index=i,
                explained_variance=float(evr[i]) if i < len(evr) else 0.0,
                positive_pole_fragments=positive_pole,
                negative_pole_fragments=negative_pole,
            ))

        # If 1D, add placeholder for Y axis
        if dimensionality == 1:
            axis_defs.append(AxisDefinition(
                index=1,
                explained_variance=0.0,
                positive_pole_fragments=[],
                negative_pole_fragments=[],
            ))

        logger.info(f"IC-5: Bound evidence to {dimensionality} axes")
        return axis_defs

    def _ic6_interpretability(
        self,
        axis_defs: List[AxisDefinition],
        fragments: List[Fragment],
        projected: List[ProjectedFragment]
    ) -> List[AxisDefinition]:
        """
        IC-6: Add interpretability labels to axes.

        Uses TF-IDF on pole fragments if axis_labeling module is available.
        Falls back to generic labels otherwise.
        """
        # Build fragment text lookup
        text_lookup = {f.id: f.text for f in fragments}

        for axis_def in axis_defs:
            if not axis_def.positive_pole_fragments and not axis_def.negative_pole_fragments:
                continue

            # Get texts for poles
            pos_texts = [text_lookup.get(fid, "") for fid in axis_def.positive_pole_fragments]
            neg_texts = [text_lookup.get(fid, "") for fid in axis_def.negative_pole_fragments]

            pos_texts = [t for t in pos_texts if t]
            neg_texts = [t for t in neg_texts if t]

            # Try to use axis labeler
            try:
                if self._axis_labeler is None:
                    from .axis_labeling import AxisLabeler
                    self._axis_labeler = AxisLabeler()

                pos_label, pos_keywords = self._axis_labeler.label_pole(pos_texts, neg_texts)
                neg_label, neg_keywords = self._axis_labeler.label_pole(neg_texts, pos_texts)

                axis_def.positive_side = AxisSideDescription(
                    label=pos_label,
                    explanation=f"Caratterizzato da: {', '.join(pos_keywords[:5])}",
                    keywords=pos_keywords[:10],
                    fragments=[{"text_preview": t[:100]} for t in pos_texts[:3]],
                )
                axis_def.negative_side = AxisSideDescription(
                    label=neg_label,
                    explanation=f"Caratterizzato da: {', '.join(neg_keywords[:5])}",
                    keywords=neg_keywords[:10],
                    fragments=[{"text_preview": t[:100]} for t in neg_texts[:3]],
                )

            except ImportError:
                logger.warning("axis_labeling module not available, using generic labels")
                self._set_generic_labels(axis_def, pos_texts, neg_texts)
            except Exception as e:
                logger.warning(f"IC-6 labeling failed: {e}, using generic labels")
                self._set_generic_labels(axis_def, pos_texts, neg_texts)

        logger.info(f"IC-6: Added interpretability to {len(axis_defs)} axes")
        return axis_defs

    def _set_generic_labels(
        self,
        axis_def: AxisDefinition,
        pos_texts: List[str],
        neg_texts: List[str]
    ):
        """Set generic axis labels when TF-IDF is not available."""
        axis_names = ["Asse principale", "Asse secondario"]
        axis_name = axis_names[axis_def.index] if axis_def.index < 2 else f"Asse {axis_def.index + 1}"

        axis_def.positive_side = AxisSideDescription(
            label=f"{axis_name} (+)",
            explanation="Polo positivo dell'asse semantico",
            keywords=[],
            fragments=[{"text_preview": t[:100]} for t in pos_texts[:3]],
        )
        axis_def.negative_side = AxisSideDescription(
            label=f"{axis_name} (-)",
            explanation="Polo negativo dell'asse semantico",
            keywords=[],
            fragments=[{"text_preview": t[:100]} for t in neg_texts[:3]],
        )

    def _build_scatter_sample(
        self,
        projected: List[ProjectedFragment],
        dimensionality: int
    ) -> List[Dict[str, Any]]:
        """Build scatter sample for visualization."""
        random.seed(self.scatter_random_seed)

        # Sample if too many
        if len(projected) > self.scatter_sample_size:
            sampled = random.sample(projected, self.scatter_sample_size)
        else:
            sampled = projected

        return [
            {
                "x": p.coordinates[0],
                "y": p.coordinates[1] if dimensionality == 2 else 0.0,
                "group_id": p.group_id,
                "text": p.text[:100] if p.text else "",
                "evidence_id": p.fragment_id,
                "confidence": p.confidence,
            }
            for p in sampled
        ]

    def _fallback_response(
        self,
        fragments: List[Fragment],
        query: str,
        reason: str
    ) -> CompassAnalysisResponse:
        """Generate fallback response when analysis fails."""
        logger.warning(f"Compass fallback: {reason}")

        # Group by party and use simple positioning
        groups_map: Dict[str, List[Fragment]] = {}
        for f in fragments:
            if f.group_id not in groups_map:
                groups_map[f.group_id] = []
            groups_map[f.group_id].append(f)

        # Simple left-right positioning based on group order
        group_list = list(groups_map.keys())
        positions = []

        for i, group_id in enumerate(group_list):
            # Spread groups evenly on X axis
            x = (i / max(len(group_list) - 1, 1)) * 4 - 2  # Range [-2, 2]

            positions.append(GroupPosition(
                group_id=group_id,
                position_x=x,
                position_y=0.0,
                dispersion=DispersionEllipse(
                    center_x=x,
                    center_y=0.0,
                    radius_x=0.2,
                    radius_y=0.1,
                    rotation=0.0,
                ),
                stats={
                    "n_fragments": len(groups_map[group_id]),
                    "confidence": 0.3,
                },
                core_evidence_ids=[],
            ))

        return CompassAnalysisResponse(
            meta=CompassMetadata(
                query=query,
                dimensionality=1,
                explained_variance_ratio=[0.0, 0.0],
                total_variance_explained=0.0,
                n_evidence=len(fragments),
                is_stable=False,
                warnings=[reason],
            ),
            axes={
                "x": AxisDefinition(
                    index=0,
                    explained_variance=0.0,
                    positive_pole_fragments=[],
                    negative_pole_fragments=[],
                ),
                "y": AxisDefinition(
                    index=1,
                    explained_variance=0.0,
                    positive_pole_fragments=[],
                    negative_pole_fragments=[],
                ),
            },
            groups=positions,
            scatter_sample=[],
        )
