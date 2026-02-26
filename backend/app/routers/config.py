"""
Configuration endpoint for exposing system settings.

Returns effective configuration WITHOUT secrets.
"""
import logging
from typing import Dict, Any, List, Optional

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
    graph_chunk_similarity_threshold: float
    graph_max_acts_per_query: int
    merger_weights: Dict[str, float]


class AuthorityConfig(BaseModel):
    """Authority scoring configuration."""
    weights: Dict[str, float]
    time_decay_acts_half_life: int
    time_decay_speeches_half_life: int
    acts_relevance_threshold: float
    interventions_relevance_threshold: float
    normalization: str
    max_component_contribution: float


class CompassConfig(BaseModel):
    """Ideological compass configuration."""
    purpose: str
    anchor_groups: Dict[str, List[str]]
    ambiguous_groups: Dict[str, Dict[str, Any]]
    unclassified_groups: List[str]


class GenerationParameters(BaseModel):
    """LLM generation parameters."""
    max_tokens: int
    temperature: float
    top_p: float


class PositionBriefConfig(BaseModel):
    """Position brief configuration."""
    enabled: bool
    max_chunks: int
    chars_per_chunk: int
    context_chars: int


class GenerationConfig(BaseModel):
    """Generation pipeline configuration."""
    models: Dict[str, str]
    parameters: GenerationParameters
    position_brief: PositionBriefConfig
    require_all_parties: bool
    enable_synthesis: bool
    no_evidence_message: str


