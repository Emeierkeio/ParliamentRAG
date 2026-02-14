"""
Main query endpoint for Multi-View RAG.

Supports both synchronous and SSE streaming responses.
"""
import json
import logging
import asyncio
import random
from datetime import date
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services.neo4j_client import Neo4jClient
from ..services.retrieval import RetrievalEngine
from ..services.authority import AuthorityScorer
from ..services.authority.coalition_logic import CoalitionLogic
from ..services.compass import IdeologyScorer
from ..services.generation import GenerationPipeline
from ..config import get_config, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Query"])


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str = Field(..., min_length=3, max_length=1000, description="User query")
    top_k: int = Field(default=100, ge=10, le=500, description="Number of evidence pieces")
    date_start: Optional[str] = Field(default=None, description="Start date filter (YYYY-MM-DD)")
    date_end: Optional[str] = Field(default=None, description="End date filter (YYYY-MM-DD)")
    stream: bool = Field(default=True, description="Enable SSE streaming")


class ExpertInfo(BaseModel):
    """Expert information for a party."""
    speaker_id: str
    speaker_name: str
    authority_score: float
    intervention_count: int


class CitationInfo(BaseModel):
    """Citation information."""
    citation_id: str
    chunk_id: str
    quote_text: str
    speaker_name: str
    party: str
    date: str
    span_start: int
    span_end: int


class QueryResponse(BaseModel):
    """Response model for non-streaming queries."""
    text: str
    citations: List[CitationInfo]
    experts: Dict[str, ExpertInfo]
    compass: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]


# Global service instances (initialized on first request)
_neo4j_client: Optional[Neo4jClient] = None
_retrieval_engine: Optional[RetrievalEngine] = None
_authority_scorer: Optional[AuthorityScorer] = None
_ideology_scorer: Optional[IdeologyScorer] = None
_generation_pipeline: Optional[GenerationPipeline] = None


def get_services():
    """Get or initialize service instances."""
    global _neo4j_client, _retrieval_engine, _authority_scorer
    global _ideology_scorer, _generation_pipeline

    if _neo4j_client is None:
        settings = get_settings()
        _neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )
        _retrieval_engine = RetrievalEngine(_neo4j_client)
        _authority_scorer = AuthorityScorer(_neo4j_client)
        _ideology_scorer = IdeologyScorer(_neo4j_client)
        _generation_pipeline = GenerationPipeline()

    return {
        "neo4j": _neo4j_client,
        "retrieval": _retrieval_engine,
        "authority": _authority_scorer,
        "ideology": _ideology_scorer,
        "generation": _generation_pipeline,
    }


