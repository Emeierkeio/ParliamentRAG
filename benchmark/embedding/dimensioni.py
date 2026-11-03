"""Confronto 3072 contro 1024 dimensioni di text-embedding-3-large, con la ricerca esatta di pgvector.

Carica i vettori della prova in uno schema a parte (`prova_emb`), senza numpy: i .npy si leggono con la libreria
standard. Uso: .venv/bin/python -m benchmark.embedding.dimensioni
"""

import ast
import json
from array import array
from pathlib import Path

import psycopg

from pipeline.ambiente import env

QUI = Path(__file__).parent


def chiave_pg() -> str:
    """La password dell'utente proprietario, da ambiente o .env; serve per creare lo schema della prova."""
    return env("PG_PASSWORD")


def leggi_npy(f: Path) -> list[array]:
    with open(f, "rb") as h:
        assert h.read(6) == b"\x93NUMPY"
        h.read(2)
        lung = int.from_bytes(h.read(2), "little")
        testa = ast.literal_eval(h.read(lung).decode())
        assert testa["descr"] == "<f4" and not testa["fortran_order"]
        righe, col = testa["shape"]
        dati = array("f"); dati.frombytes(h.read())
    return [dati[i * col:(i + 1) * col] for i in range(righe)]


def carica(c, tabella: str, righe: list[array]) -> None:
    c.execute(f"CREATE TABLE prova_emb.{tabella} (n int PRIMARY KEY, v vector(3072), v1024 vector(1024))")
    with c.cursor().copy(f"COPY prova_emb.{tabella} (n, v) FROM STDIN") as cp:
        for i, r in enumerate(righe):
            cp.write_row((i, "[" + ",".join(f"{x:.6g}" for x in r) + "]"))
    c.execute(f"UPDATE prova_emb.{tabella} SET v1024 = l2_normalize(subvector(v, 1, 1024))::vector(1024)")


def main() -> None:
    brani = [json.loads(r)["id"] for r in open(QUI / "brani.jsonl")]
    domande = [json.loads(r) for r in open(QUI / "domande.jsonl")]
    pos = {b: i for i, b in enumerate(brani)}
    with psycopg.connect(host="localhost", port=int(env("PG_PORTA", "5440")), dbname="parliamentrag",
                         user="parliamentrag", password=chiave_pg(), autocommit=True) as c:
        c.execute("DROP SCHEMA IF EXISTS prova_emb CASCADE; CREATE SCHEMA prova_emb")
        carica(c, "brani", leggi_npy(QUI / "vettori" / "openai-brani.npy"))
        carica(c, "domande", leggi_npy(QUI / "vettori" / "openai-domande.npy"))
        top = {}
        for col in ("v", "v1024"):
            top[col] = {r[0]: r[1] for r in c.execute(f"""
                SELECT d.n, (SELECT array_agg(n ORDER BY dist) FROM (
                    SELECT b.n, b.{col} <#> d.{col} AS dist FROM prova_emb.brani b ORDER BY dist LIMIT 10) t)
                FROM prova_emb.domande d""")}
    out = ["| Dimensioni | Brano giusto primo | tra i primi 5 | tra i primi 10 | MRR |", "|---|---|---|---|---|"]
    for col, nome in (("v", "3072"), ("v1024", "1024")):
        r1 = r5 = r10 = mrr = n = 0
        for i, q in enumerate(domande):
            if q["tipo"] != "nota":
                continue
            n += 1
            lista, g = top[col][i], pos[q["giusti"][0]]
            if g in lista:
                k = lista.index(g) + 1
                r1 += k == 1; r5 += k <= 5; r10 += 1; mrr += 1 / k
        out.append(f"| {nome} | {r1 / n:.2f} | {r5 / n:.2f} | {r10 / n:.2f} | {mrr / n:.2f} |")
    tema = [i for i, q in enumerate(domande) if q["tipo"] == "tema"]
    comuni = sum(len(set(top["v"][i]) & set(top["v1024"][i])) for i in tema) / (10 * len(tema))
    out.append(f"\nDomande per tema: i primi 10 brani coincidono al {comuni:.0%} tra 3072 e 1024 dimensioni.")
    (QUI / "RISULTATI-dimensioni.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
