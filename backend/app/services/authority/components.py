"""
Authority score components.

Each component contributes to the overall authority score.
All scores are normalized to [0, 1] using percentile-based normalization.
"""
import json
import math
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Union

import numpy as np

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


def parse_embedding(embedding_value: Any) -> Optional[List[float]]:
    """
    Parse an embedding value from Neo4j to a list of floats.

    Neo4j may return embeddings as:
    - List of floats (pass through)
    - JSON string representation of a list
    - String representation with brackets
    - None
    """
    if embedding_value is None:
        return None

    # Already a list
    if isinstance(embedding_value, list):
        try:
            return [float(x) for x in embedding_value]
        except (ValueError, TypeError):
            logger.warning(f"Could not convert list to floats: {type(embedding_value)}")
            return None

    # NumPy array
    if isinstance(embedding_value, np.ndarray):
        return embedding_value.tolist()

    # String representation
    if isinstance(embedding_value, str):
        if not embedding_value.strip():
            return None

        try:
            # Try JSON parsing first
            parsed = json.loads(embedding_value)
            if isinstance(parsed, list):
                return [float(x) for x in parsed]
        except json.JSONDecodeError:
            pass

        # Try eval as last resort (for Python list repr)
        try:
            # Clean up the string
            cleaned = embedding_value.strip()
            if cleaned.startswith('[') and cleaned.endswith(']'):
                import ast
                parsed = ast.literal_eval(cleaned)
                if isinstance(parsed, list):
                    return [float(x) for x in parsed]
        except (ValueError, SyntaxError):
            pass

        logger.warning(f"Could not parse embedding string (length {len(embedding_value)})")
        return None

    logger.warning(f"Unknown embedding type: {type(embedding_value)}")
    return None


def cosine_similarity(vec1: Union[List[float], Any], vec2: Union[List[float], Any]) -> float:
    """Compute cosine similarity between two vectors."""
    # Parse embeddings if needed
    v1 = parse_embedding(vec1) if not isinstance(vec1, list) or (vec1 and not isinstance(vec1[0], (int, float))) else vec1
    v2 = parse_embedding(vec2) if not isinstance(vec2, list) or (vec2 and not isinstance(vec2[0], (int, float))) else vec2

    if not v1 or not v2:
        return 0.0

    a = np.array(v1, dtype=np.float64)
    b = np.array(v2, dtype=np.float64)

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


def time_decay(days_ago: int, half_life_days: int) -> float:
    """
    Compute exponential time decay.

    Args:
        days_ago: Number of days since the activity
        half_life_days: Half-life in days

    Returns:
        Decay factor in [0, 1]
    """
    if days_ago < 0:
        return 1.0

    lambda_decay = math.log(2) / half_life_days
    return math.exp(-lambda_decay * days_ago)


class AuthorityComponent(ABC):
    """Base class for authority score components."""

    def __init__(self):
        self.config = get_config()
        self.max_contribution = self.config.load_config().get(
            "authority", {}
        ).get("max_component_contribution", 0.8)

    @abstractmethod
    def compute(
        self,
        speaker_data: Dict[str, Any],
        query_embedding: List[float],
        reference_date: date
    ) -> float:
        """
        Compute component score.

        Args:
            speaker_data: Speaker data from database
            query_embedding: Query embedding vector
            reference_date: Reference date for temporal calculations

        Returns:
            Score in [0, 1]
        """
        pass

    def cap_score(self, score: float) -> float:
        """Cap score to max contribution."""
        return min(score, self.max_contribution)


class ProfessionComponent(AuthorityComponent):
    """
    Profession relevance component.

    Computes semantic similarity between query and speaker's profession.
    """

    def compute(
        self,
        speaker_data: Dict[str, Any],
        query_embedding: List[float],
        reference_date: date
    ) -> float:
        profession_embedding = parse_embedding(speaker_data.get("profession_embedding"))

        if not profession_embedding:
            return 0.5  # Neutral default for missing data

        similarity = cosine_similarity(query_embedding, profession_embedding)
        # Map from [-1, 1] to [0, 1]
        score = (similarity + 1) / 2

        return self.cap_score(score)


