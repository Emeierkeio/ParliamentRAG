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
from ..services.authority.coalition_logic import CoalitionLogic
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

        # Compute per-speaker authority with detailed breakdowns
        authority_scores = {}
        authority_details = {}
        for speaker_id in speaker_ids:
            result = services["authority"].compute_authority(
                speaker_id, query_embedding
            )
            authority_scores[speaker_id] = result["total_score"]
            authority_details[speaker_id] = result

        # Compute experts with full details for frontend
        experts = _compute_experts(
            evidence_list, authority_scores, authority_details, services["neo4j"]
        )

        yield f"data: {json.dumps({'type': 'experts', 'data': experts}, default=str)}\n\n"

        # Step 4: Compass analysis (2D text-based positioning)
        yield f"data: {json.dumps({'type': 'progress', 'step': 4, 'message': 'Analisi compass ideologico...'})}\n\n"

        compass_result = services["ideology"].compute_2d_text_positions(evidence_dicts)
        compass_data = {
            "meta": compass_result.get("meta", {}),
            "axes": compass_result.get("axes", {}),
            "groups": compass_result.get("groups", []),
            "scatter_sample": compass_result.get("scatter_sample", []),
        }

        yield f"data: {json.dumps({'type': 'compass', 'data': compass_data}, default=str)}\n\n"

        # Step 5: Generation
        yield f"data: {json.dumps({'type': 'progress', 'step': 5, 'message': 'Generazione risposta multi-view...'})}\n\n"

        generation_result = await services["generation"].generate(
            query=request.query,
            evidence_list=evidence_dicts
        )

        # Step 6: Citations (from evidence_dicts, not generation_result)
        citations_data = _build_citations_for_frontend(evidence_dicts)

        yield f"data: {json.dumps({'type': 'citations', 'data': citations_data}, default=str)}\n\n"

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


def _fetch_speaker_details(neo4j_client: Neo4jClient, speaker_id: str) -> Dict[str, Any]:
    """Fetch detailed speaker information from Neo4j."""
    cypher = """
    MATCH (d:Deputy {id: $speaker_id})
    OPTIONAL MATCH (d)-[mc:MEMBER_OF_COMMITTEE]->(c:Committee)
    WHERE mc.end_date IS NULL OR mc.end_date >= date()
    WITH d, collect(c.name)[0] AS current_committee

    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rp:IS_PRESIDENT]->(cp:Committee)
        WHERE rp.end_date IS NULL OR rp.end_date >= date()
        RETURN collect(DISTINCT 'Presidente ' + cp.name) AS president_roles
    }
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rv:IS_VICE_PRESIDENT]->(cv:Committee)
        WHERE rv.end_date IS NULL OR rv.end_date >= date()
        RETURN collect(DISTINCT 'Vicepresidente ' + cv.name) AS vice_roles
    }
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rs:IS_SECRETARY]->(cs:Committee)
        WHERE rs.end_date IS NULL OR rs.end_date >= date()
        RETURN collect(DISTINCT 'Segretario ' + cs.name) AS secretary_roles
    }
    WITH d, current_committee, president_roles + vice_roles + secretary_roles AS all_roles

    RETURN d.id AS id,
           d.first_name AS first_name,
           d.last_name AS last_name,
           d.profession AS profession,
           d.education AS education,
           d.deputy_card AS camera_profile_url,
           current_committee,
           CASE WHEN size(all_roles) > 0 THEN all_roles[0] ELSE null END AS institutional_role
    """
    with neo4j_client.session() as session:
        result = session.run(cypher, speaker_id=speaker_id)
        record = result.single()
        if record:
            return dict(record)

    # Try GovernmentMember
    cypher_gov = """
    MATCH (m:GovernmentMember {id: $speaker_id})
    RETURN m.id AS id,
           m.first_name AS first_name,
           m.last_name AS last_name,
           m.institutional_role AS institutional_role,
           m.deputy_card AS camera_profile_url
    """
    with neo4j_client.session() as session:
        result = session.run(cypher_gov, speaker_id=speaker_id)
        record = result.single()
        if record:
            data = dict(record)
            data["profession"] = None
            data["education"] = None
            data["current_committee"] = None
            return data

    return {}


