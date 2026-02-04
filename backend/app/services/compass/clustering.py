"""
Clustering methods for ideological compass.

Handles:
- KDE (Kernel Density Estimation) for ≥3 fragments
- Mean + minimal ellipse for 1-2 fragments
- "Insufficient data" fallback for 0 fragments
"""
import logging
from typing import List, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class IdeologyClustering:
    """
    Clustering methods for computing ideological positions.
    """

    def __init__(self, bandwidth: str = "scott"):
        """
        Initialize clustering.

        Args:
            bandwidth: KDE bandwidth method ("scott", "silverman", or numeric)
        """
        self.bandwidth = bandwidth

    def compute_position(
        self,
        positions: List[float],
        confidences: Optional[List[float]] = None
    ) -> Dict[str, any]:
        """
        Compute ideological position from multiple data points.

        Args:
            positions: List of numeric positions [-1, 1]
            confidences: Optional list of confidence weights

        Returns:
            Dictionary with:
            - position: float in [-1, 1]
            - method: "kde" | "mean_ellipse" | "insufficient_data"
            - confidence: float in [0, 1]
            - distribution: Optional distribution data
        """
        n = len(positions)

        if n == 0:
            return {
                "position": 0.0,
                "method": "insufficient_data",
                "confidence": 0.0,
                "distribution": None,
            }

        if n <= 2:
            return self._mean_ellipse(positions, confidences)

        return self._kde_peak(positions, confidences)

    def _mean_ellipse(
        self,
        positions: List[float],
        confidences: Optional[List[float]] = None
    ) -> Dict[str, any]:
        """
        Compute position using weighted mean with minimal ellipse.

        Used when there are only 1-2 data points.
        """
        if confidences is None:
            confidences = [1.0] * len(positions)

        # Weighted mean
        weights = np.array(confidences)
        positions_arr = np.array(positions)

        if weights.sum() == 0:
            weights = np.ones_like(weights)

        weighted_mean = np.average(positions_arr, weights=weights)

        # Confidence based on number of points and their confidences
        base_confidence = 0.3 if len(positions) == 1 else 0.5
        confidence = base_confidence * np.mean(confidences)

        return {
            "position": float(weighted_mean),
            "method": "mean_ellipse",
            "confidence": float(confidence),
            "distribution": {
                "mean": float(weighted_mean),
                "n_points": len(positions),
            },
        }

    def _kde_peak(
        self,
        positions: List[float],
        confidences: Optional[List[float]] = None
    ) -> Dict[str, any]:
        """
        Compute position using KDE peak optimization.

        Used when there are ≥3 data points.
        """
        try:
            from scipy import stats
        except ImportError:
            logger.warning("scipy not available, falling back to mean_ellipse")
            return self._mean_ellipse(positions, confidences)

        positions_arr = np.array(positions)

        # Determine bandwidth
        if self.bandwidth == "scott":
            bw = "scott"
        elif self.bandwidth == "silverman":
            bw = "silverman"
        else:
            try:
                bw = float(self.bandwidth)
            except ValueError:
                bw = "scott"

        # Fit KDE
        try:
            kde = stats.gaussian_kde(positions_arr, bw_method=bw)
        except Exception as e:
            logger.warning(f"KDE failed: {e}, falling back to mean_ellipse")
            return self._mean_ellipse(positions, confidences)

        # Find peak
        x_range = np.linspace(-1.5, 1.5, 300)
        density = kde(x_range)
        peak_idx = np.argmax(density)
        peak_position = x_range[peak_idx]

        # Clamp to [-1, 1]
        peak_position = max(-1.0, min(1.0, peak_position))

        # Confidence based on density concentration
        # Higher concentration around peak = higher confidence
        peak_density = density[peak_idx]
        total_density = np.sum(density)
        concentration = peak_density / (total_density / len(density)) if total_density > 0 else 0.5

        # Scale confidence
        confidence = min(0.9, 0.5 + 0.4 * (concentration - 1) / 2)

        return {
            "position": float(peak_position),
            "method": "kde",
            "confidence": float(confidence),
            "distribution": {
                "peak": float(peak_position),
                "peak_density": float(peak_density),
                "n_points": len(positions),
            },
        }

    def compute_multi_view_scores(
        self,
        position: float,
        confidence: float
    ) -> Dict[str, float]:
        """
        Convert position to multi-view scores.

        Returns scores for left, center, right that sum to 1.

        Args:
            position: Position in [-1, 1]
            confidence: Confidence of the position

        Returns:
            Dictionary with left, center, right scores in [0, 1]
        """
        # Use soft-max style scoring
        # Distance from each anchor position
        left_dist = abs(position - (-1.0))
        center_dist = abs(position - 0.0)
        right_dist = abs(position - 1.0)

        # Convert distances to scores (inverse)
        # Temperature controls how "peaked" the distribution is
        temperature = 0.5

        left_score = np.exp(-left_dist / temperature)
        center_score = np.exp(-center_dist / temperature)
        right_score = np.exp(-right_dist / temperature)

        # Normalize
        total = left_score + center_score + right_score
        if total > 0:
            left_score /= total
            center_score /= total
            right_score /= total
        else:
            left_score = center_score = right_score = 1/3

        # Adjust for confidence (low confidence → more uniform)
        uniform = 1/3
        left_score = confidence * left_score + (1 - confidence) * uniform
        center_score = confidence * center_score + (1 - confidence) * uniform
        right_score = confidence * right_score + (1 - confidence) * uniform

        return {
            "left": float(left_score),
            "center": float(center_score),
            "right": float(right_score),
        }
