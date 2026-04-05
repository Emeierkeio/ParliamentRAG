#!/usr/bin/env python3
"""RRF weight sweep against evaluation_set.json ground truth.

Tests multiple RRF weight combinations and measures retrieval precision
(fraction of baseline_experts whose speaker_id appears in retrieved evidence).

Usage:
    python scripts/rrf_sweep.py
    python scripts/rrf_sweep.py --eval-set path/to/evaluation_set.json
    python scripts/rrf_sweep.py --top-k 50
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.WARNING,  # Suppress noisy retrieval logs during sweep
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RRF weight grid
# ---------------------------------------------------------------------------
RRF_GRID = [
    {"k": 60, "dense": 1.0, "sparse": 0.8, "graph": 0.5, "ner": 0.0},    # current baseline (no NER)
    {"k": 60, "dense": 1.0, "sparse": 0.8, "graph": 0.5, "ner": 0.9},    # with NER
    {"k": 60, "dense": 1.0, "sparse": 0.5, "graph": 0.8, "ner": 0.9},    # graph-boosted
    {"k": 60, "dense": 1.0, "sparse": 1.0, "graph": 0.5, "ner": 0.9},    # equal sparse
    {"k": 30, "dense": 1.0, "sparse": 0.8, "graph": 0.5, "ner": 0.9},    # lower k
    {"k": 100, "dense": 1.0, "sparse": 0.8, "graph": 0.5, "ner": 0.9},   # higher k
    {"k": 60, "dense": 1.0, "sparse": 0.8, "graph": 0.5, "ner": 1.2},    # high NER weight
]

EVAL_SET_PATH = Path(__file__).resolve().parent.parent / "evaluation_set.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmark_results"


# ---------------------------------------------------------------------------
# Precision metric
# ---------------------------------------------------------------------------

def compute_retrieval_precision(
    evidence_list: list,
    baseline_experts: list,
) -> float:
    """Compute retrieval precision: fraction of baseline experts found in evidence.

    A baseline expert is "found" if their speaker_id appears anywhere in the
    retrieved evidence list.

    Args:
        evidence_list: List of retrieved evidence dicts (must have 'speaker_id')
        baseline_experts: List of expert dicts from evaluation_set.json
                          (must have 'id' field = speaker_id)

    Returns:
        Precision in [0.0, 1.0]. Returns 0.0 if no baseline experts.
    """
    if not baseline_experts:
        return 0.0

    retrieved_speaker_ids = {
        e.get("speaker_id", "") for e in evidence_list if e.get("speaker_id")
    }

    found = 0
    for expert in baseline_experts:
        expert_id = expert.get("id", "")
        if expert_id and expert_id in retrieved_speaker_ids:
            found += 1

    return found / len(baseline_experts)


# ---------------------------------------------------------------------------
# Config override helpers
# ---------------------------------------------------------------------------

def _apply_grid_point_to_config(config, grid_point: dict) -> None:
    """Temporarily override RRF config in-memory for this sweep point.

    Modifies the config object's retrieval.rrf dict directly.
    """
    rrf = config.retrieval.get("rrf", {})
    rrf["k"] = grid_point["k"]
    rrf["dense_weight"] = grid_point["dense"]
    rrf["sparse_weight"] = grid_point["sparse"]
    rrf["graph_weight"] = grid_point["graph"]
    rrf["ner_weight"] = grid_point["ner"]
    # Write back (config.retrieval is a dict reference)
    config.retrieval["rrf"] = rrf


# ---------------------------------------------------------------------------
# Sweep runner
# ---------------------------------------------------------------------------

def run_sweep(eval_set: dict, top_k: int = 100) -> list:
    """Run the full RRF grid sweep.

    For each grid point, runs retrieval for every topic in eval_set and
    measures precision against baseline_experts.

    Args:
        eval_set: Loaded evaluation_set.json dict
        top_k: Number of results to retrieve per topic

    Returns:
        List of result dicts, one per grid point, sorted by avg_precision desc.
    """
    try:
        from app.services.deps import get_services
        from app.config import get_config
    except ImportError as e:
        print(f"ERROR: Cannot import app modules. Run from backend/ directory. {e}")
        sys.exit(1)

    services = get_services()
    engine = services.retrieval_engine
    config = get_config()

    topics = list(eval_set.keys())
    print(f"\nRunning sweep over {len(RRF_GRID)} grid points x {len(topics)} topics")
    print(f"Top-K: {top_k}\n")

    all_results = []

    for grid_idx, grid_point in enumerate(RRF_GRID):
        label = (
            f"k={grid_point['k']} "
            f"d={grid_point['dense']} "
            f"s={grid_point['sparse']} "
            f"g={grid_point['graph']} "
            f"n={grid_point['ner']}"
        )
        print(f"[{grid_idx + 1}/{len(RRF_GRID)}] Testing: {label}")

        # Apply in-memory config override
        _apply_grid_point_to_config(config, grid_point)

        per_topic_precision = {}
        topic_latencies = []
        sweep_errors = []

        for topic_name, topic_data in eval_set.items():
            baseline_experts = topic_data.get("baseline_experts", [])
            if not baseline_experts:
                per_topic_precision[topic_name] = None
                continue

            try:
                t0 = time.time()
                result = engine.retrieve_sync(query=topic_name, top_k=top_k)
                elapsed = time.time() - t0
                topic_latencies.append(elapsed)

                evidence_list = []
                for ev in result.get("evidence", []):
                    if hasattr(ev, "speaker_id"):
                        evidence_list.append({"speaker_id": ev.speaker_id})
                    elif isinstance(ev, dict):
                        evidence_list.append(ev)

                precision = compute_retrieval_precision(evidence_list, baseline_experts)
                per_topic_precision[topic_name] = precision

            except Exception as e:
                logger.warning("Error on topic '%s': %s", topic_name, e)
                per_topic_precision[topic_name] = None
                sweep_errors.append(str(e))

        # Compute average precision (exclude None topics)
        valid_precisions = [p for p in per_topic_precision.values() if p is not None]
        avg_precision = sum(valid_precisions) / len(valid_precisions) if valid_precisions else 0.0
        avg_latency = sum(topic_latencies) / len(topic_latencies) if topic_latencies else 0.0

        print(f"  avg_precision={avg_precision:.3f}  avg_latency={avg_latency:.2f}s")

        all_results.append({
            "grid_point": grid_point,
            "label": label,
            "avg_precision": avg_precision,
            "avg_latency_s": avg_latency,
            "per_topic_precision": per_topic_precision,
            "errors": sweep_errors,
        })

    # Sort by avg_precision descending
    all_results.sort(key=lambda x: x["avg_precision"], reverse=True)
    return all_results


# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------

def print_results_table(results: list) -> None:
    """Print a ranked results table."""
    print("\n" + "=" * 80)
    print("RRF SWEEP RESULTS (ranked by avg_precision)")
    print("=" * 80)
    print(f"{'Rank':<5} {'Avg Prec':>9} {'Avg Lat':>9} {'Config'}")
    print("-" * 80)

    for rank, result in enumerate(results, start=1):
        print(
            f"{rank:<5} "
            f"{result['avg_precision']:>9.3f} "
            f"{result['avg_latency_s']:>8.2f}s "
            f"{result['label']}"
        )

    print("=" * 80)

    if results:
        best = results[0]
        print(f"\nBest config: {best['label']}")
        print(f"Per-topic breakdown:")
        for topic, prec in best["per_topic_precision"].items():
            prec_str = f"{prec:.3f}" if prec is not None else "N/A"
            print(f"  {topic[:50]:<50} {prec_str}")


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def save_results(results: list, output_path: Path) -> None:
    """Save sweep results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rrf_grid": RRF_GRID,
        "results": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="RRF weight sweep against evaluation_set.json")
    parser.add_argument(
        "--eval-set",
        type=Path,
        default=EVAL_SET_PATH,
        help="Path to evaluation_set.json",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=100,
        help="Number of results to retrieve per topic (default: 100)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for results JSON (default: benchmark_results/{timestamp}_rrf_sweep.json)",
    )
    args = parser.parse_args()

    # Load evaluation set
    eval_set_path = args.eval_set
    if not eval_set_path.exists():
        print(f"ERROR: evaluation_set.json not found at {eval_set_path}")
        sys.exit(1)

    with open(eval_set_path, encoding="utf-8") as f:
        eval_set = json.load(f)

    print(f"Loaded {len(eval_set)} topics from {eval_set_path}")

    # Run sweep
    results = run_sweep(eval_set, top_k=args.top_k)

    # Print table
    print_results_table(results)

    # Save results
    if args.output:
        output_path = args.output
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = RESULTS_DIR / f"{ts}_rrf_sweep.json"

    save_results(results, output_path)


if __name__ == "__main__":
    main()
