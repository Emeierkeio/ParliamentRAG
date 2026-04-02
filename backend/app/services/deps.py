"""
Shared service instances for FastAPI routers.

Provides typed FastAPI Depends() functions backed by @lru_cache for singleton
behavior. Each function returns a single, shared service instance per process.

Usage in a router:
    from app.services.deps import get_neo4j_client

    @router.get("/example")
    async def example(neo4j: Neo4jClient = Depends(get_neo4j_client)):
        ...
"""
from functools import lru_cache

from fastapi import Depends  # noqa: F401 — re-exported for router convenience

from .neo4j_client import Neo4jClient
from .retrieval import RetrievalEngine
from .authority import AuthorityScorer
from .compass import IdeologyScorer
from .generation import GenerationPipeline
from ..config import get_settings


@lru_cache()
def get_neo4j_client() -> Neo4jClient:
    """Return the shared Neo4j client (singleton via lru_cache)."""
    settings = get_settings()
    return Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )


@lru_cache()
def get_retrieval_engine() -> RetrievalEngine:
    """Return the shared RetrievalEngine (singleton via lru_cache)."""
    return RetrievalEngine(get_neo4j_client())


@lru_cache()
def get_authority_scorer() -> AuthorityScorer:
    """Return the shared AuthorityScorer (singleton via lru_cache)."""
    return AuthorityScorer(get_neo4j_client())


@lru_cache()
def get_ideology_scorer() -> IdeologyScorer:
    """Return the shared IdeologyScorer (singleton via lru_cache)."""
    return IdeologyScorer(get_neo4j_client())


@lru_cache()
def get_generation_pipeline() -> GenerationPipeline:
    """Return the shared GenerationPipeline (singleton via lru_cache)."""
    return GenerationPipeline()


def get_services() -> dict:
    """Backward-compatible wrapper. Prefer individual Depends() functions."""
    return {
        "neo4j": get_neo4j_client(),
        "retrieval": get_retrieval_engine(),
        "authority": get_authority_scorer(),
        "ideology": get_ideology_scorer(),
        "generation": get_generation_pipeline(),
    }