async def process_query_streaming(
    request: QueryRequest
) -> AsyncGenerator[str, None]:
    """
    Process query with SSE streaming.

    Yields SSE events as the pipeline progresses.
    """
    services = get_services()

    try:
        # Step 1: Progress - Starting
        yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'message': 'Avvio retrieval...'})}\n\n"

        # Step 2: Retrieval
        retrieval_result = await services["retrieval"].retrieve(
            query=request.query,
            top_k=request.top_k,
            date_start=request.date_start,
            date_end=request.date_end
        )

        evidence_list = retrieval_result["evidence"]
        # Include embedding (excluded by default via Field(exclude=True)) for compass PCA
        evidence_dicts = []
        for e in evidence_list:
            d = e.model_dump()
            if e.embedding is not None:
                d["embedding"] = e.embedding
            evidence_dicts.append(d)

        yield f"data: {json.dumps({'type': 'progress', 'step': 2, 'message': f'Trovate {len(evidence_list)} evidenze'})}\n\n"

        # Step 3: Authority scoring
        yield f"data: {json.dumps({'type': 'progress', 'step': 3, 'message': 'Calcolo authority scores...'})}\n\n"

        # Get unique speakers
        speaker_ids = list(set(e.speaker_id for e in evidence_list if e.speaker_id))
        query_embedding = services["retrieval"].embed_query(request.query)

        # Compute per-speaker authority with detailed breakdowns in parallel
        # to avoid blocking the event loop
        from concurrent.futures import ThreadPoolExecutor

        authority_scores = {}
        authority_details = {}

        def _compute_single(sid):
            return sid, services["authority"].compute_authority(sid, query_embedding)

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=min(10, max(1, len(speaker_ids)))) as pool:
            futures = [
                loop.run_in_executor(pool, _compute_single, sid)
                for sid in speaker_ids
            ]
            results = await asyncio.gather(*futures)

        for sid, result in results:
            authority_scores[sid] = result["total_score"]
            authority_details[sid] = result

        # Inject authority scores into evidence dicts so generation can sort by authority
        for ed in evidence_dicts:
            sid = ed.get("speaker_id", "")
            ed["authority_score"] = authority_scores.get(sid, 0.0)

        # Compute experts with full details for frontend
        experts = await _compute_experts(
            evidence_list, authority_scores, authority_details, services["neo4j"]
        )

        yield f"data: {json.dumps({'type': 'experts', 'data': experts}, default=str)}\n\n"

        # Step 4: Compass analysis (2D text-based positioning)
        yield f"data: {json.dumps({'type': 'progress', 'step': 4, 'message': 'Analisi compass ideologico...'})}\n\n"

        compass_result = await asyncio.get_event_loop().run_in_executor(
            None, services["ideology"].compute_2d_text_positions, evidence_dicts
        )
        compass_data = {
            "meta": compass_result.get("meta", {}),
            "axes": compass_result.get("axes", {}),
            "groups": compass_result.get("groups", []),
            "scatter_sample": compass_result.get("scatter_sample", []),
        }

        yield f"data: {json.dumps({'type': 'compass', 'data': compass_data}, default=str)}\n\n"

        # Step 5: Generation
        yield f"data: {json.dumps({'type': 'progress', 'step': 5, 'message': 'Generazione risposta multi-view...'})}\n\n"

        generation_result = await services["generation"].generate(
            query=request.query,
            evidence_list=evidence_dicts
        )
        logger.info(f"[QUERY] Generation done. citations={len(generation_result.get('citations', []))}, "
                     f"extra_citation_ids={len(generation_result.get('extra_citation_ids', []))}")

        # === Send topic statistics for frontend clickable intro stats ===
        topic_stats = generation_result.get("topic_statistics")
        if topic_stats:
            ts_payload = {
                "intervention_count": topic_stats.get("intervention_count", 0),
                "speaker_count": topic_stats.get("speaker_count", 0),
                "first_date": (
                    topic_stats["first_date"].strftime("%Y-%m-%d")
                    if hasattr(topic_stats.get("first_date"), "strftime")
                    else str(topic_stats.get("first_date", ""))
                ),
                "last_date": (
                    topic_stats["last_date"].strftime("%Y-%m-%d")
                    if hasattr(topic_stats.get("last_date"), "strftime")
                    else str(topic_stats.get("last_date", ""))
                ),
                "speakers_detail": topic_stats.get("speakers_detail", []),
                "interventions_detail": topic_stats.get("interventions_detail", []),
                "sessions_detail": topic_stats.get("sessions_detail", []),
            }
            yield f"data: {json.dumps({'type': 'topic_stats', **ts_payload}, default=str)}\n\n"
            logger.info(
                f"[TOPIC_STATS] Sent: {ts_payload['intervention_count']} interventions, "
                f"{ts_payload['speaker_count']} speakers, "
                f"{len(ts_payload['sessions_detail'])} sessions"
            )

        # Step 6: Initial citations (first 20 from retrieval, sent early for UI)
        citations_data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _build_citations_for_frontend(evidence_dicts, neo4j_client=services["neo4j"])
        )
        logger.info(f"[QUERY] Initial citations: {len(citations_data)} (from evidence_dicts[:20])")
        yield f"data: {json.dumps({'type': 'citations', 'data': citations_data}, default=str)}\n\n"

        # === Resolve extra citation IDs via DB lookup ===
        import re as _re
        final_text = generation_result.get("text", "")
        extra_citation_ids = generation_result.get("extra_citation_ids", [])
        extra_evidence_map: Dict[str, Dict[str, Any]] = {}

        if extra_citation_ids:
            logger.info(f"[QUERY:CITATIONS] Resolving {len(extra_citation_ids)} extra IDs from DB: {extra_citation_ids[:5]}")
            try:
                db_rows = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: services["neo4j"].query(
                        """
                        UNWIND $chunk_ids AS cid
                        MATCH (c:Chunk {id: cid})<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
                        MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
                        OPTIONAL MATCH (speaker)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
                          WHERE mg.start_date <= s.date
                            AND (mg.end_date IS NULL OR mg.end_date >= s.date)
                        RETURN c.id AS chunk_id,
                               c.text AS chunk_text,
                               c.start_char_raw AS span_start,
                               c.end_char_raw AS span_end,
                               i.id AS speech_id,
                               i.text AS text,
                               speaker.id AS speaker_id,
                               speaker.first_name AS speaker_first_name,
                               speaker.last_name AS speaker_last_name,
                               CASE WHEN 'GovernmentMember' IN labels(speaker)
                                    THEN 'GovernmentMember' ELSE 'Deputy' END AS speaker_type,
                               g.name AS party,
                               s.id AS session_id,
                               s.date AS session_date,
                               d.title AS debate_title
                        """,
                        {"chunk_ids": extra_citation_ids}
                    )
                )
                from ..models.evidence import normalize_speaker_name, normalize_party_name
                config = get_config()
                for row in db_rows:
                    eid = row.get("chunk_id", "")
                    party = normalize_party_name(row.get("party") or "MISTO")
                    session_date = row.get("session_date")
                    if session_date is not None and hasattr(session_date, 'to_native'):
                        date_obj = session_date.to_native()
                    elif isinstance(session_date, str) and session_date:
                        from datetime import datetime as _dt
                        try:
                            date_obj = _dt.strptime(session_date, "%d/%m/%Y").date()
                        except ValueError:
                            date_obj = _dt.now().date()
                    else:
                        date_obj = date.today()

                    extra_evidence_map[eid] = {
                        "evidence_id": eid,
                        "chunk_text": row.get("chunk_text", ""),
                        "quote_text": row.get("chunk_text", ""),
                        "speech_id": row.get("speech_id", ""),
                        "speaker_id": row.get("speaker_id", ""),
                        "speaker_name": normalize_speaker_name(
                            row.get("speaker_first_name", ""),
                            row.get("speaker_last_name", "")
                        ),
                        "speaker_role": row.get("speaker_type", "Deputy"),
                        "party": party,
                        "coalition": config.get_coalition(party),
                        "date": date_obj,
                        "span_start": row.get("span_start", 0),
                        "span_end": row.get("span_end", 0),
                        "debate_title": row.get("debate_title", ""),
                        "session_id": row.get("session_id", ""),
                    }
                found_ids = set(extra_evidence_map.keys())
                missing_ids = set(extra_citation_ids) - found_ids
                logger.info(f"[QUERY:CITATIONS] DB lookup done: {len(found_ids)} found, {len(missing_ids)} not in DB")
                if missing_ids:
                    logger.warning(f"[QUERY:CITATIONS] IDs not in DB (will strip): {list(missing_ids)[:5]}")

                # Strip links for IDs that truly don't exist in DB
                if missing_ids:
                    def _strip_missing(match):
                        href = match.group(2)
                        if href in missing_ids:
                            logger.warning(f"[QUERY:CITATIONS] Stripping non-existent ID: {href}")
                            return match.group(1)
                        return match.group(0)
                    final_text = _re.sub(
                        r'\[([^\]]+)\]\((leg1[89]_[^)]+)\)',
                        _strip_missing,
                        final_text
                    )
            except Exception as e:
                logger.error(f"[QUERY:CITATIONS] DB lookup failed: {e}", exc_info=True)
                extra_ids_set = set(extra_citation_ids)
                def _strip_extra(match):
                    if match.group(2) in extra_ids_set:
                        return match.group(1)
                    return match.group(0)
                final_text = _re.sub(
                    r'\[([^\]]+)\]\((leg1[89]_[^)]+)\)',
                    _strip_extra,
                    final_text
                )
        else:
            logger.info("[QUERY:CITATIONS] No extra citation IDs to resolve")

        # === Build complete citation_details ===
        text_evidence_ids = set(_re.findall(r'\]\((leg1[89]_[^)]+)\)', final_text))
        evidence_map_for_cit = {e.get("evidence_id"): e for e in evidence_dicts}
        evidence_map_for_cit.update(extra_evidence_map)
        logger.info(f"[QUERY:CITATIONS] Text has {len(text_evidence_ids)} citation links, "
                     f"evidence_map has {len(evidence_map_for_cit)} entries "
                     f"(original={len(evidence_dicts)}, extra={len(extra_evidence_map)})")

        gen_citations = generation_result.get("citations", [])
        tracked_ids = {c.get("evidence_id") for c in gen_citations}
        logger.info(f"[QUERY:CITATIONS] Pipeline returned {len(gen_citations)} tracked citations")

        for eid in text_evidence_ids:
            if eid not in tracked_ids and eid in evidence_map_for_cit:
                ev = evidence_map_for_cit[eid]
                gen_citations.append({
                    "evidence_id": eid,
                    "quote_text": ev.get("quote_text", "") or ev.get("chunk_text", ""),
                    "speaker_name": ev.get("speaker_name", ""),
                    "party": ev.get("party", ""),
                    "date": str(ev.get("date", "")),
                    "span_start": ev.get("span_start", 0),
                    "span_end": ev.get("span_end", 0),
                })
                tracked_ids.add(eid)
                logger.info(f"[QUERY:CITATIONS] Recovered from text: {eid}")
            elif eid not in tracked_ids:
                logger.warning(f"[QUERY:CITATIONS] ID in text but NOT in any map: {eid}")

        logger.info(f"[QUERY:CITATIONS] Final: {len(gen_citations)} total citations to send as citation_details")

        # Send citation_details to update the sidebar with ALL cited chunks
        all_evidence_for_verify = evidence_dicts + list(extra_evidence_map.values())
        verified_citations = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _build_verified_citations(gen_citations, all_evidence_for_verify, neo4j_client=services["neo4j"])
        )
        logger.info(f"[QUERY:CITATIONS] Verified: {len(verified_citations)} citations built")
        yield f"data: {json.dumps({'type': 'citation_details', 'citations': verified_citations}, default=str)}\n\n"

        # Step 7: Stream text chunks
        chunk_size = 100
        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i:i+chunk_size]
            yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
            await asyncio.sleep(0.02)  # Small delay for streaming effect

        # Signal that text streaming is complete and baseline is starting
        yield f"data: {json.dumps({'type': 'progress', 'step': 8, 'message': 'Generazione risposta di confronto...'})}\n\n"

        # Step 8: Baseline Generation
        logger.info("[QUERY:BASELINE] Starting baseline generation...")
        baseline_text = ""
        baseline_error = None
        ab_assignment = None

        # Delay to let OpenAI rate limits recover after generation calls
        await asyncio.sleep(3)

        try:
            baseline_result = await services["generation"].generate_baseline(
                query=request.query,
                evidence_list=evidence_dicts
            )
            logger.info(f"[QUERY:BASELINE] generate_baseline() returned: keys={list(baseline_result.keys())}")
            baseline_text = baseline_result.get("text", "")
            logger.info(f"[QUERY:BASELINE] Text: len={len(baseline_text)}, empty={not baseline_text}")

            if baseline_text:
                ab_assignment = random.choice([
                    {"A": "system", "B": "baseline"},
                    {"A": "baseline", "B": "system"}
                ])
                logger.info(f"[QUERY:BASELINE] Success: {len(baseline_text)} chars, ab={ab_assignment}")
            else:
                baseline_error = "Baseline returned empty text"
                logger.warning(f"[QUERY:BASELINE] {baseline_error}")
        except Exception as e:
            baseline_error = f"{type(e).__name__}: {e}"
            logger.error(f"[QUERY:BASELINE] Failed: {baseline_error}", exc_info=True)

        # Send baseline as dedicated SSE event
        yield f"data: {json.dumps({'type': 'baseline', 'baseline_answer': baseline_text, 'ab_assignment': ab_assignment, 'baseline_error': baseline_error}, default=str)}\n\n"

        # Step 9: Complete
        yield f"data: {json.dumps({'type': 'complete', 'baseline_answer': baseline_text, 'ab_assignment': ab_assignment, 'baseline_error': baseline_error, 'metadata': retrieval_result['metadata']}, default=str)}\n\n"

    except Exception as e:
        logger.error(f"Query processing error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


def _fetch_speaker_details(neo4j_client: Neo4jClient, speaker_id: str) -> Dict[str, Any]:
    """Fetch detailed speaker information from Neo4j."""
    cypher = """
    MATCH (d:Deputy {id: $speaker_id})
    OPTIONAL MATCH (d)-[mc:MEMBER_OF_COMMITTEE]->(c:Committee)
    WHERE mc.end_date IS NULL OR mc.end_date >= date()
    WITH d, collect(c.name)[0] AS current_committee

    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rp:IS_PRESIDENT]->(cp:Committee)
        RETURN collect(DISTINCT {role: 'Presidente ' + cp.name, active: rp.end_date IS NULL OR rp.end_date >= date()}) AS president_roles
    }
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rv:IS_VICE_PRESIDENT]->(cv:Committee)
        RETURN collect(DISTINCT {role: 'Vicepresidente ' + cv.name, active: rv.end_date IS NULL OR rv.end_date >= date()}) AS vice_roles
    }
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rs:IS_SECRETARY]->(cs:Committee)
        RETURN collect(DISTINCT {role: 'Segretario ' + cs.name, active: rs.end_date IS NULL OR rs.end_date >= date()}) AS secretary_roles
    }
    WITH d, current_committee, president_roles + vice_roles + secretary_roles AS all_roles

    // Prefer active roles, fall back to any role
    WITH d, current_committee, all_roles,
         [r IN all_roles WHERE r.active | r.role] AS active_roles,
         [r IN all_roles | r.role] AS any_roles

    RETURN d.id AS id,
           d.first_name AS first_name,
           d.last_name AS last_name,
           d.profession AS profession,
           d.education AS education,
           d.deputy_card AS camera_profile_url,
           current_committee,
           CASE
               WHEN size(active_roles) > 0 THEN active_roles[0]
               WHEN size(any_roles) > 0 THEN any_roles[0]
               ELSE null
           END AS institutional_role
    """
    with neo4j_client.session() as session:
        result = session.run(cypher, speaker_id=speaker_id)
        record = result.single()
        if record:
            return dict(record)

    # Try GovernmentMember
    cypher_gov = """
    MATCH (m:GovernmentMember {id: $speaker_id})
    RETURN m.id AS id,
           m.first_name AS first_name,
           m.last_name AS last_name,
           m.institutional_role AS institutional_role,
           m.deputy_card AS camera_profile_url
    """
    with neo4j_client.session() as session:
        result = session.run(cypher_gov, speaker_id=speaker_id)
        record = result.single()
        if record:
            data = dict(record)
            data["profession"] = None
            data["education"] = None
            data["current_committee"] = None
            return data

    return {}


async def _compute_experts(
    evidence_list: List[Any],
    authority_scores: Dict[str, float],
    authority_details: Dict[str, Dict[str, Any]],
    neo4j_client: Neo4jClient
) -> List[Dict[str, Any]]:
    """Compute experts in frontend-expected format with full details."""
    from concurrent.futures import ThreadPoolExecutor
    coalition_logic = CoalitionLogic()
    party_speakers: Dict[str, Dict[str, Dict]] = {}

    for evidence in evidence_list:
        if evidence.speaker_role == "GovernmentMember":
            continue
        party = evidence.party
        speaker_id = evidence.speaker_id
        speaker_name = evidence.speaker_name

        if party not in party_speakers:
            party_speakers[party] = {}

        if speaker_id not in party_speakers[party]:
            party_speakers[party][speaker_id] = {
                "speaker_name": speaker_name,
                "authority_score": authority_scores.get(speaker_id, 0.5),
                "count": 0,
                "party": party,
            }

        party_speakers[party][speaker_id]["count"] += 1

    # Collect top speakers per party
    top_speakers_info = []
    for party, speakers in party_speakers.items():
        if speakers:
            top_speaker_id = max(
                speakers.keys(),
                key=lambda s: speakers[s]["authority_score"]
            )
            top_speakers_info.append((party, top_speaker_id, speakers[top_speaker_id]))

    # Fetch all speaker details in parallel
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(top_speakers_info)))) as pool:
        detail_futures = [
            loop.run_in_executor(pool, _fetch_speaker_details, neo4j_client, info[1])
            for info in top_speakers_info
        ]
        speaker_details_list = await asyncio.gather(*detail_futures)

    experts = []
    for (party, top_speaker_id, top_speaker), speaker_info in zip(top_speakers_info, speaker_details_list):
        coalition = coalition_logic.get_coalition(party)

        name_parts = top_speaker["speaker_name"].split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        details = authority_details.get(top_speaker_id, {})
        components = details.get("components", {})

        experts.append({
            "id": top_speaker_id,
            "first_name": first_name,
            "last_name": last_name,
            "group": party,
            "coalition": coalition,
            "authority_score": round(top_speaker["authority_score"], 2),
            "relevant_speeches_count": top_speaker["count"],
            "camera_profile_url": speaker_info.get("camera_profile_url"),
            "profession": speaker_info.get("profession"),
            "education": speaker_info.get("education"),
            "committee": speaker_info.get("current_committee"),
            "institutional_role": details.get("institutional_role") or speaker_info.get("institutional_role"),
            "score_breakdown": {
                "speeches": round(components.get("interventions", 0), 2),
                "acts": round(components.get("acts", 0), 2),
                "committee": round(components.get("committee", 0), 2),
                "profession": round(components.get("profession", 0), 2),
                "education": round(components.get("education", 0), 2),
                "role": round(components.get("role", 0), 2),
            },
        })

    return experts


