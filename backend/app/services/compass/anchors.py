"""
Group-based ideological anchors for the semi-supervised compass.

The compass serves multi-view coverage, not ideology discovery. Anchors are
soft constraints, fully configurable in config/default.yaml.
"""
import logging
from typing import Dict, Optional, Tuple

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
            "enabled": False,
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

        anchors_config = compass_config.get("anchors", {})
        self._anchors["enabled"] = anchors_config.get("enabled", False)

        if not self._anchors["enabled"]:
            logger.info("Compass anchors disabled, using neutral positioning")
            return self._anchors

        for position in ["left", "center", "right"]:
            pos_config = anchors_config.get(position, {})
            self._anchors[position]["groups"] = pos_config.get("groups", [])
            self._anchors[position]["confidence"] = pos_config.get("confidence", 0.7)

        # Ambiguous groups (e.g. M5S) and unclassified ones (e.g. MISTO).
        self._anchors["ambiguous"] = compass_config.get("ambiguous", {})
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

        for position in ["left", "center", "right"]:
            if group_name in anchors[position]["groups"]:
                return position, anchors[position]["confidence"]

        if group_name in anchors["ambiguous"]:
            amb_config = anchors["ambiguous"][group_name]
            return amb_config.get("default_position", "center"), amb_config.get("confidence", 0.5)

        if group_name in anchors["unclassified"]:
            return "center", 0.3

        logger.warning(f"Unknown group '{group_name}' for ideological positioning")
        return "center", 0.2

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
