"""
Per-query recorder of LLM calls.

A ContextVar activated at pipeline start collects every OpenAI call
(chat + embeddings) made during the query: model, duration, tokens,
prompt and response previews. The key_pool clients are wrapped only
once; the wrapper consults the ContextVar on every call, so outside a
recorded query it is a pure passthrough.

It propagates through awaits and, thanks to ContextPropagatingExecutor
(the loop's default executor), also into run_in_executor. Thread pools
created ad hoc in individual modules stay out.

Previews are truncated (_PREVIEW_CHARS) to keep the trace payload in
the tens of KB: enough to understand what each call did, not a full
dump of the prompts.
"""
import contextvars
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PREVIEW_CHARS = 600

# USD per 1M tokens (input, output) — OpenAI price list, only for the cost
# estimate shown in the trace panel. Prefix-match on the model name.
_PRICES_PER_MTOK = {
    "gpt-4o": (2.5, 10.0),
    "gpt-4.1-mini": (0.4, 1.6),
    "gpt-4.1-nano": (0.1, 0.4),
    "gpt-4.1": (2.0, 8.0),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def _estimate_cost(model: Optional[str], prompt_tokens, completion_tokens) -> Optional[float]:
    if not model:
        return None
    for prefix, (in_price, out_price) in _PRICES_PER_MTOK.items():
        if model.startswith(prefix):
            return round(
                (prompt_tokens or 0) / 1e6 * in_price
                + (completion_tokens or 0) / 1e6 * out_price,
                6,
            )
    return None

_recorder_var: contextvars.ContextVar[Optional["LlmCallRecorder"]] = contextvars.ContextVar(
    "llm_recorder", default=None
)

# Stage label for attributing calls in the trace: with the compass running
# in parallel with generation the time windows overlap, so the explicit tag
# beats inference by offset.
_stage_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "llm_stage", default=None
)


def set_llm_stage(stage: Optional[str]) -> None:
    """Tag this context's upcoming LLM calls with the given stage."""
    _stage_var.set(stage)


class LlmCallRecorder:
    """Collect the LLM calls of a single query."""

    def __init__(self):
        self.t0 = time.perf_counter()
        self.calls: List[Dict[str, Any]] = []

    def sorted_calls(self) -> List[Dict[str, Any]]:
        return sorted(self.calls, key=lambda c: c.get("t_offset_ms", 0))

    def totals(self) -> Dict[str, Any]:
        prompt = sum((c.get("tokens") or {}).get("prompt") or 0 for c in self.calls)
        completion = sum((c.get("tokens") or {}).get("completion") or 0 for c in self.calls)
        cost = sum(c.get("cost_usd") or 0 for c in self.calls)
        return {
            "calls": len(self.calls),
            "chat_calls": sum(1 for c in self.calls if c.get("endpoint") == "chat"),
            "embedding_calls": sum(1 for c in self.calls if c.get("endpoint") == "embeddings"),
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "cost_usd": round(cost, 4),
        }


def start_recording() -> LlmCallRecorder:
    """Activate a recorder in the current context and return it."""
    rec = LlmCallRecorder()
    _recorder_var.set(rec)
    return rec


def _preview(text: Any, limit: int = _PREVIEW_CHARS) -> str:
    if not isinstance(text, str):
        text = str(text)
    return text[:limit] + ("…" if len(text) > limit else "")