def _batch_fetch_deputy_cards(neo4j_client: Neo4jClient, speaker_ids: List[str]) -> Dict[str, str]:
    """Batch-fetch deputy_card URLs for a list of speaker IDs. Returns {speaker_id: url}."""
    if not speaker_ids:
        return {}
    cypher = """
    UNWIND $ids AS sid
    OPTIONAL MATCH (d:Deputy {id: sid})
    OPTIONAL MATCH (m:GovernmentMember {id: sid})
    WITH sid, coalesce(d.deputy_card, m.deputy_card) AS url
    WHERE url IS NOT NULL
    RETURN sid, url
    """
    result_map: Dict[str, str] = {}
    with neo4j_client.session() as session:
        result = session.run(cypher, ids=list(set(speaker_ids)))
        for record in result:
            result_map[record["sid"]] = record["url"]
    return result_map


def _batch_fetch_gov_roles(neo4j_client: Neo4jClient, speaker_ids: List[str]) -> Dict[str, str]:
    """
    Batch-fetch institutional roles for government members.
    Also matches Deputies who hold government positions (e.g. PM, ministers who are also MPs)
    by looking up GovernmentMember nodes with the same first_name + last_name.
    Returns {speaker_id: role}.
    """
    if not speaker_ids:
        return {}
    cypher = """
    UNWIND $ids AS sid
    // Direct GovernmentMember match
    OPTIONAL MATCH (m:GovernmentMember {id: sid})
    // Also check if a Deputy matches a GovernmentMember by name
    OPTIONAL MATCH (d:Deputy {id: sid})
    OPTIONAL MATCH (gm:GovernmentMember)
    WHERE gm.first_name = d.first_name AND gm.last_name = d.last_name
    WITH sid,
         COALESCE(m.institutional_role, gm.institutional_role) AS role
    WHERE role IS NOT NULL
    RETURN sid, role
    """
    result_map: Dict[str, str] = {}
    with neo4j_client.session() as session:
        result = session.run(cypher, ids=list(set(speaker_ids)))
        for record in result:
            result_map[record["sid"]] = record["role"]
    return result_map


