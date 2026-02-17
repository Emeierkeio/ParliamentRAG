"""
Multi-View RAG API for Italian Parliamentary Data.

FastAPI application entry point.
"""
import sys
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import query_router, evidence_router, config_router, chat_router, history_router
from .routers.graph import router as graph_router
from .routers.search import router as search_router
from .routers.survey import router as survey_router
from .routers.evaluation import router as evaluation_router
from .routers.authority import router as authority_router
from .config import get_config, get_settings


def setup_logging():
    """
    Configure logging to both console and file.

    Log files are saved to backend/logs/ with timestamp-based names.
    Each execution creates a new log file.
    """
    # Create logs directory
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Create timestamp-based log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"rag_api_{timestamp}.log"

    # Log format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler (with rotation: max 10MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return log_file


# Setup logging and get log file path
log_file_path = setup_logging()
logger = logging.getLogger(__name__)
logger.info(f"[STARTUP] Logging to file: {log_file_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Multi-View RAG API...")

    # Validate configuration
    try:
        config = get_config()
        settings = get_settings()
        logger.info(f"Configuration loaded from: {config.config_dir}")
        logger.info(f"Neo4j URI: {settings.neo4j_uri}")
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        raise

    # Warm up Neo4j vector index to avoid cold start latency
    await _warmup_neo4j_index(settings)

    # Ensure Neo4j constraints exist
    from .routers.history import ensure_constraint
    ensure_constraint()
    from .routers.survey import ensure_survey_constraint
    ensure_survey_constraint()

    yield

    # Shutdown
    logger.info("Shutting down Multi-View RAG API...")


async def _warmup_neo4j_index(settings):
    """
    Warm up Neo4j vector index by running a dummy query.

    This forces Neo4j to load the vector index into memory,
    eliminating the 15-18s cold start penalty on first real query.
    """
    import time
    from .services.neo4j_client import Neo4jClient

    logger.info("[WARMUP] Starting Neo4j vector index warmup...")
    start_time = time.time()

    try:
        client = Neo4jClient(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )

        # Create a dummy embedding with positive L2 norm (Neo4j requires non-zero vectors)
        # Using a normalized vector: [1/sqrt(1536), 1/sqrt(1536), ...]
        import math
        norm_value = 1.0 / math.sqrt(1536)
        dummy_embedding = [norm_value] * 1536

        # Run a minimal vector query to force index loading
        warmup_query = """
        CALL db.index.vector.queryNodes('chunk_embedding_index', 1, $embedding)
        YIELD node, score
        RETURN count(node) as cnt
        """

        result = client.query(warmup_query, {"embedding": dummy_embedding})

        elapsed = (time.time() - start_time) * 1000
        logger.info(f"[WARMUP] Neo4j vector index loaded in {elapsed:.1f}ms")

        client.close()

    except Exception as e:
        logger.warning(f"[WARMUP] Neo4j warmup failed (non-critical): {e}")


# Create FastAPI app
app = FastAPI(
    title="Multi-View RAG API",
    description="""
    Multi-View Retrieval-Augmented Generation system for Italian Parliamentary Data.

    ## Features
    - Dual-channel retrieval (dense + graph)
    - Query-dependent authority scoring
    - Ideological compass for multi-view coverage
    - 4-stage generation pipeline with exact citations

    ## Endpoints
    - `POST /api/chat` - Main chat endpoint (SSE streaming, frontend-compatible)
    - `POST /api/query` - Alternative query endpoint
    - `GET /api/evidence/{id}` - Get full evidence details
    - `GET /api/config` - Get system configuration

    ## Citation Integrity
    All citations are extracted via exact offset-based extraction.
    NO fuzzy matching is used.
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(query_router)
app.include_router(evidence_router)
app.include_router(config_router)
app.include_router(chat_router)  # Frontend-compatible chat endpoint
app.include_router(history_router)  # Conversation history
app.include_router(graph_router)  # Graph exploration
app.include_router(search_router)  # Parliamentary record search
app.include_router(survey_router)  # User surveys/evaluations
app.include_router(evaluation_router)  # Evaluation dashboard
app.include_router(authority_router)  # Authority ranking by topic


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Multi-View RAG API",
        "version": "1.0.0",
        "description": "Multi-View RAG for Italian Parliamentary Data",
        "docs": "/docs",
        "endpoints": {
            "query": "POST /api/query",
            "evidence": "GET /api/evidence/{id}",
            "config": "GET /api/config",
            "health": "GET /api/health",
        }
    }


if __name__ == "__main__":
    import os
    import uvicorn
    workers = int(os.environ.get("WORKERS", 4))
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=workers)
