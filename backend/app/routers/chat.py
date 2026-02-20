"""
Chat endpoint compatible with the existing frontend.

Matches the SSE event format expected by the tesi frontend.
Includes comprehensive timing logs for performance monitoring.
"""
import json
import logging
import asyncio
import random
import time
from datetime import date, datetime
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..services.neo4j_client import Neo4jClient
from ..services.retrieval import RetrievalEngine
from ..services.retrieval.commission_matcher import get_commission_matcher
from ..services.authority import AuthorityScorer
from ..services.compass import IdeologyScorer
from ..services.generation import GenerationPipeline
from ..services.task_store import get_task_store
from ..config import get_config, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])


class ChatRequest(BaseModel):
    """Request model matching frontend expectations."""
    query: str = Field(..., min_length=3, max_length=4000)
    mode: str = Field(default="standard")  # "standard" or "high_quality"
    task_id: Optional[str] = Field(default=None)  # Client-provided task ID for reconnection


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


# Limit concurrent pipeline executions to prevent thread pool and Neo4j connection exhaustion
_MAX_CONCURRENT_PIPELINES = 5
_pipeline_semaphore: Optional[asyncio.Semaphore] = None


def _get_pipeline_semaphore() -> asyncio.Semaphore:
    global _pipeline_semaphore
    if _pipeline_semaphore is None:
        _pipeline_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PIPELINES)
    return _pipeline_semaphore


