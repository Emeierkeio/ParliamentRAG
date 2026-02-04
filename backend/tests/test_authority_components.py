"""
Tests for authority score components.

Following clean code best practices:
- Arrange-Act-Assert pattern
- Descriptive test names
- Isolated component testing
- Realistic test data
"""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.authority.components import (
    ProfessionComponent,
    EducationComponent,
    CommitteeComponent,
    ActsComponent,
    InterventionsComponent,
    RoleComponent,
)


class TestProfessionComponent:
    """Test suite for profession authority component."""

    @pytest.fixture
    def component(self):
        """Create a fresh component instance."""
        with patch('app.services.authority.components.get_config') as mock_config:
            mock_config.return_value.load_config.return_value = {
                "authority": {"max_component_contribution": 0.8}
            }
            return ProfessionComponent()

    def test_missing_embedding_returns_neutral(self, component):
        """Missing profession embedding should return neutral score."""
        speaker_data = {"embedding_professione": None}
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        assert score == 0.5

    def test_identical_embedding_returns_high_score(self, component):
        """Identical embeddings should return high score."""
        embedding = [0.1] * 1536
        speaker_data = {"embedding_professione": embedding}

        score = component.compute(speaker_data, embedding, date.today())

        # Cosine similarity of identical vectors = 1.0
        # Mapped to [0,1]: (1+1)/2 = 1.0, capped at 0.8
        assert score == 0.8

    def test_orthogonal_embedding_returns_middle_score(self, component):
        """Orthogonal embeddings should return ~0.5 score."""
        query_embedding = [1.0] + [0.0] * 1535
        profession_embedding = [0.0, 1.0] + [0.0] * 1534
        speaker_data = {"embedding_professione": profession_embedding}

        score = component.compute(speaker_data, query_embedding, date.today())

        # Cosine similarity of orthogonal = 0
        # Mapped to [0,1]: (0+1)/2 = 0.5
        assert abs(score - 0.5) < 0.1


class TestEducationComponent:
    """Test suite for education authority component."""

    @pytest.fixture
    def component(self):
        """Create a fresh component instance."""
        with patch('app.services.authority.components.get_config') as mock_config:
            mock_config.return_value.load_config.return_value = {
                "authority": {"max_component_contribution": 0.8}
            }
            return EducationComponent()

    def test_missing_embedding_returns_neutral(self, component):
        """Missing education embedding should return neutral score."""
        speaker_data = {"embedding_istruzione": None}
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        assert score == 0.5


class TestCommitteeComponent:
    """Test suite for committee authority component."""

    @pytest.fixture
    def component(self):
        """Create a fresh component instance."""
        with patch('app.services.authority.components.get_config') as mock_config:
            mock_config.return_value.load_config.return_value = {
                "authority": {"max_component_contribution": 0.8}
            }
            return CommitteeComponent()

    def test_no_memberships_returns_zero(self, component):
        """No committee memberships should return 0."""
        speaker_data = {"committee_memberships": []}
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        assert score == 0.0

    def test_active_membership_returns_positive(self, component):
        """Active committee membership should return positive score."""
        speaker_data = {
            "committee_memberships": [
                {
                    "commissione_nome": "I COMMISSIONE (AFFARI COSTITUZIONALI)",
                    "dataInizio": date(2023, 1, 1),
                    "dataFine": None  # Still active
                }
            ]
        }
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        assert score > 0.0

    def test_expired_membership_excluded(self, component):
        """Expired committee membership should be excluded."""
        speaker_data = {
            "committee_memberships": [
                {
                    "commissione_nome": "I COMMISSIONE",
                    "dataInizio": date(2020, 1, 1),
                    "dataFine": date(2021, 12, 31)  # Expired
                }
            ]
        }
        query_embedding = [0.1] * 1536
        reference_date = date(2024, 1, 1)

        score = component.compute(speaker_data, query_embedding, reference_date)

        assert score == 0.0

    def test_future_membership_excluded(self, component):
        """Future committee membership should be excluded."""
        speaker_data = {
            "committee_memberships": [
                {
                    "commissione_nome": "I COMMISSIONE",
                    "dataInizio": date(2025, 1, 1),  # Future
                    "dataFine": None
                }
            ]
        }
        query_embedding = [0.1] * 1536
        reference_date = date(2024, 1, 1)

        score = component.compute(speaker_data, query_embedding, reference_date)

        assert score == 0.0


