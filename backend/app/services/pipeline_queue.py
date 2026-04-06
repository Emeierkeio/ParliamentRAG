"""
Unified pipeline concurrency queue.

Single source of truth for pipeline slot management. Replaces the scattered
semaphore + counter + list approach with an atomic queue that eliminates
race conditions between state checks and mutations.

Usage:
    queue = get_pipeline_queue()

    # Acquire with queue position updates
    acquired = await queue.acquire(task_id, emit_fn)
    if not acquired:
        # timed out
        return

    try:
        await run_pipeline(...)
    finally:
        queue.release(task_id)
"""
import asyncio
import logging
import os
from collections import OrderedDict
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

_MAX_SLOTS = int(
    os.environ.get(
        "MAX_CONCURRENT_CHAT_PIPELINES",
        os.environ.get("MAX_CONCURRENT_PIPELINES", "5"),
    )
)


class PipelineQueue:
    """Thread-safe pipeline concurrency manager.

    All state mutations happen under a single asyncio.Lock, eliminating
    TOCTOU race conditions between checking availability and acquiring.
    """

    def __init__(self, max_slots: int = _MAX_SLOTS):
        self._max_slots = max_slots
        self._lock = asyncio.Lock()
        # Tasks currently running
        self._active: set[str] = set()
        # Tasks waiting, in FIFO order. Value is an Event signaled when a slot opens.
        self._waiting: OrderedDict[str, asyncio.Event] = OrderedDict()

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def waiting_count(self) -> int:
        return len(self._waiting)

    @property
    def max_slots(self) -> int:
        return self._max_slots

    def _position_of(self, task_id: str) -> int:
        """1-indexed position in the waiting queue. 0 if not waiting."""
        for i, tid in enumerate(self._waiting, 1):
            if tid == task_id:
                return i
        return 0

    async def acquire(
        self,
        task_id: str,
        emit_fn: Optional[Callable[..., Coroutine]] = None,
        max_wait: int = 300,
        check_every: int = 10,
    ) -> bool:
        """Acquire a pipeline slot.

        If a slot is available, returns immediately. Otherwise queues the task
        and sends periodic position updates via emit_fn.

        Returns True if acquired, False if timed out.
        """
        # Fast path: try to acquire immediately (atomic check + acquire)
        async with self._lock:
            if len(self._active) < self._max_slots:
                self._active.add(task_id)
                logger.info(
                    "[QUEUE] %s acquired immediately (active=%d/%d)",
                    task_id, len(self._active), self._max_slots,
                )
                return True

            # Slow path: register in waiting queue
            ready_event = asyncio.Event()
            self._waiting[task_id] = ready_event
            position = len(self._waiting)
            active_now = len(self._active)

        logger.info(
            "[QUEUE] %s queued (position=%d, active=%d/%d)",
            task_id, position, active_now, self._max_slots,
        )

        # Send initial waiting event
        if emit_fn:
            await emit_fn("waiting", {
                "queue_position": position,
                "ahead_count": position - 1,
                "active_count": active_now,
                "elapsed_seconds": 0,
            })

        # Wait for our turn with periodic position updates
        elapsed = 0
        try:
            while elapsed < max_wait:
                try:
                    await asyncio.wait_for(ready_event.wait(), timeout=check_every)
                    # Event was set — a slot opened for us
                    async with self._lock:
                        self._waiting.pop(task_id, None)
                        self._active.add(task_id)
                        logger.info(
                            "[QUEUE] %s acquired after %ds (active=%d/%d, waiting=%d)",
                            task_id, elapsed, len(self._active),
                            self._max_slots, len(self._waiting),
                        )
                    return True

                except asyncio.TimeoutError:
                    elapsed += check_every
                    async with self._lock:
                        position = self._position_of(task_id)
                        active_now = len(self._active)

                    if emit_fn:
                        await emit_fn("waiting", {
                            "queue_position": position,
                            "ahead_count": max(0, position - 1),
                            "active_count": active_now,
                            "elapsed_seconds": elapsed,
                        })
                    logger.debug(
                        "[QUEUE] %s still waiting (%ds, pos=%d, active=%d)",
                        task_id, elapsed, position, active_now,
                    )

            # Timed out
            logger.warning("[QUEUE] %s timed out after %ds", task_id, max_wait)
            return False

        finally:
            # Clean up if we didn't acquire (timeout or error)
            async with self._lock:
                self._waiting.pop(task_id, None)

    def release(self, task_id: str) -> None:
        """Release a pipeline slot and wake the next waiting task.

        Synchronous because it only touches internal state; the Event.set()
        wakes the waiting coroutine in its own asyncio context.
        """
        self._active.discard(task_id)

        # Wake the first waiting task (FIFO)
        if self._waiting:
            next_tid, next_event = next(iter(self._waiting.items()))
            next_event.set()
            logger.info(
                "[QUEUE] %s released → waking %s (active=%d, waiting=%d)",
                task_id, next_tid, len(self._active), len(self._waiting),
            )
        else:
            logger.info(
                "[QUEUE] %s released (active=%d, no waiters)",
                task_id, len(self._active),
            )

    def status(self) -> dict[str, Any]:
        """Current queue status for monitoring."""
        return {
            "max_slots": self._max_slots,
            "active": len(self._active),
            "waiting": len(self._waiting),
            "active_tasks": list(self._active),
            "waiting_tasks": list(self._waiting.keys()),
        }


# Singleton
_queue: Optional[PipelineQueue] = None


def get_pipeline_queue() -> PipelineQueue:
    global _queue
    if _queue is None:
        _queue = PipelineQueue()
    return _queue