async def process_chat_background(request: ChatRequest, task_id: str):
    """
    Process chat pipeline in the background, storing events in TaskStore.

    This runs independently of the SSE connection so that mobile browsers
    can disconnect without losing results.
    """
    store = get_task_store()

    async def emit(event_type: str, data: Any):
        """Emit an SSE event to both the task store and format it."""
        if isinstance(data, dict):
            payload = {"type": event_type, **data}
        else:
            payload = {"type": event_type, "data": data}
        await store.add_event(task_id, payload)

    services = get_services()
    pipeline_start = time.time()
    step_times: Dict[str, float] = {}

    logger.info("=" * 60)
    logger.info(f"[PIPELINE START] Task: {task_id}")
    logger.info(f"[PIPELINE START] Query: {request.query[:80]}...")
    logger.info(f"[PIPELINE START] Mode: {request.mode}")
    logger.info("=" * 60)

    semaphore = _get_pipeline_semaphore()
    if semaphore.locked():
        logger.info(f"[PIPELINE] Semaphore full, task {task_id} waiting...")
        await emit("waiting", {"message": "Attualmente troppi utenti stanno utilizzando il sistema, aspetta..."})
    await semaphore.acquire()

    try:
        # === Step 1: Analisi query ===
        step_start = time.time()
        await emit("progress", {"step": 1, "total": 9, "message": "Analisi query"})
        step_times["step_1_init"] = time.time() - step_start
        logger.info(f"[TIMING] Step 1 (Init): {step_times['step_1_init']*1000:.1f}ms")

        # === Step 2: Commissioni ===
        step_start = time.time()
        await emit("progress", {"step": 2, "total": 9, "message": "Commissioni"})

        commission_matcher = get_commission_matcher()
        relevant_commissions = commission_matcher.find_relevant_commissions(
            query=request.query, top_k=3, min_score=0.1
        )
        await emit("commissioni", {"commissioni": relevant_commissions})
        step_times["step_2_commissioni"] = time.time() - step_start
        logger.info(f"[TIMING] Step 2 (Commissioni): {step_times['step_2_commissioni']*1000:.1f}ms - {len(relevant_commissions)} found")

        # === Step 3: Esperti (Authority) ===
        step_start = time.time()
        await emit("progress", {"step": 3, "total": 9, "message": "Esperti"})

        logger.info("[RETRIEVAL] Starting dual-channel retrieval...")
        retrieval_start = time.time()

        def _do_retrieval():
            return services["retrieval"].retrieve_sync(query=request.query, top_k=100)

        retrieval_result = await asyncio.get_event_loop().run_in_executor(None, _do_retrieval)
        retrieval_time = time.time() - retrieval_start
        logger.info(f"[TIMING] Retrieval completed: {retrieval_time*1000:.1f}ms")

        evidence_list = retrieval_result["evidence"]
        evidence_dicts = []
        for e in evidence_list:
            d = e.model_dump()
            d["embedding"] = e.embedding
            evidence_dicts.append(d)

        logger.info(f"[RETRIEVAL] Retrieved {len(evidence_list)} evidence pieces")
        logger.info(f"[RETRIEVAL] Dense: {retrieval_result['metadata'].get('dense_channel_count', 0)}, "
                   f"Graph: {retrieval_result['metadata'].get('graph_channel_count', 0)}")

        speaker_ids = list(set(
            e.speaker_id for e in evidence_list
            if e.speaker_id and e.speaker_role == "Deputy"
        ))
        logger.info(f"[AUTHORITY] Computing scores for {len(speaker_ids)} unique speakers...")
        authority_start = time.time()

        query_embedding = services["retrieval"].embed_query(request.query)

        authority_scores = {}
        authority_details = {}
        if speaker_ids:
            from concurrent.futures import ThreadPoolExecutor

            def _compute_single(sid):
                return sid, services["authority"].compute_authority(sid, query_embedding)

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=min(10, len(speaker_ids))) as pool:
                futures = [loop.run_in_executor(pool, _compute_single, sid) for sid in speaker_ids]
                results = await asyncio.gather(*futures)

            for sid, result in results:
                authority_scores[sid] = result["total_score"]
                authority_details[sid] = result

        authority_time = time.time() - authority_start
        step_times["step_3_authority"] = time.time() - step_start
        logger.info(f"[TIMING] Authority scoring: {authority_time*1000:.1f}ms")
        logger.info(f"[TIMING] Step 3 (Esperti) total: {step_times['step_3_authority']*1000:.1f}ms")

        experts = await _compute_experts_for_frontend(
            evidence_list, authority_scores, authority_details, services["neo4j"]
        )
        maggioranza_experts = sum(1 for e in experts if e.get("coalizione") == "maggioranza")
        opposizione_experts = sum(1 for e in experts if e.get("coalizione") == "opposizione")
        logger.info(f"[EXPERTS] Found {len(experts)} experts: {maggioranza_experts} maggioranza, {opposizione_experts} opposizione")

        await emit("experts", {"experts": experts})

        # === Step 4: Interventi (Citations) ===
        step_start = time.time()
        await emit("progress", {"step": 4, "total": 9, "message": "Interventi"})

        citations = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _build_citations_for_frontend(evidence_dicts, neo4j_client=services["neo4j"])
        )
        if citations:
            logger.info(f"[CITATIONS] Sample citation[0]: deputy={citations[0].get('deputy_first_name')} {citations[0].get('deputy_last_name')}, "
                       f"group={citations[0].get('group')}, coalition={citations[0].get('coalition')}, "
                       f"text_len={len(citations[0].get('text', ''))}")
        await emit("citations", {"citations": citations})
        step_times["step_4_citations"] = time.time() - step_start
        logger.info(f"[TIMING] Step 4 (Interventi): {step_times['step_4_citations']*1000:.1f}ms - {len(citations)} citations")

        # === Step 5: Statistiche (Balance) ===
        step_start = time.time()
        await emit("progress", {"step": 5, "total": 9, "message": "Statistiche"})

        balance = _compute_balance_metrics(evidence_dicts)
        await emit("balance", balance)
        step_times["step_5_balance"] = time.time() - step_start
        logger.info(f"[TIMING] Step 5 (Statistiche): {step_times['step_5_balance']*1000:.1f}ms")
        logger.info(f"[BALANCE] Maggioranza: {balance.get('maggioranza_percentage', 0):.1f}%, "
                   f"Opposizione: {balance.get('opposizione_percentage', 0):.1f}%, "
                   f"Bias: {balance.get('bias_score', 0):.2f}")

        # === Step 6: Bussola Ideologica (Compass) ===
        step_start = time.time()
        await emit("progress", {"step": 6, "total": 9, "message": "Bussola Ideologica"})

        compass_data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _compute_compass_data(services["ideology"], evidence_dicts)
        )
        logger.info(f"[COMPASS] meta={compass_data.get('meta', {})}, "
                   f"groups_count={len(compass_data.get('groups', []))}, "
                   f"axes_keys={list(compass_data.get('axes', {}).keys())}")
        await emit("compass", compass_data)
        step_times["step_6_compass"] = time.time() - step_start
        logger.info(f"[TIMING] Step 6 (Bussola): {step_times['step_6_compass']*1000:.1f}ms")

        # === Step 7: Generazione ===
        step_start = time.time()
        await emit("progress", {"step": 7, "total": 9, "message": "Generazione"})

        logger.info("[GENERATION] Starting 4-stage generation pipeline...")
        generation_start = time.time()

        generation_result = await services["generation"].generate(
            query=request.query, evidence_list=evidence_dicts
        )

        generation_time = time.time() - generation_start
        logger.info(f"[TIMING] Generation pipeline: {generation_time*1000:.1f}ms")

        final_text = generation_result.get("text", "")

        # === Send topic statistics ===
        topic_stats = generation_result.get("topic_statistics")
        if topic_stats:
            # Enrich speakers/interventions with photo URLs from Neo4j
            speakers_detail = topic_stats.get("speakers_detail", [])
            interventions_detail = topic_stats.get("interventions_detail", [])
            neo4j = services.get("neo4j")
            if neo4j:
                all_sids = list(set(
                    s.get("speaker_id", "") for s in speakers_detail
                ) | set(
                    i.get("speaker_id", "") for i in interventions_detail
                    if i.get("speaker_id")
                ))
                photo_map = _batch_fetch_photos(neo4j, [s for s in all_sids if s])
                for s in speakers_detail:
                    s["photo"] = photo_map.get(s.get("speaker_id", ""))
                for i in interventions_detail:
                    i["photo"] = photo_map.get(i.get("speaker_id", ""))

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
                "speakers_detail": speakers_detail,
                "interventions_detail": interventions_detail,
                "sessions_detail": topic_stats.get("sessions_detail", []),
            }
            await emit("topic_stats", ts_payload)
            logger.info(
                f"[TOPIC_STATS] Sent: {ts_payload['intervention_count']} interventions, "
                f"{ts_payload['speaker_count']} speakers, "
                f"{len(ts_payload['sessions_detail'])} sessions"
            )

        # === Resolve extra citation IDs via DB lookup ===
        import re as _re
        extra_citation_ids = generation_result.get("extra_citation_ids", [])
        extra_evidence_map: Dict[str, Dict[str, Any]] = {}

        if extra_citation_ids:
            logger.info(f"[CITATIONS] Resolving {len(extra_citation_ids)} extra citation IDs from DB...")
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
                logger.info(
                    f"[CITATIONS] DB lookup: {len(found_ids)} found, "
                    f"{len(missing_ids)} not in DB"
                )

                if missing_ids:
                    def _strip_missing(match):
                        href = match.group(2)
                        if href in missing_ids:
                            logger.warning(f"[CITATIONS] Stripping non-existent ID: {href}")
                            return match.group(1)
                        return match.group(0)
                    final_text = _re.sub(
                        r'\[([^\]]+)\]\((leg1[89]_[^)]+)\)',
                        _strip_missing,
                        final_text
                    )
            except Exception as e:
                logger.error(f"[CITATIONS] DB lookup failed: {e}", exc_info=True)
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

        # Stream text content in chunks
        chunk_size = 50
        logger.info(f"[GENERATION] Generated {len(final_text)} chars, streaming in {len(final_text)//chunk_size + 1} chunks")

        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i:i+chunk_size]
            await emit("chunk", {"content": chunk})
            await asyncio.sleep(0.02)

        step_times["step_7_generation"] = time.time() - step_start
        logger.info(f"[TIMING] Step 7 (Generazione) total: {step_times['step_7_generation']*1000:.1f}ms")

        # === Citation details (verified citations) ===
        text_evidence_ids = set(_re.findall(r'\]\((leg1[89]_[^)]+)\)', final_text))
        evidence_map_for_cit = {e.get("evidence_id"): e for e in evidence_dicts}
        evidence_map_for_cit.update(extra_evidence_map)

        gen_citations = generation_result.get("citations", [])
        tracked_ids = {c.get("evidence_id") for c in gen_citations}

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
                logger.info(f"[CITATIONS] Recovered from text scan: {eid}")

        logger.info(f"[CITATIONS] {len(gen_citations)} total citations ({len(text_evidence_ids)} in text, {len(tracked_ids)} tracked)")

        all_evidence_for_verify = evidence_dicts + list(extra_evidence_map.values())
        verified_citations = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _build_verified_citations(gen_citations, all_evidence_for_verify, neo4j_client=services["neo4j"])
        )
        logger.info(f"[CITATIONS] {len(verified_citations)} verified citations to send")
        await emit("citation_details", {"citations": verified_citations})

        # === Step 8: Baseline Generation ===
        step_start = time.time()
        await emit("progress", {"step": 8, "total": 9, "message": "Generazione Baseline"})

        await asyncio.sleep(3)

        baseline_text = ""
        baseline_error = None
        ab_assignment = None
        try:
            logger.info("[BASELINE] Starting baseline generation...")
            logger.info(f"[BASELINE] Input: query='{request.query[:80]}...', evidence_count={len(evidence_dicts)}")
            baseline_result = await services["generation"].generate_baseline(
                query=request.query, evidence_list=evidence_dicts
            )
            logger.info(f"[BASELINE] generate_baseline() returned: keys={list(baseline_result.keys())}")
            baseline_text = baseline_result.get("text", "")
            logger.info(f"[BASELINE] Extracted text: type={type(baseline_text).__name__}, len={len(baseline_text) if baseline_text else 0}")

            if baseline_text:
                ab_assignment = random.choice([
                    {"A": "system", "B": "baseline"},
                    {"A": "baseline", "B": "system"}
                ])
                logger.info(f"[BASELINE] Success: {len(baseline_text)} chars, ab_assignment={ab_assignment}")
            else:
                baseline_error = "Baseline returned empty text"
                logger.warning(f"[BASELINE] {baseline_error}")
        except Exception as e:
            baseline_error = f"{type(e).__name__}: {e}"
            logger.error(f"[BASELINE] Generation failed: {baseline_error}", exc_info=True)

        step_times["step_8_baseline"] = time.time() - step_start
        logger.info(f"[TIMING] Step 8 (Baseline): {step_times['step_8_baseline']*1000:.1f}ms")

        await emit("baseline", {
            "baseline_answer": baseline_text,
            "ab_assignment": ab_assignment,
            "baseline_error": baseline_error,
        })

        # === Step 9: Valutazione (if high_quality mode) ===
        if request.mode == "high_quality":
            step_start = time.time()
            await emit("progress", {"step": 9, "total": 9, "message": "Valutazione"})
            await emit("hq_variants", {
                "variants": [{"text": final_text, "score": 8.5, "is_best": True}]
            })
            step_times["step_9_valutazione"] = time.time() - step_start
            logger.info(f"[TIMING] Step 9 (Valutazione): {step_times['step_9_valutazione']*1000:.1f}ms")

        # === Complete ===
        total_time = time.time() - pipeline_start
        step_times["total"] = total_time

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

        await emit("complete", {
            "baseline_answer": baseline_text,
            "ab_assignment": ab_assignment,
            "baseline_error": baseline_error,
            "metadata": {
                **retrieval_result.get("metadata", {}),
                "timing": {k: round(v * 1000, 1) for k, v in step_times.items()},
            }
        })

        await store.complete_task(task_id)

    except Exception as e:
        total_time = time.time() - pipeline_start
        logger.error(f"[PIPELINE ERROR] Failed after {total_time*1000:.1f}ms: {e}", exc_info=True)
        await emit("error", {"message": str(e)})
        await store.fail_task(task_id, str(e))
    finally:
        semaphore.release()
        logger.info(f"[PIPELINE] Semaphore released for task {task_id}")


