"""
Configuration endpoint for exposing system settings.

Returns effective configuration WITHOUT secrets.
"""
import logging
import re
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
        model=qr_data.get("model", "gpt-4.1-mini"),
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


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "en"


@router.post("/translate")
async def translate_text(req: TranslateRequest):
    """On-demand translation of a text string."""
    from ..services.translation import _translate_text
    from ..key_pool import make_async_client

    if not req.text or req.target_lang == "it":
        return {"translated": req.text}

    client = make_async_client()
    try:
        translated = await _translate_text(client, req.text, max_tokens=4000)
        return {"translated": translated}
    except Exception as e:
        logger.warning("On-demand translation failed: %s", e)
        return {"translated": req.text}


_recent_topics_cache: dict = {}  # lang -> {"at": ts, "data": {...}}
_RECENT_TOPICS_TTL_S = 3600


async def _label_acts(titles: list[str], lang: str) -> list[dict]:
    """Chip label + expanded query phrase (in the UI language) per act title.

    Bills mostly carry no EuroVoc subject in the source data, so both are
    distilled from the official title with the same nano model used for
    translations. The label feeds the chip, the phrase feeds the query sent
    on click — "firme digitali" alone would lose the electoral context.
    Raises on any LLM problem — the caller falls back to EuroVoc subjects.
    """
    import json as _json
    from ..key_pool import make_async_client
    lang_names = {"it": "italiano", "en": "English", "fr": "français",
                  "de": "Deutsch", "es": "español", "pt": "português"}
    lang_name = lang_names.get(lang, lang)
    llm = make_async_client()
    resp = await llm.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": (
                "You label Italian parliamentary act titles. For each title "
                "return a JSON object with two fields, BOTH strictly written "
                f"in {lang_name} (translate if needed):\n"
                '- "label": a theme label, 2-5 words, lowercase, clear on its '
                "own, and distinct from the labels of the other acts (when "
                "two acts share a theme, name the specific aspect of each);\n"
                '- "query": a noun phrase of 8-18 words describing precisely '
                "what the measure is about. No lead-in such as \"the position "
                "of parliamentary groups\": the phrase will be inserted into "
                "that sentence by the caller.\n"
                "Some titles carry no subject (just an act number and the "
                "presenter): for those, derive label and query from the "
                "EuroVoc subjects appended after \"soggetti:\". Never label "
                "the act form (mozione, risoluzione): always the topic.\n"
                "Reply ONLY with a JSON array of objects, same order as the titles."
            )},
            {"role": "user", "content": _json.dumps(titles, ensure_ascii=False)},
        ],
        temperature=0,
        max_tokens=700,
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    items = _json.loads(raw)
    if not isinstance(items, list):
        raise ValueError("not a list")
    return [
        {"label": str(x.get("label", "")).strip(),
         "query": str(x.get("query", "")).strip()}
        for x in items
    ]


