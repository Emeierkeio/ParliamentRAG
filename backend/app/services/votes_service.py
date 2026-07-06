"""
votes_service.py — Single source of truth for all Phase 14 vote analytics.

Provides:
  Pure math (no DB):
    rice_index      — Rice cohesion index for one party on one vote
    mean_rice       — Mean Rice across votes for a party

  Availability guard (F3 degradation):
    has_individual_votes — checks IndividualVote data exists for (chamber, legislature)

  F3 — Cohesion & rebellion:
    get_party_cohesion    — mean Rice per party for full legislature
    get_deputy_vote_stats — rebellion rate + participation rate for one deputy

  F5 — Votes explorer:
    search_votes   — paginated vote search with filters

  F4 — Vote facts for RAG:
    get_vote_facts — structured vote facts for a list of session_ids

  F1 — Speech-vote coherence:
    get_vote_coherence — vote data grouped by session_id for SSE event

Design notes:
  - Every graph function accepts `neo4j` (Neo4jClient) as first argument (injected by FastAPI Depends).
  - Every Cypher that traverses Session nodes filters both `s.chamber` and `s.legislature`
    (Phase 12 rule — multi-chamber, multi-legislature DB).
  - MEMBER_OF_GROUP relationships are date-scoped at vote date:
      mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
  - No scipy, no sklearn — must import cleanly in the anaconda Python 3.12 env.
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Pure math — no DB, no numpy, no scipy
# ---------------------------------------------------------------------------


def rice_index(favor: int, against: int) -> Optional[float]:
    """Rice cohesion index for one party on one vote.

    Formula: |F - A| / (F + A), where F = votes in favor, A = votes against.
    Abstentions are excluded from the denominator per the standard definition.

    Returns None when favor + against == 0 (abstain-only vote — undefined).
    Range: [0.0, 1.0] where 0.0 = perfect split, 1.0 = unanimous.
    """
    denom = favor + against
    if denom == 0:
        return None
    return abs(favor - against) / denom


def mean_rice(vote_rows: list[dict], exclude_unanimous: bool = True) -> float:
    """Mean Rice index across votes for a single party.

    Args:
        vote_rows: list of {"favor": int, "against": int} dicts — one per vote.
        exclude_unanimous: when True, exclude votes where rice==1.0 (procedural
            unanimity inflates cohesion and obscures genuine disagreements).

    Returns 0.0 for an empty list or when all valid rows are filtered out.
    """
    indices = [rice_index(r["favor"], r["against"]) for r in vote_rows]
    # Remove None (abstain-only votes)
    indices = [r for r in indices if r is not None]
    if exclude_unanimous:
        indices = [r for r in indices if r < 1.0]
    return sum(indices) / len(indices) if indices else 0.0


# ---------------------------------------------------------------------------
# F3 degradation guard
# ---------------------------------------------------------------------------

_HAS_INDIVIDUAL_VOTES_CYPHER = """
MATCH (dep:Deputy)-[:VOTED]->(iv:IndividualVote)-[:ON_VOTE]->(v:Vote)<-[:HAS_VOTE]-(s:Session)
WHERE s.chamber = $chamber AND s.legislature = $legislature
RETURN count(iv) AS n LIMIT 1
"""


def has_individual_votes(neo4j, chamber: str, legislature: int) -> bool:
    """Return True if IndividualVote data exists for the given (chamber, legislature).

    Used by get_party_cohesion and get_deputy_vote_stats to detect degraded state
    before computing Rice-based metrics (Pitfall 3 guard).
    """
    rows = neo4j.query(
        _HAS_INDIVIDUAL_VOTES_CYPHER,
        {"chamber": chamber, "legislature": legislature},
    )
    if not rows:
        return False
    return (rows[0].get("n") or 0) > 0


# ---------------------------------------------------------------------------
# F3 — Party cohesion (Rice index across legislature)
# ---------------------------------------------------------------------------

_PARTY_COHESION_CYPHER = """
MATCH (s:Session {chamber: $chamber, legislature: $legislature})-[:HAS_VOTE]->(v:Vote)
MATCH (dep:Deputy)-[:VOTED]->(iv:IndividualVote)-[:ON_VOTE]->(v)
MATCH (dep)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
  WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
