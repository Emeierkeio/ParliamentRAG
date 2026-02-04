"""
Configuration endpoint for exposing system settings.

Returns effective configuration WITHOUT secrets.
"""
import logging
from typing import Dict, Any, List

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["Configuration"])


class RetrievalConfig(BaseModel):
    """Retrieval configuration."""
    dense_top_k: int
    dense_similarity_threshold: float
    graph_lexical_min_match: int
    graph_semantic_threshold: float
    merger_weights: Dict[str, float]


class AuthorityConfig(BaseModel):
    """Authority scoring configuration."""
    weights: Dict[str, float]
    time_decay_acts_half_life: int
    time_decay_speeches_half_life: int
    normalization: str
    max_component_contribution: float


class CompassConfig(BaseModel):
    """Ideological compass configuration."""
    purpose: str
    anchor_groups: Dict[str, List[str]]
    ambiguous_groups: Dict[str, Dict[str, Any]]
    unclassified_groups: List[str]


class GenerationConfig(BaseModel):
    """Generation pipeline configuration."""
    models: Dict[str, str]
    require_all_parties: bool
    no_evidence_message: str


class CoalitionsConfig(BaseModel):
    """Coalition definitions."""
    maggioranza: List[str]
    opposizione: List[str]


class CitationConfig(BaseModel):
    """Citation configuration."""
    method: str
    format: str
    verify_on_insert: bool


class ConfigResponse(BaseModel):
    """Full configuration response (no secrets)."""
    retrieval: RetrievalConfig
    authority: AuthorityConfig
    compass: CompassConfig
    generation: GenerationConfig
    coalitions: CoalitionsConfig
    citation: CitationConfig
    all_parties: List[str]


@router.get("", response_model=ConfigResponse)
async def get_configuration():
    """
    Get effective system configuration.

    Returns all configurable weights, thresholds, and settings.
    Does NOT include secrets (API keys, passwords).
    """
    config = get_config()
    config_data = config.load_config()

    # Retrieval config
    retrieval_data = config_data.get("retrieval", {})
    dense = retrieval_data.get("dense_channel", {})
    graph = retrieval_data.get("graph_channel", {})
    merger = retrieval_data.get("merger", {})

    retrieval_config = RetrievalConfig(
        dense_top_k=dense.get("top_k", 200),
        dense_similarity_threshold=dense.get("similarity_threshold", 0.3),
        graph_lexical_min_match=graph.get("lexical_keywords_min_match", 1),
        graph_semantic_threshold=graph.get("semantic_similarity_threshold", 0.4),
        merger_weights={
            "relevance": merger.get("relevance_weight", 0.2),
            "diversity": merger.get("diversity_weight", 0.2),
            "coverage": merger.get("coverage_weight", 0.3),
            "authority": merger.get("authority_weight", 0.3),
        }
    )

    # Authority config
    authority_data = config_data.get("authority", {})
    time_decay = authority_data.get("time_decay", {})

    authority_config = AuthorityConfig(
        weights=authority_data.get("weights", {}),
        time_decay_acts_half_life=time_decay.get("acts_half_life_days", 365),
        time_decay_speeches_half_life=time_decay.get("speeches_half_life_days", 180),
        normalization=authority_data.get("normalization", "percentile"),
        max_component_contribution=authority_data.get("max_component_contribution", 0.8),
    )

    # Compass config
    compass_data = config_data.get("compass", {})
    anchors = compass_data.get("anchors", {})

    compass_config = CompassConfig(
        purpose=compass_data.get("purpose", "multi-view coverage"),
        anchor_groups={
            "left": anchors.get("left", {}).get("groups", []),
            "center": anchors.get("center", {}).get("groups", []),
            "right": anchors.get("right", {}).get("groups", []),
        },
        ambiguous_groups=compass_data.get("ambiguous", {}),
        unclassified_groups=compass_data.get("unclassified", []),
    )

    # Generation config
    generation_data = config_data.get("generation", {})

    generation_config = GenerationConfig(
        models=generation_data.get("models", {}),
        require_all_parties=generation_data.get("require_all_parties", True),
        no_evidence_message=generation_data.get(
            "no_evidence_message",
            "Nel corpus analizzato non risultano interventi rilevanti su questo tema."
        ),
    )

    # Coalitions config
    coalitions_data = config_data.get("coalitions", {})

    coalitions_config = CoalitionsConfig(
        maggioranza=coalitions_data.get("maggioranza", []),
        opposizione=coalitions_data.get("opposizione", []),
    )

    # Citation config
    citation_data = config_data.get("citation", {})

    citation_config = CitationConfig(
        method=citation_data.get("method", "offset"),
        format=citation_data.get("format", "«{quote}» [{speaker}, {party}, {date}, ID:{id}]"),
        verify_on_insert=citation_data.get("verify_on_insert", True),
    )

    # All parties
    all_parties = config.get_all_parties()

    return ConfigResponse(
        retrieval=retrieval_config,
        authority=authority_config,
        compass=compass_config,
        generation=generation_config,
        coalitions=coalitions_config,
        citation=citation_config,
        all_parties=all_parties,
    )


@router.get("/parties")
async def get_parties():
    """Get list of all parliamentary parties."""
    config = get_config()
    return {"parties": config.get_all_parties()}


@router.get("/coalitions")
async def get_coalitions():
    """Get coalition definitions."""
    config = get_config()
    config_data = config.load_config()
    return config_data.get("coalitions", {})
