"""
Temporal coalition logic for authority scoring.

CRITICAL RULE: When a deputy crosses MAGGIORANZA ↔ OPPOSIZIONE boundary,
their prior authority contributions are INVALIDATED.
"""
import logging
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple, Any

from ...config import get_config

logger = logging.getLogger(__name__)


def parse_neo4j_date(date_value: Any) -> Optional[date]:
    """
    Parse a date value from Neo4j to Python date.

    Neo4j may return dates as:
    - neo4j.time.Date objects
    - Strings in DD/MM/YYYY or YYYYMMDD format
    - Float/int values like 20250612.0
    - datetime.date objects
    - None
    """
    if date_value is None:
        return None

    # Already a date object
    if isinstance(date_value, date):
        return date_value

    # Neo4j Date object (has to_native method)
    if hasattr(date_value, 'to_native'):
        return date_value.to_native()

    # Float or int (e.g., 20250612.0 or 20250612)
    if isinstance(date_value, (float, int)):
        try:
            date_str = str(int(date_value))
            if len(date_str) == 8:  # YYYYMMDD format
                return datetime.strptime(date_str, "%Y%m%d").date()
        except (ValueError, OverflowError):
            pass
        logger.warning(f"Could not parse date number: {date_value}")
        return None

    # String format - try common formats
    if isinstance(date_value, str):
        # Handle empty strings
        if not date_value.strip():
            return None

        # Remove decimal part if present (e.g., "20250612.0" -> "20250612")
        date_str = date_value.split('.')[0].strip()

        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y%m%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        logger.warning(f"Could not parse date string: {date_value}")
        return None

    logger.warning(f"Unknown date type: {type(date_value)} - {date_value}")
    return None


class CoalitionLogic:
    """
    Handles temporal coalition membership and authority validity.

    Core principle: Authority earned while in one coalition does NOT
    carry over when switching to the opposing coalition.
    """

    def __init__(self):
        self.config = get_config()
        self._coalition_cache: Dict[str, str] = {}

    def get_coalition(self, group_name: str) -> str:
        """
        Get coalition for a parliamentary group.

        Args:
            group_name: Name of the parliamentary group

        Returns:
            "maggioranza" or "opposizione"
        """
        if group_name in self._coalition_cache:
            return self._coalition_cache[group_name]

        coalitions = self.config.load_config().get("coalitions", {})

        # Government members are always in maggioranza
        if group_name.upper() in ("GOVERNO",):
            self._coalition_cache[group_name] = "maggioranza"
            return "maggioranza"
        # Case-insensitive comparison against config values
        group_upper = group_name.upper()

        for g in coalitions.get("maggioranza", []):
            if g.upper() == group_upper:
                self._coalition_cache[group_name] = "maggioranza"
                return "maggioranza"

        for g in coalitions.get("opposizione", []):
            if g.upper() == group_upper:
                self._coalition_cache[group_name] = "opposizione"
                return "opposizione"
            
        else:
            # Default unknown groups to opposition
            logger.warning(f"Unknown group '{group_name}', defaulting to opposizione")
            self._coalition_cache[group_name] = "opposizione"
            return "opposizione"

    def authority_carries_over(
        self,
        old_group: str,
        new_group: str
    ) -> bool:
        """
        Check if authority from old_group is valid for new_group.

        Returns FALSE if crossing MAGGIORANZA ↔ OPPOSIZIONE boundary.

        Args:
            old_group: Previous parliamentary group
            new_group: Current parliamentary group

        Returns:
            True if authority carries over, False otherwise
        """
        old_coalition = self.get_coalition(old_group)
        new_coalition = self.get_coalition(new_group)

        # Same coalition → authority carries over
        if old_coalition == new_coalition:
            return True

        # Different coalition → authority invalidated
        logger.info(
            f"Coalition crossing detected: {old_group} ({old_coalition}) → "
            f"{new_group} ({new_coalition}). Authority invalidated."
        )
        return False

    def get_valid_periods(
        self,
        memberships: List[Dict],
        reference_date: date,
        current_group: str
    ) -> List[Tuple[date, date, str]]:
        """
        Get time periods where authority contributions are valid.

        Only periods in the SAME coalition as current_group count.

        Args:
            memberships: List of group memberships with dates
                         [{"group": str, "start_date": date, "end_date": date}, ...]
            reference_date: Reference date for authority calculation
            current_group: Current parliamentary group of the speaker

        Returns:
            List of (start_date, end_date, group_name) tuples for valid periods
        """
        current_coalition = self.get_coalition(current_group)
        valid_periods = []

        for membership in memberships:
            group = membership.get("group", "")
            start = parse_neo4j_date(membership.get("start_date"))
            end = parse_neo4j_date(membership.get("end_date"))

            # Skip if no dates
            if not start:
                continue

            # Use reference_date as end if membership is ongoing
            if not end or end > reference_date:
                end = reference_date

            # Skip if period is after reference date
            if start > reference_date:
                continue

            # Check if same coalition
            if self.get_coalition(group) == current_coalition:
                valid_periods.append((start, end, group))
            else:
                logger.debug(
                    f"Excluding period {start} - {end} in {group} "
                    f"(coalition mismatch with current {current_group})"
                )

        return valid_periods

    def filter_activities_by_coalition(
        self,
        activities: List[Dict],
        memberships: List[Dict],
        reference_date: date,
        current_group: str
    ) -> List[Dict]:
        """
        Filter activities to only those in valid coalition periods.

        Args:
            activities: List of activities (interventions, acts, etc.)
                        Each must have a "date" field
            memberships: List of group memberships with dates
            reference_date: Reference date for authority calculation
            current_group: Current parliamentary group

        Returns:
            Filtered list of activities in valid coalition periods
        """
        valid_periods = self.get_valid_periods(
            memberships, reference_date, current_group
        )

        if not valid_periods:
            return []

        valid_activities = []
        for activity in activities:
            activity_date = parse_neo4j_date(activity.get("date"))
            if not activity_date:
                continue

            # Check if activity falls in any valid period
            for start, end, _ in valid_periods:
                if start <= activity_date <= end:
                    valid_activities.append(activity)
                    break

        logger.debug(
            f"Coalition filter: {len(valid_activities)}/{len(activities)} "
            f"activities valid for coalition {self.get_coalition(current_group)}"
        )

        return valid_activities


def test_coalition_crossing_invalidates_authority():
    """
    Unit test: Deputy moves from PD (opposition) to FdI (majority).
    Their interventions while in PD should NOT count for FdI authority.
    """
    logic = CoalitionLogic()

    # Test basic coalition crossing
    assert logic.authority_carries_over("Partito Democratico - Italia Democratica e Progressista",
                                        "Fratelli d'Italia") == False

    # Test same coalition
    assert logic.authority_carries_over("Fratelli d'Italia",
                                        "Lega - Salvini Premier") == True

    # Test opposition stays opposition
    assert logic.authority_carries_over("Movimento 5 Stelle",
                                        "Alleanza Verdi e Sinistra") == True

    print("Coalition crossing test PASSED")


if __name__ == "__main__":
    test_coalition_crossing_invalidates_authority()
