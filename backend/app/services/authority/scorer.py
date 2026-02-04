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
        # Try Deputato first
        cypher = """
        MATCH (d:Deputato {id: $speaker_id})
        OPTIONAL MATCH (d)-[mg:MEMBRO_GRUPPO]->(g:GruppoParlamentare)
        WITH d, collect({
            gruppo: g.nome,
            dataInizio: mg.dataInizio,
            dataFine: mg.dataFine
        }) AS group_memberships

        OPTIONAL MATCH (d)-[mc:MEMBRO_COMMISSIONE]->(c:Commissione)
        WITH d, group_memberships, collect({
            commissione_nome: c.nome,
            dataInizio: mc.dataInizio,
            dataFine: mc.dataFine
        }) AS committee_memberships

        OPTIONAL MATCH (d)-[:PRIMO_FIRMATARIO|ALTRO_FIRMATARIO]->(a:AttoParlamentare)
        WITH d, group_memberships, committee_memberships, collect({
            uri: a.uri,
            date: a.dataPresentazione
        }) AS acts

        OPTIONAL MATCH (i:Intervento)-[:PRONUNCIATO_DA]->(d)
        OPTIONAL MATCH (i)<-[:CONTIENE_INTERVENTO]-(:Fase)<-[:HA_FASE]-(:Dibattito)<-[:HA_DIBATTITO]-(s:Seduta)
        WITH d, group_memberships, committee_memberships, acts, collect({
            intervento_id: i.id,
            date: s.data
        }) AS interventions

        RETURN d.id AS speaker_id,
               d.nome AS nome,
               d.cognome AS cognome,
               d.embedding_professione AS embedding_professione,
               d.embedding_istruzione AS embedding_istruzione,
               group_memberships,
               committee_memberships,
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
                    start = parse_neo4j_date(membership.get("dataInizio"))
                    end = parse_neo4j_date(membership.get("dataFine"))

                    if start and start <= reference_date:
                        if not end or end >= reference_date:
                            current_group = membership.get("gruppo", "MISTO")
                            break

                data["current_group"] = current_group
                return data

        # Try MembroGoverno if not found as Deputato
        cypher_gov = """
        MATCH (m:MembroGoverno {id: $speaker_id})
        OPTIONAL MATCH (i:Intervento)-[:PRONUNCIATO_DA]->(m)
        OPTIONAL MATCH (i)<-[:CONTIENE_INTERVENTO]-(:Fase)<-[:HA_FASE]-(:Dibattito)<-[:HA_DIBATTITO]-(s:Seduta)
        WITH m, collect({
            intervento_id: i.id,
            date: s.data
        }) AS interventions

        RETURN m.id AS speaker_id,
               m.nome AS nome,
               m.cognome AS cognome,
               [] AS group_memberships,
               [] AS committee_memberships,
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