def _compute_experts(
    evidence_list: List[Any],
    authority_scores: Dict[str, float],
    authority_details: Dict[str, Dict[str, Any]],
    neo4j_client: Neo4jClient
) -> List[Dict[str, Any]]:
    """Compute experts in frontend-expected format with full details."""
    coalition_logic = CoalitionLogic()
    party_speakers: Dict[str, Dict[str, Dict]] = {}

    for evidence in evidence_list:
        if evidence.speaker_role == "GovernmentMember":
            continue
        party = evidence.party
        speaker_id = evidence.speaker_id
        speaker_name = evidence.speaker_name

        if party not in party_speakers:
            party_speakers[party] = {}

        if speaker_id not in party_speakers[party]:
            party_speakers[party][speaker_id] = {
                "speaker_name": speaker_name,
                "authority_score": authority_scores.get(speaker_id, 0.5),
                "count": 0,
                "party": party,
            }

        party_speakers[party][speaker_id]["count"] += 1

    experts = []
    for party, speakers in party_speakers.items():
        if speakers:
            top_speaker_id = max(
                speakers.keys(),
                key=lambda s: speakers[s]["authority_score"]
            )
            top_speaker = speakers[top_speaker_id]
            coalition = coalition_logic.get_coalition(party)

            name_parts = top_speaker["speaker_name"].split(" ", 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            details = authority_details.get(top_speaker_id, {})
            components = details.get("components", {})

            speaker_info = _fetch_speaker_details(neo4j_client, top_speaker_id)

            experts.append({
                "id": top_speaker_id,
                "first_name": first_name,
                "last_name": last_name,
                "group": party,
                "coalition": coalition,
                "authority_score": round(top_speaker["authority_score"], 2),
                "relevant_speeches_count": top_speaker["count"],
                "camera_profile_url": speaker_info.get("camera_profile_url"),
                "profession": speaker_info.get("profession"),
                "education": speaker_info.get("education"),
                "committee": speaker_info.get("current_committee"),
                "institutional_role": speaker_info.get("institutional_role"),
                "score_breakdown": {
                    "speeches": round(components.get("interventions", 0), 2),
                    "acts": round(components.get("acts", 0), 2),
                    "committee": round(components.get("committee", 0), 2),
                    "profession": round(components.get("profession", 0), 2),
                    "education": round(components.get("education", 0), 2),
                    "role": round(components.get("role", 0), 2),
                },
            })

    return experts


def _build_citations_for_frontend(
    evidence_dicts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Build citations in frontend-expected format from evidence dicts."""
    coalition_logic = CoalitionLogic()
    citations = []

    for i, e in enumerate(evidence_dicts[:20]):
        evidence_id = e.get("evidence_id", f"cit_{i+1}")
        speaker_name = e.get("speaker_name", "")
        party = e.get("party", "MISTO")
        coalition = coalition_logic.get_coalition(party)

        name_parts = speaker_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        chunk_text = e.get("chunk_text") or ""
        quote_text = e.get("quote_text") or ""
        display_text = (chunk_text or quote_text)[:300]

        citations.append({
            "chunk_id": evidence_id,
            "deputy_first_name": first_name,
            "deputy_last_name": last_name,
            "text": display_text,
            "quote_text": quote_text,
            "full_text": chunk_text or quote_text,
            "group": party,
            "coalition": coalition,
            "date": str(e.get("date", "")),
            "similarity": round(e.get("similarity", 0), 2),
            "debate": e.get("debate_title", ""),
            "intervention_id": e.get("speech_id", ""),
        })

    return citations


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
