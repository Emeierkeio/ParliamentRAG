"""Response cache and in-flight deduplication for the chat pipeline.

The cache stores the ordered list of SSE events a completed pipeline run
produced (minus transient queue/progress events), keyed by a versioned
fingerprint of the request. A hit replays those events into a fresh task:
the frontend sees a normally-completed response, with no queue entry and
no pipeline run. Disabled by default (RESPONSE_CACHE_ENABLED).

The key includes the data version (SchemaMeta.updated_at, or the newest
Session date) and a pipeline/config fingerprint, so a `make update-data`
or a prompt/config change logically invalidates old entries without any
explicit purge. When the data version cannot be determined the cache is
bypassed entirely: serving possibly-stale answers is worse than a miss.

Storage is behind CacheBackend so a Redis implementation can replace the
in-memory LRU without touching the business logic in routers/chat.py.
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Bump when the pipeline output shape or behavior changes in a way that
# makes previously cached responses misleading (prompt overhauls, new SSE
# events, integrator mode changes).
PIPELINE_VERSION = "2026-09-19.1"

# Corpus identity: the whole deployment serves one chamber/legislature.
LEGISLATURE = "leg19"

# Transient events never worth replaying: queue state and step progress
# belong to the run that produced them, not to the answer. The `cached`
# marker is minted per-replay by lookup() and must never be persisted.
NON_CACHEABLE_EVENT_TYPES = {"waiting", "progress", "step_result", "cached"}


def normalize_query(query: str) -> str:
    """Collapse the query to its cache identity (case/whitespace-insensitive)."""
    normalized = re.sub(r"\s+", " ", query.strip().lower())
    return normalized.rstrip(" ?!.")


def build_cache_key(
    *,
    query: str,
    locale: str,
    mode: str,
    data_version: str,
    pipeline_version: str = PIPELINE_VERSION,
    config_fingerprint: str = "",
    legislature: str = LEGISLATURE,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Versioned cache key: same answer only if every dimension matches.

    `extra` carries endpoint-specific request parameters that change the
    answer (e.g. top_k, date filters on /api/query).
    """
    payload = json.dumps(
        {
            "q": normalize_query(query),
            "locale": locale,
            "mode": mode,
            "legislature": legislature,
            "data_version": data_version,
            "pipeline_version": pipeline_version,
            "config": config_fingerprint,
            "extra": extra or {},
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def config_fingerprint(config_data: Dict[str, Any]) -> str:
    """Fingerprint of the config slices that change the answer.

    Models, integrator mode and coherence thresholds shape the generated
    text; merger weights shape the evidence pool. Anything else (UI,
    logging) is irrelevant to cache identity.
    """
    relevant = {
        "generation": config_data.get("generation", {}),
        "citation": config_data.get("citation", {}),
        "retrieval": config_data.get("retrieval", {}),
        "authority": config_data.get("authority", {}),
    }
    payload = json.dumps(relevant, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def filter_cacheable_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop transient events; keep everything the frontend needs to render."""
    return [e for e in events if e.get("type") not in NON_CACHEABLE_EVENT_TYPES]


class CacheBackend(ABC):
    """Minimal async KV contract so Redis can slot in behind ResponseCache."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Return the stored value, or None when absent or expired."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Store value under key with the given time-to-live."""


class InMemoryCacheBackend(CacheBackend):
    """LRU + TTL cache for a single-process deployment.

    Values are held by reference: callers must treat cached events as
    immutable (the replay path only reads them).
    """

    def __init__(self, max_entries: int = 512):
        self._max_entries = max_entries
        self._entries: "OrderedDict[str, tuple]" = OrderedDict()  # key -> (expires_at, value)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._entries[key]
                logger.info("[RESPONSE_CACHE] CACHE_EXPIRED key=%s", key[:16])
                return None
            self._entries.move_to_end(key)
            return value

    async def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        async with self._lock:
            self._entries[key] = (time.monotonic() + ttl_seconds, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                evicted, _ = self._entries.popitem(last=False)
                logger.info("[RESPONSE_CACHE] evicted LRU key=%s", evicted[:16])


class ResponseCache:
    """Business-logic wrapper: enabled flag, TTL, structured logging."""

    def __init__(
        self,
        backend: Optional[CacheBackend] = None,
        enabled: Optional[bool] = None,
        ttl_seconds: Optional[float] = None,
    ):
        if enabled is None:
            enabled = os.environ.get("RESPONSE_CACHE_ENABLED", "false").lower() in (
                "1", "true", "yes",
            )
        if ttl_seconds is None:
            ttl_seconds = float(os.environ.get("RESPONSE_CACHE_TTL_SECONDS", "21600"))
        max_entries = int(os.environ.get("RESPONSE_CACHE_MAX_ENTRIES", "512"))

        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self._backend = backend or InMemoryCacheBackend(max_entries=max_entries)

    async def lookup(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Return cached events for key, logging hit/miss.

        A hit is prepended with a `cached` marker event carrying the
        original generation timestamp, so the frontend can tell an instant
        archive replay apart from a live pipeline run and explain it.
        """
        value = await self._backend.get(key)
        if value is not None:
            events = value["events"]
            marker = {
                "type": "cached",
                "generated_at": datetime.fromtimestamp(
                    value["stored_at"], tz=timezone.utc
                ).isoformat(),
            }
            logger.info(
                "[RESPONSE_CACHE] CACHE_HIT key=%s events=%d", key[:16], len(events)
            )
            return [marker, *events]
        logger.info("[RESPONSE_CACHE] CACHE_MISS key=%s", key[:16])
        return None

    async def store(self, key: str, events: List[Dict[str, Any]]) -> None:
        """Store the cacheable subset of a completed run's events."""
        cacheable = filter_cacheable_events(events)
        if not any(e.get("type") == "complete" for e in cacheable):
            logger.warning(
                "[RESPONSE_CACHE] refusing to store incomplete run key=%s", key[:16]
            )
            return
        entry = {"stored_at": time.time(), "events": cacheable}
        await self._backend.set(key, entry, self.ttl_seconds)
        logger.info(
            "[RESPONSE_CACHE] CACHE_STORE key=%s events=%d ttl=%.0fs",
            key[:16], len(cacheable), self.ttl_seconds,
        )


class InFlightRegistry:
    """Single-flight registry: one pipeline per cache key at a time.

    claim() is atomic under an asyncio.Lock (single event loop), so two
    simultaneous identical requests cannot both become leaders.
    """

    def __init__(self):
        self._leaders: Dict[str, str] = {}  # cache_key -> leader task_id
        self._lock = asyncio.Lock()

    async def claim(self, key: str, task_id: str) -> Optional[str]:
        """Claim leadership for key.

        Returns None when task_id becomes the leader (caller runs the
        pipeline), or the existing leader's task_id (caller joins it).
        """
        async with self._lock:
            leader = self._leaders.get(key)
            if leader is not None:
                logger.info(
                    "[RESPONSE_CACHE] INFLIGHT_JOIN key=%s leader=%s follower=%s",
                    key[:16], leader, task_id,
                )
                return leader
            self._leaders[key] = task_id
            return None

    async def release(self, key: str, task_id: str) -> None:
        """Release leadership; only the current leader can release."""
        async with self._lock:
            if self._leaders.get(key) == task_id:
                del self._leaders[key]


# Data-version anchor, refreshed at most every 10 minutes: it moves only at
# `make update-data` (SchemaMeta.updated_at), so a short in-process cache
# avoids one Neo4j round-trip per chat request.
_DATA_VERSION_TTL_S = 600
_data_version_cache: tuple = (0.0, None)  # (monotonic timestamp, version)


async def get_data_version() -> Optional[str]:
    """Return the corpus data version, or None (→ cache bypass) on failure."""
    global _data_version_cache
    now = time.monotonic()
    ts, cached = _data_version_cache
    if cached is not None and now - ts < _DATA_VERSION_TTL_S:
        return cached

    def _query():
        from .deps import get_services
        return get_services()["neo4j"].query(
            "OPTIONAL MATCH (m:SchemaMeta {id: 'singleton'}) "
            "WITH m.updated_at AS stamped "
            "OPTIONAL MATCH (s:Session) "
            "WITH stamped, max(s.date) AS newest "
            "RETURN coalesce(toString(stamped), toString(newest)) AS v"
        )

    try:
        rows = await asyncio.get_running_loop().run_in_executor(None, _query)
        version = rows[0]["v"] if rows and rows[0].get("v") else None
    except Exception as e:
        logger.warning("[RESPONSE_CACHE] data version lookup failed: %s", e)
        version = None
    if version:
        _data_version_cache = (now, version)
    return version


async def replay_into_task(task_id: str, events: List[Dict[str, Any]]):
    """Replay a cached run into a fresh task: instant, no queue, no pipeline."""
    from .task_store import get_task_store
    store = get_task_store()
    for event in events:
        await store.add_event(task_id, event)
    await store.complete_task(task_id)


async def mirror_task(
    follower_id: str,
    leader_id: str,
    locale: str = "it",
    poll_interval: float = 0.25,
    max_wait: float = 900.0,
):
    """Forward a running leader task's events to a follower task.

    In-flight deduplication: identical concurrent requests share one
    pipeline. The TaskStore queue has a single consumer, so followers
    mirror the leader's persisted event list instead of reading its queue.
    """
    from .task_store import get_task_store
    store = get_task_store()
    forwarded = 0
    waited = 0.0
    leader = await store.get_task(leader_id)
    while leader is not None and waited <= max_wait:
        for event in leader.events[forwarded:]:
            await store.add_event(follower_id, event)
        forwarded = len(leader.events)
        if leader.status != "processing":
            break
        await asyncio.sleep(poll_interval)
        waited += poll_interval
        leader = await store.get_task(leader_id)

    if leader is None or leader.status == "processing":
        msg = (
            "L'analisi condivisa non è più disponibile. Riprova."
            if locale == "it"
            else "The shared analysis is no longer available. Please retry."
        )
        await store.add_event(follower_id, {"type": "error", "message": msg})
        await store.fail_task(follower_id, "inflight leader unavailable")
        return

    # Forward any tail emitted between the last poll and the status flip
    for event in leader.events[forwarded:]:
        await store.add_event(follower_id, event)

    if leader.status == "completed":
        await store.complete_task(follower_id)
    elif leader.status == "cancelled":
        msg = (
            "L'analisi è stata interrotta. Riprova."
            if locale == "it"
            else "The analysis was interrupted. Please retry."
        )
        await store.add_event(follower_id, {"type": "error", "message": msg})
        await store.fail_task(follower_id, "inflight leader cancelled")
    else:
        await store.fail_task(follower_id, leader.error_message or "inflight leader failed")


_response_cache: Optional[ResponseCache] = None
_inflight_registry: Optional[InFlightRegistry] = None


def get_response_cache() -> ResponseCache:
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache()
    return _response_cache


def get_inflight_registry() -> InFlightRegistry:
    global _inflight_registry
    if _inflight_registry is None:
        _inflight_registry = InFlightRegistry()
    return _inflight_registry
