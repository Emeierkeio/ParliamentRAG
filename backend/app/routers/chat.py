"""
Chat endpoint compatible with the existing frontend.

Matches the SSE event format expected by the tesi frontend.
Includes comprehensive timing logs for performance monitoring.
"""
import json
import logging
import asyncio
import os
import time
from datetime import date, datetime
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..services.neo4j_client import Neo4jClient
from ..services.compass import IdeologyScorer
from ..services.retrieval.commission_matcher import get_commission_matcher
from ..services.task_store import get_task_store
from ..services.deps import get_services
from ..services.experts import compute_experts, patch_experts_for_cited_speakers
from ..services.translation import translate_citation_batch, translate_response_text, translate_compass_axes
from ..services.generation.direct_writer import DirectWriter
from ..config import get_config, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat"])


class TaskCancelledError(Exception):
    """Raised when the user explicitly cancels a running pipeline."""


def _raise_if_cancelled(task_id: str, store) -> None:
    """Synchronous check — raises TaskCancelledError if the task was cancelled."""
    if store.is_cancelled(task_id):
        raise TaskCancelledError(f"Task {task_id} was cancelled by the user")


class ChatRequest(BaseModel):
    """Request model matching frontend expectations."""
    query: str = Field(..., min_length=3, max_length=4000)
    mode: str = Field(default="standard")  # "standard" or "high_quality"
    task_id: Optional[str] = Field(default=None)  # Client-provided task ID for reconnection
    locale: str = Field(default="it")  # Language for citation translation
    chamber: str = Field(default="both", description="Filter: 'camera' | 'senato' | 'both'")




def sse_event(event_type: str, data: Any) -> str:
    """Format SSE event."""
    if isinstance(data, dict):
        payload = {"type": event_type, **data}
    else:
        payload = {"type": event_type, "data": data}
    return f"data: {json.dumps(payload, default=str)}\n\n"


# Limit concurrent pipeline executions to prevent thread pool and Neo4j connection exhaustion.
# Each pipeline opens a ThreadPoolExecutor(10) + several OpenAI calls concurrently.
# 5 per worker is the default ceiling; adjust with _MAX_CONCURRENT_PIPELINES env var.
_MAX_CONCURRENT_PIPELINES = int(os.environ.get("MAX_CONCURRENT_CHAT_PIPELINES",
                                                os.environ.get("MAX_CONCURRENT_PIPELINES", "5")))
_pipeline_semaphore: Optional[asyncio.Semaphore] = None
_pipeline_counter_lock: Optional[asyncio.Lock] = None
_waiting_queue: list[str] = []  # ordered list of waiting task_ids (front = next to run)
_pipeline_active: int = 0       # tasks currently running


def _get_pipeline_semaphore() -> asyncio.Semaphore:
    global _pipeline_semaphore
    if _pipeline_semaphore is None:
        _pipeline_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PIPELINES)
    return _pipeline_semaphore


def _get_counter_lock() -> asyncio.Lock:
    global _pipeline_counter_lock
    if _pipeline_counter_lock is None:
        _pipeline_counter_lock = asyncio.Lock()
    return _pipeline_counter_lock


