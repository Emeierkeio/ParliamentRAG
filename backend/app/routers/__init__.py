"""API routers for Multi-View RAG system."""
from .query import router as query_router
from .evidence import router as evidence_router
from .config import router as config_router
from .chat import router as chat_router
from .history import router as history_router

__all__ = [
    "query_router",
    "evidence_router",
    "config_router",
    "chat_router",
    "history_router",
]
