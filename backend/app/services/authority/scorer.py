"""
Authority scorer for query-dependent speaker authority.

Orchestrates all authority components and applies:
- Query-dependent weighting
- Temporal coalition logic
- Percentile-based normalization
"""
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Union

import numpy as np

from ..neo4j_client import Neo4jClient
from .coalition_logic import CoalitionLogic
from .components import (
    ProfessionComponent,
    EducationComponent,
    CommitteeComponent,
    ActsComponent,
    InterventionsComponent,
    RoleComponent,
)
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


class AuthorityScorer:
    """
    Computes query-dependent authority scores for speakers.

    Authority(speaker, query, date) = Σ wi × component_i

    Components:
    - Profession relevance (semantic similarity)
    - Education relevance (semantic similarity)
    - Committee membership (temporal + topic relevance)
    - Acts on topic (count with time decay)
    - Interventions on topic (count with time decay)
    - Institutional role (role weights)
    """

    def __init__(self, neo4j_client: Neo4jClient):
        self.client = neo4j_client
        self.config = get_config()
        self.coalition_logic = CoalitionLogic()

        # Initialize components
        self.components = {
            "profession": ProfessionComponent(),
            "education": EducationComponent(),
            "committee": CommitteeComponent(),
            "acts": ActsComponent(),
            "interventions": InterventionsComponent(),
            "role": RoleComponent(),
        }

        # Load weights from config
        authority_config = self.config.load_config().get("authority", {})
        weights = authority_config.get("weights", {})

        self.weights = {
            "profession": weights.get("profession", 0.10),
            "education": weights.get("education", 0.10),
            "committee": weights.get("committee", 0.20),
            "acts": weights.get("acts", 0.25),
            "interventions": weights.get("interventions", 0.30),
            "role": weights.get("role", 0.05),
        }

    def compute_authority(
        self,
        speaker_id: str,
        query_embedding: List[float],
        reference_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Compute authority score for a speaker.

        Args:
            speaker_id: ID of the speaker (deputato or governo membro)
            query_embedding: Embedding of the query
            reference_date: Reference date (default: today)

        Returns:
            Dictionary with total score and component breakdown
        """
        if reference_date is None:
            reference_date = date.today()

        # Fetch speaker data from database
        speaker_data = self._fetch_speaker_data(speaker_id, reference_date)

        if not speaker_data:
            logger.warning(f"No data found for speaker {speaker_id}")
            return {
                "speaker_id": speaker_id,
                "total_score": 0.5,
                "components": {},
                "coalition": "unknown",
            }

        # Apply coalition filtering to activities
        current_group = speaker_data.get("current_group", "MISTO")
        memberships = speaker_data.get("group_memberships", [])

        # Filter acts and interventions by coalition
        speaker_data["acts"] = self.coalition_logic.filter_activities_by_coalition(
            speaker_data.get("acts", []),
            memberships,
            reference_date,
            current_group
        )

        speaker_data["interventions"] = self.coalition_logic.filter_activities_by_coalition(
            speaker_data.get("interventions", []),
            memberships,
            reference_date,
            current_group
        )

        # Compute each component
        component_scores = {}
        for name, component in self.components.items():
            score = component.compute(speaker_data, query_embedding, reference_date)
            component_scores[name] = score

        # Weighted sum
        total_score = sum(
            self.weights[name] * score
            for name, score in component_scores.items()
        )

        # Ensure total is in [0, 1]
        total_score = max(0.0, min(1.0, total_score))

        return {
            "speaker_id": speaker_id,
            "total_score": total_score,
            "components": component_scores,
            "coalition": self.coalition_logic.get_coalition(current_group),
            "current_group": current_group,
        }

    def compute_batch_authority(
        self,
        speaker_ids: List[str],
        query_embedding: List[float],
        reference_date: Optional[date] = None
    ) -> Dict[str, float]:
        """
        Compute authority scores for multiple speakers.

        Returns a dictionary mapping speaker_id to total_score.
        """
        scores = {}
        for speaker_id in speaker_ids:
            result = self.compute_authority(speaker_id, query_embedding, reference_date)
            scores[speaker_id] = result["total_score"]
        return scores

    def normalize_scores_percentile(
        self,
        scores: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Normalize scores using percentile-based normalization.

        This prevents hyper-active deputies from dominating.
        """
        if not scores:
            return {}

        values = list(scores.values())

        if len(values) == 1:
            return {k: 0.5 for k in scores}

        # Compute percentile ranks
        sorted_values = sorted(values)
        normalized = {}

        for speaker_id, score in scores.items():
            # Find percentile rank
            rank = sorted_values.index(score)
            percentile = rank / (len(sorted_values) - 1)
            normalized[speaker_id] = percentile

        return normalized

    def _fetch_speaker_data(
        self,
        speaker_id: str,
        reference_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch all necessary data for a speaker from Neo4j.
        """
        # Try Deputy first
        cypher = """
        MATCH (d:Deputy {id: $speaker_id})
        OPTIONAL MATCH (d)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WITH d, collect({
            group: g.name,
            start_date: mg.start_date,
            end_date: mg.end_date
        }) AS group_memberships

        OPTIONAL MATCH (d)-[mc:MEMBER_OF_COMMITTEE]->(c:Committee)
        WITH d, group_memberships, collect({
            committee_name: c.name,
            committee_embedding: c.embedding,
            start_date: mc.start_date,
            end_date: mc.end_date
        }) AS committee_memberships

        // Fetch institutional roles (President, Vice President, Secretary of committees)
        OPTIONAL MATCH (d)-[rp:IS_PRESIDENT]->(cp:Committee)
        WITH d, group_memberships, committee_memberships, collect({
            role_type: 'president',
            committee_name: cp.name,
            committee_embedding: cp.embedding,
            start_date: rp.start_date,
            end_date: rp.end_date
        }) AS president_roles

        OPTIONAL MATCH (d)-[rv:IS_VICE_PRESIDENT]->(cv:Committee)
        WITH d, group_memberships, committee_memberships, president_roles, collect({
            role_type: 'vice_president',
            committee_name: cv.name,
            committee_embedding: cv.embedding,
            start_date: rv.start_date,
            end_date: rv.end_date
        }) AS vice_president_roles

        OPTIONAL MATCH (d)-[rs:IS_SECRETARY]->(cs:Committee)
        WITH d, group_memberships, committee_memberships, president_roles, vice_president_roles, collect({
            role_type: 'secretary',
            committee_name: cs.name,
            committee_embedding: cs.embedding,
            start_date: rs.start_date,
            end_date: rs.end_date
        }) AS secretary_roles

        WITH d, group_memberships, committee_memberships,
             president_roles + vice_president_roles + secretary_roles AS institutional_roles

        OPTIONAL MATCH (d)-[:PRIMARY_SIGNATORY|CO_SIGNATORY]->(a:ParliamentaryAct)
        WITH d, group_memberships, committee_memberships, institutional_roles, collect({
            uri: a.uri,
            date: a.presentation_date
        }) AS acts

        OPTIONAL MATCH (i:Speech)-[:SPOKEN_BY]->(d)
        OPTIONAL MATCH (i)<-[:CONTAINS_SPEECH]-(:Phase)<-[:HAS_PHASE]-(:Debate)<-[:HAS_DEBATE]-(s:Session)
        WITH d, group_memberships, committee_memberships, institutional_roles, acts, collect({
            speech_id: i.id,
            date: s.date
        }) AS interventions

        RETURN d.id AS speaker_id,
               d.first_name AS first_name,
               d.last_name AS last_name,
               d.profession_embedding AS profession_embedding,
               d.education_embedding AS education_embedding,
               group_memberships,
               committee_memberships,
               institutional_roles,
               acts,
               interventions
        """

        with self.client.session() as session:
            result = session.run(cypher, speaker_id=speaker_id)
            record = result.single()

            if record:
                data = dict(record)

                # Determine current group
                current_group = "MISTO"
                for membership in data.get("group_memberships", []):
                    start = parse_neo4j_date(membership.get("start_date"))
                    end = parse_neo4j_date(membership.get("end_date"))

                    if start and start <= reference_date:
                        if not end or end >= reference_date:
                            current_group = membership.get("group", "MISTO")
                            break

                data["current_group"] = current_group
                return data

        # Try GovernmentMember if not found as Deputy
        cypher_gov = """
        MATCH (m:GovernmentMember {id: $speaker_id})
        OPTIONAL MATCH (i:Speech)-[:SPOKEN_BY]->(m)
        OPTIONAL MATCH (i)<-[:CONTAINS_SPEECH]-(:Phase)<-[:HAS_PHASE]-(:Debate)<-[:HAS_DEBATE]-(s:Session)
        WITH m, collect({
            speech_id: i.id,
            date: s.date
        }) AS interventions

        RETURN m.id AS speaker_id,
               m.first_name AS first_name,
               m.last_name AS last_name,
               m.institutional_role AS government_position,
               [] AS group_memberships,
               [] AS committee_memberships,
               [] AS institutional_roles,
               [] AS acts,
               interventions
        """

        with self.client.session() as session:
            result = session.run(cypher_gov, speaker_id=speaker_id)
            record = result.single()

            if record:
                data = dict(record)
                # Government members are always "maggioranza" by definition
                data["current_group"] = "GOVERNO"
                return data

        return None
