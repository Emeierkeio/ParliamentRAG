"""
LangSmith tracing bootstrap (SDK standalone, nessuna dipendenza da LangChain).

Attivo solo se LANGSMITH_API_KEY è presente in .env. I client OpenAI creati
da key_pool vengono wrappati con wrap_openai, quindi ogni chiamata LLM è
tracciata (modello, token, costo, latenza). Gli stadi della pipeline sono
annotati con @stage(...) per ottenere la waterfall annidata per query.

Settings carica il .env via pydantic-settings con extra="ignore", quindi
l'SDK non vedrebbe mai LANGSMITH_* da solo: init_tracing() copia i valori
in os.environ prima che venga creato il primo client.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from langsmith import traceable as _traceable
    from langsmith.wrappers import wrap_openai as _wrap_openai
    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False

_enabled: Optional[bool] = None


def init_tracing() -> bool:
    """Esporta LANGSMITH_* in os.environ dai Settings. Idempotente."""
    global _enabled
    if _enabled is not None:
        return _enabled

    if not _LANGSMITH_AVAILABLE:
        _enabled = False
        return False

    # Import lazy per evitare cicli (stesso pattern di key_pool)
    from .config import get_settings
    settings = get_settings()

    api_key = (settings.langsmith_api_key or "").strip()
    if not api_key:
        _enabled = False
        logger.info("LangSmith tracing disabilitato (LANGSMITH_API_KEY assente)")
        return False

    os.environ.setdefault("LANGSMITH_API_KEY", api_key)
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    _enabled = True
    logger.info(
        "LangSmith tracing attivo (project=%s)",
        os.environ["LANGSMITH_PROJECT"],
    )
    return True


def wrap_llm_client(client):
    """Wrappa un client OpenAI per il tracing; passthrough se disabilitato."""
    if not init_tracing():
        return client
    client = _wrap_openai(client)
    # wrap_openai (langsmith 0.11) copre chat/completions ma non embeddings:
    # la pipeline chiama embeddings in engine, coherence_validator e dedup
    if not hasattr(client.embeddings.create, "__wrapped__"):
        client.embeddings.create = _traceable(
            name="openai_embeddings", run_type="embedding"
        )(client.embeddings.create)
    return client


def _drop_self(inputs: dict) -> dict:
    return {k: v for k, v in inputs.items() if k != "self"}


def stage(name: str):
    """
    Decorator per gli stadi della pipeline: crea un run annidato con il nome
    dato. No-op se langsmith non è installato o il tracing è disabilitato
    (traceable non registra nulla senza LANGSMITH_TRACING in ambiente).
    """
    def deco(fn):
        if not _LANGSMITH_AVAILABLE:
            return fn
        return _traceable(name=name, run_type="chain", process_inputs=_drop_self)(fn)
    return deco
