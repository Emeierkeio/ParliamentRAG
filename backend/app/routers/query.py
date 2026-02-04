"""
Main query endpoint for Multi-View RAG.

Supports both synchronous and SSE streaming responses.
"""
import json
import logging
import asyncio
from datetime import date
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services.neo4j_client import Neo4jClient
from ..services.retrieval import RetrievalEngine
from ..services.authority import AuthorityScorer
from ..services.compass import IdeologyScorer
from ..services.generation import GenerationPipeline
from ..config import get_config, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Query"])


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str = Field(..., min_length=3, max_length=1000, description="User query")
    top_k: int = Field(default=100, ge=10, le=500, description="Number of evidence pieces")
    date_start: Optional[str] = Field(default=None, description="Start date filter (YYYY-MM-DD)")
    date_end: Optional[str] = Field(default=None, description="End date filter (YYYY-MM-DD)")
    stream: bool = Field(default=True, description="Enable SSE streaming")


class ExpertInfo(BaseModel):
    """Expert information for a party."""
    speaker_id: str
    speaker_name: str
    authority_score: float
    intervention_count: int


class CitationInfo(BaseModel):
    """Citation information."""
    citation_id: str
    chunk_id: str
    quote_text: str
    speaker_name: str
    party: str
    date: str
    span_start: int
    span_end: int


class QueryResponse(BaseModel):
    """Response model for non-streaming queries."""
    text: str
    citations: List[CitationInfo]
    experts: Dict[str, ExpertInfo]
    compass: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]


# Global service instances (initialized on first request)
_neo4j_client: Optional[Neo4jClient] = None
_retrieval_engine: Optional[RetrievalEngine] = None
_authority_scorer: Optional[AuthorityScorer] = None
_ideology_scorer: Optional[IdeologyScorer] = None
_generation_pipeline: Optional[GenerationPipeline] = None


def get_services():
    """Get or initialize service instances."""
    global _neo4j_client, _retrieval_engine, _authority_scorer
    global _ideology_scorer, _generation_pipeline

    if _neo4j_client is None:
        settings = get_settings()
        _neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )
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


