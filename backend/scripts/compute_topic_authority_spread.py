"""
compute_topic_authority_spread.py

Pre-computes the authority score distribution (spread) across ALL Deputies
for each topic in evaluation_set.json.

This is used to compute a meaningful authority_discrimination metric that
reflects how much authority scores vary across ALL parliamentarians on each topic,
not just among the small set of cited experts.

For each topic the script computes:

  authority_spread:
    std      – population standard deviation of all deputies' scores
    mean     – mean authority score across all deputies
    p25      – 25th percentile
    median   – median (50th percentile)
    p75      – 75th percentile
    n        – number of deputies scored

  authority_spread_by_group:
    {group: {std, mean, n}} – same statistics per parliamentary group

The results are stored back in evaluation_set.json under each topic entry.
After running this script, evaluation.py will use authority_spread.std as the
authority_discrimination metric instead of the cited-experts std.

Usage (run from backend/ directory with venv active):
    python scripts/compute_topic_authority_spread.py [--dry-run] [--topic "Partial name"]

Options:
    --dry-run       Print results without writing to disk
    --topic NAME    Process only the topic whose name contains NAME (for testing)
"""

import sys
import json
import math
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add backend/ to sys.path so app.* imports work when called from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.neo4j_client import Neo4jClient
from app.services.authority.scorer import AuthorityScorer
from app.services.retrieval.engine import RetrievalEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("compute_topic_authority_spread")

EVAL_SET_PATH = Path(__file__).parent.parent / "evaluation_set.json"


def _fetch_all_deputy_ids(client: Neo4jClient) -> List[str]:
    """Fetch all Deputy node IDs from Neo4j."""
    results = client.query("MATCH (d:Deputy) RETURN d.id AS id")
    ids = [r["id"] for r in results if r.get("id")]
    return ids


def _fetch_deputy_names(client: Neo4jClient, ids: List[str]) -> Dict[str, str]:
    """Fetch full names for a list of deputy IDs. Returns {id: 'FirstName LastName'}."""
    if not ids:
        return {}
    results = client.query(
        "MATCH (d:Deputy) WHERE d.id IN $ids "
        "RETURN d.id AS id, d.first_name AS first_name, d.last_name AS last_name",
        {"ids": ids},
    )
    return {
        r["id"]: f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
        for r in results
        if r.get("id")
    }


def _compute_stats(scores: List[float]) -> Dict[str, Any]:
    """Compute population std, mean, and percentiles for a list of scores."""
    n = len(scores)
    if n == 0:
        return {"std": 0.0, "mean": 0.0, "p25": 0.0, "median": 0.0, "p75": 0.0, "n": 0}

    mean = sum(scores) / n
    variance = sum((x - mean) ** 2 for x in scores) / n  # population std
    std = math.sqrt(variance)

    sorted_scores = sorted(scores)

    def percentile(p: float) -> float:
        idx = (n - 1) * p / 100
        lo = int(idx)
        hi = lo + 1
        if hi >= n:
            return sorted_scores[-1]
        return sorted_scores[lo] + (idx - lo) * (sorted_scores[hi] - sorted_scores[lo])

    return {
        "std": round(std, 6),
        "mean": round(mean, 6),
        "p25": round(percentile(25), 6),
        "median": round(percentile(50), 6),
        "p75": round(percentile(75), 6),
        "n": n,
    }


def process_topic(
    authority_scorer: AuthorityScorer,
    retrieval: RetrievalEngine,
    client: Neo4jClient,
    all_deputy_ids: List[str],
    topic: str,
) -> Dict[str, Any]:
    """Compute authority spread for all deputies on one topic.

    Returns a dict with 'authority_spread' and 'authority_spread_by_group' keys
    to be merged into the existing evaluation_set.json entry for this topic.
    """
    logger.info(f"  Embedding topic query: {topic[:60]}…")
    query_embedding = retrieval.embed_query(topic)

    logger.info(f"  Scoring {len(all_deputy_ids)} deputies…")
    all_scores = authority_scorer.compute_all_authority(all_deputy_ids, query_embedding)

    # Collect scores and group memberships from the returned result dicts
    scores_list: List[float] = []
    group_scores: Dict[str, List[float]] = {}
    min_sid: Optional[str] = None
    max_sid: Optional[str] = None
    min_score: float = float("inf")
    max_score: float = float("-inf")

    for sid, result in all_scores.items():
        score = result.get("total_score", 0.0)
        group = result.get("current_group", "")
        scores_list.append(score)
        if group:
            group_scores.setdefault(group, []).append(score)
        if score < min_score:
            min_score = score
            min_sid = sid
        if score > max_score:
            max_score = score
            max_sid = sid

    spread = _compute_stats(scores_list)
    spread_by_group = {g: _compute_stats(s) for g, s in group_scores.items() if s}

    # Fetch names for min/max deputies
    ids_to_fetch = [sid for sid in [min_sid, max_sid] if sid is not None]
    name_map = _fetch_deputy_names(client, ids_to_fetch)

    spread["min_score"] = round(min_score, 6) if min_sid else None
    spread["min_id"] = min_sid
    spread["min_name"] = name_map.get(min_sid, min_sid) if min_sid else None
    spread["max_score"] = round(max_score, 6) if max_sid else None
    spread["max_id"] = max_sid
    spread["max_name"] = name_map.get(max_sid, max_sid) if max_sid else None

    logger.info(
        f"  Spread: std={spread['std']:.4f}  mean={spread['mean']:.4f}  "
        f"n={spread['n']}  groups={len(spread_by_group)}"
    )
    logger.info(f"  Min: {spread['min_name']} ({spread['min_score']:.4f})")
    logger.info(f"  Max: {spread['max_name']} ({spread['max_score']:.4f})")

    return {
        "authority_spread": spread,
        "authority_spread_by_group": spread_by_group,
    }


