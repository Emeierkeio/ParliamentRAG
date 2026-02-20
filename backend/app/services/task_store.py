"""
In-memory task store for background query processing.

Decouples pipeline execution from the SSE connection so that:
- Mobile browsers can disconnect without losing results
- The frontend can poll for results after reconnection
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Task TTL: 30 minutes
TASK_TTL_SECONDS = 30 * 60


@dataclass
class TaskState:
    """State of a background query task."""
    task_id: str
    status: str = "processing"  # "processing" | "completed" | "error" | "cancelled"
    events: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    cancelled: bool = False


class TaskStore:
    """Thread-safe in-memory store for background tasks."""

    def __init__(self):
        self._tasks: Dict[str, TaskState] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    def generate_task_id(self) -> str:
        return f"task_{uuid.uuid4().hex[:12]}"

    async def create_task(self, task_id: str) -> TaskState:
        async with self._lock:
            state = TaskState(task_id=task_id)
            self._tasks[task_id] = state
            self._queues[task_id] = asyncio.Queue()
            logger.info(f"[TaskStore] Created task {task_id}")
            return state

    async def add_event(self, task_id: str, event: Dict[str, Any]):
        """Add an SSE event to the task and notify the queue."""
        async with self._lock:
            state = self._tasks.get(task_id)
            if state:
                state.events.append(event)
        queue = self._queues.get(task_id)
        if queue:
            await queue.put(event)

    async def complete_task(self, task_id: str):
        async with self._lock:
            state = self._tasks.get(task_id)
            if state:
                state.status = "completed"
                logger.info(f"[TaskStore] Task {task_id} completed with {len(state.events)} events")
        queue = self._queues.get(task_id)
        if queue:
            await queue.put(None)  # Sentinel to signal completion

    async def fail_task(self, task_id: str, error: str):
        async with self._lock:
            state = self._tasks.get(task_id)
            if state:
                state.status = "error"
                state.error_message = error
                logger.error(f"[TaskStore] Task {task_id} failed: {error}")
        queue = self._queues.get(task_id)
        if queue:
            await queue.put(None)  # Sentinel

    async def cancel_task(self, task_id: str):
        """Mark a task as cancelled and unblock any queue reader."""
        async with self._lock:
            state = self._tasks.get(task_id)
            if state:
                state.cancelled = True
                state.status = "cancelled"
                logger.info(f"[TaskStore] Task {task_id} marked as cancelled")
        queue = self._queues.get(task_id)
        if queue:
            await queue.put(None)  # Unblock stream_from_task

    def is_cancelled(self, task_id: str) -> bool:
        """Fast synchronous check — safe to call without await."""
        state = self._tasks.get(task_id)
        return state.cancelled if state else False

    async def get_task(self, task_id: str) -> Optional[TaskState]:
        async with self._lock:
            return self._tasks.get(task_id)

    def get_queue(self, task_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(task_id)

    async def cleanup_expired(self):
        """Remove tasks older than TTL."""
        now = time.time()
        async with self._lock:
            expired = [
                tid for tid, state in self._tasks.items()
                if now - state.created_at > TASK_TTL_SECONDS
            ]
            for tid in expired:
                del self._tasks[tid]
                self._queues.pop(tid, None)
            if expired:
                logger.info(f"[TaskStore] Cleaned up {len(expired)} expired tasks")


# Singleton instance
_store: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    global _store
    if _store is None:
        _store = TaskStore()
    return _store
