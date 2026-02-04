"""
Tests for coalition logic and authority scoring.

CRITICAL: These tests verify the temporal coalition rules that are
fundamental to the system's correctness.
"""
import pytest
from datetime import date

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.authority.coalition_logic import CoalitionLogic


class TestCoalitionLogic:
    """Test suite for CoalitionLogic."""

    def setup_method(self):
        """Setup for each test."""
        self.logic = CoalitionLogic()

    def test_get_coalition_maggioranza(self):
        """Test that majority parties are correctly identified."""
        maggioranza_parties = [
            "FRATELLI D'ITALIA",
            "LEGA - SALVINI PREMIER",
            "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
            "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE",
        ]

        for party in maggioranza_parties:
            assert self.logic.get_coalition(party) == "maggioranza", \
                f"{party} should be maggioranza"

    def test_get_coalition_opposizione(self):
        """Test that opposition parties are correctly identified."""
        opposizione_parties = [
            "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
            "MOVIMENTO 5 STELLE",
            "ALLEANZA VERDI E SINISTRA",
            "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE",
            "ITALIA VIVA-IL CENTRO-RENEW EUROPE",
            "MISTO",
        ]

        for party in opposizione_parties:
            assert self.logic.get_coalition(party) == "opposizione", \
                f"{party} should be opposizione"

    def test_coalition_crossing_invalidates_authority(self):
        """
        CRITICAL TEST: Deputy moves from PD (opposition) to FdI (majority).
        Their interventions while in PD should NOT count for FdI authority.
        """
        # Opposition -> Majority crossing
        assert self.logic.authority_carries_over(
            "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
            "FRATELLI D'ITALIA"
        ) == False

        # Majority -> Opposition crossing
        assert self.logic.authority_carries_over(
            "LEGA - SALVINI PREMIER",
            "MOVIMENTO 5 STELLE"
        ) == False

    def test_same_coalition_carries_over(self):
        """Authority should carry over within same coalition."""
        # Within majority
        assert self.logic.authority_carries_over(
            "FRATELLI D'ITALIA",
            "LEGA - SALVINI PREMIER"
        ) == True

        # Within opposition
        assert self.logic.authority_carries_over(
            "MOVIMENTO 5 STELLE",
            "ALLEANZA VERDI E SINISTRA"
        ) == True

    def test_same_party_carries_over(self):
        """Authority should carry over if staying in same party."""
        assert self.logic.authority_carries_over(
            "FRATELLI D'ITALIA",
            "FRATELLI D'ITALIA"
        ) == True

    def test_get_valid_periods(self, sample_memberships):
        """Test valid period calculation with coalition filtering."""
        reference_date = date(2024, 6, 1)
        current_group = "FRATELLI D'ITALIA"

        valid_periods = self.logic.get_valid_periods(
            sample_memberships,
            reference_date,
            current_group
        )

        # Should only return the FdI period (same coalition as current)
        assert len(valid_periods) == 1
        start, end, group = valid_periods[0]
        assert group == "FRATELLI D'ITALIA"
        assert start == date(2024, 1, 16)

    def test_get_valid_periods_excludes_crossing(self, sample_memberships):
        """Test that periods in different coalition are excluded."""
        reference_date = date(2024, 6, 1)
        current_group = "FRATELLI D'ITALIA"  # Majority

        valid_periods = self.logic.get_valid_periods(
            sample_memberships,
            reference_date,
            current_group
        )

        # PD period should be excluded (different coalition)
        groups_in_periods = [g for _, _, g in valid_periods]
        assert "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA" not in groups_in_periods

    def test_filter_activities_by_coalition(self, sample_memberships, sample_activities):
        """Test activity filtering respects coalition boundaries."""
        reference_date = date(2024, 6, 1)
        current_group = "FRATELLI D'ITALIA"

        filtered = self.logic.filter_activities_by_coalition(
            sample_activities,
            sample_memberships,
            reference_date,
            current_group
        )

        # Only activities during FdI membership should remain
        filtered_ids = [a["id"] for a in filtered]

        # act_1 and act_2 were during PD membership (opposition) - should be excluded
        assert "act_1" not in filtered_ids
        assert "act_2" not in filtered_ids

        # act_3 and act_4 were during FdI membership (majority) - should be included
        assert "act_3" in filtered_ids
        assert "act_4" in filtered_ids

    def test_unknown_party_defaults_to_opposizione(self):
        """Unknown parties should default to opposition."""
        assert self.logic.get_coalition("PARTITO SCONOSCIUTO") == "opposizione"


class TestCoalitionCrossingScenarios:
    """Detailed scenarios for coalition crossing."""

    def setup_method(self):
        self.logic = CoalitionLogic()

    def test_scenario_pd_to_fdi(self):
        """
        Scenario: Deputy in PD for 2 years, then joins FdI.
        All their PD activities should be discarded for FdI authority.
        """
        memberships = [
            {
                "gruppo": "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
                "dataInizio": date(2022, 10, 1),
                "dataFine": date(2024, 3, 1),
            },
            {
                "gruppo": "FRATELLI D'ITALIA",
                "dataInizio": date(2024, 3, 2),
                "dataFine": None,
            },
        ]

        activities = [
            {"id": f"pd_act_{i}", "date": date(2023, i, 15)}
            for i in range(1, 13)  # 12 activities during PD
        ] + [
            {"id": f"fdi_act_{i}", "date": date(2024, i+3, 15)}
            for i in range(1, 7)  # 6 activities during FdI
        ]

        reference_date = date(2024, 10, 1)
        current_group = "FRATELLI D'ITALIA"

        filtered = self.logic.filter_activities_by_coalition(
            activities,
            memberships,
            reference_date,
            current_group
        )

        # All 12 PD activities should be excluded
        pd_ids = [a["id"] for a in filtered if a["id"].startswith("pd_")]
        assert len(pd_ids) == 0

        # All 6 FdI activities should remain
        fdi_ids = [a["id"] for a in filtered if a["id"].startswith("fdi_")]
        assert len(fdi_ids) == 6

    def test_scenario_m5s_to_pd(self):
        """
        Scenario: Deputy moves from M5S to PD (both opposition).
        Activities should carry over since same coalition.
        """
        memberships = [
            {
                "gruppo": "MOVIMENTO 5 STELLE",
                "dataInizio": date(2022, 10, 1),
                "dataFine": date(2024, 1, 1),
            },
            {
                "gruppo": "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
                "dataInizio": date(2024, 1, 2),
                "dataFine": None,
            },
        ]

        activities = [
            {"id": "m5s_act_1", "date": date(2023, 6, 15)},
            {"id": "pd_act_1", "date": date(2024, 6, 15)},
        ]

        reference_date = date(2024, 10, 1)
        current_group = "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA"

        filtered = self.logic.filter_activities_by_coalition(
            activities,
            memberships,
            reference_date,
            current_group
        )

        # Both activities should remain (same coalition)
        filtered_ids = [a["id"] for a in filtered]
        assert "m5s_act_1" in filtered_ids
        assert "pd_act_1" in filtered_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
