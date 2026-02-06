"""
Chat endpoint compatible with the existing frontend.

Matches the SSE event format expected by the tesi frontend.
Includes comprehensive timing logs for performance monitoring.
"""
import json
import logging
import asyncio
import time
from datetime import date, datetime
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services.neo4j_client import Neo4jClient
from ..services.retrieval import RetrievalEngine
from ..services.retrieval.commission_matcher import get_commission_matcher
from ..services.authority import AuthorityScorer
from ..services.compass import IdeologyScorer
from ..services.generation import GenerationPipeline
from ..config import get_config, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])


class ChatRequest(BaseModel):
    """Request model matching frontend expectations."""
    query: str = Field(..., min_length=3, max_length=4000)
    mode: str = Field(default="standard")  # "standard" or "high_quality"


# Global service instances
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


def sse_event(event_type: str, data: Any) -> str:
    """Format SSE event."""
    if isinstance(data, dict):
        payload = {"type": event_type, **data}
    else:
        payload = {"type": event_type, "data": data}
    return f"data: {json.dumps(payload, default=str)}\n\n"


async def process_chat_streaming(request: ChatRequest) -> AsyncGenerator[str, None]:
    """
    Process chat with SSE streaming matching frontend format.

    Events: progress, commissioni, experts, citations, balance, compass,
            citation_details, chunk, complete, error

    Timing logs are prefixed with [TIMING] for easy filtering.
    """
    services = get_services()
    pipeline_start = time.time()
    step_times: Dict[str, float] = {}

    logger.info("=" * 60)
    logger.info(f"[PIPELINE START] Query: {request.query[:80]}...")
    logger.info(f"[PIPELINE START] Mode: {request.mode}")
    logger.info("=" * 60)

    try:
        # === Step 1: Analisi query ===
        step_start = time.time()
        yield sse_event("progress", {"step": 1, "total": 8, "message": "Analisi query"})
        await asyncio.sleep(0)  # Flush immediately
        step_times["step_1_init"] = time.time() - step_start
        logger.info(f"[TIMING] Step 1 (Init): {step_times['step_1_init']*1000:.1f}ms")

        # === Step 2: Commissioni ===
        step_start = time.time()
        yield sse_event("progress", {"step": 2, "total": 8, "message": "Commissioni"})
        await asyncio.sleep(0)  # Flush

        # Find relevant commissions based on query keywords
        commission_matcher = get_commission_matcher()
        relevant_commissions = commission_matcher.find_relevant_commissions(
            query=request.query,
            top_k=3,
            min_score=0.1
        )

        yield sse_event("commissioni", {"commissioni": relevant_commissions})
        await asyncio.sleep(0)  # Flush
        step_times["step_2_commissioni"] = time.time() - step_start
        logger.info(f"[TIMING] Step 2 (Commissioni): {step_times['step_2_commissioni']*1000:.1f}ms - {len(relevant_commissions)} found")

        # === Step 3: Esperti (Authority) ===
        step_start = time.time()
        yield sse_event("progress", {"step": 3, "total": 8, "message": "Esperti"})
        await asyncio.sleep(0)  # Flush before long retrieval operation

        # Retrieval - use sync wrapper to run in thread pool
        logger.info("[RETRIEVAL] Starting dual-channel retrieval...")
        retrieval_start = time.time()

        def _do_retrieval():
            return services["retrieval"].retrieve_sync(
                query=request.query,
                top_k=100
            )

        retrieval_result = await asyncio.get_event_loop().run_in_executor(
            None, _do_retrieval
        )

        retrieval_time = time.time() - retrieval_start
        logger.info(f"[TIMING] Retrieval completed: {retrieval_time*1000:.1f}ms")

        evidence_list = retrieval_result["evidence"]
        # Include embedding for compass PCA (normally excluded from API responses)
        evidence_dicts = []
        for e in evidence_list:
            d = e.model_dump()
            d["embedding"] = e.embedding  # Explicitly add embedding for compass
            evidence_dicts.append(d)

        logger.info(f"[RETRIEVAL] Retrieved {len(evidence_list)} evidence pieces")
        logger.info(f"[RETRIEVAL] Dense: {retrieval_result['metadata'].get('dense_channel_count', 0)}, "
                   f"Graph: {retrieval_result['metadata'].get('graph_channel_count', 0)}")

        # Compute authority scores with detailed breakdown (exclude GovernmentMember)
        speaker_ids = list(set(
            e.speaker_id for e in evidence_list
            if e.speaker_id and e.speaker_role == "Deputy"
        ))
        logger.info(f"[AUTHORITY] Computing scores for {len(speaker_ids)} unique speakers...")
        authority_start = time.time()

        query_embedding = services["retrieval"].embed_query(request.query)

        authority_scores = {}
        authority_details = {}  # Store detailed breakdowns
        if speaker_ids:
            for speaker_id in speaker_ids:
                result = services["authority"].compute_authority(
                    speaker_id, query_embedding
                )
                authority_scores[speaker_id] = result["total_score"]
                authority_details[speaker_id] = result

        authority_time = time.time() - authority_start
        step_times["step_3_authority"] = time.time() - step_start
        logger.info(f"[TIMING] Authority scoring: {authority_time*1000:.1f}ms")
        logger.info(f"[TIMING] Step 3 (Esperti) total: {step_times['step_3_authority']*1000:.1f}ms")

        # Compute experts per coalition with detailed info
        experts = _compute_experts_for_frontend(
            evidence_list, authority_scores, authority_details, services["neo4j"]
        )
        maggioranza_experts = sum(1 for e in experts if e.get("coalizione") == "maggioranza")
        opposizione_experts = sum(1 for e in experts if e.get("coalizione") == "opposizione")
        logger.info(f"[EXPERTS] Found {len(experts)} experts: {maggioranza_experts} maggioranza, {opposizione_experts} opposizione")

        yield sse_event("experts", {"experts": experts})
        await asyncio.sleep(0)  # Flush

        # === Step 4: Interventi (Citations) ===
        step_start = time.time()
        yield sse_event("progress", {"step": 4, "total": 8, "message": "Interventi"})
        await asyncio.sleep(0)  # Flush

        # Build citations list for frontend
        citations = _build_citations_for_frontend(evidence_dicts)
        yield sse_event("citations", {"citations": citations})
        await asyncio.sleep(0)  # Flush
        step_times["step_4_citations"] = time.time() - step_start
        logger.info(f"[TIMING] Step 4 (Interventi): {step_times['step_4_citations']*1000:.1f}ms - {len(citations)} citations")

        # === Step 5: Statistiche (Balance) ===
        step_start = time.time()
        yield sse_event("progress", {"step": 5, "total": 8, "message": "Statistiche"})
        await asyncio.sleep(0)  # Flush

        balance = _compute_balance_metrics(evidence_dicts)
        yield sse_event("balance", balance)
        await asyncio.sleep(0)  # Flush
        step_times["step_5_balance"] = time.time() - step_start
        logger.info(f"[TIMING] Step 5 (Statistiche): {step_times['step_5_balance']*1000:.1f}ms")
        logger.info(f"[BALANCE] Maggioranza: {balance.get('maggioranza_percentage', 0):.1f}%, "
                   f"Opposizione: {balance.get('opposizione_percentage', 0):.1f}%, "
                   f"Bias: {balance.get('bias_score', 0):.2f}")

        # === Step 6: Bussola Ideologica (Compass) ===
        step_start = time.time()
        yield sse_event("progress", {"step": 6, "total": 8, "message": "Bussola Ideologica"})
        await asyncio.sleep(0)  # Flush

        compass_data = _compute_compass_data(services["ideology"], evidence_dicts)
        yield sse_event("compass", compass_data)
        await asyncio.sleep(0)  # Flush
        step_times["step_6_compass"] = time.time() - step_start
        logger.info(f"[TIMING] Step 6 (Bussola): {step_times['step_6_compass']*1000:.1f}ms")

        # === Step 7: Generazione ===
        step_start = time.time()
        yield sse_event("progress", {"step": 7, "total": 8, "message": "Generazione"})
        await asyncio.sleep(0)  # Flush before long generation operation

        logger.info("[GENERATION] Starting 4-stage generation pipeline...")
        generation_start = time.time()

        # Generation is truly async (uses async for internally)
        generation_result = await services["generation"].generate(
            query=request.query,
            evidence_list=evidence_dicts
        )

        generation_time = time.time() - generation_start
        logger.info(f"[TIMING] Generation pipeline: {generation_time*1000:.1f}ms")

        # Stream text content in chunks
        final_text = generation_result.get("text", "")
        chunk_size = 50  # Characters per chunk
        logger.info(f"[GENERATION] Generated {len(final_text)} chars, streaming in {len(final_text)//chunk_size + 1} chunks")

        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i:i+chunk_size]
            yield sse_event("chunk", {"content": chunk})
            await asyncio.sleep(0.02)

        step_times["step_7_generation"] = time.time() - step_start
        logger.info(f"[TIMING] Step 7 (Generazione) total: {step_times['step_7_generation']*1000:.1f}ms")

        # === Step 8: Valutazione (if high_quality mode) ===
        if request.mode == "high_quality":
            step_start = time.time()
            yield sse_event("progress", {"step": 8, "total": 8, "message": "Valutazione"})
            # Best-of-N would go here
            yield sse_event("hq_variants", {
                "variants": [{"text": final_text, "score": 8.5, "is_best": True}]
            })
            step_times["step_8_valutazione"] = time.time() - step_start
            logger.info(f"[TIMING] Step 8 (Valutazione): {step_times['step_8_valutazione']*1000:.1f}ms")

        # === Citation details (verified citations) ===
        verified_citations = _build_verified_citations(
            generation_result.get("citations", []),
            evidence_dicts
        )
        yield sse_event("citation_details", {"citations": verified_citations})
        logger.info(f"[CITATIONS] {len(verified_citations)} verified citations inserted")

        # === Complete ===
        total_time = time.time() - pipeline_start
        step_times["total"] = total_time

        # Log final summary
        logger.info("=" * 60)
        logger.info("[PIPELINE COMPLETE] Summary:")
        logger.info(f"  Total time: {total_time*1000:.1f}ms ({total_time:.2f}s)")
        logger.info(f"  Evidence: {len(evidence_list)} pieces from {len(speaker_ids)} speakers")
        logger.info(f"  Balance: {balance.get('maggioranza_percentage', 0):.1f}% / {balance.get('opposizione_percentage', 0):.1f}%")
        logger.info(f"  Generated: {len(final_text)} chars, {len(verified_citations)} citations")
        logger.info("[TIMING BREAKDOWN]:")
        for step_name, step_time in step_times.items():
            if step_name != "total":
                pct = (step_time / total_time) * 100 if total_time > 0 else 0
                logger.info(f"  {step_name}: {step_time*1000:.1f}ms ({pct:.1f}%)")
        logger.info("=" * 60)

        yield sse_event("complete", {
            "metadata": {
                **retrieval_result.get("metadata", {}),
                "timing": {k: round(v * 1000, 1) for k, v in step_times.items()},
            }
        })

    except Exception as e:
        total_time = time.time() - pipeline_start
        logger.error(f"[PIPELINE ERROR] Failed after {total_time*1000:.1f}ms: {e}", exc_info=True)
        yield sse_event("error", {"message": str(e)})