def _record_chat(rec, kwargs, response, t_start, duration_ms, error=None) -> None:
    messages = kwargs.get("messages") or []
    entry: Dict[str, Any] = {
        "endpoint": "chat",
        "model": kwargs.get("model"),
        "t_offset_ms": round((t_start - rec.t0) * 1000, 1),
        "duration_ms": round(duration_ms, 1),
        "temperature": kwargs.get("temperature"),
        "messages": [
            {
                "role": m.get("role"),
                "chars": len(m.get("content") or ""),
                "preview": _preview(m.get("content") or ""),
            }
            for m in messages
            if isinstance(m, dict)
        ],
    }
    stage = _stage_var.get()
    if stage:
        entry["stage"] = stage
    if error is not None:
        entry["error"] = _preview(str(error), 300)
    elif response is not None:
        usage = getattr(response, "usage", None)
        if usage is not None:
            entry["tokens"] = {
                "prompt": getattr(usage, "prompt_tokens", None),
                "completion": getattr(usage, "completion_tokens", None),
                "total": getattr(usage, "total_tokens", None),
            }
            # OpenAI automatic prompt caching: how many prompt tokens were
            # cached (repeated prefixes >=1024 tokens, discounted 50%)
            details = getattr(usage, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", None) if details else None
            if cached:
                entry["tokens"]["cached"] = cached
            entry["cost_usd"] = _estimate_cost(
                entry.get("model"),
                entry["tokens"]["prompt"],
                entry["tokens"]["completion"],
            )
        choices = getattr(response, "choices", None) or []
        if choices:
            msg = getattr(choices[0], "message", None)
            content = getattr(msg, "content", None) if msg is not None else None
            entry["response_chars"] = len(content or "")
            entry["response_preview"] = _preview(content or "")
            entry["finish_reason"] = getattr(choices[0], "finish_reason", None)
    rec.calls.append(entry)


def _record_embeddings(rec, kwargs, response, t_start, duration_ms, error=None) -> None:
    raw_input = kwargs.get("input")
    if isinstance(raw_input, str):
        n_inputs, sample = 1, raw_input
    elif isinstance(raw_input, (list, tuple)):
        n_inputs = len(raw_input)
        sample = raw_input[0] if raw_input and isinstance(raw_input[0], str) else ""
    else:
        n_inputs, sample = 0, ""
    entry: Dict[str, Any] = {
        "endpoint": "embeddings",
        "model": kwargs.get("model"),
        "t_offset_ms": round((t_start - rec.t0) * 1000, 1),
        "duration_ms": round(duration_ms, 1),
        "inputs": n_inputs,
        "input_preview": _preview(sample, 200),
    }
    stage = _stage_var.get()
    if stage:
        entry["stage"] = stage
    if error is not None:
        entry["error"] = _preview(str(error), 300)
    elif response is not None:
        usage = getattr(response, "usage", None)
        if usage is not None:
            entry["tokens"] = {
                "prompt": getattr(usage, "prompt_tokens", None),
                "completion": 0,
                "total": getattr(usage, "total_tokens", None),
            }
            entry["cost_usd"] = _estimate_cost(entry.get("model"), entry["tokens"]["prompt"], 0)
    rec.calls.append(entry)


def wrap_recording(client):
    """
    Wrap chat.completions.create and embeddings.create of an OpenAI client
    (sync or async) to record calls in the active recorder.
    Apply after the LangSmith wrapper, so it measures the total time as
    perceived by the pipeline.
    """
    import openai

    orig_chat = client.chat.completions.create
    orig_emb = client.embeddings.create

    if isinstance(client, openai.AsyncOpenAI):

        async def chat_create(*args, **kwargs):
            rec = _recorder_var.get()
            if rec is None:
                return await orig_chat(*args, **kwargs)
            t_start = time.perf_counter()
            try:
                resp = await orig_chat(*args, **kwargs)
            except Exception as e:
                _record_chat(rec, kwargs, None, t_start, (time.perf_counter() - t_start) * 1000, error=e)
                raise
            _record_chat(rec, kwargs, resp, t_start, (time.perf_counter() - t_start) * 1000)
            return resp

        async def emb_create(*args, **kwargs):
            rec = _recorder_var.get()
            if rec is None:
                return await orig_emb(*args, **kwargs)
            t_start = time.perf_counter()
            try:
                resp = await orig_emb(*args, **kwargs)
            except Exception as e:
                _record_embeddings(rec, kwargs, None, t_start, (time.perf_counter() - t_start) * 1000, error=e)
                raise
            _record_embeddings(rec, kwargs, resp, t_start, (time.perf_counter() - t_start) * 1000)
            return resp

    else:

        def chat_create(*args, **kwargs):
            rec = _recorder_var.get()
            if rec is None:
                return orig_chat(*args, **kwargs)
            t_start = time.perf_counter()
            try:
                resp = orig_chat(*args, **kwargs)
            except Exception as e:
                _record_chat(rec, kwargs, None, t_start, (time.perf_counter() - t_start) * 1000, error=e)
                raise
            _record_chat(rec, kwargs, resp, t_start, (time.perf_counter() - t_start) * 1000)
            return resp

        def emb_create(*args, **kwargs):
            rec = _recorder_var.get()
            if rec is None:
                return orig_emb(*args, **kwargs)
            t_start = time.perf_counter()
            try:
                resp = orig_emb(*args, **kwargs)
            except Exception as e:
                _record_embeddings(rec, kwargs, None, t_start, (time.perf_counter() - t_start) * 1000, error=e)
                raise
            _record_embeddings(rec, kwargs, resp, t_start, (time.perf_counter() - t_start) * 1000)
            return resp

    client.chat.completions.create = chat_create
    client.embeddings.create = emb_create
    return client