def _build_citations_for_frontend(
    evidence_dicts: List[Dict[str, Any]],
    neo4j_client: Neo4jClient = None,
) -> List[Dict[str, Any]]:
    """Build citations in frontend-expected format from evidence dicts."""
    coalition_logic = CoalitionLogic()
    citations = []

    # Batch-fetch deputy_card URLs and government roles
    deputy_card_map: Dict[str, str] = {}
    gov_role_map: Dict[str, str] = {}
    if neo4j_client:
        speaker_ids = [e.get("speaker_id", "") for e in evidence_dicts[:20] if e.get("speaker_id")]
        deputy_card_map = _batch_fetch_deputy_cards(neo4j_client, speaker_ids)
        gov_role_map = _batch_fetch_gov_roles(neo4j_client, speaker_ids)

    for i, e in enumerate(evidence_dicts[:20]):
        evidence_id = e.get("evidence_id", f"cit_{i+1}")
        speaker_name = e.get("speaker_name", "")
        speaker_id = e.get("speaker_id", "")
        party = e.get("party", "MISTO")
        is_government = e.get("speaker_role") == "GovernmentMember" or speaker_id in gov_role_map

        if is_government:
            group = "Governo"
            coalition = "governo"
        else:
            group = party
            coalition = coalition_logic.get_coalition(party)

        name_parts = speaker_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        chunk_text = e.get("chunk_text") or ""
        quote_text = e.get("quote_text") or ""
        display_text = (chunk_text or quote_text)[:300]

        cit_data: Dict[str, Any] = {
            "chunk_id": evidence_id,
            "deputy_first_name": first_name,
            "deputy_last_name": last_name,
            "text": display_text,
            "quote_text": quote_text,
            "full_text": chunk_text or quote_text,
            "group": group,
            "coalition": coalition,
            "date": str(e.get("date", "")),
            "similarity": round(e.get("similarity", 0), 2),
            "debate": e.get("debate_title", ""),
            "intervention_id": e.get("speech_id", ""),
            "camera_profile_url": deputy_card_map.get(speaker_id),
        }
        if is_government:
            role = gov_role_map.get(speaker_id)
            if not role and neo4j_client:
                try:
                    with neo4j_client.session() as sess:
                        rec = sess.run(
                            "MATCH (m:GovernmentMember {id: $sid}) RETURN m.institutional_role AS role",
                            sid=speaker_id
                        ).single()
                        if rec and rec["role"]:
                            role = rec["role"]
                except Exception:
                    pass
            if role:
                cit_data["institutional_role"] = role
        citations.append(cit_data)

    return citations


