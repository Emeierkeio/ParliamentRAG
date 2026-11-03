"""Vettori dei brani e delle domande per i due modelli in prova.

  openai invia brani|domande    batch di text-embedding-3-large (3072 dimensioni)
  openai raccogli brani|domande scrive vettori/openai-<cosa>.npy
  e5 brani|domande              multilingual-e5-large sul Mac (ambiente separato con sentence-transformers)

I vettori si salvano normalizzati, nello stesso ordine di brani.jsonl e domande.jsonl.
"""

import json
import os
import sys
import time
from pathlib import Path

QUI = Path(__file__).parent
VETTORI = QUI / "vettori"
OPENAI = "text-embedding-3-large"
E5 = os.environ.get("E5_MODELLO", "intfloat/multilingual-e5-large")  # o una cartella locale col modello già scaricato
PER_RICHIESTA = 100
PER_FILE = 2_000


def _testi(cosa: str) -> list[str]:
    f = "brani.jsonl" if cosa == "brani" else "domande.jsonl"
    campo = "testo" if cosa == "brani" else "domanda"
    return [json.loads(r)[campo] for r in open(QUI / f)]


def openai_invia(cosa: str) -> None:
    """Un batch ogni PER_FILE testi: la connessione non regge file da 20 MB in un colpo solo."""
    from pipeline import openai_batch as batch
    testi = _testi(cosa)
    ids = []
    for parte, inizio in enumerate(range(0, len(testi), PER_FILE)):
        f = QUI / f"richieste-vettori-{cosa}-{parte}.jsonl"
        with open(f, "w") as out:
            for i in range(inizio, min(inizio + PER_FILE, len(testi)), PER_RICHIESTA):
                out.write(json.dumps({"custom_id": f"{cosa}-{i}", "method": "POST", "url": "/v1/embeddings",
                                      "body": {"model": OPENAI, "input": testi[i:i + PER_RICHIESTA]}}, ensure_ascii=False) + "\n")
        ids.append(batch.invia(f, "/v1/embeddings", f"prova embedding: {cosa} {parte}"))
    (QUI / f"batch-vettori-{cosa}.txt").write_text("\n".join(ids))
    print(len(testi), "testi inviati in", len(ids), "batch")


def openai_raccogli(cosa: str) -> None:
    import numpy as np
    from pipeline import openai_batch as batch
    ris = {}
    for bid in (QUI / f"batch-vettori-{cosa}.txt").read_text().split():
        s = batch.aspetta(bid)
        if s["status"] != "completed":
            sys.exit(f"batch {s['status']}")
        ris |= batch.risultati(s)
    n = len(_testi(cosa))
    righe = []
    for i in range(0, n, PER_RICHIESTA):
        corpo = ris[f"{cosa}-{i}"]
        righe += [d["embedding"] for d in sorted(corpo["data"], key=lambda d: d["index"])]
    m = np.array(righe, dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    VETTORI.mkdir(exist_ok=True)
    np.save(VETTORI / f"openai-{cosa}.npy", m)
    print(m.shape, "token:", sum((c.get("usage") or {}).get("total_tokens", 0) for c in ris.values()))


def e5(cosa: str) -> None:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    modello = SentenceTransformer(E5, device="mps")
    prefisso = "passage: " if cosa == "brani" else "query: "  # come chiede la scheda del modello
    t0 = time.time()
    m = modello.encode([prefisso + t for t in _testi(cosa)], batch_size=32, normalize_embeddings=True,
                       show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
    VETTORI.mkdir(exist_ok=True)
    np.save(VETTORI / f"e5-{cosa}.npy", m)
    print(m.shape, f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    if sys.argv[1] == "openai":
        {"invia": openai_invia, "raccogli": openai_raccogli}[sys.argv[2]](sys.argv[3])
    else:
        e5(sys.argv[2])
