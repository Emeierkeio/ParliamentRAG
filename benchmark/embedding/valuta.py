"""Punteggi della prova. Si lancia con l'ambiente che ha numpy (quello di sentence-transformers).

  valuta.py giudizi invia     batch dei giudizi sui primi 10 brani di ogni modello, per le domande per tema
  valuta.py giudizi raccogli  scrive giudizi.json
  valuta.py rapporto          scrive RISULTATI.md

Modelli confrontati: text-embedding-3-large a 3072 dimensioni, lo stesso troncato a 1024 (la riduzione che OpenAI
prevede), multilingual-e5-large a 1024. Domande con brano noto: richiamo a 1, 5, 10 e MRR. Domande per tema:
precisione a 10 e nDCG a 10, con giudizi 0/1/2 dati a ciechi dal modello di chat sull'unione dei primi 10.
"""

import json
import math
import random
import sys
from pathlib import Path

import numpy as np

QUI = Path(__file__).parent
V = QUI / "vettori"
MODELLO_GIUDICE = "gpt-5.6-terra"
GIUDICE = """Ti do una domanda su un tema del Parlamento italiano e un brano di resoconto. Quanto è utile il brano per rispondere?
2 = parla proprio di questo tema e contiene una posizione, un fatto o un argomento utile per la risposta
1 = tocca il tema ma di passaggio, o è utile solo come contesto
0 = non c'entra
Rispondi con una sola cifra."""


def _norm(m: np.ndarray) -> np.ndarray:
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def modelli() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    ob, od = np.load(V / "openai-brani.npy"), np.load(V / "openai-domande.npy")
    return {
        "text-embedding-3-large (3072)": (ob, od),
        "text-embedding-3-large (1024)": (_norm(ob[:, :1024]), _norm(od[:, :1024])),
        "multilingual-e5-large (1024)": (np.load(V / "e5-brani.npy"), np.load(V / "e5-domande.npy")),
    }


def _primi(b: np.ndarray, d: np.ndarray, k: int = 10) -> np.ndarray:
    s = d @ b.T
    idx = np.argpartition(-s, k, axis=1)[:, :k]
    ordine = np.take_along_axis(s, idx, axis=1).argsort(axis=1)[:, ::-1]
    return np.take_along_axis(idx, ordine, axis=1)


def _dati():
    brani = [json.loads(r) for r in open(QUI / "brani.jsonl")]
    domande = [json.loads(r) for r in open(QUI / "domande.jsonl")]
    return brani, domande


def giudizi_invia() -> None:
    from benchmark.embedding import batch
    brani, domande = _dati()
    coppie = set()
    for b, d in modelli().values():
        top = _primi(b, d)
        for i, q in enumerate(domande):
            if q["tipo"] == "tema":
                coppie |= {(i, int(j)) for j in top[i]}
    coppie = sorted(coppie)
    random.Random(3).shuffle(coppie)  # ordine non legato al modello
    f = QUI / "richieste-giudizi.jsonl"
    with open(f, "w") as out:
        for i, j in coppie:
            out.write(json.dumps({"custom_id": f"{i}:{j}", "method": "POST", "url": "/v1/responses", "body": {
                "model": MODELLO_GIUDICE, "instructions": GIUDICE,
                "input": f"Domanda: {domande[i]['domanda']}\n\nBrano: {brani[j]['testo']}"}}, ensure_ascii=False) + "\n")
    bid = batch.invia(f, "/v1/responses", "prova embedding: giudizi")
    (QUI / "batch-giudizi.txt").write_text(bid)
    print(len(coppie), "coppie da giudicare")


def giudizi_raccogli() -> None:
    from benchmark.embedding import batch
    from benchmark.embedding.domande import _testo
    s = batch.aspetta((QUI / "batch-giudizi.txt").read_text().strip())
    voti = {}
    for cid, corpo in batch.risultati(s).items():
        t = _testo(corpo)
        voti[cid] = int(t[0]) if t[:1] in ("0", "1", "2") else None
    (QUI / "giudizi.json").write_text(json.dumps(voti))
    print(len(voti), "giudizi,", sum(v is None for v in voti.values()), "non leggibili")


def rapporto() -> None:
    brani, domande = _dati()
    pos = {b["id"]: k for k, b in enumerate(brani)}
    voti = json.loads((QUI / "giudizi.json").read_text()) if (QUI / "giudizi.json").exists() else {}
    righe = []
    for nome, (b, d) in modelli().items():
        top = _primi(b, d)
        r1 = r5 = r10 = mrr = n = 0
        p10 = ndcg = m = 0
        for i, q in enumerate(domande):
            lista = [int(j) for j in top[i]]
            if q["tipo"] == "nota":
                g = pos[q["giusti"][0]]
                n += 1
                if g in lista:
                    rango = lista.index(g) + 1
                    r1 += rango == 1; r5 += rango <= 5; r10 += 1; mrr += 1 / rango
            else:
                g = [voti.get(f"{i}:{j}") or 0 for j in lista]
                ideale = sorted([v or 0 for c, v in voti.items() if c.startswith(f"{i}:")], reverse=True)[:10]
                dcg = sum(v / math.log2(k + 2) for k, v in enumerate(g))
                idcg = sum(v / math.log2(k + 2) for k, v in enumerate(ideale)) or 1
                p10 += sum(v >= 1 for v in g) / 10; ndcg += dcg / idcg; m += 1
        righe.append((nome, r1 / n, r5 / n, r10 / n, mrr / n, p10 / max(m, 1), ndcg / max(m, 1)))
    out = ["# Prova dei modelli per la ricerca per significato", "",
           f"{len(brani)} brani di interventi (Camera e Senato, Aula e commissioni, stenografici e sommari); "
           f"{sum(q['tipo'] == 'nota' for q in domande)} domande con il brano giusto noto, "
           f"{sum(q['tipo'] == 'tema' for q in domande)} domande per tema giudicate a ciechi.", "",
           "| Modello | Brano giusto primo | tra i primi 5 | tra i primi 10 | MRR | Precisione a 10 (tema) | nDCG a 10 (tema) |",
           "|---|---|---|---|---|---|---|"]
    out += [f"| {r[0]} | " + " | ".join(f"{x:.2f}" for x in r[1:]) + " |" for r in righe]
    (QUI / "RISULTATI.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    if sys.argv[1] == "giudizi":
        {"invia": giudizi_invia, "raccogli": giudizi_raccogli}[sys.argv[2]]()
    else:
        rapporto()