def _build_verified_citations(
    generation_citations: List[Dict],
    evidence_dicts: List[Dict],
    neo4j_client: Neo4jClient = None,
) -> List[Dict[str, Any]]:
    """
    Build verified citations with full details for citation_details event.

    Uses evidence_id as chunk_id for consistent linking.
    """
    coalition_logic = CoalitionLogic()
    evidence_map = {e.get("evidence_id"): e for e in evidence_dicts}

    # Batch-fetch deputy_card URLs and government roles
    deputy_card_map: Dict[str, str] = {}
    gov_role_map: Dict[str, str] = {}
    if neo4j_client:
        speaker_ids = []
        for cit in generation_citations:
            eid = cit.get("evidence_id", "")
            evidence = evidence_map.get(eid, {})
            sid = cit.get("speaker_id") or evidence.get("speaker_id", "")
            if sid:
                speaker_ids.append(sid)
        deputy_card_map = _batch_fetch_deputy_cards(neo4j_client, speaker_ids)
        gov_role_map = _batch_fetch_gov_roles(neo4j_client, speaker_ids)

    verified = []
    for cit in generation_citations:
        eid = cit.get("evidence_id", "")
        evidence = evidence_map.get(eid, {})
        party = cit.get("party", evidence.get("party", "MISTO"))
        speaker_id = cit.get("speaker_id") or evidence.get("speaker_id", "")
        speaker_role = cit.get("speaker_role") or evidence.get("speaker_role", "Deputy")
        is_government = speaker_role == "GovernmentMember" or speaker_id in gov_role_map

        if is_government:
            group = "Governo"
            coalition = "governo"
        else:
            group = party
            coalition = coalition_logic.get_coalition(party)

        speaker_name = cit.get("speaker_name", evidence.get("speaker_name", ""))
        name_parts = speaker_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        cit_data: Dict[str, Any] = {
            "chunk_id": eid,
            "deputy_first_name": first_name,
            "deputy_last_name": last_name,
            "text": cit.get("quote_text", "") or evidence.get("chunk_text", ""),
            "quote_text": cit.get("quote_text", ""),
            "full_text": evidence.get("chunk_text", ""),
            "group": group,
            "coalition": coalition,
            "date": str(cit.get("date", "")),
            "span_start": cit.get("span_start", 0),
            "span_end": cit.get("span_end", 0),
            "debate": evidence.get("debate_title", ""),
            "intervention_id": evidence.get("speech_id", ""),
            "camera_profile_url": deputy_card_map.get(speaker_id),
            "verified": True,
        }
        if is_government:
            role = gov_role_map.get(speaker_id)
            if not role and neo4j_client:
                try:
                    with neo4j_client.session() as sess:
                        rec = sess.run(
                            "MATCH (m:GovernmentMember {id: $sid}) RETURN m.institutional_role AS role",
                            sid=speaker_id
                        ).single()
                        if rec and rec["role"]:
                            role = rec["role"]
                except Exception:
                    pass
            if role:
                cit_data["institutional_role"] = role
        verified.append(cit_data)

    return verified