WITH g.name AS party, v.id AS vote_id,
     sum(CASE WHEN iv.outcome = 'favor' THEN 1 ELSE 0 END) AS favor,
     sum(CASE WHEN iv.outcome = 'against' THEN 1 ELSE 0 END) AS against
WHERE favor + against > 0
RETURN party, collect({favor: favor, against: against}) AS votes, count(vote_id) AS votes_sampled
"""


def get_party_cohesion(neo4j, chamber: str, legislature: int) -> dict:
    """Compute mean Rice cohesion index per party across a full legislature.

    Returns {"available": False, ...} when no IndividualVote data exists —
    never returns zeros that could be mistaken for genuine zero cohesion.

    Shape: {
        "available": True,
        "chamber": str,
        "legislature": int,
        "parties": [{"party": str, "rice": float, "votes_sampled": int}, ...] sorted desc
    }
    """
    if not has_individual_votes(neo4j, chamber, legislature):
        return {
            "available": False,
            "reason": "individual_votes_pending",
            "parties": [],
        }

    rows = neo4j.query(
        _PARTY_COHESION_CYPHER,
        {"chamber": chamber, "legislature": legislature},
    )

    parties = []
    for row in rows:
        rice = mean_rice(row["votes"], exclude_unanimous=True)
        parties.append({
            "party": row["party"],
            "rice": round(rice, 4),
            "votes_sampled": row["votes_sampled"],
        })

    parties.sort(key=lambda p: p["rice"], reverse=True)

    return {
        "available": True,
        "chamber": chamber,
        "legislature": legislature,
        "parties": parties,
    }


# ---------------------------------------------------------------------------
# F3 — Deputy rebellion + participation rates
# ---------------------------------------------------------------------------

_REBELLION_QUERY = """
MATCH (d:Deputy {id: $deputy_id})-[:VOTED]->(iv:IndividualVote)-[:ON_VOTE]->(v:Vote)
MATCH (s:Session {chamber: $chamber, legislature: $legislature})-[:HAS_VOTE]->(v)
MATCH (d)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
  WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
MATCH (d2:Deputy)-[:VOTED]->(iv2:IndividualVote)-[:ON_VOTE]->(v)
MATCH (d2)-[mg2:MEMBER_OF_GROUP]->(g)
  WHERE mg2.start_date <= s.date AND (mg2.end_date IS NULL OR mg2.end_date >= s.date)
WITH iv.outcome AS my_vote,
     CASE WHEN sum(CASE WHEN iv2.outcome='favor' THEN 1 ELSE 0 END) >=
               sum(CASE WHEN iv2.outcome='against' THEN 1 ELSE 0 END)
          THEN 'favor' ELSE 'against' END AS party_majority,
     count(*) AS total_votes
RETURN sum(CASE WHEN my_vote <> party_majority THEN 1 ELSE 0 END) AS rebellions,
       total_votes
"""

_PARTICIPATION_QUERY = """
MATCH (d:Deputy {id: $deputy_id})-[:VOTED]->(iv:IndividualVote)
WITH count(iv) AS votes_cast
MATCH (d:Deputy {id: $deputy_id})-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
MATCH (s:Session {chamber: $chamber, legislature: $legislature})-[:HAS_VOTE]->(v)
  WHERE s.date >= mg.start_date AND (mg.end_date IS NULL OR s.date <= mg.end_date)