async def stream_from_task(task_id: str) -> AsyncGenerator[str, None]:
    """
    Stream SSE events from a background task via its queue.

    If the client disconnects, the background task keeps running.
    The client can reconnect and poll for results via GET /api/chat/task/{task_id}.
    """
    store = get_task_store()
    queue = store.get_queue(task_id)
    if not queue:
        yield sse_event("error", {"message": f"Task {task_id} not found"})
        return

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=60.0)
            if event is None:  # Sentinel: task completed
                break
            yield f"data: {json.dumps(event, default=str)}\n\n"
        except asyncio.TimeoutError:
            # Send keepalive comment to prevent proxy timeouts
            yield ": keepalive\n\n"
        except Exception:
            break


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
        yield sse_event("progress", {"step": 1, "total": 9, "message": "Analisi query"})
        await asyncio.sleep(0)  # Flush immediately
        step_times["step_1_init"] = time.time() - step_start
        logger.info(f"[TIMING] Step 1 (Init): {step_times['step_1_init']*1000:.1f}ms")

        # === Step 2: Commissioni ===
        step_start = time.time()
        yield sse_event("progress", {"step": 2, "total": 9, "message": "Commissioni"})
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
        yield sse_event("progress", {"step": 3, "total": 9, "message": "Esperti"})
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
            # Run authority scoring in parallel using ThreadPoolExecutor
            # to avoid blocking the event loop
            from concurrent.futures import ThreadPoolExecutor

            def _compute_single(sid):
                return sid, services["authority"].compute_authority(sid, query_embedding)

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=min(10, len(speaker_ids))) as pool:
                futures = [
                    loop.run_in_executor(pool, _compute_single, sid)
                    for sid in speaker_ids
                ]
                results = await asyncio.gather(*futures)

            for sid, result in results:
                authority_scores[sid] = result["total_score"]
                authority_details[sid] = result

        authority_time = time.time() - authority_start
        step_times["step_3_authority"] = time.time() - step_start
        logger.info(f"[TIMING] Authority scoring: {authority_time*1000:.1f}ms")
        logger.info(f"[TIMING] Step 3 (Esperti) total: {step_times['step_3_authority']*1000:.1f}ms")

        # Compute experts per coalition with detailed info
        experts = await _compute_experts_for_frontend(
            evidence_list, authority_scores, authority_details, services["neo4j"]
        )
        maggioranza_experts = sum(1 for e in experts if e.get("coalizione") == "maggioranza")
        opposizione_experts = sum(1 for e in experts if e.get("coalizione") == "opposizione")
        logger.info(f"[EXPERTS] Found {len(experts)} experts: {maggioranza_experts} maggioranza, {opposizione_experts} opposizione")

        yield sse_event("experts", {"experts": experts})
        await asyncio.sleep(0)  # Flush

        # === Step 4: Interventi (Citations) ===
        step_start = time.time()
        yield sse_event("progress", {"step": 4, "total": 9, "message": "Interventi"})
        await asyncio.sleep(0)  # Flush

        # Build citations list for frontend (run in executor to avoid blocking)
        citations = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _build_citations_for_frontend(evidence_dicts, neo4j_client=services["neo4j"])
        )
        if citations:
            logger.info(f"[CITATIONS] Sample citation[0]: deputy={citations[0].get('deputy_first_name')} {citations[0].get('deputy_last_name')}, "
                       f"group={citations[0].get('group')}, coalition={citations[0].get('coalition')}, "
                       f"text_len={len(citations[0].get('text', ''))}")
        yield sse_event("citations", {"citations": citations})
        await asyncio.sleep(0)  # Flush
        step_times["step_4_citations"] = time.time() - step_start
        logger.info(f"[TIMING] Step 4 (Interventi): {step_times['step_4_citations']*1000:.1f}ms - {len(citations)} citations")

        # === Step 5: Statistiche (Balance) ===
        step_start = time.time()
        yield sse_event("progress", {"step": 5, "total": 9, "message": "Statistiche"})
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
        yield sse_event("progress", {"step": 6, "total": 9, "message": "Bussola Ideologica"})
        await asyncio.sleep(0)  # Flush

        compass_data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _compute_compass_data(services["ideology"], evidence_dicts)
        )
        logger.info(f"[COMPASS] meta={compass_data.get('meta', {})}, "
                   f"groups_count={len(compass_data.get('groups', []))}, "
                   f"axes_keys={list(compass_data.get('axes', {}).keys())}")
        yield sse_event("compass", compass_data)
        await asyncio.sleep(0)  # Flush
        step_times["step_6_compass"] = time.time() - step_start
        logger.info(f"[TIMING] Step 6 (Bussola): {step_times['step_6_compass']*1000:.1f}ms")

        # === Step 7: Generazione ===
        step_start = time.time()
        yield sse_event("progress", {"step": 7, "total": 9, "message": "Generazione"})
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

        final_text = generation_result.get("text", "")

        # === Send topic statistics for frontend clickable intro stats ===
        topic_stats = generation_result.get("topic_statistics")
        if topic_stats:
            # Enrich speakers/interventions with photo URLs from Neo4j
            speakers_detail = topic_stats.get("speakers_detail", [])
            interventions_detail = topic_stats.get("interventions_detail", [])
            neo4j = services.get("neo4j")
            if neo4j:
                all_sids = list(set(
                    s.get("speaker_id", "") for s in speakers_detail
                ) | set(
                    i.get("speaker_id", "") for i in interventions_detail
                    if i.get("speaker_id")
                ))
                photo_map = _batch_fetch_photos(neo4j, [s for s in all_sids if s])
                for s in speakers_detail:
                    s["photo"] = photo_map.get(s.get("speaker_id", ""))
                for i in interventions_detail:
                    i["photo"] = photo_map.get(i.get("speaker_id", ""))

            # Serialize dates to strings for JSON
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
                "speakers_detail": speakers_detail,
                "interventions_detail": interventions_detail,
                "sessions_detail": topic_stats.get("sessions_detail", []),
            }
            yield sse_event("topic_stats", ts_payload)
            await asyncio.sleep(0)  # Flush
            logger.info(
                f"[TOPIC_STATS] Sent: {ts_payload['intervention_count']} interventions, "
                f"{ts_payload['speaker_count']} speakers, "
                f"{len(ts_payload['sessions_detail'])} sessions"
            )

        # === Resolve extra citation IDs via DB lookup ===
        # The pipeline found citation links in the text whose IDs are not in
        # the initial evidence_list (e.g. the LLM cited chunks from broader
        # context).  Query Neo4j to verify they exist and fetch metadata.
        import re as _re
        extra_citation_ids = generation_result.get("extra_citation_ids", [])
        extra_evidence_map: Dict[str, Dict[str, Any]] = {}

        if extra_citation_ids:
            logger.info(f"[CITATIONS] Resolving {len(extra_citation_ids)} extra citation IDs from DB...")
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
                logger.info(
                    f"[CITATIONS] DB lookup: {len(found_ids)} found, "
                    f"{len(missing_ids)} not in DB"
                )

                # Strip links for IDs that truly don't exist in DB
                if missing_ids:
                    def _strip_missing(match):
                        href = match.group(2)
                        if href in missing_ids:
                            logger.warning(f"[CITATIONS] Stripping non-existent ID: {href}")
                            return match.group(1)  # keep display text only
                        return match.group(0)
                    final_text = _re.sub(
                        r'\[([^\]]+)\]\((leg1[89]_[^)]+)\)',
                        _strip_missing,
                        final_text
                    )
            except Exception as e:
                logger.error(f"[CITATIONS] DB lookup failed: {e}", exc_info=True)
                # On failure, strip all extra IDs to avoid broken links
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

        # Stream text content in chunks
        chunk_size = 50  # Characters per chunk
        logger.info(f"[GENERATION] Generated {len(final_text)} chars, streaming in {len(final_text)//chunk_size + 1} chunks")

        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i:i+chunk_size]
            yield sse_event("chunk", {"content": chunk})
            await asyncio.sleep(0.02)

        step_times["step_7_generation"] = time.time() - step_start
        logger.info(f"[TIMING] Step 7 (Generazione) total: {step_times['step_7_generation']*1000:.1f}ms")

        # === Citation details (verified citations) ===
        # Build the complete citation list including DB-resolved extra IDs.
        text_evidence_ids = set(_re.findall(r'\]\((leg1[89]_[^)]+)\)', final_text))
        evidence_map_for_cit = {e.get("evidence_id"): e for e in evidence_dicts}
        # Merge extra evidence from DB lookup
        evidence_map_for_cit.update(extra_evidence_map)

        gen_citations = generation_result.get("citations", [])
        tracked_ids = {c.get("evidence_id") for c in gen_citations}

        # Add any evidence IDs found in text but not yet tracked
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
                logger.info(f"[CITATIONS] Recovered from text scan: {eid}")

        logger.info(f"[CITATIONS] {len(gen_citations)} total citations ({len(text_evidence_ids)} in text, {len(tracked_ids)} tracked)")

        # Combine original + extra evidence for building verified citations
        all_evidence_for_verify = evidence_dicts + list(extra_evidence_map.values())
        verified_citations = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _build_verified_citations(gen_citations, all_evidence_for_verify, neo4j_client=services["neo4j"])
        )
        logger.info(f"[CITATIONS] {len(verified_citations)} verified citations to send")
        yield sse_event("citation_details", {"citations": verified_citations})
        await asyncio.sleep(0)  # Flush

        # === Step 8: Baseline Generation ===
        step_start = time.time()
        yield sse_event("progress", {"step": 8, "total": 9, "message": "Generazione Baseline"})

        # Delay to let OpenAI rate limits recover after ~13 calls from Step 7
        await asyncio.sleep(3)

        baseline_text = ""
        baseline_error = None
        ab_assignment = None
        try:
            logger.info("[BASELINE] Starting baseline generation (no authority, no surgeon, sequential sections)...")
            logger.info(f"[BASELINE] Input: query='{request.query[:80]}...', evidence_count={len(evidence_dicts)}")
            baseline_result = await services["generation"].generate_baseline(
                query=request.query,
                evidence_list=evidence_dicts
            )
            logger.info(f"[BASELINE] generate_baseline() returned: keys={list(baseline_result.keys())}")
            logger.info(f"[BASELINE] Result metadata: {baseline_result.get('metadata', {})}")
            baseline_text = baseline_result.get("text", "")
            logger.info(f"[BASELINE] Extracted text: type={type(baseline_text).__name__}, len={len(baseline_text) if baseline_text else 0}, empty={not baseline_text}, repr_start={repr(baseline_text[:200]) if baseline_text else 'EMPTY'}")

            if baseline_text:
                # Random A/B assignment for blind evaluation
                ab_assignment = random.choice([
                    {"A": "system", "B": "baseline"},
                    {"A": "baseline", "B": "system"}
                ])
                logger.info(f"[BASELINE] Success: {len(baseline_text)} chars, ab_assignment={ab_assignment}")
            else:
                baseline_error = "Baseline returned empty text"
                logger.warning(f"[BASELINE] {baseline_error}")
                logger.warning(f"[BASELINE] Full result dump: sections={baseline_result.get('sections', [])}, citations={baseline_result.get('citations', [])}")

        except Exception as e:
            baseline_error = f"{type(e).__name__}: {e}"
            logger.error(
                f"[BASELINE] Generation failed: {baseline_error}",
                exc_info=True
            )

        step_times["step_8_baseline"] = time.time() - step_start
        logger.info(f"[TIMING] Step 8 (Baseline): {step_times['step_8_baseline']*1000:.1f}ms")
        logger.info(f"[BASELINE] FINAL STATE: text_len={len(baseline_text)}, ab_assignment={ab_assignment}, error={baseline_error}")

        # Send baseline as a dedicated SSE event so it's not lost if the
        # complete event payload is large (metadata can bloat the JSON).
        yield sse_event("baseline", {
            "baseline_answer": baseline_text,
            "ab_assignment": ab_assignment,
            "baseline_error": baseline_error,
        })
        await asyncio.sleep(0)  # Flush

        # === Step 9: Valutazione (if high_quality mode) ===
        if request.mode == "high_quality":
            step_start = time.time()
            yield sse_event("progress", {"step": 9, "total": 9, "message": "Valutazione"})
            yield sse_event("hq_variants", {
                "variants": [{"text": final_text, "score": 8.5, "is_best": True}]
            })
            step_times["step_9_valutazione"] = time.time() - step_start
            logger.info(f"[TIMING] Step 9 (Valutazione): {step_times['step_9_valutazione']*1000:.1f}ms")

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
            "baseline_answer": baseline_text,
            "ab_assignment": ab_assignment,
            "baseline_error": baseline_error,
            "metadata": {
                **retrieval_result.get("metadata", {}),
                "timing": {k: round(v * 1000, 1) for k, v in step_times.items()},
            }
        })

    except Exception as e:
        total_time = time.time() - pipeline_start
        logger.error(f"[PIPELINE ERROR] Failed after {total_time*1000:.1f}ms: {e}", exc_info=True)
        yield sse_event("error", {"message": str(e)})


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


