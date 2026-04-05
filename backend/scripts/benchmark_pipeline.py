#!/usr/bin/env python3
"""
Pipeline benchmark harness.

Runs all topics in evaluation_set.json through the full pipeline
(retrieval + authority + generation) and produces a metrics JSON report.

Metrics captured per topic:
  latency_total_s       — wall-clock time for the full pipeline
  latency_retrieval_s   — retrieval portion
  latency_generation_s  — generation portion
  cost_estimate_usd     — estimated from OpenAI usage (input + output tokens)
  citation_count        — number of citations in the output text
  parties_covered       — distinct parties with at least one citation
  section_completeness  — fraction of 10 Italian parliamentary groups with a section heading

Usage:
  python scripts/benchmark_pipeline.py
  python scripts/benchmark_pipeline.py --output benchmark_results/my_run.json
  python scripts/benchmark_pipeline.py --models analyst=gpt-4.1-mini,writer=gpt-4.1-mini,integrator=gpt-4.1-mini
"""
import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add backend root to path so app.* imports work when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.deps import get_services
from app.config import get_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Price table: (input_price_per_M, output_price_per_M) in USD
# ---------------------------------------------------------------------------
PRICE_TABLE = {
    "gpt-4o":        (2.50, 10.00),
    "gpt-4o-mini":   (0.15,  0.60),
    "gpt-4.1":       (2.00,  8.00),
    "gpt-4.1-mini":  (0.20,  0.80),
    "gpt-4.1-nano":  (0.05,  0.20),
}

# All 10 Italian parliamentary groups for section completeness check
ALL_PARTIES = [
    "Fratelli d'Italia",
    "Lega",
    "Forza Italia",
    "Partito Democratico",
    "Movimento 5 Stelle",
    "Alleanza Verdi",
    "Azione",
    "Italia Viva",
    "Noi Moderati",
    "Misto",
]

EVAL_SET_PATH = Path(__file__).resolve().parent.parent / "evaluation_set.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmark_results"


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def estimate_cost(usage: dict, model_name: str) -> float:
    """
    Estimate USD cost from OpenAI usage dict and model name.

    Args:
        usage: dict with 'prompt_tokens' and 'completion_tokens' (or 'input_tokens'/'output_tokens')
        model_name: OpenAI model identifier

    Returns:
        Estimated cost in USD
    """
    # Support both OpenAI SDK field names
    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens", 0)
    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens", 0)

    # Find price entry with partial key match (handles model variants)
    prices = None
    for key, val in PRICE_TABLE.items():
        if key in model_name or model_name.startswith(key):
            prices = val
            break

    if prices is None:
        # Fallback to gpt-4o pricing for unknown models
        logger.warning(f"Unknown model '{model_name}', falling back to gpt-4o pricing")
        prices = PRICE_TABLE["gpt-4o"]

    input_price_per_m, output_price_per_m = prices
    return (input_tokens * input_price_per_m + output_tokens * output_price_per_m) / 1_000_000


# ---------------------------------------------------------------------------
# Citation and coverage metrics
# ---------------------------------------------------------------------------

def count_citations(text: str) -> int:
    """Count [CIT:...] style citations or markdown link citations in output text."""
    cit_pattern = re.findall(r'\[CIT:[^\]]+\]', text)
    # Also count ID:... inline citations from surgeon output
    id_pattern = re.findall(r'ID:[a-zA-Z0-9_\-]+', text)
    return len(cit_pattern) + len(id_pattern)


def count_parties_covered(text: str) -> int:
    """Count distinct parties mentioned in citations."""
    # Look for party names in citation markers: «...» [Speaker, Party, Date, ID:...]
    # or section headings
    parties_found = set()
    for party in ALL_PARTIES:
        if party.lower() in text.lower():
            parties_found.add(party)
    return len(parties_found)


def compute_section_completeness(text: str) -> bool:
    """
    Return True if all 10 Italian parliamentary groups have a section heading.

    A section heading is detected by any party name appearing in a ## heading.
    """
    headings = re.findall(r'^#{1,3}\s+(.+)$', text, re.MULTILINE | re.IGNORECASE)
    heading_text = " ".join(headings).lower()

    covered = 0
    for party in ALL_PARTIES:
        if any(word.lower() in heading_text for word in party.split() if len(word) > 4):
            covered += 1

    return covered >= len(ALL_PARTIES)


# ---------------------------------------------------------------------------
# Single-topic benchmark
# ---------------------------------------------------------------------------