@router.post("/query")
async def query_endpoint(request: QueryRequest):
    """
    Main query endpoint.

    Supports SSE streaming (default) or synchronous response.
    """
    if request.stream:
        return StreamingResponse(
            process_query_streaming(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        # Synchronous response
        services = get_services()

        try:
            # Retrieval
            retrieval_result = await services["retrieval"].retrieve(
                query=request.query,
                top_k=request.top_k,
                date_start=request.date_start,
                date_end=request.date_end
            )

            evidence_list = retrieval_result["evidence"]
            evidence_dicts = [e.model_dump() for e in evidence_list]

            # Authority
            speaker_ids = list(set(e.speaker_id for e in evidence_list if e.speaker_id))
            query_embedding = services["retrieval"].embed_query(request.query)

            # Compute authority in parallel
            from concurrent.futures import ThreadPoolExecutor as _TPE
            authority_scores = {}
            authority_details = {}

            def _compute_single_sync(sid):
                return sid, services["authority"].compute_authority(sid, query_embedding)

            loop = asyncio.get_event_loop()
            with _TPE(max_workers=min(10, max(1, len(speaker_ids)))) as pool:
                futs = [loop.run_in_executor(pool, _compute_single_sync, sid) for sid in speaker_ids]
                results = await asyncio.gather(*futs)
            for sid, result in results:
                authority_scores[sid] = result["total_score"]
                authority_details[sid] = result

            # Experts
            experts = await _compute_experts(
                evidence_list, authority_scores, authority_details, services["neo4j"]
            )

            # Compass
            coverage = services["ideology"].compute_coverage_metrics(evidence_dicts)

            # Generation
            gen_result = await services["generation"].generate(
                query=request.query,
                evidence_list=evidence_dicts
            )

            # Build citations
            citations = [
                CitationInfo(
                    citation_id=f"cit_{i+1}",
                    chunk_id=c.get("evidence_id", ""),
                    quote_text=c.get("quote_text", ""),
                    speaker_name=c.get("speaker_name", ""),
                    party=c.get("party", ""),
                    date=c.get("date", ""),
                    span_start=c.get("span_start", 0),
                    span_end=c.get("span_end", 0),
                )
                for i, c in enumerate(gen_result.get("citations", []))
            ]

            return QueryResponse(
                text=gen_result.get("text", ""),
                citations=citations,
                experts=experts,
                compass=coverage,
                metadata=retrieval_result["metadata"]
            )

        except Exception as e:
            logger.error(f"Query error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        services = get_services()
        # Quick DB check
        services["neo4j"].verify_connectivity()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
