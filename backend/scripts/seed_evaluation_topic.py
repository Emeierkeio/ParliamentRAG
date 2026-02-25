"""
Seed evaluation_set.json with a new baseline entry for a given topic.

Riceve il topic e il baseline_answer come argomenti; calcola automaticamente
baseline_experts tramite retrieval + authority scoring.

Usage (from backend/ directory, with venv active):

  # Testo da file:
  python scripts/seed_evaluation_topic.py "Golden Power" --answer-file golden_power.md

  # Testo da stdin (incolla e poi Ctrl+D):
  python scripts/seed_evaluation_topic.py "Golden Power" --answer-stdin

Options:
    --answer-file <path>   Legge il baseline_answer dal file indicato
    --answer-stdin         Legge il baseline_answer da stdin
    --overwrite            Sostituisce l'entry se esiste già

After seeding, run enrich_evaluation_set.py to compute baseline_metrics:
    python scripts/enrich_evaluation_set.py
"""
import sys
import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add backend/ to path so app.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.deps import get_services
from app.routers.chat import _compute_experts_for_frontend

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed_evaluation_topic")

EVAL_SET_PATH = Path(__file__).parent.parent / "evaluation_set.json"


async def compute_experts(query: str, services: dict) -> list:
    """Retrieval + authority scoring + experts for a query."""
    loop = asyncio.get_running_loop()

    logger.info(f"[{query}] Retrieval...")
    retrieval_result = await loop.run_in_executor(
        None, lambda: services["retrieval"].retrieve_sync(query=query, top_k=100)
    )
    evidence_list = retrieval_result["evidence"]
    evidence_dicts = []
    for e in evidence_list:
        d = e.model_dump()
        d["embedding"] = e.embedding
        evidence_dicts.append(d)
    logger.info(
        f"[{query}] {len(evidence_list)} evidence "
        f"(dense={retrieval_result['metadata'].get('dense_channel_count', 0)}, "
        f"graph={retrieval_result['metadata'].get('graph_channel_count', 0)})"
    )

    logger.info(f"[{query}] Authority scoring...")
    speaker_ids = list(set(
        e.speaker_id for e in evidence_list
        if e.speaker_id and e.speaker_role == "Deputy"
    ))
    query_embedding = await loop.run_in_executor(
        None, lambda: services["retrieval"].embed_query(query)
    )
    authority_scores: dict = {}
    authority_details: dict = {}
    if speaker_ids:
        def _compute_single(sid):
            return sid, services["authority"].compute_authority(sid, query_embedding)

        with ThreadPoolExecutor(max_workers=min(10, len(speaker_ids))) as pool:
            futures = [loop.run_in_executor(pool, _compute_single, sid) for sid in speaker_ids]
            results = await asyncio.gather(*futures)
        for sid, result in results:
            authority_scores[sid] = result["total_score"]
            authority_details[sid] = result

    for d in evidence_dicts:
        sid = d.get("speaker_id", "")
        if sid in authority_scores:
            d["authority_score"] = authority_scores[sid]
    logger.info(f"[{query}] Scored {len(authority_scores)} speakers")

    logger.info(f"[{query}] Computing experts...")
    experts = await _compute_experts_for_frontend(
        evidence_list, authority_scores, authority_details, services["neo4j"]
    )
    logger.info(f"[{query}] {len(experts)} experts found")
    return experts


async def main_async(topic: str, baseline_answer: str, overwrite: bool) -> None:
    logger.info(f"Loading {EVAL_SET_PATH}")
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        data: dict = json.load(f)

    if topic in data and not overwrite:
        logger.warning(f"'{topic}' già presente — usa --overwrite per sostituirlo")
        return

    services = get_services()
    try:
        experts = await compute_experts(topic, services)
        data[topic] = {
            "baseline_answer": baseline_answer,
            "baseline_experts": experts,
        }
        with open(EVAL_SET_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Salvato '{topic}' in {EVAL_SET_PATH}")
    finally:
        services["neo4j"].close()


def _parse_args():
    args = sys.argv[1:]
    overwrite = "--overwrite" in args
    args = [a for a in args if a != "--overwrite"]

    # topic is always the first positional argument
    if not args:
        print(__doc__)
        sys.exit(1)
    topic = args[0]

    baseline_answer = None

    if "--answer-file" in args:
        idx = args.index("--answer-file")
        path = Path(args[idx + 1])
        baseline_answer = path.read_text(encoding="utf-8")
        logger.info(f"Letto baseline_answer da {path} ({len(baseline_answer)} chars)")

    elif "--answer-stdin" in args:
        print("Incolla il baseline_answer e premi Ctrl+D quando hai finito:")
        baseline_answer = sys.stdin.read()

    else:
        print("Errore: specifica --answer-file <path> oppure --answer-stdin")
        sys.exit(1)

    return topic, baseline_answer.strip(), overwrite


def main() -> None:
    topic, baseline_answer, overwrite = _parse_args()
    asyncio.run(main_async(topic, baseline_answer, overwrite))


if __name__ == "__main__":
    main()
