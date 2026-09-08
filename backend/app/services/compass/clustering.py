"""Convert 1D ideological positions to soft multi-view scores."""
from typing import Dict

import numpy as np


class IdeologyClustering:
    """Turn an anchor position and its confidence into left/center/right scores."""

    def compute_multi_view_scores(
        self,
        position: float,
        confidence: float
    ) -> Dict[str, float]:
        """
        Convert a position in [-1, 1] to left/center/right scores summing to 1.

        Softmax over negative distances to the three anchor points; low
        confidence blends the result toward the uniform distribution.
        """
        left_dist = abs(position - (-1.0))
        center_dist = abs(position - 0.0)
        right_dist = abs(position - 1.0)

        # Temperature controls how peaked the distribution is.
        temperature = 0.5

        left_score = np.exp(-left_dist / temperature)
        center_score = np.exp(-center_dist / temperature)
        right_score = np.exp(-right_dist / temperature)

        total = left_score + center_score + right_score
        left_score /= total
        center_score /= total
        right_score /= total

        uniform = 1 / 3
        left_score = confidence * left_score + (1 - confidence) * uniform
        center_score = confidence * center_score + (1 - confidence) * uniform
        right_score = confidence * right_score + (1 - confidence) * uniform

        return {
            "left": float(left_score),
            "center": float(center_score),
            "right": float(right_score),
        }