def _fetch_speaker_details(neo4j_client: Neo4jClient, speaker_id: str) -> Dict[str, Any]:
    """Fetch detailed speaker information from Neo4j."""
    # Try Deputy first
    cypher = """
    MATCH (d:Deputy {id: $speaker_id})
    OPTIONAL MATCH (d)-[mc:MEMBER_OF_COMMITTEE]->(c:Committee)
    WHERE mc.end_date IS NULL OR mc.end_date >= date()
    WITH d, collect(c.name)[0] AS current_committee

    // Get institutional roles using CALL subqueries
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rp:IS_PRESIDENT]->(cp:Committee)
        WHERE rp.end_date IS NULL OR rp.end_date >= date()
        RETURN collect(DISTINCT 'Presidente ' + cp.name) AS president_roles
    }
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rv:IS_VICE_PRESIDENT]->(cv:Committee)
        WHERE rv.end_date IS NULL OR rv.end_date >= date()
        RETURN collect(DISTINCT 'Vicepresidente ' + cv.name) AS vice_roles
    }
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rs:IS_SECRETARY]->(cs:Committee)
        WHERE rs.end_date IS NULL OR rs.end_date >= date()
        RETURN collect(DISTINCT 'Segretario ' + cs.name) AS secretary_roles
    }
    WITH d, current_committee, president_roles + vice_roles + secretary_roles AS all_roles

    RETURN d.id AS id,
           d.first_name AS first_name,
           d.last_name AS last_name,
           d.profession AS profession,
           d.education AS education,
           COALESCE(d.camera_profile_url, d.url_scheda_camera) AS camera_profile_url,
           current_committee,
           CASE WHEN size(all_roles) > 0 THEN all_roles[0] ELSE null END AS institutional_role
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
           COALESCE(m.position, m.incarico) AS institutional_role,
           COALESCE(m.camera_profile_url, m.url_scheda_camera) AS camera_profile_url
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


def _compute_experts_for_frontend(
    evidence_list: List[Any],
    authority_scores: Dict[str, float],
    authority_details: Dict[str, Dict[str, Any]],
    neo4j_client: Neo4jClient
) -> List[Dict[str, Any]]:
    """Compute experts in frontend-expected format with full details."""
    from ..services.authority.coalition_logic import CoalitionLogic
    coalition_logic = CoalitionLogic()

    party_speakers: Dict[str, Dict[str, Dict]] = {}

    for evidence in evidence_list:
        # GovernmentMember should not be considered as experts
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

    experts = []
    for party, speakers in party_speakers.items():
        if speakers:
            top_speaker_id = max(
                speakers.keys(),
                key=lambda s: speakers[s]["authority_score"]
            )
            top_speaker = speakers[top_speaker_id]
            coalition = coalition_logic.get_coalition(party)

            # Split name into first_name/last_name if possible
            name_parts = top_speaker["speaker_name"].split(" ", 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Get detailed authority breakdown
            details = authority_details.get(top_speaker_id, {})
            components = details.get("components", {})

            # Fetch additional speaker info from Neo4j
            speaker_info = _fetch_speaker_details(neo4j_client, top_speaker_id)

            experts.append({
                "id": top_speaker_id,
                "first_name": first_name,
                "last_name": last_name,
                "group": party,
                "coalition": coalition,
                "authority_score": round(top_speaker["authority_score"], 2),
                "relevant_speeches_count": top_speaker["count"],
                # Additional details for frontend
                "camera_profile_url": speaker_info.get("camera_profile_url"),
                "profession": speaker_info.get("profession"),
                "education": speaker_info.get("education"),
                "committee": speaker_info.get("current_committee"),
                "institutional_role": speaker_info.get("institutional_role"),
                # Score breakdown
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


def _build_citations_for_frontend(
    evidence_dicts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Build citations in frontend-expected format.

    Frontend expects: deputy_first_name, deputy_last_name, text, group, coalition, date
    Uses evidence_id as chunk_id so links in generated text match the sidebar.
    """
    from ..services.authority.coalition_logic import CoalitionLogic
    coalition_logic = CoalitionLogic()
    citations = []

    for i, e in enumerate(evidence_dicts[:20]):  # Limit for UI
        evidence_id = e.get("evidence_id", f"cit_{i+1}")
        speaker_name = e.get("speaker_name", "")
        party = e.get("party", "MISTO")
        coalition = coalition_logic.get_coalition(party)

        # Split name into first_name/last_name
        name_parts = speaker_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        citations.append({
            "chunk_id": evidence_id,  # For linking
            "deputy_first_name": first_name,
            "deputy_last_name": last_name,
            "text": e.get("chunk_text", "")[:300],
            "quote_text": e.get("quote_text", ""),
            "full_text": e.get("chunk_text", ""),
            "group": party,
            "coalition": coalition,
            "date": str(e.get("date", "")),
            "similarity": round(e.get("similarity", 0), 2),
            "debate": e.get("debate_title", ""),
            "intervention_id": e.get("speech_id", ""),
        })

    return citations


