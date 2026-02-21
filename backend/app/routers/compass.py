"""
Standalone compass endpoint.

Returns only the ideological compass analysis for a given query,
without authority scoring or text generation.
"""
import time
import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .query import get_services

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Compass"])


class CompassRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=100, ge=10, le=500)


@router.post("/compass")
async def compass_endpoint(request: CompassRequest):
    """Compute ideological compass for all parties on a given topic."""
    services = get_services()
    start = time.time()

    try:
        # Step 1: Retrieve evidence
        retrieval_result = await services["retrieval"].retrieve(
            query=request.query,
            top_k=request.top_k,
        )
        evidence_list = retrieval_result["evidence"]

        # Include embeddings for PCA
        evidence_dicts = []
        for e in evidence_list:
            d = e.model_dump()
            if e.embedding is not None:
                d["embedding"] = e.embedding
            evidence_dicts.append(d)

        # Step 2: Compute compass positions
        compass_result = await asyncio.get_running_loop().run_in_executor(
            None, services["ideology"].compute_2d_text_positions, evidence_dicts
        )

        elapsed_ms = round((time.time() - start) * 1000)

        return {
            "meta": compass_result.get("meta", {}),
            "axes": compass_result.get("axes", {}),
            "groups": compass_result.get("groups", []),
            "scatter_sample": compass_result.get("scatter_sample", []),
            "computation_time_ms": elapsed_ms,
        }

    except Exception as e:
        logger.error(f"Compass endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