class EducationComponent(AuthorityComponent):
    """
    Education relevance component.

    Computes semantic similarity between query and speaker's education.
    """

    def compute(
        self,
        speaker_data: Dict[str, Any],
        query_embedding: List[float],
        reference_date: date
    ) -> float:
        education_embedding = parse_embedding(speaker_data.get("education_embedding"))

        if not education_embedding:
            return 0.5  # Neutral default for missing data

        similarity = cosine_similarity(query_embedding, education_embedding)
        # Map from [-1, 1] to [0, 1]
        score = (similarity + 1) / 2

        return self.cap_score(score)


class CommitteeComponent(AuthorityComponent):
    """
    Committee membership component.

    Computes score based on:
    - Temporal membership validity
    - Topic relevance of committee to query
    """

    def __init__(self):
        super().__init__()
        self._topic_matcher = None

    def compute(
        self,
        speaker_data: Dict[str, Any],
        query_embedding: List[float],
        reference_date: date
    ) -> float:
        memberships = speaker_data.get("committee_memberships", [])

        if not memberships:
            return 0.0

        total_relevance = 0.0
        active_committees = 0

        for membership in memberships:
            # Check temporal validity - parse dates from Neo4j
            membership_start = parse_neo4j_date(membership.get("start_date"))
            membership_end = parse_neo4j_date(membership.get("end_date"))

            if membership_start and membership_start > reference_date:
                continue

            if membership_end and membership_end < reference_date:
                continue

            # Committee is active at reference_date
            active_committees += 1

            # Compute topic relevance
            committee_name = membership.get("committee_name", "")
            topic_relevance = self._compute_topic_relevance(
                committee_name, query_embedding
            )
            total_relevance += topic_relevance

        if active_committees == 0:
            return 0.0

        # Average relevance across active committees
        score = total_relevance / active_committees

        return self.cap_score(score)

    def _compute_topic_relevance(
        self,
        commissione_nome: str,
        query_embedding: List[float]
    ) -> float:
        """Compute topic relevance between commission and query."""
        # Load commission topics from config
        import yaml
        import os

        config_path = os.path.join(
            os.path.dirname(__file__),
            "../../../config/commissioni_topics.yaml"
        )

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                topics_config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Commission topics config not found: {config_path}")
            return 0.5

        commissioni = topics_config.get("commissioni", {})
        commission_data = commissioni.get(commissione_nome, {})

        if not commission_data:
            # Try partial match
            for name, data in commissioni.items():
                if commissione_nome in name or name in commissione_nome:
                    commission_data = data
                    break

        if not commission_data:
            return 0.3  # Low score for unknown commission

        keywords = commission_data.get("keywords", [])

        # Simple keyword relevance (semantic matching would need embeddings)
        # For now, return moderate relevance for any matched commission
        return 0.6 if keywords else 0.3


class ActsComponent(AuthorityComponent):
    """
    Parliamentary acts component.

    Computes score based on:
    - Count of relevant acts
    - Time decay (more recent = higher weight)
    - Coalition validity (via filtered activities)
    """

    def compute(
        self,
        speaker_data: Dict[str, Any],
        query_embedding: List[float],
        reference_date: date
    ) -> float:
        acts = speaker_data.get("acts", [])

        if not acts:
            return 0.0

        authority_config = self.config.load_config().get("authority", {})
        time_decay_config = authority_config.get("time_decay", {})
        half_life = time_decay_config.get("acts_half_life_days", 365)

        total_weight = 0.0

        for act in acts:
            act_date = parse_neo4j_date(act.get("date"))
            if not act_date:
                continue

            if act_date > reference_date:
                continue

            # Compute time decay
            days_ago = (reference_date - act_date).days
            decay = time_decay(days_ago, half_life)

            # Add weighted contribution
            total_weight += decay

        # Log scale to prevent hyper-active deputies from dominating
        if total_weight > 0:
            score = math.log(1 + total_weight) / math.log(1 + 100)  # Normalize assuming max ~100 weighted acts
            score = min(score, 1.0)
        else:
            score = 0.0

        return self.cap_score(score)