class TestActsComponent:
    """Test suite for parliamentary acts authority component."""

    @pytest.fixture
    def component(self):
        """Create a fresh component instance."""
        with patch('app.services.authority.components.get_config') as mock_config:
            mock_config.return_value.load_config.return_value = {
                "authority": {
                    "max_component_contribution": 0.8,
                    "time_decay": {"acts_half_life_days": 365}
                }
            }
            return ActsComponent()

    def test_no_acts_returns_zero(self, component):
        """No acts should return 0."""
        speaker_data = {"acts": []}
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        assert score == 0.0

    def test_recent_acts_higher_than_old(self, component):
        """Recent acts should contribute more than old acts."""
        reference_date = date(2024, 6, 1)

        speaker_data_recent = {
            "acts": [{"date": date(2024, 5, 1)}]  # 1 month ago
        }
        speaker_data_old = {
            "acts": [{"date": date(2022, 1, 1)}]  # 2.5 years ago
        }
        query_embedding = [0.1] * 1536

        score_recent = component.compute(speaker_data_recent, query_embedding, reference_date)
        score_old = component.compute(speaker_data_old, query_embedding, reference_date)

        assert score_recent > score_old

    def test_future_acts_excluded(self, component):
        """Future acts should be excluded."""
        reference_date = date(2024, 1, 1)
        speaker_data = {
            "acts": [{"date": date(2025, 1, 1)}]  # Future
        }
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, reference_date)

        assert score == 0.0

    def test_multiple_acts_higher_than_single(self, component):
        """Multiple acts should result in higher score."""
        reference_date = date(2024, 6, 1)
        single_act = {"acts": [{"date": date(2024, 5, 1)}]}
        multiple_acts = {
            "acts": [
                {"date": date(2024, 5, 1)},
                {"date": date(2024, 4, 1)},
                {"date": date(2024, 3, 1)},
            ]
        }
        query_embedding = [0.1] * 1536

        score_single = component.compute(single_act, query_embedding, reference_date)
        score_multiple = component.compute(multiple_acts, query_embedding, reference_date)

        assert score_multiple > score_single


class TestInterventionsComponent:
    """Test suite for interventions authority component."""

    @pytest.fixture
    def component(self):
        """Create a fresh component instance."""
        with patch('app.services.authority.components.get_config') as mock_config:
            mock_config.return_value.load_config.return_value = {
                "authority": {
                    "max_component_contribution": 0.8,
                    "time_decay": {"speeches_half_life_days": 180}
                }
            }
            return InterventionsComponent()

    def test_no_interventions_returns_zero(self, component):
        """No interventions should return 0."""
        speaker_data = {"interventions": []}
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        assert score == 0.0

    def test_recent_interventions_higher_than_old(self, component):
        """Recent interventions should contribute more than old ones."""
        reference_date = date(2024, 6, 1)

        speaker_data_recent = {
            "interventions": [{"date": date(2024, 5, 1)}]
        }
        speaker_data_old = {
            "interventions": [{"date": date(2022, 1, 1)}]
        }
        query_embedding = [0.1] * 1536

        score_recent = component.compute(speaker_data_recent, query_embedding, reference_date)
        score_old = component.compute(speaker_data_old, query_embedding, reference_date)

        assert score_recent > score_old


class TestRoleComponent:
    """Test suite for institutional role authority component."""

    @pytest.fixture
    def component(self):
        """Create a fresh component instance."""
        with patch('app.services.authority.components.get_config') as mock_config:
            mock_config.return_value.load_config.return_value = {
                "authority": {"max_component_contribution": 0.8}
            }
            return RoleComponent()

    def test_no_roles_returns_base_score(self, component):
        """No roles should return base score (0.3)."""
        speaker_data = {"roles": []}
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        assert score == 0.3

    def test_ministro_returns_high_score(self, component):
        """Ministro role should return high score."""
        speaker_data = {
            "roles": [
                {
                    "role": "Ministro dell'Interno",
                    "dataInizio": date(2023, 1, 1),
                    "dataFine": None
                }
            ]
        }
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        assert score >= 0.8  # Capped at 0.8

    def test_expired_role_excluded(self, component):
        """Expired roles should be excluded."""
        reference_date = date(2024, 1, 1)
        speaker_data = {
            "roles": [
                {
                    "role": "Ministro dell'Interno",
                    "dataInizio": date(2020, 1, 1),
                    "dataFine": date(2021, 12, 31)  # Expired
                }
            ]
        }
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, reference_date)

        assert score == 0.3  # Base score (no active roles)

    def test_presidente_camera_highest_score(self, component):
        """Presidente della Camera should return highest role score."""
        speaker_data = {
            "roles": [
                {
                    "role": "Presidente della Camera",
                    "dataInizio": date(2023, 1, 1),
                    "dataFine": None
                }
            ]
        }
        query_embedding = [0.1] * 1536

        score = component.compute(speaker_data, query_embedding, date.today())

        # Presidente della Camera weight is 1.0, capped at 0.8
        assert score == 0.8
