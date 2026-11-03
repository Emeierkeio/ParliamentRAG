"""Domande della prova: 150 con il brano giusto noto, scritte dal modello di chat; 30 per tema, prese dal benchmark.

Uso:
  .venv/bin/python -m benchmark.embedding.domande invia     crea il batch delle domande generate
  .venv/bin/python -m benchmark.embedding.domande raccogli  aspetta il batch e scrive domande.jsonl
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from pipeline import openai_batch as batch

QUI = Path(__file__).parent
MODELLO = "gpt-5.6-terra"  # lo stesso dell'agente del prototipo
CANDIDATI = 220            # alcuni brani sono procedurali e il modello li salta
NOTE = 150
TEMA = 30

ISTRUZIONI = """Ti do un brano di un resoconto del Parlamento italiano. Scrivi UNA domanda, in italiano, che un cittadino o un giornalista potrebbe fare a un motore di ricerca e a cui questo brano risponde bene.

Regole:
- Usa parole tue: non copiare frasi del brano, non ripetere termini rari o tecnici se esiste un modo comune di dirlo.
- Puoi nominare il tema, l'atto o la persona solo se senza quel nome la domanda non avrebbe senso.
- Al massimo 25 parole, niente premesse.
- Se il brano è solo procedurale (apertura di seduta, votazioni senza contenuto, saluti) o non dice niente di riconoscibile, rispondi soltanto: SALTA"""


def _brani() -> list[dict]:
    return [json.loads(r) for r in open(QUI / "brani.jsonl")]


def invia() -> None:
    rnd = random.Random(7)
    per_tipo = defaultdict(list)
    for b in _brani():
        per_tipo[(b["ramo"], b["resoconto"])].append(b)
    tot = sum(len(v) for v in per_tipo.values())
    scelti = []
    for chiave, v in per_tipo.items():  # stesse proporzioni dei brani
        scelti += rnd.sample(v, max(1, round(CANDIDATI * len(v) / tot)))
    f = QUI / "richieste-domande.jsonl"
    with open(f, "w") as out:
        for b in scelti:
            out.write(json.dumps({"custom_id": b["id"], "method": "POST", "url": "/v1/responses", "body": {
                "model": MODELLO, "instructions": ISTRUZIONI, "input": b["testo"]}}, ensure_ascii=False) + "\n")
    bid = batch.invia(f, "/v1/responses", "prova embedding: domande generate")
    (QUI / "batch-domande.txt").write_text(bid)
    print(len(scelti), "richieste, batch", bid)


def _testo(corpo: dict) -> str:
    for voce in corpo.get("output", []):
        for parte in voce.get("content", []) or []:
            if parte.get("type") == "output_text":
                return parte["text"].strip()
    return ""


def raccogli() -> None:
    s = batch.aspetta((QUI / "batch-domande.txt").read_text().strip())
    if s["status"] != "completed":
        sys.exit(f"batch {s['status']}")
    generate = []
    for bid, corpo in batch.risultati(s).items():
        t = _testo(corpo)
        if t and "SALTA" not in t:
            generate.append({"id": "G-" + str(len(generate) + 1), "tipo": "nota", "domanda": t, "giusti": [bid]})
    random.Random(7).shuffle(generate)
    generate = generate[:NOTE]
    tema = [json.loads(r) for r in open(QUI.parent / "domande.jsonl")]
    tema = [d for d in tema if d["tipo_risposta"] in ("sintesi_con_citazioni", "confronto_gruppi") and d["copertura"] == "si"]
    tema = random.Random(7).sample(tema, TEMA)
    with open(QUI / "domande.jsonl", "w") as out:
        for d in generate:
            out.write(json.dumps(d, ensure_ascii=False) + "\n")
        for d in tema:
            out.write(json.dumps({"id": d["id"], "tipo": "tema", "domanda": d["domanda"], "giusti": []}, ensure_ascii=False) + "\n")
    print(len(generate), "domande con brano noto,", len(tema), "per tema")


if __name__ == "__main__":
    {"invia": invia, "raccogli": raccogli}[sys.argv[1]]()