class QueryRewritingConfig(BaseModel):
    """Query rewriting configuration."""
    enabled: bool
    model: str
    max_query_words: int


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
    query_rewriting: QueryRewritingConfig
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
        graph_chunk_similarity_threshold=graph.get("chunk_similarity_threshold", 0.3),
        graph_max_acts_per_query=graph.get("max_acts_per_query", 100),
        merger_weights={
            "relevance": merger.get("relevance_weight", 0.15),
            "diversity": merger.get("diversity_weight", 0.15),
            "coverage": merger.get("coverage_weight", 0.25),
            "authority": merger.get("authority_weight", 0.25),
            "salience": merger.get("salience_weight", 0.20),
        }
    )

    # Authority config
    authority_data = config_data.get("authority", {})
    time_decay = authority_data.get("time_decay", {})

    authority_config = AuthorityConfig(
        weights=authority_data.get("weights", {}),
        time_decay_acts_half_life=time_decay.get("acts_half_life_days", 365),
        time_decay_speeches_half_life=time_decay.get("speeches_half_life_days", 180),
        acts_relevance_threshold=authority_data.get("acts_relevance_threshold", 0.25),
        interventions_relevance_threshold=authority_data.get("interventions_relevance_threshold", 0.25),
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
    gen_params = generation_data.get("parameters", {})
    gen_pos_brief = generation_data.get("position_brief", {})

    generation_config = GenerationConfig(
        models=generation_data.get("models", {}),
        parameters=GenerationParameters(
            max_tokens=gen_params.get("max_tokens", 4000),
            temperature=gen_params.get("temperature", 0.3),
            top_p=gen_params.get("top_p", 1.0),
        ),
        position_brief=PositionBriefConfig(
            enabled=gen_pos_brief.get("enabled", True),
            max_chunks=gen_pos_brief.get("max_chunks", 5),
            chars_per_chunk=gen_pos_brief.get("chars_per_chunk", 200),
            context_chars=gen_pos_brief.get("context_chars", 500),
        ),
        require_all_parties=generation_data.get("require_all_parties", True),
        enable_synthesis=generation_data.get("enable_synthesis", True),
        no_evidence_message=generation_data.get(
            "no_evidence_message",
            "Nel corpus analizzato non risultano interventi rilevanti su questo tema."
        ),
    )

    # Query rewriting config
    qr_data = config_data.get("query_rewriting", {})
    query_rewriting_config = QueryRewritingConfig(
        enabled=qr_data.get("enabled", True),
        model=qr_data.get("model", "gpt-4o-mini"),
        max_query_words=qr_data.get("max_query_words", 5),
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
        query_rewriting=query_rewriting_config,
        all_parties=all_parties,
    )


class ConfigUpdateRequest(BaseModel):
    """Partial config update. Only provided fields are merged."""
    retrieval: Optional[Dict[str, Any]] = None
    authority: Optional[Dict[str, Any]] = None
    generation: Optional[Dict[str, Any]] = None
    query_rewriting: Optional[Dict[str, Any]] = None

    class Config:
        extra = "forbid"


def _deep_merge(base: Dict, updates: Dict) -> Dict:
    """Recursively merge updates into base dict."""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_retrieval_update(current: Dict, update: Dict) -> Dict:
    """Map flat API field names back to nested YAML structure."""
    retrieval = current.get("retrieval", {})
    dense = retrieval.get("dense_channel", {})
    graph = retrieval.get("graph_channel", {})
    merger = retrieval.get("merger", {})

    if "dense_top_k" in update:
        dense["top_k"] = update["dense_top_k"]
    if "dense_similarity_threshold" in update:
        dense["similarity_threshold"] = update["dense_similarity_threshold"]
    if "graph_lexical_min_match" in update:
        graph["lexical_keywords_min_match"] = update["graph_lexical_min_match"]
    if "graph_semantic_threshold" in update:
        graph["semantic_similarity_threshold"] = update["graph_semantic_threshold"]
    if "graph_chunk_similarity_threshold" in update:
        graph["chunk_similarity_threshold"] = update["graph_chunk_similarity_threshold"]
    if "graph_max_acts_per_query" in update:
        graph["max_acts_per_query"] = update["graph_max_acts_per_query"]
    if "merger_weights" in update:
        mw = update["merger_weights"]
        if "relevance" in mw:
            merger["relevance_weight"] = mw["relevance"]
        if "diversity" in mw:
            merger["diversity_weight"] = mw["diversity"]
        if "coverage" in mw:
            merger["coverage_weight"] = mw["coverage"]
        if "authority" in mw:
            merger["authority_weight"] = mw["authority"]
        if "salience" in mw:
            merger["salience_weight"] = mw["salience"]

    retrieval["dense_channel"] = dense
    retrieval["graph_channel"] = graph
    retrieval["merger"] = merger
    current["retrieval"] = retrieval
    return current


def _apply_authority_update(current: Dict, update: Dict) -> Dict:
    """Map flat API field names back to nested YAML structure."""
    authority = current.get("authority", {})

    if "weights" in update:
        authority["weights"] = update["weights"]
    if "time_decay_acts_half_life" in update:
        authority.setdefault("time_decay", {})["acts_half_life_days"] = update["time_decay_acts_half_life"]
    if "time_decay_speeches_half_life" in update:
        authority.setdefault("time_decay", {})["speeches_half_life_days"] = update["time_decay_speeches_half_life"]
    if "acts_relevance_threshold" in update:
        authority["acts_relevance_threshold"] = update["acts_relevance_threshold"]
    if "interventions_relevance_threshold" in update:
        authority["interventions_relevance_threshold"] = update["interventions_relevance_threshold"]
    if "normalization" in update:
        authority["normalization"] = update["normalization"]
    if "max_component_contribution" in update:
        authority["max_component_contribution"] = update["max_component_contribution"]

    current["authority"] = authority
    return current


def _apply_generation_update(current: Dict, update: Dict) -> Dict:
    """Map flat API field names back to nested YAML structure."""
    generation = current.get("generation", {})

    if "models" in update:
        generation["models"] = _deep_merge(generation.get("models", {}), update["models"])
    if "parameters" in update:
        generation["parameters"] = _deep_merge(generation.get("parameters", {}), update["parameters"])
    if "position_brief" in update:
        generation["position_brief"] = _deep_merge(generation.get("position_brief", {}), update["position_brief"])
    if "require_all_parties" in update:
        generation["require_all_parties"] = update["require_all_parties"]
    if "enable_synthesis" in update:
        generation["enable_synthesis"] = update["enable_synthesis"]
    if "no_evidence_message" in update:
        generation["no_evidence_message"] = update["no_evidence_message"]

    current["generation"] = generation
    return current


def _apply_query_rewriting_update(current: Dict, update: Dict) -> Dict:
    """Map flat API field names back to nested YAML structure."""
    qr = current.get("query_rewriting", {})

    if "enabled" in update:
        qr["enabled"] = update["enabled"]
    if "model" in update:
        qr["model"] = update["model"]
    if "max_query_words" in update:
        qr["max_query_words"] = update["max_query_words"]

    current["query_rewriting"] = qr
    return current


@router.put("", response_model=ConfigResponse)
async def update_configuration(update: ConfigUpdateRequest):
    """
    Update system configuration (partial merge).

    Only retrieval, authority, and generation sections can be updated.
    Changes are persisted to config/default.yaml.
    """
    config = get_config()
    current = config.load_config()

    if update.retrieval is not None:
        current = _apply_retrieval_update(current, update.retrieval)
    if update.authority is not None:
        current = _apply_authority_update(current, update.authority)
    if update.generation is not None:
        current = _apply_generation_update(current, update.generation)
    if update.query_rewriting is not None:
        current = _apply_query_rewriting_update(current, update.query_rewriting)

    config.save_config(current)
    logger.info("Configuration updated via API")

    return await get_configuration()


@router.post("/reload", response_model=ConfigResponse)
async def reload_configuration():
    """
    Reload configuration from config/default.yaml, discarding any in-memory overrides.

    Use this when the YAML file has been changed and you want the backend
    to pick up the new values without restarting the process.
    """
    config = get_config()
    config._config = None  # Clear in-memory cache
    logger.info("Configuration cache cleared — reloading from disk")
    return await get_configuration()


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
