"""Response cache, in-flight deduplication and queue-slot regression tests.

Covers the ten cache acceptance cases plus the MAX_CONCURRENT_PIPELINES=1
queue scenario (A processing, B waiting #1, C waiting #2) at unit level:
the same _acquire_pipeline_slot the endpoint uses, with a local semaphore.
"""
import asyncio
import json
import time

from app.services.response_cache import (
    InFlightRegistry,
    InMemoryCacheBackend,
    ResponseCache,
    build_cache_key,
    filter_cacheable_events,
    normalize_query,
)
from app.services.task_store import TaskStore


COMPLETE_EVENTS = [
    {"type": "experts", "data": [{"id": "dep1", "authority_score": 0.8}]},
    {"type": "citations", "data": [{"chunk_id": "leg19_a_chunk_1", "quote_text": "testo"}]},
    {"type": "compass", "data": {"groups": [{"group_id": "FdI"}]}},
    {"type": "chunk", "data": "## Introduzione\n\nTesto della risposta."},
    {"type": "citation_details", "citations": [
        {"chunk_id": "leg19_a_chunk_1", "deputy_last_name": "Rossi", "verified": True}
    ]},
    {"type": "trace", "trace": {"total_ms": 42000}},
    {"type": "complete", "metadata": {"total_results": 1}},
]

TRANSIENT_EVENTS = [
    {"type": "waiting", "queue_position": 1, "ahead_count": 0},
    {"type": "progress", "step": 1, "total": 8, "message": "Analisi query"},
    {"type": "step_result", "step": 2, "detail": "Commissione"},
]


def _key(**overrides):
    base = dict(
        query="Legge elettorale",
        locale="it",
        mode="standard",
        data_version="2026-09-18",
        config_fingerprint="abc123",
    )
    base.update(overrides)
    return build_cache_key(**base)


def _cache(ttl=60.0):
    return ResponseCache(backend=InMemoryCacheBackend(max_entries=8), enabled=True, ttl_seconds=ttl)


class TestCacheKey:
    def test_normalization_makes_equivalent_queries_identical(self):
        assert normalize_query("  Legge   ELETTORALE? ") == normalize_query("legge elettorale")
        assert _key(query="LEGGE  ELETTORALE?") == _key(query="legge elettorale")

    def test_different_query_different_key(self):
        assert _key(query="salario minimo") != _key()

    def test_different_data_version_different_key(self):
        assert _key(data_version="2026-09-19") != _key()

    def test_different_pipeline_version_different_key(self):
        assert _key(pipeline_version="9999.9") != _key()

    def test_locale_mode_and_config_in_key(self):
        assert _key(locale="en") != _key()
        assert _key(mode="high_quality") != _key()
        assert _key(config_fingerprint="other") != _key()


class TestResponseCache:
    def test_first_lookup_is_miss(self):
        cache = _cache()
        assert asyncio.run(cache.lookup(_key())) is None

    def test_store_then_hit_returns_identical_events(self):
        cache = _cache()

        async def scenario():
            await cache.store(_key(), TRANSIENT_EVENTS + COMPLETE_EVENTS)
            return await cache.lookup(_key())

        cached = asyncio.run(scenario())
        # A hit is announced by a replay-time `cached` marker; after it,
        # citations, compass, trace and metadata survive byte-identical
        # and transient queue/progress events never enter the cache.
        assert cached[0]["type"] == "cached"
        assert cached[0]["generated_at"]
        assert cached[1:] == COMPLETE_EVENTS

    def test_expired_entry_is_miss(self):
        cache = _cache(ttl=0.05)

        async def scenario():
            await cache.store(_key(), COMPLETE_EVENTS)
            await asyncio.sleep(0.1)
            return await cache.lookup(_key())

        assert asyncio.run(scenario()) is None

    def test_incomplete_run_is_not_stored(self):
        cache = _cache()

        async def scenario():
            await cache.store(_key(), TRANSIENT_EVENTS)  # no "complete" event
            return await cache.lookup(_key())

        assert asyncio.run(scenario()) is None

    def test_filter_drops_only_transient_events(self):
        filtered = filter_cacheable_events(TRANSIENT_EVENTS + COMPLETE_EVENTS)
        assert filtered == COMPLETE_EVENTS


class TestInFlightDeduplication:
    def test_concurrent_identical_claims_have_one_leader(self):
        registry = InFlightRegistry()

        async def scenario():
            results = await asyncio.gather(
                registry.claim("k", "task_A"),
                registry.claim("k", "task_B"),
                registry.claim("k", "task_C"),
            )
            return results

        results = asyncio.run(scenario())
        leaders = [r for r in results if r is None]
        followers = [r for r in results if r is not None]
        assert len(leaders) == 1
        assert followers == ["task_A", "task_A"]

    def test_release_frees_the_key(self):
        registry = InFlightRegistry()

        async def scenario():
            assert await registry.claim("k", "task_A") is None
            await registry.release("k", "task_B")  # non-leader: no-op
            assert await registry.claim("k", "task_X") == "task_A"
            await registry.release("k", "task_A")
            return await registry.claim("k", "task_B")

        assert asyncio.run(scenario()) is None

    def test_followers_receive_the_leader_result(self):
        # A, B, C same query: one pipeline (leader), B and C mirror its
        # events and complete when it completes.
        from app.services.response_cache import mirror_task

        async def scenario():
            store = TaskStore()
            import app.services.task_store as task_store_module
            original = task_store_module._store
            task_store_module._store = store
            try:
                await store.create_task("leader")
                await store.create_task("follower")
                mirror = asyncio.create_task(
                    mirror_task("follower", "leader", poll_interval=0.02)
                )
                for event in COMPLETE_EVENTS:
                    await store.add_event("leader", event)
                await store.complete_task("leader")
                await asyncio.wait_for(mirror, timeout=2)
                follower = await store.get_task("follower")
                return follower
            finally:
                task_store_module._store = original

        follower = asyncio.run(scenario())
        assert follower.status == "completed"
        assert follower.events == COMPLETE_EVENTS


