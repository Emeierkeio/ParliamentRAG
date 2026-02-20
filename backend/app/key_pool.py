"""
Round-robin OpenAI API key pool for rate limit distribution.

Usage:
    from .key_pool import make_client, make_async_client

    client = make_client()          # openai.OpenAI with next key
    async_client = make_async_client()  # openai.AsyncOpenAI with next key

Configuration (in .env):
    # Single key (existing behaviour):
    OPENAI_API_KEY=sk-...

    # Multiple keys (comma-separated) – each key gets its own rate limit bucket:
    OPENAI_API_KEY=sk-key1...,sk-key2...,sk-key3...

Each call to make_client / make_async_client picks the next key in the cycle,
distributing load evenly across all configured keys.
"""
import itertools
import threading
from typing import List

import openai

_lock = threading.Lock()
_keys: List[str] | None = None
_cycle = None


def _load_keys() -> List[str]:
    """Parse keys from config (supports comma-separated values)."""
    from .config import get_settings
    raw = get_settings().openai_api_key
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise ValueError("No valid OpenAI API keys found in OPENAI_API_KEY")
    return keys


def _ensure_pool() -> None:
    """Lazy-initialise pool (called under lock)."""
    global _keys, _cycle
    if _keys is None:
        _keys = _load_keys()
        _cycle = itertools.cycle(_keys)


def next_key() -> str:
    """Return the next API key in round-robin order (thread-safe)."""
    global _cycle
    with _lock:
        _ensure_pool()
        return next(_cycle)  # type: ignore[arg-type]


def key_count() -> int:
    """Return the number of configured keys."""
    with _lock:
        _ensure_pool()
        return len(_keys)  # type: ignore[arg-type]


def make_client(**kwargs) -> openai.OpenAI:
    """Create a synchronous OpenAI client with the next round-robin key."""
    return openai.OpenAI(api_key=next_key(), **kwargs)


def make_async_client(**kwargs) -> openai.AsyncOpenAI:
    """Create an async OpenAI client with the next round-robin key."""
    return openai.AsyncOpenAI(api_key=next_key(), **kwargs)