@router.get("/recent-topics")
async def get_recent_topics(lang: str = "it"):
    """Topics of the provvedimenti most recently discussed on the floor.

    Chips and tooltip share one source: Session → Debate → DISCUSSES → act.
    DISCUSSES points at placeholder act nodes minted from transcript
    references, so they are resolved to the real SPARQL acts by number (base
    number for lettered variants, '-'→'/' for mozioni). Bills first, mozioni
    and risoluzioni as filler — never the ODG/interrogazioni that dominate by
    volume. Window cascade 7→30→90 days (recess-proof). Topic labels are
    distilled from the act titles in the UI language (bills carry no EuroVoc
    in the source data), with EuroVoc subjects as fallback. Titles in the
    tooltip stay in Italian — they are official act names, like quotations.
    Cached per language for an hour.
    """
    import time as _time
    cached = _recent_topics_cache.get(lang)
    if cached is not None and _time.time() - cached["at"] < _RECENT_TOPICS_TTL_S:
        return cached["data"]
    from ..services.deps import get_services
    neo4j = get_services()["neo4j"]
    topics: list[str] = []
    acts: list[dict] = []
    subjects_by_act: list[list[str]] = []
    since = None
    try:
        for days in (7, 30, 90):
            act_rows = neo4j.query(
                "MATCH (se:Session)-[:HAS_DEBATE]->(:Debate)-[:DISCUSSES]->(ph) "
                "WHERE se.date >= date() - duration({days: $days}) "
                "WITH DISTINCT ph, max(se.date) AS sd "
                "WITH ph, sd, split(ph.number, '-')[0] AS base "
                "MATCH (a:ParliamentaryAct) "
                "WHERE a.uri STARTS WITH 'http' AND a.title IS NOT NULL AND a.title <> '' "
                "  AND (a.number = ph.number OR a.number = base "
                "       OR a.number = replace(ph.number, '-', '/')) "
                "  AND (CASE WHEN ph.type = 'pdl' THEN a.type IN ['Progetto di Legge', 'pdl'] "
                "       ELSE toLower(a.type) CONTAINS toLower(ph.type) END) "
                "WITH DISTINCT a, sd, CASE "
                "  WHEN a.type IN ['Progetto di Legge', 'pdl'] THEN 0 ELSE 1 END AS prio "
                "OPTIONAL MATCH (a)-[:HAS_SUBJECT]->(c:EurovocConcept) "
                "WITH a, sd, prio, collect(c.label_it) AS subjects "
                "RETURN a.title AS title, toString(sd) AS date, a.type AS type, subjects "
                "ORDER BY prio, date DESC LIMIT 6",
                {"days": days},
            )
            if len(act_rows) >= 2:
                acts = [
                    {
                        "title": re.sub(r"<[^>]+>", "", r["title"]),
                        "date": r["date"],
                        "type": r["type"],
                    }
                    for r in act_rows
                ]
                subjects_by_act = [r["subjects"] or [] for r in act_rows]
                since_row = neo4j.query(
                    "RETURN toString(date() - duration({days: $days})) AS since",
                    {"days": days},
                )
                since = since_row[0]["since"] if since_row else None
                break
    except Exception as e:
        logger.warning("Failed to get recent topics: %s", e)
    if acts:
        try:
            # Mozioni/risoluzioni have number-only titles: append their
            # EuroVoc subjects so the label names the topic, not the form
            llm_inputs = [
                a["title"] + (f" — soggetti: {'; '.join(subs[:6])}" if subs else "")
                for a, subs in zip(acts, subjects_by_act)
            ]
            items = await _label_acts(llm_inputs, lang)
            # Per-act label in the tooltip: the official title alone is
            # unreadable legalese, the label says what the measure is about
            for act, item in zip(acts, items):
                act["topic"] = item["label"] or None
            seen: set = set()
            for item in items:
                if item["label"] and item["label"].lower() not in seen and len(topics) < 6:
                    seen.add(item["label"].lower())
                    topics.append({
                        "label": item["label"],
                        "query": item["query"] or item["label"],
                    })
        except Exception as e:
            logger.warning("Recent-topics labelling failed, EuroVoc fallback: %s", e)
            # Max 2 subjects per act so one multi-subject act cannot
            # monopolise the list (Italian only — no LLM available here)
            seen = set()
            for act, subjects in zip(acts, subjects_by_act):
                act["topic"] = subjects[0] if subjects else None
                for subject in subjects[:2]:
                    if subject and subject not in seen and len(topics) < 6:
                        seen.add(subject)
                        topics.append({"label": subject, "query": subject})
    data = {"topics": topics, "since": since, "acts": acts[:4]}
    _recent_topics_cache[lang] = {"at": _time.time(), "data": data}
    return data


@router.get("/last-update")
async def get_last_update():
    """Date of the last `make update-data` run (SchemaMeta.updated_at).

    Falls back to the most recent Session date for DBs stamped before
    updated_at existed.
    """
    from ..services.deps import get_services
    client = get_services()["neo4j"]
    try:
        result = client.query(
            "OPTIONAL MATCH (m:SchemaMeta {id: 'singleton'}) "
            "WITH date(m.updated_at) AS stamped "
            "OPTIONAL MATCH (s:Session) "
            "WITH stamped, max(s.date) AS newest "
            "RETURN coalesce(stamped, newest) AS last_date"
        )
        if result and result[0].get("last_date"):
            d = result[0]["last_date"]
            if hasattr(d, "to_native"):
                d = d.to_native()
            return {"last_update": str(d)}
    except Exception as e:
        logger.warning("Failed to get last update date: %s", e)
    return {"last_update": None}
