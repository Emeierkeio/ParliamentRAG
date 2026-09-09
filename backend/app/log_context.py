"""
Per-query correlation ID in logs.

query_id_var is a ContextVar: it propagates by itself through the awaits of
the same task, so everything the pipeline does in async inherits the id.
It does NOT cross threads: that is why the lifespan installs
ContextPropagatingExecutor as the loop's default executor, so that
run_in_executor(None, ...) calls (retrieval, authority, compass) keep the id
too. ThreadPoolExecutors created ad hoc in individual modules stay out:
their logs show "-".
"""
import contextvars
import functools
import uuid
from concurrent.futures import ThreadPoolExecutor

query_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "query_id", default="-"
)


def new_query_id() -> str:
    """Generate and activate a short id for the current query."""
    qid = uuid.uuid4().hex[:6]
    query_id_var.set(qid)
    return qid


class ContextPropagatingExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor that runs each task in the caller's context."""

    def submit(self, fn, /, *args, **kwargs):
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, functools.partial(fn, *args, **kwargs))