RETURN votes_cast, count(DISTINCT v) AS eligible_votes
"""


def get_deputy_vote_stats(
    neo4j, deputy_id: str, chamber: str, legislature: int
) -> dict:
    """Return rebellion rate and participation rate for a single deputy.

    Degradation: returns {"available": False, ...} when the deputy has zero
    IndividualVote nodes (data not yet ingested for this chamber).

    Shape: {
        "available": bool,
        "rebellion_rate": float | None,
        "participation_rate": float | None,
        "votes_cast": int,
        "rebellions": int,
    }
    """
    # Quick availability check for this specific deputy
    check_rows = neo4j.query(
        """
        MATCH (d:Deputy {id: $deputy_id})-[:VOTED]->(iv:IndividualVote)
        RETURN count(iv) AS n LIMIT 1
        """,
        {"deputy_id": deputy_id},
    )
    if not check_rows or (check_rows[0].get("n") or 0) == 0:
        return {
            "available": False,
            "rebellion_rate": None,
            "participation_rate": None,
            "votes_cast": 0,
            "rebellions": 0,
        }

    # Rebellion rate
    rebellion_rows = neo4j.query(
        _REBELLION_QUERY,
        {"deputy_id": deputy_id, "chamber": chamber, "legislature": legislature},
    )
    if rebellion_rows and rebellion_rows[0].get("total_votes"):
        r = rebellion_rows[0]
        rebellions = r.get("rebellions") or 0
        total_votes = r.get("total_votes") or 0
        rebellion_rate = rebellions / total_votes if total_votes > 0 else 0.0
    else:
        rebellions = 0
        total_votes = 0
        rebellion_rate = 0.0

    # Participation rate
    participation_rows = neo4j.query(
        _PARTICIPATION_QUERY,
        {"deputy_id": deputy_id, "chamber": chamber, "legislature": legislature},
    )
    if participation_rows and participation_rows[0].get("eligible_votes"):
        p = participation_rows[0]
        votes_cast = p.get("votes_cast") or 0
        eligible_votes = p.get("eligible_votes") or 0
        participation_rate = votes_cast / eligible_votes if eligible_votes > 0 else 0.0
    else:
        votes_cast = total_votes
        participation_rate = 0.0

    return {
        "available": True,
        "rebellion_rate": round(rebellion_rate, 4),
        "participation_rate": round(participation_rate, 4),
        "votes_cast": votes_cast,
        "rebellions": rebellions,
    }


# ---------------------------------------------------------------------------
# F5 — Paginated votes search
# ---------------------------------------------------------------------------

_SEARCH_VOTES_CYPHER = """
MATCH (s:Session)-[:HAS_VOTE]->(v:Vote)
WHERE ($chamber = 'both' OR s.chamber = $chamber)
  AND s.legislature = $legislature
  AND ($from_date IS NULL OR s.date >= date($from_date))
  AND ($to_date IS NULL OR s.date <= date($to_date))
  AND ($outcome IS NULL OR v.outcome = $outcome)
OPTIONAL MATCH (d:Debate)<-[:HAS_DEBATE]-(s)
OPTIONAL MATCH (d)-[:DISCUSSES]->(a:ParliamentaryAct)
WITH v, s, d, a,
     abs(coalesce(v.inFavor, 0) - coalesce(v.against, 0)) AS margin
WHERE $min_margin IS NULL OR margin >= $min_margin
RETURN v.id AS vote_id,
       v.number AS number,
       v.outcome AS outcome,
       v.inFavor AS in_favor,
       v.against AS against,
       v.abstained AS abstained,
       v.majority AS majority,
       margin,
       toString(s.date) AS date,
       s.id AS session_id,
       s.chamber AS chamber,
       s.legislature AS legislature,
       d.id AS debate_id,
       coalesce(a.title, d.title, v.subject) AS label
