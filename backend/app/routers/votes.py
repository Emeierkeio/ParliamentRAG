"""
Votes intelligence router — Phase 14.

Exposes two thin endpoints:
  GET /api/votes           — F5 paginated vote search with filters
  GET /api/rankings/votes  — F3 party cohesion (Rice) or per-deputy rebellion stats

All graph work is delegated to votes_service; no Cypher lives here.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ..services.deps import get_neo4j_client
from ..services.neo4j_client import Neo4jClient
from ..services import votes_service

router = APIRouter(prefix="/api", tags=["votes"])


@router.get("/votes")
async def search_votes_endpoint(
    chamber: str = "both",
    legislature: int = 19,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    outcome: Optional[str] = None,
    min_margin: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> dict:
    """Paginated vote search with optional filters (F5 — Votes Explorer).

    Query parameters:
      chamber      — 'camera' | 'senato' | 'both' (default: 'both')
      legislature  — legislature number (default: 19)
      from_date    — ISO date string lower bound (inclusive)
      to_date      — ISO date string upper bound (inclusive)
      outcome      — filter by vote outcome string
      min_margin   — minimum margin as % of expressed votes (e.g. 10 = 10 pp lead)
      limit        — page size (default: 50)
      offset       — page offset (default: 0)

    Returns {"votes": [...], "limit": int, "offset": int, "count": int}.
    """
    return votes_service.search_votes(
        neo4j,
        chamber=chamber,
        legislature=legislature,
        from_date=from_date,
        to_date=to_date,
        outcome=outcome,
        min_margin=min_margin,
        limit=limit,
        offset=offset,
    )


@router.get("/votes/{vote_id}/individual")
async def get_individual_votes_endpoint(
    vote_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> dict:
    """Per-deputy individual vote breakdown for a single vote (vote explorer drill-down).

    Returns deputies grouped by party and outcome (favor / against / abstained).
    Always returns {"available": False, ...} when IndividualVote data has not yet
    been ingested for this vote — never presents an empty list as a completed record.
    """
    return votes_service.get_vote_individual_votes(neo4j, vote_id)


@router.get("/rankings/votes")
async def rankings_votes_endpoint(
    chamber: str = "camera",
    legislature: int = 19,
    deputy_id: Optional[str] = None,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> dict:
    """Party cohesion rankings or per-deputy vote stats (F3).

    Without deputy_id: returns mean Rice cohesion index per party.
    With deputy_id:    returns rebellion rate + participation rate for that deputy.

    Returns {"available": False, ...} when IndividualVote data has not yet been
    ingested — never returns zeros that could be mistaken for genuine zero cohesion.
    """
    if deputy_id:
        return votes_service.get_deputy_vote_stats(neo4j, deputy_id, chamber, legislature)
    return votes_service.get_party_cohesion(neo4j, chamber, legislature)