async def benchmark_single_topic(
    topic_name: str,
    services: dict,
    config,
    model_overrides: dict = None,
) -> dict:
    """
    Run the full pipeline for one topic and return per-topic metrics.

    Args:
        topic_name: The topic/query string
        services: dict from get_services()
        config: AppConfig instance
        model_overrides: optional dict of {role: model_name} to override config

    Returns:
        dict with all per-topic metrics
    """
    import asyncio

    wall_start = time.time()
    cost_usd = 0.0
    error = None

    try:
        # --- Retrieval ---
        ret_start = time.time()
        retrieval_result = await services["retrieval"].retrieve(
            query=topic_name,
            top_k=100,
        )
        latency_retrieval_s = time.time() - ret_start

        evidence_list = retrieval_result["evidence"]
        evidence_dicts = []
        for e in evidence_list:
            d = e.model_dump()
            if e.embedding is not None:
                d["embedding"] = e.embedding
            if e.text:
                d["text"] = e.text
            evidence_dicts.append(d)

        # --- Authority scoring ---
        loop = asyncio.get_running_loop()
        speaker_ids = list(set(e.speaker_id for e in evidence_list if e.speaker_id))
        query_embedding = retrieval_result.get("query_embedding")
        if query_embedding is None:
            query_embedding = await loop.run_in_executor(
                None, lambda: services["retrieval"].embed_query(topic_name)
            )

        authority_all = await loop.run_in_executor(
            None,
            lambda: services["authority"].compute_all_authority(speaker_ids, query_embedding),
        )
        authority_scores = {sid: r["total_score"] for sid, r in authority_all.items()}

        for ed in evidence_dicts:
            sid = ed.get("speaker_id", "")
            ed["authority_score"] = authority_scores.get(sid, 0.0)

        # --- Generation ---
        gen_start = time.time()
        generation_result = await services["generation"].generate(
            query=topic_name,
            evidence_list=evidence_dicts,
        )
        latency_generation_s = time.time() - gen_start

        # Extract generated text
        generated_text = generation_result.get("text", "")

        # Accumulate cost from generation metadata
        gen_meta = generation_result.get("metadata", {})
        stages_meta = gen_meta.get("stages", {})
        for stage_name, stage_data in stages_meta.items():
            usage = stage_data.get("usage") or stage_data.get("token_usage") or {}
            if usage:
                model = stage_data.get("model", "gpt-4o")
                if model_overrides:
                    model = model_overrides.get(stage_name, model)
                cost_usd += estimate_cost(usage, model)

        # Fallback: try usage at top level
        top_usage = generation_result.get("usage", {})
        if top_usage and cost_usd == 0.0:
            models_config = config.load_config().get("generation", {}).get("models", {})
            analyst_model = model_overrides.get("analyst", models_config.get("analyst", "gpt-4o")) if model_overrides else models_config.get("analyst", "gpt-4o")
            cost_usd += estimate_cost(top_usage, analyst_model)

        citation_count = count_citations(generated_text)
        parties_covered = count_parties_covered(generated_text)
        section_completeness = compute_section_completeness(generated_text)

    except Exception as exc:
        logger.error(f"Topic '{topic_name}' failed: {exc}", exc_info=True)
        error = str(exc)
        latency_retrieval_s = 0.0
        latency_generation_s = 0.0
        citation_count = 0
        parties_covered = 0
        section_completeness = False

    latency_total_s = time.time() - wall_start

    return {
        "topic": topic_name,
        "latency_total_s": round(latency_total_s, 3),
        "latency_retrieval_s": round(latency_retrieval_s, 3),
        "latency_generation_s": round(latency_generation_s, 3),
        "cost_estimate_usd": round(cost_usd, 6),
        "citation_count": citation_count,
        "parties_covered": parties_covered,
        "section_completeness": section_completeness,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Full benchmark run
# ---------------------------------------------------------------------------

async def run_benchmark(eval_set: dict, model_overrides: dict = None) -> list:
    """
    Run benchmark for all topics in eval_set sequentially.

    Args:
        eval_set: dict loaded from evaluation_set.json
        model_overrides: optional {role: model_name} dict

    Returns:
        list of per-topic result dicts
    """
    services = get_services()
    config = get_config()

    results = []
    topics = list(eval_set.keys())
    logger.info(f"Running benchmark for {len(topics)} topics...")

    for i, topic_name in enumerate(topics, 1):
        logger.info(f"[{i}/{len(topics)}] Running topic: {topic_name[:60]}")
        result = await benchmark_single_topic(topic_name, services, config, model_overrides)
        results.append(result)
        status = "ERROR" if result["error"] else "OK"
        logger.info(
            f"  {status} | latency={result['latency_total_s']:.1f}s | "
            f"cost=${result['cost_estimate_usd']:.4f} | "
            f"citations={result['citation_count']} | "
            f"parties={result['parties_covered']}"
        )

    return results


# ---------------------------------------------------------------------------
# Summary printing
# ---------------------------------------------------------------------------

def print_summary(results: list) -> None:
    """Print a human-readable summary table of benchmark results."""
    print("\n" + "=" * 90)
    print(f"{'TOPIC':<40} {'LAT(s)':>7} {'COST($)':>9} {'CITS':>5} {'PRTS':>5} {'SECT':>5}")
    print("-" * 90)

    total_latency = 0.0
    total_cost = 0.0
    total_citations = 0
    total_parties = 0
    completed = 0
    errors = 0

    for r in results:
        topic = r["topic"][:39]
        lat = r["latency_total_s"]
        cost = r["cost_estimate_usd"]
        cits = r["citation_count"]
        prts = r["parties_covered"]
        sect = "Y" if r["section_completeness"] else "N"
        err = " ERROR" if r["error"] else ""

        print(f"{topic:<40} {lat:>7.1f} {cost:>9.4f} {cits:>5} {prts:>5} {sect:>5}{err}")

        if not r["error"]:
            total_latency += lat
            total_cost += cost
            total_citations += cits
            total_parties += prts
            completed += 1
        else:
            errors += 1

    print("=" * 90)
    if completed > 0:
        print(
            f"{'AVERAGES':<40} {total_latency/completed:>7.1f} "
            f"{total_cost/completed:>9.4f} "
            f"{total_citations//completed:>5} "
            f"{total_parties//completed:>5}"
        )
        print(f"\nTotals: {completed} completed, {errors} errors | "
              f"Total cost: ${total_cost:.4f} | Total time: {total_latency:.1f}s")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_model_overrides(raw: str) -> dict:
    """
    Parse --models argument like 'analyst=gpt-4.1-mini,writer=gpt-4.1-mini'.

    Returns dict {role: model_name}.
    """
    overrides = {}
    for part in raw.split(","):
        part = part.strip()
        if "=" in part:
            role, model = part.split("=", 1)
            overrides[role.strip()] = model.strip()
    return overrides


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Pipeline benchmark — runs evaluation_set.json topics through full pipeline."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path. Default: benchmark_results/<timestamp>_baseline.json",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Model overrides: analyst=gpt-4.1-mini,writer=gpt-4.1-mini,integrator=gpt-4.1-mini",
    )
    parser.add_argument(
        "--topics",
        default=None,
        help="Comma-separated list of topic names to run (default: all)",
    )
    args = parser.parse_args()

    # Load evaluation set
    if not EVAL_SET_PATH.exists():
        print(f"ERROR: evaluation_set.json not found at {EVAL_SET_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        eval_set = json.load(f)

    # Filter topics if requested
    if args.topics:
        topic_filter = {t.strip() for t in args.topics.split(",") if t.strip()}
        eval_set = {k: v for k, v in eval_set.items() if k in topic_filter}
        if not eval_set:
            print("ERROR: No matching topics found.", file=sys.stderr)
            sys.exit(1)

    # Parse model overrides
    model_overrides = parse_model_overrides(args.models) if args.models else None

    # Determine output path
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = RESULTS_DIR / f"{ts}_baseline.json"

    # Run benchmark
    try:
        results = asyncio.run(run_benchmark(eval_set, model_overrides))
    except Exception as exc:
        logger.error(f"Benchmark failed: {exc}", exc_info=True)
        # Write placeholder so baseline_before_opt.json always exists
        placeholder = {
            "status": "deferred",
            "reason": f"services unavailable: {exc}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(placeholder, f, indent=2)
        print(f"WARNING: Benchmark failed. Placeholder written to {output_path}")
        print(f"Reason: {exc}")
        sys.exit(0)

    # Build report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_overrides": model_overrides or {},
        "topics_count": len(results),
        "results": results,
        "summary": {
            "avg_latency_total_s": round(
                sum(r["latency_total_s"] for r in results) / max(len(results), 1), 3
            ),
            "avg_latency_retrieval_s": round(
                sum(r["latency_retrieval_s"] for r in results) / max(len(results), 1), 3
            ),
            "avg_latency_generation_s": round(
                sum(r["latency_generation_s"] for r in results) / max(len(results), 1), 3
            ),
            "total_cost_usd": round(sum(r["cost_estimate_usd"] for r in results), 6),
            "avg_cost_usd": round(
                sum(r["cost_estimate_usd"] for r in results) / max(len(results), 1), 6
            ),
            "avg_citation_count": round(
                sum(r["citation_count"] for r in results) / max(len(results), 1), 2
            ),
            "avg_parties_covered": round(
                sum(r["parties_covered"] for r in results) / max(len(results), 1), 2
            ),
            "section_completeness_rate": round(
                sum(1 for r in results if r["section_completeness"]) / max(len(results), 1), 3
            ),
            "error_count": sum(1 for r in results if r["error"]),
        }
    }

    # Save report
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print_summary(results)
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
