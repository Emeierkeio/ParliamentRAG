"""
Vote-based compass pipeline (F2).

Computes a party × vote matrix from IndividualVote aggregations in Neo4j,
reduces to 2D via numpy SVD-PCA, caches per (legislature, chamber), and
exposes get_vote_compass() for the GET /api/compass/votes endpoint.

No scipy — numpy only (anaconda NumPy 2.x / scipy incompatibility).
"""
import logging
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cypher — aggregate IndividualVote by party majority per vote
# Chamber + legislature filter per Phase 12 rule.
# ---------------------------------------------------------------------------
PARTY_VOTE_MATRIX_QUERY = """
MATCH (s:Session {chamber: $chamber, legislature: $legislature})-[:HAS_VOTE]->(v:Vote)
MATCH (d:Deputy)-[:VOTED]->(iv:IndividualVote)-[:ON_VOTE]->(v)
MATCH (d)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
  WHERE mg.start_date <= s.date
    AND (mg.end_date IS NULL OR mg.end_date >= s.date)
WITH v.id AS vote_id, g.name AS party,
     sum(CASE WHEN iv.outcome = 'favor' THEN 1 ELSE 0 END) AS favor,
     sum(CASE WHEN iv.outcome = 'against' THEN 1 ELSE 0 END) AS against,
     sum(CASE WHEN iv.outcome = 'abstain' THEN 1 ELSE 0 END) AS abstain
RETURN vote_id, party, favor, against, abstain
"""

# ---------------------------------------------------------------------------
# TTL cache — in-process dict, one entry per (legislature, chamber)
# ---------------------------------------------------------------------------
_vote_compass_cache: dict[tuple[int, str], tuple[dict, float]] = {}
VOTE_COMPASS_TTL_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Matrix construction
# ---------------------------------------------------------------------------

def build_party_vote_matrix(
    rows: list[dict],
) -> tuple[np.ndarray, list[str], list[str]]:
    """Build a party × vote matrix from aggregated IndividualVote rows.

    Encoding per cell:
      - favor > against  → 1.0
      - against > favor  → 0.0
      - favor == against → 0.5  (tie, abstain-dominated, or total == 0)
      - missing combo    → 0.5  (default; treated as abstain)

    Args:
        rows: List of dicts with keys {party, vote_id, favor, against, abstain}.

    Returns:
        (matrix, party_labels, vote_ids) where matrix[i][j] is party i's
        position on vote j.
    """
    parties = sorted({r["party"] for r in rows})
    votes = sorted({r["vote_id"] for r in rows})
    party_idx = {p: i for i, p in enumerate(parties)}
    vote_idx = {v: i for i, v in enumerate(votes)}

    matrix = np.full((len(parties), len(votes)), 0.5)  # default = abstain

    for r in rows:
        i, j = party_idx[r["party"]], vote_idx[r["vote_id"]]
        total = r["favor"] + r["against"] + r["abstain"]
        if total == 0:
            continue  # leave default 0.5
        if r["favor"] > r["against"]:
            matrix[i][j] = 1.0
        elif r["against"] > r["favor"]:
            matrix[i][j] = 0.0
        else:
            matrix[i][j] = 0.5  # tie (includes favor == against == 0 after total > 0 guard)

    return matrix, parties, votes


# ---------------------------------------------------------------------------
# SVD-PCA 2D projection
# ---------------------------------------------------------------------------

def pca_2d(
    matrix: np.ndarray,
) -> tuple[np.ndarray, list[float]]:
    """Project a party × vote matrix to 2D via SVD-PCA.

    Centres each vote (column) across parties, then applies truncated SVD.

    Args:
        matrix: Shape (n_parties, n_votes), float64.

    Returns:
        (coords, variance_explained) where:
          coords — shape (n_parties, 2), the 2D party coordinates.
          variance_explained — list of up to 2 floats summing to <= 1.0.
                               Empty list when guard triggers.

    Guard: if matrix has < 2 rows OR < 2 columns, returns zeros of shape
    (n_parties, 2) and an empty variance list.
    """
    n_parties, n_votes = matrix.shape
    if n_parties < 2 or n_votes < 2:
        return np.zeros((n_parties, 2)), []

    # Center per vote across parties
    M = matrix - matrix.mean(axis=0, keepdims=True)

    U, S, Vt = np.linalg.svd(M, full_matrices=False)

    total_var = (S ** 2).sum()
    if total_var == 0:
        return np.zeros((n_parties, 2)), []

    variance_explained = ((S ** 2) / total_var).tolist()

    # Take first 2 components; guard against fewer than 2 singular values
    k = min(2, len(S))
    coords = np.zeros((n_parties, 2))
    coords[:, :k] = U[:, :k] * S[:k]

    return coords, variance_explained


# ---------------------------------------------------------------------------
# Internal compute (called by cache wrapper)
# ---------------------------------------------------------------------------

def _compute_vote_compass(
    legislature: int,
    chamber: str,
    neo4j: Any,
) -> dict:
    """Query Neo4j, build matrix, run PCA, return compass dict.

    Returns {"available": False, "reason": "individual_votes_pending"}
    when fewer than 3 parties have IndividualVote data.
    """
    rows = neo4j.query(
        PARTY_VOTE_MATRIX_QUERY,
        {"chamber": chamber, "legislature": legislature},
    )

    # Count distinct parties that actually have data
    parties_with_data = {r["party"] for r in rows}
    if len(parties_with_data) < 3:
        logger.info(
            "[COMPASS-VOTES] < 3 parties with IndividualVote data for "
            "legislature=%s chamber=%s — returning unavailable",
            legislature,
            chamber,
        )
        return {
            "available": False,
            "reason": "individual_votes_pending",
        }

    matrix, parties, votes = build_party_vote_matrix(rows)
    coords, variance_explained = pca_2d(matrix)

    result = {
        "available": True,
        "legislature": legislature,
        "chamber": chamber,
        "parties": [
            {
                "party": p,
                "x": round(float(coords[i, 0]), 4),
                "y": round(float(coords[i, 1]), 4),
            }
            for i, p in enumerate(parties)
        ],
        "variance_explained": [round(v, 4) for v in variance_explained[:2]],
    }

    logger.info(
        "[COMPASS-VOTES] Computed: legislature=%s chamber=%s "
        "parties=%d votes=%d variance_explained=%s",
        legislature,
        chamber,
        len(parties),
        len(votes),
        result["variance_explained"],
    )
    return result


# ---------------------------------------------------------------------------
# Public cache-aware entry point
# ---------------------------------------------------------------------------

def get_vote_compass(
    legislature: int,
    chamber: str,
    neo4j: Any,
) -> dict:
    """Return cached or freshly computed vote compass for (legislature, chamber).

    Caches results for VOTE_COMPASS_TTL_SECONDS seconds per key.
    """
    key = (legislature, chamber)
    if key in _vote_compass_cache:
        cached_result, ts = _vote_compass_cache[key]
        if time.time() - ts < VOTE_COMPASS_TTL_SECONDS:
            return cached_result

    result = _compute_vote_compass(legislature, chamber, neo4j)
    _vote_compass_cache[key] = (result, time.time())
    return result