async def process_query_streaming(
    request: QueryRequest
) -> AsyncGenerator[str, None]:
    """
    Process query with SSE streaming.

    Yields SSE events as the pipeline progresses.
    """
    services = get_services()

    try:
        # Step 1: Progress - Starting
        yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'message': 'Avvio retrieval...'})}\n\n"

        # Step 2: Retrieval
        retrieval_result = await services["retrieval"].retrieve(
            query=request.query,
            top_k=request.top_k,
            date_start=request.date_start,
            date_end=request.date_end
        )

        evidence_list = retrieval_result["evidence"]
        evidence_dicts = [e.model_dump() for e in evidence_list]

        yield f"data: {json.dumps({'type': 'progress', 'step': 2, 'message': f'Trovate {len(evidence_list)} evidenze'})}\n\n"

        # Step 3: Authority scoring
        yield f"data: {json.dumps({'type': 'progress', 'step': 3, 'message': 'Calcolo authority scores...'})}\n\n"

        # Get unique speakers
        speaker_ids = list(set(e.speaker_id for e in evidence_list if e.speaker_id))
        query_embedding = services["retrieval"].embed_query(request.query)

        authority_scores = services["authority"].compute_batch_authority(
            speaker_ids, query_embedding
        )

        # Compute experts per party
        experts = _compute_experts(evidence_list, authority_scores)

        yield f"data: {json.dumps({'type': 'experts', 'data': experts})}\n\n"

        # Step 4: Compass analysis
        yield f"data: {json.dumps({'type': 'progress', 'step': 4, 'message': 'Analisi compass ideologico...'})}\n\n"

        coverage_metrics = services["ideology"].compute_coverage_metrics(evidence_dicts)

        compass_data = {
            "balance_score": coverage_metrics["balance_score"],
            "position_coverage": coverage_metrics["position_coverage"],
            "missing_positions": coverage_metrics["missing_positions"],
        }

        yield f"data: {json.dumps({'type': 'compass', 'data': compass_data})}\n\n"

        # Step 5: Generation
        yield f"data: {json.dumps({'type': 'progress', 'step': 5, 'message': 'Generazione risposta multi-view...'})}\n\n"

        # Stream callback for generation progress
        async def gen_callback(event):
            pass  # We'll handle this differently

        generation_result = await services["generation"].generate(
            query=request.query,
            evidence_list=evidence_dicts
        )

        # Step 6: Citations
        citations_data = []
        for i, cit in enumerate(generation_result.get("citations", [])):
            citations_data.append({
                "chunk_id": f"cit_{i+1}",
                "chunk_real_id": cit.get("evidence_id", ""),
                "quote_text": cit.get("quote_text", ""),
                "speaker_name": cit.get("speaker_name", ""),
                "party": cit.get("party", ""),
                "date": cit.get("date", ""),
            })

        yield f"data: {json.dumps({'type': 'citations', 'data': citations_data})}\n\n"

        # Step 7: Stream text chunks
        final_text = generation_result.get("text", "")

        # Split into chunks for streaming effect
        chunk_size = 100
        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i:i+chunk_size]
            yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
            await asyncio.sleep(0.02)  # Small delay for streaming effect

        # Step 8: Complete
        yield f"data: {json.dumps({'type': 'complete', 'metadata': retrieval_result['metadata']})}\n\n"

    except Exception as e:
        logger.error(f"Query processing error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


def _compute_experts(
    evidence_list: List[Any],
    authority_scores: Dict[str, float]
) -> Dict[str, Dict[str, Any]]:
    """Compute top expert per party."""
    party_speakers: Dict[str, Dict[str, Dict]] = {}

    for evidence in evidence_list:
        party = evidence.party
        speaker_id = evidence.speaker_id
        speaker_name = evidence.speaker_name

        if party not in party_speakers:
            party_speakers[party] = {}

        if speaker_id not in party_speakers[party]:
            party_speakers[party][speaker_id] = {
                "speaker_name": speaker_name,
                "authority_score": authority_scores.get(speaker_id, 0.5),
                "count": 0
            }

        party_speakers[party][speaker_id]["count"] += 1

    # Get top expert per party
    experts = {}
    for party, speakers in party_speakers.items():
        if speakers:
            top_speaker_id = max(
                speakers.keys(),
                key=lambda s: speakers[s]["authority_score"]
            )
            top_speaker = speakers[top_speaker_id]
            experts[party] = {
                "speaker_id": top_speaker_id,
                "speaker_name": top_speaker["speaker_name"],
                "authority_score": top_speaker["authority_score"],
                "intervention_count": top_speaker["count"],
            }

    return experts


@router.post("/query")
async def query_endpoint(request: QueryRequest):
    """
    Main query endpoint.

    Supports SSE streaming (default) or synchronous response.
    """
    if request.stream:
        return StreamingResponse(
            process_query_streaming(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        # Synchronous response
        services = get_services()

        try:
            # Retrieval
            retrieval_result = await services["retrieval"].retrieve(
                query=request.query,
                top_k=request.top_k,
                date_start=request.date_start,
                date_end=request.date_end
            )

            evidence_list = retrieval_result["evidence"]
            evidence_dicts = [e.model_dump() for e in evidence_list]

            # Authority
            speaker_ids = list(set(e.speaker_id for e in evidence_list))
            query_embedding = services["retrieval"].embed_query(request.query)
            authority_scores = services["authority"].compute_batch_authority(
                speaker_ids, query_embedding
            )

            # Experts
            experts = _compute_experts(evidence_list, authority_scores)

            # Compass
            coverage = services["ideology"].compute_coverage_metrics(evidence_dicts)

            # Generation
            gen_result = await services["generation"].generate(
                query=request.query,
                evidence_list=evidence_dicts
            )

            # Build citations
            citations = [
                CitationInfo(
                    citation_id=f"cit_{i+1}",
                    chunk_id=c.get("evidence_id", ""),
                    quote_text=c.get("quote_text", ""),
                    speaker_name=c.get("speaker_name", ""),
                    party=c.get("party", ""),
                    date=c.get("date", ""),
                    span_start=c.get("span_start", 0),
                    span_end=c.get("span_end", 0),
                )
                for i, c in enumerate(gen_result.get("citations", []))
            ]

            return QueryResponse(
                text=gen_result.get("text", ""),
                citations=citations,
                experts=experts,
                compass=coverage,
                metadata=retrieval_result["metadata"]
            )

        except Exception as e:
            logger.error(f"Query error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        services = get_services()
        # Quick DB check
        services["neo4j"].verify_connectivity()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