ORDER BY s.date DESC, v.number ASC
SKIP $offset LIMIT $limit
"""


def search_votes(
    neo4j,
    chamber: str = "both",
    legislature: int = 19,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    outcome: Optional[str] = None,
    min_margin: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Paginated full-text vote search with filter support (F5).

    Label uses coalesce(a.title, d.title, v.subject) to avoid displaying
    generic "Votazione" labels from SPARQL-ingested votes (Pitfall 4).

    Returns {"votes": [...], "limit": int, "offset": int, "count": int}.
    """
    rows = neo4j.query(
        _SEARCH_VOTES_CYPHER,
        {
            "chamber": chamber,
            "legislature": legislature,
            "from_date": from_date,
            "to_date": to_date,
            "outcome": outcome,
            "min_margin": min_margin,
            "limit": limit,
            "offset": offset,
        },
    )
    return {
        "votes": rows,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# F4 — Vote facts for RAG prompt injection
# ---------------------------------------------------------------------------

_VOTE_FACTS_CYPHER = """
UNWIND $session_ids AS sid
MATCH (s:Session {id: sid})-[:HAS_VOTE]->(v:Vote)
OPTIONAL MATCH (d:Debate)<-[:HAS_DEBATE]-(s)
OPTIONAL MATCH (d)-[:DISCUSSES]->(a:ParliamentaryAct)
WHERE a IS NOT NULL OR d IS NOT NULL
RETURN v.id AS vote_id, coalesce(a.title, d.title, v.subject) AS label,
       v.outcome AS outcome, v.inFavor AS in_favor, v.against AS against,
       v.abstained AS abstained, toString(s.date) AS date, s.id AS session_id, d.id AS debate_id
ORDER BY s.date DESC, v.number LIMIT 20
"""


def get_vote_facts(neo4j, session_ids: list[str]) -> list[dict]:
    """Return structured vote facts for a list of session_ids (F4 lookup).

    Used by DirectWriter to inject [FATTO DI VOTO] lines into the LLM prompt.
    Returns [] immediately when session_ids is empty (no DB hit required).
    """
    if not session_ids:
        return []
    return neo4j.query(_VOTE_FACTS_CYPHER, {"session_ids": session_ids})


# ---------------------------------------------------------------------------
# F1 — Vote coherence per session (for SSE event)
# ---------------------------------------------------------------------------

_VOTE_COHERENCE_CYPHER = """
UNWIND $session_ids AS sid
MATCH (s:Session {id: sid})-[:HAS_VOTE]->(v:Vote)
MATCH (d:Debate)<-[:HAS_DEBATE]-(s)
OPTIONAL MATCH (d)-[:DISCUSSES]->(a:ParliamentaryAct)
OPTIONAL MATCH (dep:Deputy)-[:VOTED]->(iv:IndividualVote)-[:ON_VOTE]->(v)
OPTIONAL MATCH (dep)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
  WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
WITH v, d, a, s,
     g.name AS party,
     sum(CASE WHEN iv.outcome = 'favor' THEN 1 ELSE 0 END) AS party_favor,
     sum(CASE WHEN iv.outcome = 'against' THEN 1 ELSE 0 END) AS party_against,
     sum(CASE WHEN iv.outcome = 'abstain' THEN 1 ELSE 0 END) AS party_abstain
RETURN s.id AS session_id,
       v.id AS vote_id,
       v.outcome AS outcome,
       v.inFavor AS in_favor,
       v.against AS against,
       d.id AS debate_id,
       coalesce(a.title, d.title, v.subject) AS label,
       collect(DISTINCT {party: party, favor: party_favor, against: party_against, abstain: party_abstain}) AS party_breakdown
ORDER BY v.number
"""


def get_vote_coherence(
    neo4j, session_ids: list[str], legislature: int
) -> dict:
    """Return vote data grouped by session_id for the F1 vote_coherence SSE event.

    Groups results as:
        { "<session_id>": {"votes": [...], "debate_id": str} }

    Each vote entry: {vote_id, label, outcome, in_favor, against,
                      party_breakdown: [{party, favor, against, abstain}]}

    party_breakdown entries with null party are filtered out.
    Returns {} immediately when session_ids is empty (no DB hit required).
    """
    if not session_ids:
        return {}

    rows = neo4j.query(
        _VOTE_COHERENCE_CYPHER,
        {"session_ids": session_ids, "legislature": legislature},
    )

    grouped: dict[str, dict] = {}
    for row in rows:
        sid = row["session_id"]
        if sid not in grouped:
            grouped[sid] = {"votes": [], "debate_id": row.get("debate_id")}

        # Filter null parties from breakdown
        breakdown = [
            pb for pb in (row.get("party_breakdown") or [])
            if pb.get("party") is not None
        ]

        grouped[sid]["votes"].append({
            "vote_id": row["vote_id"],
            "label": row["label"],
            "outcome": row["outcome"],
            "in_favor": row["in_favor"],
            "against": row["against"],
            "party_breakdown": breakdown,
        })

    return grouped