class TestCacheHitPath:
    def test_replay_creates_no_queue_entry_and_no_pipeline(self):
        # Cache hit: the task is filled by replay only — the waiting queue
        # stays untouched and the task completes with exactly the cached
        # events (citations and metadata included).
        import app.routers.chat as chat_router
        from app.services.response_cache import replay_into_task
        import app.services.task_store as task_store_module

        async def scenario():
            store = TaskStore()
            original = task_store_module._store
            task_store_module._store = store
            chat_router._waiting_queue.clear()
            try:
                await store.create_task("hit_task")
                await replay_into_task("hit_task", COMPLETE_EVENTS)
                state = await store.get_task("hit_task")
                return state, list(chat_router._waiting_queue)
            finally:
                task_store_module._store = original

        state, waiting = asyncio.run(scenario())
        assert waiting == []
        assert state.status == "completed"
        assert state.events == COMPLETE_EVENTS
        # No waiting/progress event reaches the frontend on a hit
        assert all(e["type"] not in ("waiting", "progress") for e in state.events)


class TestQueryEndpointCacheHit:
    def test_stream_serves_cached_events_without_pipeline(self):
        # /api/query is the router the frontend actually calls: a HIT must
        # stream the stored events verbatim, without touching the pipeline
        # (which would blow up here — no LLM, no Neo4j mocked).
        import app.services.response_cache as rc
        import app.services.task_store as tsm
        from app.routers.query import _rate_limited_query, QueryRequest
        from app.config import get_config

        async def scenario():
            original_cache = rc._response_cache
            original_dv = rc._data_version_cache
            original_store = tsm._store
            rc._response_cache = ResponseCache(
                backend=InMemoryCacheBackend(), enabled=True, ttl_seconds=60
            )
            rc._data_version_cache = (time.monotonic(), "vtest")
            tsm._store = TaskStore()
            try:
                key = rc.build_cache_key(
                    query="Legge elettorale",
                    locale="it",
                    mode="standard",
                    data_version="vtest",
                    config_fingerprint=rc.config_fingerprint(
                        get_config().load_config()
                    ),
                    extra={"top_k": 100, "date_start": None, "date_end": None},
                )
                await rc._response_cache.store(key, COMPLETE_EVENTS)

                lines = []
                async for line in _rate_limited_query(
                    QueryRequest(query="Legge elettorale"), None
                ):
                    lines.append(line)
                return lines
            finally:
                rc._response_cache = original_cache
                rc._data_version_cache = original_dv
                tsm._store = original_store

        lines = asyncio.run(scenario())
        payloads = [
            json.loads(line.split("data: ", 1)[1])
            for line in lines if line.startswith("data: ")
        ]
        assert payloads[0]["type"] == "cached"
        assert payloads[1:] == COMPLETE_EVENTS


class TestQueueSlots:
    def test_positions_progress_with_single_slot(self):
        # MAX_CONCURRENT_PIPELINES=1 scenario: A processing, B waiting #1,
        # C waiting #2; positions and counters stay coherent as the queue
        # advances.
        import app.routers.chat as chat_router

        async def scenario():
            chat_router._waiting_queue.clear()
            chat_router._pipeline_active = 0
            sem = asyncio.Semaphore(1)
            events = {"A": [], "B": [], "C": []}

            def emitter(name):
                async def emit(event_type, data):
                    events[name].append({"type": event_type, **data})
                return emit

            async def release_slot():
                async with chat_router._get_counter_lock():
                    chat_router._pipeline_active = max(0, chat_router._pipeline_active - 1)
                sem.release()

            # A: fast path, no queue entry
            assert await chat_router._acquire_pipeline_slot(
                sem, emitter("A"), "A", max_wait=5, check_every=0.05)
            assert events["A"] == []

            # B and C: queued in order
            b = asyncio.create_task(chat_router._acquire_pipeline_slot(
                sem, emitter("B"), "B", max_wait=5, check_every=0.05))
            await asyncio.sleep(0.02)
            c = asyncio.create_task(chat_router._acquire_pipeline_slot(
                sem, emitter("C"), "C", max_wait=5, check_every=0.05))
            await asyncio.sleep(0.02)

            assert events["B"][0]["queue_position"] == 1
            assert events["B"][0]["ahead_count"] == 0
            assert events["B"][0]["active_count"] == 1
            assert events["C"][0]["queue_position"] == 2
            assert events["C"][0]["ahead_count"] == 1
            assert events["C"][0]["elapsed_seconds"] == 0

            # A finishes: B acquires, C advances to the front
            await release_slot()
            assert await asyncio.wait_for(b, timeout=2)
            await asyncio.sleep(0.12)  # let C's periodic update fire
            c_last = events["C"][-1]
            assert c_last["queue_position"] == 1
            assert c_last["ahead_count"] == 0
            assert c_last["elapsed_seconds"] > 0

            # B finishes: C acquires
            await release_slot()
            assert await asyncio.wait_for(c, timeout=2)
            assert chat_router._waiting_queue == []
            await release_slot()

        asyncio.run(scenario())
