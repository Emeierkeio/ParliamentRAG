"""Measure the retrieval-pool impact of the graph-channel similarity fix.

Until 2026-09-08 the graph channel fed raw cosine similarity into the merger
while the dense channel used the Neo4j vector-index scale ((1+cos)/2), so the
merger's relevance term compared incompatible magnitudes. This script runs
retrieval for every topic in evaluation_set.json and merges the same channel
outputs twice: once with the fixed (normalized) graph similarities and once
with the pre-fix (raw) ones, then reports pool composition deltas.

Cost: one embedding call per topic, no generation. The query rewriter is
skipped so both arms embed the identical text.

Approximation: graph chunks without an embedding keep the 0.5 neutral prior
in both arms (pre-fix they also carried 0.5), so only re-scored chunks are
de-normalized (raw = 2 * normalized - 1).

Usage: venv/bin/python scripts/eval_similarity_scale_delta.py
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.deps import get_services  # noqa: E402


def pool_stats(merged):
    channels = {}
    parties = set()
    for r in merged:
        channels[r.get("retrieval_channel", "?")] = channels.get(
            r.get("retrieval_channel", "?"), 0) + 1
        if r.get("party"):
            parties.add(r["party"])
    return {
        "size": len(merged),
        "graph_share": round(channels.get("graph", 0) / max(1, len(merged)), 3),
        "channels": channels,
        "parties": len(parties),
    }


def main():
    services = get_services()
    engine = services["retrieval"]
    eval_set = json.load(open(Path(__file__).resolve().parents[1] / "evaluation_set.json"))

    rows = []
    for topic in eval_set:
        query = topic
        emb = engine.embed_query(query)
        dense = engine.dense_channel.retrieve(query_embedding=emb, top_k=200)
        graph = engine.graph_channel.retrieve(query=query, query_embedding=emb)

        graph_old = copy.deepcopy(graph)
        for r in graph_old:
            s = r.get("similarity", 0.5)
            if s != 0.5:  # 0.5 = neutral prior for missing embeddings, unchanged pre-fix
                r["similarity"] = 2.0 * s - 1.0

        merged_new = engine.merger.merge(dense, copy.deepcopy(graph), None, top_k=100)
        merged_old = engine.merger.merge(dense, graph_old, None, top_k=100)

        ids_new = {r["evidence_id"] for r in merged_new}
        ids_old = {r["evidence_id"] for r in merged_old}
        overlap = len(ids_new & ids_old) / max(1, len(ids_new | ids_old))

        row = {
            "topic": query[:60],
            "dense": len(dense),
            "graph": len(graph),
            "old": pool_stats(merged_old),
            "new": pool_stats(merged_new),
            "jaccard_overlap": round(overlap, 3),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))

    n = len(rows)
    print("\n=== SUMMARY over", n, "topics ===")
    print("mean graph share old:", round(sum(r["old"]["graph_share"] for r in rows) / n, 3))
    print("mean graph share new:", round(sum(r["new"]["graph_share"] for r in rows) / n, 3))
    print("mean pool jaccard overlap old vs new:", round(sum(r["jaccard_overlap"] for r in rows) / n, 3))


if __name__ == "__main__":
    main()
