"""
Unit tests for the unified expert computation service (app.services.experts).

Tests cover:
1. One expert per party
2. Combined ranking formula (0.70 * authority + 0.30 * similarity)
3. party_changed speakers use current_party
4. Expert dict contains all frozen fields
5. GovernmentMember speakers are excluded
6. patch_experts_for_cited_speakers updates experts based on citations
"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_evidence(
    speaker_id: str,
    speaker_name: str,
    party: str,
    speaker_role: str = "Deputy",
    similarity: float = 0.5,
    party_changed: bool = False,
    current_party: str | None = None,
):
    """Build a minimal evidence-like object for testing."""
    ev = MagicMock()
    ev.speaker_id = speaker_id
    ev.speaker_name = speaker_name
    ev.party = party
    ev.speaker_role = speaker_role
    ev.similarity = similarity
    ev.party_changed = party_changed
    ev.current_party = current_party
    return ev


def _make_authority_scores(entries: dict[str, float]) -> dict[str, float]:
    return entries


def _make_authority_details(entries: dict[str, dict]) -> dict[str, dict]:
    return entries


def _make_neo4j_mock():
    """Return a Neo4jClient-like mock that never makes real DB calls."""
    return MagicMock()


def _canned_speaker_details(neo4j_client, speaker_id: str) -> dict:
    """Return a predictable speaker-details dict without touching Neo4j."""
    return {
        "id": speaker_id,
        "first_name": "Mario",
        "last_name": "Rossi",
        "profession": "Avvocato",
        "education": "Laurea in Giurisprudenza",
        "camera_profile_url": f"https://camera.it/{speaker_id}",
        "photo": f"https://camera.it/photo/{speaker_id}.jpg",
        "current_committee": "Commissione Giustizia",
        "institutional_role": None,
    }


# ---------------------------------------------------------------------------
# Helper to run async tests
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test 1: compute_experts returns one expert per party
# ---------------------------------------------------------------------------

class TestOneExpertPerParty:
    """Given 3 speakers from 2 parties, compute_experts must return 2 experts."""

    def test_one_expert_per_party(self):
        from app.services.experts import compute_experts

        evidence_list = [
            _make_evidence("sp1", "Mario Rossi", "Partito A", similarity=0.8),
            _make_evidence("sp2", "Luigi Bianchi", "Partito A", similarity=0.3),
            _make_evidence("sp3", "Anna Verdi", "Partito B", similarity=0.9),
        ]
        authority_scores = _make_authority_scores({"sp1": 0.9, "sp2": 0.6, "sp3": 0.7})
        authority_details = _make_authority_details({
            "sp1": {"components": {}, "institutional_role": None},
            "sp2": {"components": {}, "institutional_role": None},
            "sp3": {"components": {}, "institutional_role": None},
        })
        neo4j_mock = _make_neo4j_mock()

        with patch(
            "app.services.experts._fetch_speaker_details",
            side_effect=_canned_speaker_details,
        ):
            experts = run(compute_experts(evidence_list, authority_scores, authority_details, neo4j_mock))

        assert len(experts) == 2, f"Expected 2 experts, got {len(experts)}"
        parties = {e["group"] for e in experts}
        assert parties == {"Partito A", "Partito B"}


# ---------------------------------------------------------------------------
# Test 2: Combined ranking formula (0.70 * authority + 0.30 * similarity)
# ---------------------------------------------------------------------------

class TestCombinedRankingFormula:
    """The top speaker per party is chosen via 0.70 * authority + 0.30 * similarity."""

    def test_combined_formula_selects_correct_speaker(self):
        from app.services.experts import compute_experts

        # sp1: authority=0.6, similarity=0.9 → combined = 0.42 + 0.27 = 0.69
        # sp2: authority=0.8, similarity=0.2 → combined = 0.56 + 0.06 = 0.62
        # sp1 should win despite lower authority because similarity is higher
        evidence_list = [
            _make_evidence("sp1", "Mario Rossi", "Partito A", similarity=0.9),
            _make_evidence("sp2", "Luigi Bianchi", "Partito A", similarity=0.2),
        ]
        authority_scores = _make_authority_scores({"sp1": 0.6, "sp2": 0.8})
        authority_details = _make_authority_details({
            "sp1": {"components": {}, "institutional_role": None},
            "sp2": {"components": {}, "institutional_role": None},
        })
        neo4j_mock = _make_neo4j_mock()

        with patch(
            "app.services.experts._fetch_speaker_details",
            side_effect=_canned_speaker_details,
        ):
            experts = run(compute_experts(evidence_list, authority_scores, authority_details, neo4j_mock))

        assert len(experts) == 1
        assert experts[0]["id"] == "sp1", (
            f"Expected sp1 to win via combined formula, got {experts[0]['id']}"
        )

    def test_authority_only_formula_selects_correct_speaker(self):
        """ranking_formula='authority_only' should select by authority score alone."""
        from app.services.experts import compute_experts

        # sp1: authority=0.6, sp2: authority=0.8 → sp2 wins with authority_only
        evidence_list = [
            _make_evidence("sp1", "Mario Rossi", "Partito A", similarity=0.9),
            _make_evidence("sp2", "Luigi Bianchi", "Partito A", similarity=0.2),
        ]
        authority_scores = _make_authority_scores({"sp1": 0.6, "sp2": 0.8})
        authority_details = _make_authority_details({
            "sp1": {"components": {}, "institutional_role": None},
            "sp2": {"components": {}, "institutional_role": None},
        })
        neo4j_mock = _make_neo4j_mock()

        with patch(
            "app.services.experts._fetch_speaker_details",
            side_effect=_canned_speaker_details,
        ):
            experts = run(compute_experts(
                evidence_list, authority_scores, authority_details, neo4j_mock,
                ranking_formula="authority_only",
            ))

        assert len(experts) == 1
        assert experts[0]["id"] == "sp2", (
            f"Expected sp2 to win via authority_only formula, got {experts[0]['id']}"
        )


# ---------------------------------------------------------------------------
# Test 3: party_changed speakers use current_party
# ---------------------------------------------------------------------------

class TestPartyChanged:
    """When party_changed=True, the speaker is bucketed under current_party."""

    def test_party_changed_uses_current_party(self):
        from app.services.experts import compute_experts

        evidence_list = [
            _make_evidence(
                "sp1", "Mario Rossi", "Partito Vecchio",
                party_changed=True, current_party="Partito Nuovo",
            ),
        ]
        authority_scores = _make_authority_scores({"sp1": 0.7})
        authority_details = _make_authority_details({"sp1": {"components": {}, "institutional_role": None}})
        neo4j_mock = _make_neo4j_mock()

        with patch(
            "app.services.experts._fetch_speaker_details",
            side_effect=_canned_speaker_details,
        ):
            experts = run(compute_experts(evidence_list, authority_scores, authority_details, neo4j_mock))

        assert len(experts) == 1
        assert experts[0]["group"] == "Partito Nuovo", (
            f"Expected current_party 'Partito Nuovo', got '{experts[0]['group']}'"
        )


# ---------------------------------------------------------------------------
# Test 4: Expert dict contains all frozen fields
# ---------------------------------------------------------------------------

class TestFrozenFields:
    """Every expert dict must contain the full frozen field set."""

    REQUIRED_FIELDS = {
        "id", "first_name", "last_name", "group", "coalition",
        "authority_score", "relevant_speeches_count", "score_breakdown",
        "camera_profile_url", "photo", "profession", "education",
        "committee", "institutional_role",
    }

    def test_expert_has_all_frozen_fields(self):
        from app.services.experts import compute_experts

        evidence_list = [
            _make_evidence("sp1", "Mario Rossi", "Partito A"),
        ]
        authority_scores = _make_authority_scores({"sp1": 0.7})
        authority_details = _make_authority_details({"sp1": {"components": {"interventions": 0.5, "acts": 0.4, "committee": 0.3, "profession": 0.2, "education": 0.1, "role": 0.0}, "institutional_role": "Presidente Commissione"}})
        neo4j_mock = _make_neo4j_mock()

        with patch(
            "app.services.experts._fetch_speaker_details",
            side_effect=_canned_speaker_details,
        ):
            experts = run(compute_experts(evidence_list, authority_scores, authority_details, neo4j_mock))

        assert len(experts) == 1
        expert = experts[0]
        missing = self.REQUIRED_FIELDS - set(expert.keys())
        assert not missing, f"Expert dict missing fields: {missing}"

    def test_score_breakdown_has_all_components(self):
        """score_breakdown must contain speeches, acts, committee, profession, education, role."""
        from app.services.experts import compute_experts

        evidence_list = [
            _make_evidence("sp1", "Mario Rossi", "Partito A"),
        ]
        authority_scores = _make_authority_scores({"sp1": 0.7})
        authority_details = _make_authority_details({
            "sp1": {
                "components": {
                    "interventions": 0.5, "acts": 0.4, "committee": 0.3,
                    "profession": 0.2, "education": 0.1, "role": 0.0
                },
                "institutional_role": None,
            }
        })
        neo4j_mock = _make_neo4j_mock()

        with patch(
            "app.services.experts._fetch_speaker_details",
            side_effect=_canned_speaker_details,
        ):
            experts = run(compute_experts(evidence_list, authority_scores, authority_details, neo4j_mock))

        breakdown = experts[0]["score_breakdown"]
        for field in ("speeches", "acts", "committee", "profession", "education", "role"):
            assert field in breakdown, f"score_breakdown missing '{field}'"


# ---------------------------------------------------------------------------
# Test 5: GovernmentMember speakers are excluded
# ---------------------------------------------------------------------------

class TestGovernmentMemberExcluded:
    """GovernmentMember speakers must not appear in the experts list."""

    def test_government_member_excluded(self):
        from app.services.experts import compute_experts

        evidence_list = [
            _make_evidence("sp1", "Mario Rossi", "Partito A", speaker_role="Deputy"),
            _make_evidence("gov1", "Ministro Verde", "Governo", speaker_role="GovernmentMember"),
        ]
        authority_scores = _make_authority_scores({"sp1": 0.7, "gov1": 0.9})
        authority_details = _make_authority_details({
            "sp1": {"components": {}, "institutional_role": None},
            "gov1": {"components": {}, "institutional_role": "Ministro"},
        })
        neo4j_mock = _make_neo4j_mock()

        with patch(
            "app.services.experts._fetch_speaker_details",
            side_effect=_canned_speaker_details,
        ):
            experts = run(compute_experts(evidence_list, authority_scores, authority_details, neo4j_mock))

        ids = [e["id"] for e in experts]
        assert "gov1" not in ids, "GovernmentMember should not appear in experts"
        assert "sp1" in ids, "Deputy should appear in experts"

    def test_all_government_members_returns_empty(self):
        from app.services.experts import compute_experts

        evidence_list = [
            _make_evidence("gov1", "Ministro Verde", "Governo", speaker_role="GovernmentMember"),
        ]
        authority_scores = _make_authority_scores({"gov1": 0.9})
        authority_details = _make_authority_details({"gov1": {"components": {}, "institutional_role": None}})
        neo4j_mock = _make_neo4j_mock()

        with patch("app.services.experts._fetch_speaker_details", side_effect=_canned_speaker_details):
            experts = run(compute_experts(evidence_list, authority_scores, authority_details, neo4j_mock))

        assert experts == [], "Expected empty list when all speakers are GovernmentMember"


# ---------------------------------------------------------------------------
# Test 6: patch_experts_for_cited_speakers
# ---------------------------------------------------------------------------

class TestPatchExpertsForCitedSpeakers:
    """patch_experts_for_cited_speakers replaces experts with actually cited speakers."""

    def _make_expert(self, speaker_id: str, party: str) -> dict:
        return {
            "id": speaker_id,
            "first_name": "Top",
            "last_name": "Speaker",
            "group": party,
            "coalition": "opposizione",
            "authority_score": 0.8,
            "relevant_speeches_count": 3,
            "photo": None,
            "camera_profile_url": None,
            "profession": None,
            "education": None,
            "committee": None,
            "institutional_role": None,
            "score_breakdown": {
                "speeches": 0.8, "acts": 0.0, "committee": 0.0,
                "profession": 0.0, "education": 0.0, "role": 0.0,
            },
        }

    def _make_citation(self, evidence_id: str, party: str) -> dict:
        return {"evidence_id": evidence_id, "party": party}

    def _make_evidence_dict(
        self,
        evidence_id: str,
        speaker_id: str,
        party: str,
        speaker_name: str = "Cited Speaker",
    ) -> dict:
        return {
            "evidence_id": evidence_id,
            "speaker_id": speaker_id,
            "party": party,
            "speaker_name": speaker_name,
        }

    def test_patch_replaces_mismatched_expert(self):
        from app.services.experts import patch_experts_for_cited_speakers

        experts = [self._make_expert("top_sp1", "Partito A")]
        citations = [self._make_citation("ev1", "Partito A")]
        evidence_dicts = [self._make_evidence_dict("ev1", "cited_sp1", "Partito A", "Cited Speaker")]
        authority_scores = {"cited_sp1": 0.6, "top_sp1": 0.9}
        authority_details = {
            "cited_sp1": {"components": {}, "institutional_role": None},
            "top_sp1": {"components": {}, "institutional_role": None},
        }
        neo4j_mock = _make_neo4j_mock()

        with patch(
            "app.services.experts._fetch_speaker_details",
            side_effect=_canned_speaker_details,
        ):
            updated = run(patch_experts_for_cited_speakers(
                experts, citations, evidence_dicts,
                authority_scores, authority_details, neo4j_mock,
            ))

        assert updated is not None, "Should return updated list when mismatch found"
        assert updated[0]["id"] == "cited_sp1", (
            f"Expert should be updated to cited speaker, got {updated[0]['id']}"
        )

    def test_patch_returns_none_when_no_mismatch(self):
        from app.services.experts import patch_experts_for_cited_speakers

        experts = [self._make_expert("sp1", "Partito A")]
        # Citation matches the existing expert
        citations = [self._make_citation("ev1", "Partito A")]
        evidence_dicts = [self._make_evidence_dict("ev1", "sp1", "Partito A")]
        authority_scores = {"sp1": 0.9}
        authority_details = {"sp1": {"components": {}, "institutional_role": None}}
        neo4j_mock = _make_neo4j_mock()

        with patch("app.services.experts._fetch_speaker_details", side_effect=_canned_speaker_details):
            updated = run(patch_experts_for_cited_speakers(
                experts, citations, evidence_dicts,
                authority_scores, authority_details, neo4j_mock,
            ))

        assert updated is None, "Should return None when all experts already match citations"
