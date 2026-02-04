"""
Group-based ideological anchors for semi-supervised compass.

IMPORTANT: The compass is used for MULTI-VIEW COVERAGE, not ideology discovery.
Anchors are SOFT constraints, fully configurable in config/default.yaml.
"""
import logging
from typing import Dict, List, Optional, Tuple

from ...config import get_config

logger = logging.getLogger(__name__)


class AnchorManager:
    """
    Manages ideological anchors for multi-view coverage.

    Anchors provide weak supervision for left/center/right positioning
    based on parliamentary group membership.
    """

    def __init__(self):
        self.config = get_config()
        self._anchors: Optional[Dict] = None

    def _load_anchors(self) -> Dict:
        """Load anchor configuration."""
        if self._anchors is not None:
            return self._anchors

        config = self.config.load_config()
        compass_config = config.get("compass", {})

        self._anchors = {
            "left": {
                "groups": [],
                "confidence": 0.8,
            },
            "center": {
                "groups": [],
                "confidence": 0.6,
            },
            "right": {
                "groups": [],
                "confidence": 0.8,
            },
            "ambiguous": {},
            "unclassified": [],
        }

        # Load from config
        anchors_config = compass_config.get("anchors", {})

        for position in ["left", "center", "right"]:
            pos_config = anchors_config.get(position, {})
            self._anchors[position]["groups"] = pos_config.get("groups", [])
            self._anchors[position]["confidence"] = pos_config.get("confidence", 0.7)

        # Ambiguous groups (like M5S)
        self._anchors["ambiguous"] = compass_config.get("ambiguous", {})

        # Unclassified groups (like MISTO)
        self._anchors["unclassified"] = compass_config.get("unclassified", [])

        return self._anchors

    def get_position_for_group(
        self,
        group_name: str
    ) -> Tuple[str, float]:
        """
        Get ideological position for a parliamentary group.

        Args:
            group_name: Name of the parliamentary group

        Returns:
            Tuple of (position, confidence) where position is "left", "center", or "right"
            and confidence is in [0, 1]
        """
        anchors = self._load_anchors()

        # Check explicit anchors
        for position in ["left", "center", "right"]:
            if group_name in anchors[position]["groups"]:
                return position, anchors[position]["confidence"]

        # Check ambiguous groups
        if group_name in anchors["ambiguous"]:
            amb_config = anchors["ambiguous"][group_name]
            return amb_config.get("default_position", "center"), amb_config.get("confidence", 0.5)

        # Check unclassified
        if group_name in anchors["unclassified"]:
            return "center", 0.3  # Low confidence center default

        # Unknown group
        logger.warning(f"Unknown group '{group_name}' for ideological positioning")
        return "center", 0.2

    def get_anchor_groups(self, position: str) -> List[str]:
        """Get all groups anchored to a position."""
        anchors = self._load_anchors()
        return anchors.get(position, {}).get("groups", [])

    def get_all_positions(self) -> Dict[str, Tuple[str, float]]:
        """
        Get position and confidence for all known groups.

        Returns:
            Dictionary mapping group_name to (position, confidence)
        """
        anchors = self._load_anchors()
        result = {}

        # Explicit anchors
        for position in ["left", "center", "right"]:
            confidence = anchors[position]["confidence"]
            for group in anchors[position]["groups"]:
                result[group] = (position, confidence)

        # Ambiguous groups
        for group, config in anchors["ambiguous"].items():
            result[group] = (
                config.get("default_position", "center"),
                config.get("confidence", 0.5)
            )

        # Unclassified
        for group in anchors["unclassified"]:
            result[group] = ("center", 0.3)

        return result

    def position_to_numeric(self, position: str) -> float:
        """
        Convert position to numeric value.

        Uses wider range for better visualization spread:
        left = -3.0, center = 0.0, right = 3.0
        """
        mapping = {
            "left": -3.0,
            "center": 0.0,
            "right": 3.0,
        }
        return mapping.get(position, 0.0)

    def numeric_to_position(self, value: float) -> str:
        """
        Convert numeric value to position.

        Uses thresholds: < -0.33 = left, > 0.33 = right, else center
        """
        if value < -0.33:
            return "left"
        elif value > 0.33:
            return "right"
        else:
            return "center"