class InterventionsComponent(AuthorityComponent):
    """
    Parliamentary interventions component.

    Computes score based on:
    - Count of relevant interventions
    - Time decay (more recent = higher weight)
    - Coalition validity (via filtered activities)
    """

    def compute(
        self,
        speaker_data: Dict[str, Any],
        query_embedding: List[float],
        reference_date: date
    ) -> float:
        interventions = speaker_data.get("interventions", [])

        if not interventions:
            return 0.0

        authority_config = self.config.load_config().get("authority", {})
        time_decay_config = authority_config.get("time_decay", {})
        half_life = time_decay_config.get("speeches_half_life_days", 180)

        total_weight = 0.0

        for intervention in interventions:
            intervention_date = parse_neo4j_date(intervention.get("date"))
            if not intervention_date:
                continue

            if intervention_date > reference_date:
                continue

            # Compute time decay
            days_ago = (reference_date - intervention_date).days
            decay = time_decay(days_ago, half_life)

            # Add weighted contribution
            total_weight += decay

        # Log scale to prevent hyper-active deputies from dominating
        if total_weight > 0:
            score = math.log(1 + total_weight) / math.log(1 + 500)  # Normalize assuming max ~500 weighted interventions
            score = min(score, 1.0)
        else:
            score = 0.0

        return self.cap_score(score)


class RoleComponent(AuthorityComponent):
    """
    Institutional role component.

    Computes score based on:
    1. Base role weight (president > vice_president > secretary)
    2. Topic relevance bonus if the committee is relevant to the query

    Formula: base_weight × (1 + relevance_bonus)
    """

    # Base weights for institutional roles in committees
    ROLE_BASE_WEIGHTS = {
        "president": 0.7,
        "vice_president": 0.5,
        "secretary": 0.4,
    }

    # Government position weights (for GovernmentMember)
    GOVERNMENT_WEIGHTS = {
        "ministro": 0.9,
        "viceministro": 0.8,
        "sottosegretario": 0.7,
    }

    # Relevance bonus multiplier when committee is topically relevant
    RELEVANCE_BONUS = 0.3

    # Similarity threshold for topic relevance
    RELEVANCE_THRESHOLD = 0.5

    def compute(
        self,
        speaker_data: Dict[str, Any],
        query_embedding: List[float],
        reference_date: date
    ) -> float:
        # Check for government position first (GovernmentMember)
        gov_position = speaker_data.get("government_position", "")
        if gov_position:
            for key, weight in self.GOVERNMENT_WEIGHTS.items():
                if key in gov_position.lower():
                    return self.cap_score(weight)

        # Get institutional roles from graph
                institutional_roles = [
            r for r in speaker_data.get("institutional_roles", [])
            if r.get("committee_name")
        ]

        if not institutional_roles:
            return 0.3  # Base score for regular deputies without roles

        max_role_score = 0.3  # Minimum base

        for role in institutional_roles:
            role_type = role.get("role_type", "")
            role_start = parse_neo4j_date(role.get("start_date"))
            role_end = parse_neo4j_date(role.get("end_date"))

            # Check temporal validity
            if role_start and role_start > reference_date:
                continue
            if role_end and role_end < reference_date:
                continue

            # Get base weight for this role type
            base_weight = self.ROLE_BASE_WEIGHTS.get(role_type, 0.3)

            # Calculate topic relevance bonus
            committee_embedding = role.get("committee_embedding")
            relevance_multiplier = 1.0

            if committee_embedding and query_embedding:
                similarity = cosine_similarity(query_embedding, committee_embedding)
                if similarity >= self.RELEVANCE_THRESHOLD:
                    # Apply relevance bonus proportional to similarity
                    relevance_multiplier = 1.0 + (self.RELEVANCE_BONUS * similarity)

            # Final score for this role
            role_score = base_weight * relevance_multiplier
            max_role_score = max(max_role_score, role_score)

        return self.cap_score(max_role_score)
