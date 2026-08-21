"""Calibrazione soglie del relevance gate (issue #22).

Esegue il canale denso per i 15 topic reali dell'evaluation set e per un
gruppo di query fuori dominio, replicando la pipeline (rewrite -> embed ->
vector search), e stampa la distribuzione delle similarità. Serve a fissare
`retrieval.relevance_gate` in default.yaml: i topic reali devono passare
tutti, le query fuori dominio no.

Uso:  backend/venv/bin/python build/calibrate_relevance_gate.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.key_pool import make_client  # noqa: E402
from app.services.neo4j_client import Neo4jClient  # noqa: E402
from app.services.retrieval.dense_channel import DenseChannel  # noqa: E402
from app.services.retrieval.query_rewriter import QueryRewriter  # noqa: E402

OUT_OF_DOMAIN = [
    "opinioni sul conflitto in belgio",
    "guerra tra francia e germania",
    "ricette di pasta alla carbonara",
    "campionato di serie A risultati",
    "migliori spiagge della sardegna",
    "riforma delle pensioni in spagna",
    "opinioni sull'indipendenza della scozia",
]

THRESHOLDS = (0.72, 0.75, 0.78, 0.80, 0.82)
RANKS = (10, 25, 50, 100)


def main() -> None:
    settings = get_settings()
    client = Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    dense = DenseChannel(client)
    rewriter = QueryRewriter()
    openai = make_client()

    eval_topics = list(json.load(open(ROOT / "backend" / "evaluation_set.json")))

    def run(query: str) -> dict:
        rewritten = rewriter.rewrite(query)
        emb = openai.embeddings.create(
            input=rewritten, model="text-embedding-3-small"
        ).data[0].embedding
        results = dense.retrieve(emb, top_k=200, similarity_threshold=0.01)
        sims = sorted((r.get("similarity", 0.0) for r in results), reverse=True)
        return {
            "rewritten": rewritten if rewritten != query else None,
            "n": len(sims),
            "max": sims[0] if sims else 0.0,
            "counts": {t: sum(1 for s in sims if s >= t) for t in THRESHOLDS},
            "at_rank": {k: (sims[k - 1] if len(sims) >= k else 0.0) for k in RANKS},
        }

    for label, queries in (("REALI (eval set)", eval_topics),
                           ("FUORI DOMINIO", OUT_OF_DOMAIN)):
        print(f"\n=== {label} ===")
        header = ("max    "
                  + "  ".join(f">={t:.2f}" for t in THRESHOLDS)
                  + "   " + "  ".join(f"@{k}" for k in RANKS))
        print(f"{'query':<45} {header}")
        for q in queries:
            r = run(q)
            counts = "  ".join(f"{r['counts'][t]:>5}" for t in THRESHOLDS)
            ranks = "  ".join(f"{r['at_rank'][k]:.3f}" for k in RANKS)
            print(f"{q[:44]:<45} {r['max']:.3f}  {counts}   {ranks}")

    client.close()


if __name__ == "__main__":
    main()
