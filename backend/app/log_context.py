"""
Correlation ID per query nei log.

query_id_var è un ContextVar: si propaga da solo attraverso gli await dello
stesso task, quindi tutto ciò che la pipeline fa in async eredita l'id.
NON attraversa i thread: per questo il lifespan installa
ContextPropagatingExecutor come default executor del loop, così anche i
run_in_executor(None, ...) (retrieval, authority, compass) mantengono l'id.
I ThreadPoolExecutor creati ad hoc nei singoli moduli restano fuori: i loro
log mostrano "-".
"""
import contextvars
import functools
import uuid
from concurrent.futures import ThreadPoolExecutor

query_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "query_id", default="-"
)


def new_query_id() -> str:
    """Genera e attiva un id breve per la query corrente."""
    qid = uuid.uuid4().hex[:6]
    query_id_var.set(qid)
    return qid


class ContextPropagatingExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor che esegue ogni task nel contesto del chiamante."""

    def submit(self, fn, /, *args, **kwargs):
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, functools.partial(fn, *args, **kwargs))