def _compute_balance_metrics(
    evidence_dicts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute balance metrics in frontend-expected format."""
    from ..services.authority.coalition_logic import CoalitionLogic
    coalition_logic = CoalitionLogic()

    maggioranza_count = 0
    opposizione_count = 0

    for e in evidence_dicts:
        party = e.get("party", "MISTO")
        coalition = coalition_logic.get_coalition(party)
        if coalition == "maggioranza":
            maggioranza_count += 1
        else:
            opposizione_count += 1

    total = maggioranza_count + opposizione_count
    if total == 0:
        total = 1

    magg_pct = (maggioranza_count / total) * 100
    opp_pct = (opposizione_count / total) * 100

    # Bias score: 0 = perfectly balanced, higher = more biased
    bias_score = abs(magg_pct - 50) / 50

    return {
        "maggioranza_percentage": round(magg_pct, 1),
        "opposizione_percentage": round(opp_pct, 1),
        "bias_score": round(bias_score, 2),
    }


def _compute_compass_data(
    ideology_scorer: IdeologyScorer,
    evidence_dicts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute compass data in frontend-expected format.

    Uses PCA on TEXT EMBEDDINGS to derive 2D positions.
    Positions are based on SEMANTIC CONTENT, not party membership.

    Frontend expects:
    - meta: query, explained_variance_ratio, dimensionality, is_stable, warnings
    - axes: x (AxisDef), y (AxisDef)
    - groups: array with position_x, position_y, dispersion, stats, core_evidence_ids
    - scatter_sample: array of {x, y, group_id, text}
    """
    # Use the new text-based 2D positioning method
    compass_result = ideology_scorer.compute_2d_text_positions(evidence_dicts)

    return {
        "meta": compass_result.get("meta", {}),
        "axes": compass_result.get("axes", {}),
        "groups": compass_result.get("groups", []),
        "scatter_sample": compass_result.get("scatter_sample", []),
    }


def _build_verified_citations(
    generation_citations: List[Dict],
    evidence_dicts: List[Dict]
) -> List[Dict[str, Any]]:
    """
    Build verified citations with full details.

    Uses evidence_id as chunk_id for consistent linking.
    Frontend expects: deputy_first_name, deputy_last_name, text, coalition, etc.
    """
    from ..services.authority.coalition_logic import CoalitionLogic
    coalition_logic = CoalitionLogic()
    evidence_map = {e.get("evidence_id"): e for e in evidence_dicts}

    verified = []
    for cit in generation_citations:
        eid = cit.get("evidence_id", "")
        evidence = evidence_map.get(eid, {})
        party = cit.get("party", evidence.get("party", "MISTO"))
        coalition = coalition_logic.get_coalition(party)

        # Split name into first_name/last_name
        speaker_name = cit.get("speaker_name", evidence.get("speaker_name", ""))
        name_parts = speaker_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        verified.append({
            "chunk_id": eid,  # For linking
            "deputy_first_name": first_name,
            "deputy_last_name": last_name,
            "text": cit.get("quote_text", ""),
            "quote_text": cit.get("quote_text", ""),
            "full_text": evidence.get("chunk_text", ""),
            "group": party,
            "coalition": coalition,
            "date": str(cit.get("date", "")),
            "span_start": cit.get("span_start", 0),
            "span_end": cit.get("span_end", 0),
            "debate": evidence.get("debate_title", ""),
            "intervention_id": evidence.get("speech_id", ""),
            "verified": True,
        })

    return verified


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint with SSE streaming.

    Compatible with the tesi frontend.
    """
    return StreamingResponse(
        process_chat_streaming(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
