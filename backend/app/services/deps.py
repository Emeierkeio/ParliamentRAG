"""
Shared service instances for FastAPI routers.

Centralizes lazy initialization of heavy services (Neo4j, pipelines, scorers)
so that multiple routers share a single instance.
"""
import logging
from typing import Optional

from .neo4j_client import Neo4jClient
from .retrieval import RetrievalEngine
from .authority import AuthorityScorer
from .compass import IdeologyScorer
from .generation import GenerationPipeline
from ..config import get_settings

logger = logging.getLogger(__name__)

_neo4j_client: Optional[Neo4jClient] = None
_retrieval_engine: Optional[RetrievalEngine] = None
_authority_scorer: Optional[AuthorityScorer] = None
_ideology_scorer: Optional[IdeologyScorer] = None
_generation_pipeline: Optional[GenerationPipeline] = None


def _check_schema_version(client: Neo4jClient, uri: str) -> None:
    """Log the DB schema version (v2 C9).

    Log-only while the backend must run against both v1 and v2 during
    flip testing; becomes a hard fail after the v2 cutover.
    """
    try:
        rows = client.query(
            "MATCH (m:SchemaMeta {id: 'singleton'}) "
            "RETURN m.version AS v, toString(m.built_at) AS built"
        )
        if rows:
            logger.info(
                "Connected to DB schema v%s (built %s) at %s",
                rows[0]["v"], rows[0]["built"], uri,
            )
        else:
            logger.warning(
                "No SchemaMeta found at %s — assuming legacy v1 schema", uri
            )
    except Exception as exc:
        logger.warning("SchemaMeta check failed: %s", exc)


def get_services() -> dict:
    """Return (or lazily initialize) the shared service instances."""
    global _neo4j_client, _retrieval_engine, _authority_scorer
    global _ideology_scorer, _generation_pipeline

    if _neo4j_client is None:
        settings = get_settings()
        _neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        _check_schema_version(_neo4j_client, settings.neo4j_uri)
        _retrieval_engine = RetrievalEngine(_neo4j_client)
        _authority_scorer = AuthorityScorer(_neo4j_client)
        _ideology_scorer = IdeologyScorer(_neo4j_client)
        _generation_pipeline = GenerationPipeline()

    return {
        "neo4j": _neo4j_client,
        "retrieval": _retrieval_engine,
        "authority": _authority_scorer,
        "ideology": _ideology_scorer,
        "generation": _generation_pipeline,
    }