def _save(data: dict) -> None:
    """Atomically write *data* to EVAL_SET_PATH via a temp file."""
    tmp = EVAL_SET_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(EVAL_SET_PATH)
    logger.info(f"Saved {EVAL_SET_PATH}")


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    topic_filter: Optional[str] = None
    if "--topic" in sys.argv:
        idx = sys.argv.index("--topic")
        if idx + 1 < len(sys.argv):
            topic_filter = sys.argv[idx + 1]

    logger.info(f"Loading evaluation set from {EVAL_SET_PATH}")
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        data: dict = json.load(f)

    settings = get_settings()
    logger.info(f"Connecting to Neo4j at {settings.neo4j_uri}")
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)

    authority_scorer = AuthorityScorer(client)
    retrieval = RetrievalEngine(client)

    logger.info("Fetching all Deputy IDs from Neo4j…")
    all_deputy_ids = _fetch_all_deputy_ids(client)
    logger.info(f"Found {len(all_deputy_ids)} deputies")

    if not all_deputy_ids:
        logger.error("No deputies found in Neo4j — aborting.")
        sys.exit(1)

    # Pre-populate enriched with all existing entries so that intermediate
    # saves always contain the full file (processed + still-to-process).
    enriched: dict = dict(data)

    topics = list(data.items())
    total = sum(
        1 for _, e in topics
        if not topic_filter or topic_filter.lower() in _.lower()
    )
    processed = 0

    for topic, entry in topics:
        # Apply optional single-topic filter (useful for smoke-testing)
        if topic_filter and topic_filter.lower() not in topic.lower():
            continue

        # Normalise old-format entries (plain string → dict)
        if isinstance(entry, str):
            entry = {"baseline_answer": entry}
        elif not isinstance(entry, dict):
            logger.warning(f"[{topic}] Unexpected entry type {type(entry)}, skipping.")
            continue

        processed += 1
        logger.info(f"\n{'─'*60}")
        logger.info(f"Topic ({processed}/{total}): {topic}")
        logger.info(f"{'─'*60}")

        try:
            spread_data = process_topic(authority_scorer, retrieval, client, all_deputy_ids, topic)
            # Merge spread data into existing entry (preserving baseline_answer, experts, metrics)
            enriched[topic] = {**entry, **spread_data}
        except Exception as exc:
            logger.error(f"[{topic}] Processing failed: {exc}", exc_info=True)
            enriched[topic] = entry

        if not dry_run:
            _save(enriched)

    if dry_run:
        logger.info("\n── DRY-RUN SUMMARY (not writing to disk) ──")
        for topic, entry in enriched.items():
            if not isinstance(entry, dict):
                continue
            spread = entry.get("authority_spread", {})
            print(f"\n{topic}")
            print(
                f"  std={spread.get('std', 'N/A')}  mean={spread.get('mean', 'N/A')}  "
                f"n={spread.get('n', 'N/A')}"
            )
            print(
                f"  min={spread.get('min_score', 'N/A')} ({spread.get('min_name', '?')})  "
                f"max={spread.get('max_score', 'N/A')} ({spread.get('max_name', '?')})"
            )
            by_group = entry.get("authority_spread_by_group", {})
            for g, s in sorted(by_group.items()):
                print(f"    [{g[:35]:35s}]  std={s['std']:.4f}  mean={s['mean']:.4f}  n={s['n']}")
        return

    logger.info(f"\nAll {processed} topic(s) processed and saved to {EVAL_SET_PATH}")

    # Print summary table
    logger.info("\n── SUMMARY ──")
    logger.info(f"{'Topic':<50} {'Std':>8} {'Mean':>8} {'N':>6}")
    logger.info("─" * 76)
    for topic, entry in enriched.items():
        if not isinstance(entry, dict):
            continue
        spread = entry.get("authority_spread", {})
        print(
            f"{topic[:49]:<50} {spread.get('std', 0):>8.4f} "
            f"{spread.get('mean', 0):>8.4f} {spread.get('n', 0):>6}"
        )


if __name__ == "__main__":
    main()