async def _acquire_pipeline_slot(
    semaphore: asyncio.Semaphore,
    emit_fn,
    task_id: str,
    max_wait: int = 300,   # 5-minute hard timeout
    check_every: int = 10,  # send position update every N seconds
) -> bool:
    """
    Acquire a pipeline slot, sending periodic queue-position updates to the client.

    Returns True if the slot was acquired, False if the max_wait timeout expired.
    The approach is correct: asyncio.wait_for cancels the acquire() coroutine on
    timeout (properly removing us from the waiters list), then we re-queue.

    Position tracking uses an ordered list so each task knows its exact rank even
    as tasks ahead of it complete and leave the queue.
    """
    global _waiting_queue, _pipeline_active
    lock = _get_counter_lock()

    # Fast path: slot available immediately
    if not semaphore.locked():
        await semaphore.acquire()
        async with lock:
            _pipeline_active += 1
        logger.info(f"[SEMAPHORE] Task {task_id} acquired immediately (active={_pipeline_active})")
        return True

    # Slow path: add to ordered waiting queue
    async with lock:
        _waiting_queue.append(task_id)
        position = len(_waiting_queue)   # 1-indexed position in queue
        ahead = position - 1             # people ahead of this task
        active_now = _pipeline_active
    logger.info(f"[SEMAPHORE] Task {task_id} queued (position={position}, ahead={ahead}, active={active_now})")

    def _current_position() -> tuple[int, int]:
        """Return (position, ahead) for this task. Must be called under lock."""
        try:
            pos = _waiting_queue.index(task_id) + 1
        except ValueError:
            pos = 1
        return pos, pos - 1

    try:
        await emit_fn("waiting", {
            "queue_position": position,
            "ahead_count": ahead,
            "active_count": active_now,
            "elapsed_seconds": 0,
        })

        elapsed = 0
        while elapsed < max_wait:
            try:
                await asyncio.wait_for(semaphore.acquire(), timeout=check_every)
                async with lock:
                    _pipeline_active += 1
                logger.info(f"[SEMAPHORE] Task {task_id} acquired after {elapsed}s "
                            f"(active={_pipeline_active}, still_waiting={len(_waiting_queue) - 1})")
                return True
            except asyncio.TimeoutError:
                elapsed += check_every
                async with lock:
                    position, ahead = _current_position()
                    active_now = _pipeline_active
                logger.info(f"[SEMAPHORE] Task {task_id} still waiting "
                            f"({elapsed}s, position={position}, ahead={ahead}, active={active_now})")
                await emit_fn("waiting", {
                    "queue_position": position,
                    "ahead_count": ahead,
                    "active_count": active_now,
                    "elapsed_seconds": elapsed,
                })

        logger.warning(f"[SEMAPHORE] Task {task_id} timed out after {max_wait}s")
        return False

    finally:
        async with lock:
            try:
                _waiting_queue.remove(task_id)
            except ValueError:
                pass


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
    logger.info(f"[PIPELINE START] Mode: {request.mode}, Locale: {request.locale}")
    logger.info("=" * 60)

    _en = request.locale == "en"
    def _t(it: str, en: str) -> str:
        return en if _en else it

    semaphore = _get_pipeline_semaphore()
    acquired = await _acquire_pipeline_slot(semaphore, emit, task_id)
    if not acquired:
        await emit("error", {"message": "Il sistema è troppo occupato al momento. Riprova tra qualche minuto."})
        await store.fail_task(task_id, "Timeout in coda")
        return

    try:
        # === Step 1: Analisi query ===
        _raise_if_cancelled(task_id, store)
        step_start = time.time()
        await emit("progress", {"step": 1, "total": 8, "message": _t("Analisi query", "Query analysis")})
        step_times["step_1_init"] = time.time() - step_start
        logger.info(f"[TIMING] Step 1 (Init): {step_times['step_1_init']*1000:.1f}ms")

        # === Step 2: Commissioni ===
        _raise_if_cancelled(task_id, store)
        step_start = time.time()
        await emit("progress", {"step": 2, "total": 8, "message": _t("Commissioni", "Committees")})

        commission_matcher = get_commission_matcher()
        relevant_commissions = commission_matcher.find_relevant_commissions(
            query=request.query, top_k=3, min_score=0.1
        )
        await emit("commissioni", {"commissioni": relevant_commissions})
        step_times["step_2_commissioni"] = time.time() - step_start
        logger.info(f"[TIMING] Step 2 (Commissioni): {step_times['step_2_commissioni']*1000:.1f}ms - {len(relevant_commissions)} found")

        # === Step 3: Esperti (Authority) ===
        _raise_if_cancelled(task_id, store)
        step_start = time.time()
        await emit("progress", {"step": 3, "total": 8, "message": _t("Esperti", "Authoritative sources")})

        logger.info("[RETRIEVAL] Starting dual-channel retrieval...")
        retrieval_start = time.time()

        chambers = ["camera", "senato"] if request.chamber == "both" else [request.chamber]

        def _do_retrieval():
            return services["retrieval"].retrieve_sync(query=request.query, top_k=100, chambers=chambers)

        retrieval_result = await asyncio.get_running_loop().run_in_executor(None, _do_retrieval)
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

        # Reuse query_embedding from retrieval result — no duplicate embed call
        query_embedding = retrieval_result["query_embedding"]

        authority_scores = {}
        authority_details = {}
        if speaker_ids:
            from concurrent.futures import ThreadPoolExecutor

            def _compute_single(sid):
                return sid, services["authority"].compute_authority(sid, query_embedding)

            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=min(10, len(speaker_ids))) as pool:
                futures = [loop.run_in_executor(pool, _compute_single, sid) for sid in speaker_ids]
                results = await asyncio.gather(*futures)

            for sid, result in results:
                authority_scores[sid] = result["total_score"]
                authority_details[sid] = result

        # Write computed authority scores back into evidence_dicts so that the
        # generation pipeline can use real scores for per-party citation ranking.
        # (evidence_dicts are built from model_dump() before scoring, so
        # authority_score is 0.0 by default until this back-fill.)
        for d in evidence_dicts:
            sid = d.get("speaker_id", "")
            if sid in authority_scores:
                d["authority_score"] = authority_scores[sid]

        authority_time = time.time() - authority_start
        step_times["step_3_authority"] = time.time() - step_start
        logger.info(f"[TIMING] Authority scoring: {authority_time*1000:.1f}ms")
        logger.info(f"[TIMING] Step 3 (Esperti) total: {step_times['step_3_authority']*1000:.1f}ms")

        experts = await compute_experts(
            evidence_list, authority_scores, authority_details, services["neo4j"]
        )
        maggioranza_experts = sum(1 for e in experts if e.get("coalizione") == "maggioranza")
        opposizione_experts = sum(1 for e in experts if e.get("coalizione") == "opposizione")
        logger.info(f"[EXPERTS] Found {len(experts)} experts: {maggioranza_experts} maggioranza, {opposizione_experts} opposizione")

        await emit("experts", {"experts": experts})

        # === Step 4: Interventi (Citations) ===
        _raise_if_cancelled(task_id, store)
        step_start = time.time()
        await emit("progress", {"step": 4, "total": 8, "message": _t("Interventi", "Speeches")})

        citations = await asyncio.get_running_loop().run_in_executor(
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
        _raise_if_cancelled(task_id, store)
        step_start = time.time()
        await emit("progress", {"step": 5, "total": 8, "message": _t("Statistiche", "Statistics")})

        balance = _compute_balance_metrics(evidence_dicts)
        await emit("balance", balance)
        step_times["step_5_balance"] = time.time() - step_start
        logger.info(f"[TIMING] Step 5 (Statistiche): {step_times['step_5_balance']*1000:.1f}ms")
        logger.info(f"[BALANCE] Maggioranza: {balance.get('maggioranza_percentage', 0):.1f}%, "
                   f"Opposizione: {balance.get('opposizione_percentage', 0):.1f}%, "
                   f"Bias: {balance.get('bias_score', 0):.2f}")

        # === Step 6: Bussola Ideologica (Compass) ===
        _raise_if_cancelled(task_id, store)
        step_start = time.time()
        await emit("progress", {"step": 6, "total": 8, "message": _t("Bussola Ideologica", "Ideological Compass")})

        compass_data = await asyncio.get_running_loop().run_in_executor(
            None, lambda: _compute_compass_data(services["ideology"], evidence_dicts)
        )
        logger.info(f"[COMPASS] meta={compass_data.get('meta', {})}, "
                   f"groups_count={len(compass_data.get('groups', []))}, "
                   f"axes_keys={list(compass_data.get('axes', {}).keys())}")
        if request.locale != "it":
            compass_data = await translate_compass_axes(compass_data, target_lang=request.locale)
        await emit("compass", compass_data)
        step_times["step_6_compass"] = time.time() - step_start
        logger.info(f"[TIMING] Step 6 (Bussola): {step_times['step_6_compass']*1000:.1f}ms")

        # === Step 7: Generazione ===
        _raise_if_cancelled(task_id, store)
        step_start = time.time()
        await emit("progress", {"step": 7, "total": 8, "message": _t("Generazione", "Generation")})

        gen_config = get_config().load_config().get("generation", {})
        gen_mode = gen_config.get("mode", "pipeline")
        generation_start = time.time()

        if gen_mode == "direct":
            logger.info("[GENERATION] Using DirectWriter (locale=%s)", request.locale)
            writer = DirectWriter()
            generation_result = await writer.generate(
                query=request.query,
                evidence_list=evidence_dicts,
                locale=request.locale,
            )
        else:
            logger.info("[GENERATION] Starting 4-stage generation pipeline...")
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
                photo_map = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: _batch_fetch_photos(neo4j, [s for s in all_sids if s])
                )
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
                db_rows = await asyncio.get_running_loop().run_in_executor(
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

        # Translate response text if needed
        if request.locale != "it":
            final_text = await translate_response_text(final_text, target_lang=request.locale)

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
                })
                tracked_ids.add(eid)
                logger.info(f"[CITATIONS] Recovered from text scan: {eid}")

        logger.info(f"[CITATIONS] {len(gen_citations)} total citations ({len(text_evidence_ids)} in text, {len(tracked_ids)} tracked)")

        all_evidence_for_verify = evidence_dicts + list(extra_evidence_map.values())
        verified_citations = await asyncio.get_running_loop().run_in_executor(
            None, lambda: _build_verified_citations(gen_citations, all_evidence_for_verify, neo4j_client=services["neo4j"])
        )
        logger.info(f"[CITATIONS] {len(verified_citations)} verified citations to send")
        if request.locale != "it":
            verified_citations = await translate_citation_batch(verified_citations, target_lang=request.locale)
        await emit("citation_details", {"citations": verified_citations})

        # === Step 8: Valutazione (if high_quality mode) ===
        if request.mode == "high_quality":
            _raise_if_cancelled(task_id, store)
            step_start = time.time()
            await emit("progress", {"step": 8, "total": 8, "message": _t("Valutazione", "Evaluation")})
            await emit("hq_variants", {
                "variants": [{"text": final_text, "score": 8.5, "is_best": True}]
            })
            step_times["step_8_valutazione"] = time.time() - step_start
            logger.info(f"[TIMING] Step 8 (Valutazione): {step_times['step_8_valutazione']*1000:.1f}ms")

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
            "metadata": {
                **retrieval_result.get("metadata", {}),
                "timing": {k: round(v * 1000, 1) for k, v in step_times.items()},
            }
        })

        await store.complete_task(task_id)

    except TaskCancelledError:
        total_time = time.time() - pipeline_start
        logger.info(f"[PIPELINE] Task {task_id} cancelled after {total_time*1000:.1f}ms")
        await store.cancel_task(task_id)
    except Exception as e:
        total_time = time.time() - pipeline_start
        logger.error(f"[PIPELINE ERROR] Failed after {total_time*1000:.1f}ms: {e}", exc_info=True)
        await emit("error", {"message": str(e)})
        await store.fail_task(task_id, str(e))
    finally:
        global _pipeline_active
        async with _get_counter_lock():
            _pipeline_active = max(0, _pipeline_active - 1)
        semaphore.release()
        logger.info(f"[PIPELINE] Semaphore released for task {task_id} "
                    f"(active={_pipeline_active}, waiting={len(_waiting_queue)})")


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
        except asyncio.CancelledError:
            logger.info("[SSE] Stream cancelled for task %s", task_id)
            break
        except Exception as e:
            logger.error("[SSE] Stream error for task %s: %s", task_id, e)
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
    logger.info(f"[PIPELINE START] Mode: {request.mode}, Locale: {request.locale}")
    logger.info("=" * 60)

    _en = request.locale == "en"
    def _t(it: str, en: str) -> str:
        return en if _en else it

    try:
        # === Step 1: Analisi query ===
        step_start = time.time()
        yield sse_event("progress", {"step": 1, "total": 8, "message": _t("Analisi query", "Query analysis")})
        await asyncio.sleep(0)  # Flush immediately
        step_times["step_1_init"] = time.time() - step_start
        logger.info(f"[TIMING] Step 1 (Init): {step_times['step_1_init']*1000:.1f}ms")

        # === Step 2: Commissioni ===
        step_start = time.time()
        yield sse_event("progress", {"step": 2, "total": 8, "message": _t("Commissioni", "Committees")})
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
        yield sse_event("progress", {"step": 3, "total": 8, "message": _t("Esperti", "Authoritative sources")})
        await asyncio.sleep(0)  # Flush before long retrieval operation

        # Retrieval - use sync wrapper to run in thread pool
        logger.info("[RETRIEVAL] Starting dual-channel retrieval...")
        retrieval_start = time.time()

        _chambers = ["camera", "senato"] if request.chamber == "both" else [request.chamber]

        def _do_retrieval():
            return services["retrieval"].retrieve_sync(
                query=request.query,
                top_k=100,
                chambers=_chambers,
            )

        retrieval_result = await asyncio.get_running_loop().run_in_executor(
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

        # Reuse query_embedding from retrieval result — no duplicate embed call
        query_embedding = retrieval_result["query_embedding"]

        authority_scores = {}
        authority_details = {}  # Store detailed breakdowns
        if speaker_ids:
            # Run authority scoring in parallel using ThreadPoolExecutor
            # to avoid blocking the event loop
            from concurrent.futures import ThreadPoolExecutor

            def _compute_single(sid):
                return sid, services["authority"].compute_authority(sid, query_embedding)

            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=min(10, len(speaker_ids))) as pool:
                futures = [
                    loop.run_in_executor(pool, _compute_single, sid)
                    for sid in speaker_ids
                ]
                results = await asyncio.gather(*futures)

            for sid, result in results:
                authority_scores[sid] = result["total_score"]
                authority_details[sid] = result

        # Write computed authority scores back into evidence_dicts so that the
        # generation pipeline can use real scores for per-party citation ranking.
        for d in evidence_dicts:
            sid = d.get("speaker_id", "")
            if sid in authority_scores:
                d["authority_score"] = authority_scores[sid]

        authority_time = time.time() - authority_start
        step_times["step_3_authority"] = time.time() - step_start
        logger.info(f"[TIMING] Authority scoring: {authority_time*1000:.1f}ms")
        logger.info(f"[TIMING] Step 3 (Esperti) total: {step_times['step_3_authority']*1000:.1f}ms")

        # Compute experts per coalition with detailed info
        experts = await compute_experts(
            evidence_list, authority_scores, authority_details, services["neo4j"]
        )
        maggioranza_experts = sum(1 for e in experts if e.get("coalizione") == "maggioranza")
        opposizione_experts = sum(1 for e in experts if e.get("coalizione") == "opposizione")
        logger.info(f"[EXPERTS] Found {len(experts)} experts: {maggioranza_experts} maggioranza, {opposizione_experts} opposizione")

        yield sse_event("experts", {"experts": experts})
        await asyncio.sleep(0)  # Flush

        # === Step 4: Interventi (Citations) ===
        step_start = time.time()
        yield sse_event("progress", {"step": 4, "total": 8, "message": _t("Interventi", "Speeches")})
        await asyncio.sleep(0)  # Flush

        # Build citations list for frontend (run in executor to avoid blocking)
        citations = await asyncio.get_running_loop().run_in_executor(
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
        yield sse_event("progress", {"step": 5, "total": 8, "message": _t("Statistiche", "Statistics")})
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
        yield sse_event("progress", {"step": 6, "total": 8, "message": _t("Bussola Ideologica", "Ideological Compass")})
        await asyncio.sleep(0)  # Flush

        compass_data = await asyncio.get_running_loop().run_in_executor(
            None, lambda: _compute_compass_data(services["ideology"], evidence_dicts)
        )
        logger.info(f"[COMPASS] meta={compass_data.get('meta', {})}, "
                   f"groups_count={len(compass_data.get('groups', []))}, "
                   f"axes_keys={list(compass_data.get('axes', {}).keys())}")
        if request.locale != "it":
            compass_data = await translate_compass_axes(compass_data, target_lang=request.locale)
        yield sse_event("compass", compass_data)
        await asyncio.sleep(0)  # Flush
        step_times["step_6_compass"] = time.time() - step_start
        logger.info(f"[TIMING] Step 6 (Bussola): {step_times['step_6_compass']*1000:.1f}ms")

        # === Step 7: Generazione ===
        step_start = time.time()
        yield sse_event("progress", {"step": 7, "total": 8, "message": _t("Generazione", "Generation")})
        await asyncio.sleep(0)  # Flush before long generation operation

        gen_config = get_config().load_config().get("generation", {})
        gen_mode = gen_config.get("mode", "pipeline")
        generation_start = time.time()

        if gen_mode == "direct":
            logger.info("[GENERATION] Using DirectWriter (locale=%s)", request.locale)
            writer = DirectWriter()
            generation_result = await writer.generate(
                query=request.query,
                evidence_list=evidence_dicts,
                locale=request.locale,
            )
        else:
            logger.info("[GENERATION] Starting 4-stage generation pipeline...")
            generation_result = await services["generation"].generate(
                query=request.query,
                evidence_list=evidence_dicts
            )

        generation_time = time.time() - generation_start
        logger.info(f"[TIMING] Generation: {generation_time*1000:.1f}ms (mode={gen_mode})")

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
                photo_map = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: _batch_fetch_photos(neo4j, [s for s in all_sids if s])
                )
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
                db_rows = await asyncio.get_running_loop().run_in_executor(
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

        # Translate response text if needed
        if request.locale != "it":
            final_text = await translate_response_text(final_text, target_lang=request.locale)

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
                })
                tracked_ids.add(eid)
                logger.info(f"[CITATIONS] Recovered from text scan: {eid}")

        logger.info(f"[CITATIONS] {len(gen_citations)} total citations ({len(text_evidence_ids)} in text, {len(tracked_ids)} tracked)")

        # Combine original + extra evidence for building verified citations
        all_evidence_for_verify = evidence_dicts + list(extra_evidence_map.values())
        verified_citations = await asyncio.get_running_loop().run_in_executor(
            None, lambda: _build_verified_citations(gen_citations, all_evidence_for_verify, neo4j_client=services["neo4j"])
        )
        logger.info(f"[CITATIONS] {len(verified_citations)} verified citations to send")
        if request.locale != "it":
            verified_citations = await translate_citation_batch(verified_citations, target_lang=request.locale)
        yield sse_event("citation_details", {"citations": verified_citations})
        await asyncio.sleep(0)  # Flush

        # === Patch experts: re-emit if the cited speaker differs from the top-ranked one ===
        # The pre-generation ranking may pick a different speaker than who the writer
        # actually cites. Correct the expert panel to always show the cited speaker.
        try:
            patched_experts = await patch_experts_for_cited_speakers(
                experts=experts,
                gen_citations=gen_citations,
                evidence_dicts=evidence_dicts + list(extra_evidence_map.values()),
                authority_scores=authority_scores,
                authority_details=authority_details,
                neo4j_client=services["neo4j"],
            )
            if patched_experts is not None:
                logger.info(
                    f"[EXPERTS] Post-generation patch: {sum(1 for a, b in zip(experts, patched_experts) if a.get('id') != b.get('id'))} "
                    f"expert(s) corrected to match cited speakers"
                )
                experts = patched_experts
                yield sse_event("experts", {"experts": experts})
                await asyncio.sleep(0)  # Flush
        except Exception as _patch_err:
            logger.warning(f"[EXPERTS] Post-generation patch failed (non-critical): {_patch_err}")

        # === Step 8: Valutazione (if high_quality mode) ===
        if request.mode == "high_quality":
            step_start = time.time()
            yield sse_event("progress", {"step": 8, "total": 8, "message": _t("Valutazione", "Evaluation")})
            yield sse_event("hq_variants", {
                "variants": [{"text": final_text, "score": 8.5, "is_best": True}]
            })
            step_times["step_8_valutazione"] = time.time() - step_start
            logger.info(f"[TIMING] Step 8 (Valutazione): {step_times['step_8_valutazione']*1000:.1f}ms")

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
        # Trasparenza cambio gruppo: mostra sempre se il deputato ha cambiato partito
        if e.get("party_changed") and e.get("current_party"):
            cit_data["party_changed"] = True
            cit_data["current_party"] = e["current_party"]
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
            "debate": evidence.get("debate_title", ""),
            "intervention_id": evidence.get("speech_id", ""),
            "camera_profile_url": deputy_card_map.get(speaker_id),
            "verified": True,
        }
        # Trasparenza cambio gruppo: leggi da evidence (già popolato da _process_results)
        party_changed = evidence.get("party_changed") or cit.get("party_changed", False)
        current_party = evidence.get("current_party") or cit.get("current_party")
        if party_changed and current_party:
            cit_data["party_changed"] = True
            cit_data["current_party"] = current_party
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
async def chat_endpoint(request: ChatRequest, http_request: Request):
    """
    Main chat endpoint with SSE streaming.

    Uses a background task so the pipeline continues even if the client
    disconnects (e.g. mobile browser going to background).
    The client can poll GET /api/chat/task/{task_id} to recover results.
    """
    # Read locale from Accept-Language header and inject into request
    accept_lang = http_request.headers.get("accept-language", "it")
    request.locale = "en" if "en" in accept_lang else "it"
    logger.info(f"[CHAT] Accept-Language: {accept_lang!r}, resolved locale: {request.locale}")

    store = get_task_store()

    # Cleanup expired tasks periodically
    await store.cleanup_expired()

    # Use client-provided task_id or generate one
    task_id = request.task_id or store.generate_task_id()
    await store.create_task(task_id)

    # Launch pipeline in background (runs independently of this response)
    def _on_task_done(t: asyncio.Task) -> None:
        if t.cancelled():
            logger.warning("[CHAT] Background task %s cancelled", task_id)
        elif exc := t.exception():
            logger.error("[CHAT] Background task %s failed: %s", task_id, exc, exc_info=exc)
    bg_task = asyncio.create_task(process_chat_background(request, task_id))
    bg_task.add_done_callback(_on_task_done)

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


@router.delete("/chat/task/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a running pipeline task.

    Marks the task as cancelled; the background pipeline checks this flag
    between pipeline steps and stops early, releasing the semaphore slot.
    """
    store = get_task_store()
    task = await store.get_task(task_id)

    if not task:
        # Task may have already finished — not an error, just a no-op
        return JSONResponse({"cancelled": False, "reason": "task_not_found"})

    if task.status in ("completed", "error", "cancelled"):
        return JSONResponse({"cancelled": False, "reason": task.status})

    await store.cancel_task(task_id)
    logger.info(f"[CANCEL] Task {task_id} cancellation requested via API")
    return JSONResponse({"cancelled": True})