def _batch_fetch_photos(neo4j_client: Neo4jClient, speaker_ids: List[str]) -> Dict[str, str]:
    """Batch-fetch photo URLs for a list of speaker IDs. Returns {speaker_id: url}."""
    if not speaker_ids:
        return {}
    cypher = """
    UNWIND $ids AS sid
    OPTIONAL MATCH (d:Deputy {id: sid})
    WITH sid, d.photo AS url
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
    // Also check if a Deputy matches a GovernmentMember by name (indexed lookup, no full scan)
    OPTIONAL MATCH (d:Deputy {id: sid})
    OPTIONAL MATCH (gm:GovernmentMember {first_name: d.first_name, last_name: d.last_name})
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
           d.deputy_card AS camera_profile_url,
           d.photo AS photo,
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


async def _compute_experts_for_frontend(
    evidence_list: List[Any],
    authority_scores: Dict[str, float],
    authority_details: Dict[str, Dict[str, Any]],
    neo4j_client: Neo4jClient
) -> List[Dict[str, Any]]:
    """Compute experts in frontend-expected format with full details."""
    from ..services.authority.coalition_logic import CoalitionLogic
    from concurrent.futures import ThreadPoolExecutor
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

        # Split name into first_name/last_name if possible
        name_parts = top_speaker["speaker_name"].split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Get detailed authority breakdown
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
            # Additional details for frontend
            "photo": speaker_info.get("photo"),
            "camera_profile_url": speaker_info.get("camera_profile_url"),
            "profession": speaker_info.get("profession"),
            "education": speaker_info.get("education"),
            "committee": speaker_info.get("current_committee"),
            "institutional_role": details.get("institutional_role") or speaker_info.get("institutional_role"),
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
    evidence_dicts: List[Dict[str, Any]],
    neo4j_client: Neo4jClient = None,
) -> List[Dict[str, Any]]:
    """
    Build citations in frontend-expected format.

    Frontend expects: deputy_first_name, deputy_last_name, text, group, coalition, date
    Uses evidence_id as chunk_id so links in generated text match the sidebar.
    """
    from ..services.authority.coalition_logic import CoalitionLogic
    coalition_logic = CoalitionLogic()
    citations = []

    if evidence_dicts:
        sample = evidence_dicts[0]
        logger.info(f"[CITATIONS_DEBUG] evidence_dicts[0] keys: {list(sample.keys())}")
        logger.info(f"[CITATIONS_DEBUG] speaker_name={sample.get('speaker_name')}, "
                   f"party={sample.get('party')}, coalition={sample.get('coalition')}")

    # Batch-fetch deputy_card URLs and government roles
    deputy_card_map: Dict[str, str] = {}
    gov_role_map: Dict[str, str] = {}
    if neo4j_client:
        speaker_ids = [e.get("speaker_id", "") for e in evidence_dicts[:20] if e.get("speaker_id")]
        deputy_card_map = _batch_fetch_deputy_cards(neo4j_client, speaker_ids)
        # Check ALL speakers for government roles (Deputies who are also ministers)
        gov_role_map = _batch_fetch_gov_roles(neo4j_client, speaker_ids)

    for i, e in enumerate(evidence_dicts[:20]):  # Limit for UI
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

        # Split name into first_name/last_name
        name_parts = speaker_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        chunk_text = e.get("chunk_text") or ""
        quote_text = e.get("quote_text") or ""
        display_text = (chunk_text or quote_text)[:300]

        cit_data: Dict[str, Any] = {
            "chunk_id": evidence_id,  # For linking
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
                # Fallback: fetch role directly for GovernmentMember not in batch
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
    evidence_dicts: List[Dict],
    neo4j_client: Neo4jClient = None,
) -> List[Dict[str, Any]]:
    """
    Build verified citations with full details.

    Uses evidence_id as chunk_id for consistent linking.
    Frontend expects: deputy_first_name, deputy_last_name, text, coalition, etc.
    """
    from ..services.authority.coalition_logic import CoalitionLogic
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
        # Check ALL speakers for government roles (Deputies who are also ministers)
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

        # Split name into first_name/last_name
        speaker_name = cit.get("speaker_name", evidence.get("speaker_name", ""))
        name_parts = speaker_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        cit_data = {
            "chunk_id": eid,  # For linking
            "deputy_first_name": first_name,
            "deputy_last_name": last_name,
            "text": cit.get("quote_text", ""),
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


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint with SSE streaming.

    Uses a background task so the pipeline continues even if the client
    disconnects (e.g. mobile browser going to background).
    The client can poll GET /api/chat/task/{task_id} to recover results.
    """
    store = get_task_store()

    # Cleanup expired tasks periodically
    await store.cleanup_expired()

    # Use client-provided task_id or generate one
    task_id = request.task_id or store.generate_task_id()
    await store.create_task(task_id)

    # Launch pipeline in background (runs independently of this response)
    asyncio.create_task(process_chat_background(request, task_id))

    # Stream events from the background task to the client
    async def stream_with_task_id():
        # Send task_id as the first event so the client can use it for reconnection
        yield sse_event("task_id", {"task_id": task_id})
        async for chunk in stream_from_task(task_id):
            yield chunk

    return StreamingResponse(
        stream_with_task_id(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/chat/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Poll endpoint for recovering task results after SSE disconnection.

    Returns the task status and all accumulated events.
    Used by the frontend when the user returns to the page after
    the mobile browser killed the SSE connection.
    """
    store = get_task_store()
    task = await store.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return JSONResponse({
        "task_id": task.task_id,
        "status": task.status,
        "events": task.events,
        "error_message": task.error_message,
    })
