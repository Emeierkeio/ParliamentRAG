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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import query_router, evidence_router, config_router, chat_router, history_router
from .routers.graph import router as graph_router
from .routers.search import router as search_router
from .routers.survey import router as survey_router
from .routers.evaluation import router as evaluation_router
from .routers.authority import router as authority_router
from .routers.compass import router as compass_router
from .config import MAINTENANCE_MODE, get_config, get_settings


def setup_logging():
    """
    Configure logging to console and two rotating log files:

    - logs/app_TIMESTAMP.log   : INFO+  — log operativo pulito, niente rumore da librerie
    - logs/debug_TIMESTAMP.log : DEBUG+ — traccia completa per investigazione

    Librerie rumorose (httpx, urllib3, ecc.) vengono silenziati a WARNING
    in modo che non inquinino né il terminale né i file.

    Moduli sotto investigazione attiva vengono portati a DEBUG esplicitamente
    così i loro log di dettaglio finiscono nel debug file.
    """
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    app_log_file   = log_dir / f"app_{timestamp}.log"
    debug_log_file = log_dir / f"debug_{timestamp}.log"

    # Formato: livello giustificato a 8 char per allineamento visivo
    fmt = "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S,%f"[:-3])

    # Il root logger deve stare a DEBUG: i singoli handler/logger filtrano il resto
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # --- Console: INFO+ (visibile durante lo sviluppo) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # --- app log: INFO+, 20 MB rotating, 10 backup ---
    app_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=20 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    # --- debug log: DEBUG+, 50 MB rotating, 5 backup ---
    debug_handler = RotatingFileHandler(
        debug_log_file,
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_handler)
    root_logger.addHandler(debug_handler)

    # ------------------------------------------------------------------
    # Silenzia librerie di terze parti rumorose (a livello di logger,
    # quindi il filtro vale per tutti gli handler in modo uniforme)
    # ------------------------------------------------------------------
    _NOISY_LIBS = (
        "httpx",
        "httpcore",
        "urllib3",
        "openai",
        "neo4j.notifications",
    )
    for lib in _NOISY_LIBS:
        logging.getLogger(lib).setLevel(logging.WARNING)

    # ------------------------------------------------------------------
    # Moduli sotto investigazione attiva → DEBUG esplicito
    # I loro log di dettaglio finiscono nel debug file senza spam nel
    # log operativo (che resta a INFO)
    # ------------------------------------------------------------------
    _DEBUG_MODULES = (
        "app.services.generation.integrator",       # corrupt citations context
        "app.services.generation.coherence_validator",  # embedding scores raw
    )
    for mod in _DEBUG_MODULES:
        logging.getLogger(mod).setLevel(logging.DEBUG)

    return app_log_file, debug_log_file


# Setup logging
_app_log, _debug_log = setup_logging()
logger = logging.getLogger(__name__)
logger.info(f"[STARTUP] App log  : {_app_log}")
logger.info(f"[STARTUP] Debug log: {_debug_log}")


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

@app.middleware("http")
async def maintenance_middleware(request: Request, call_next):
    """Block all requests with 503 when MAINTENANCE_MODE is True."""
    if MAINTENANCE_MODE:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Sistema in manutenzione. Torneremo presto.",
                "maintenance": True,
            },
            headers={"Retry-After": "3600"},
        )
    return await call_next(request)


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
app.include_router(compass_router)  # Standalone ideological compass


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
