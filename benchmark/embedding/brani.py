"""Brani per la prova dei modelli di ricerca per significato: 20 mila, presi a caso dagli interventi in Postgres.

Proporzioni per tipo di resoconto come nel database; interventi sotto i 300 caratteri esclusi (quasi sempre
procedurali); interventi lunghi tagliati in brani di circa 1.500 caratteri, a fine frase. Seme fisso.

Uso: .venv/bin/python -m benchmark.embedding.brani
"""

import json
import random
import re
from pathlib import Path

from api.db import connessione

QUI = Path(__file__).parent
QUANTI = 20_000
LUNGHEZZA = 1_500
FINE_FRASE = re.compile(r"(?<=[.!?»])\s+(?=[A-ZÀ-Ú«(])")


def taglia(testo: str) -> list[str]:
    """Brani di circa LUNGHEZZA caratteri, mai a metà frase."""
    brani, corrente = [], ""
    for frase in FINE_FRASE.split(testo):
        if corrente and len(corrente) + len(frase) > LUNGHEZZA:
            brani.append(corrente.strip())
            corrente = ""
        corrente += frase + " "
    if corrente.strip():
        brani.append(corrente.strip())
    return [b for b in brani if len(b) >= 300]


def main() -> None:
    with connessione() as c:
        c.execute("SELECT setseed(0.42)")
        righe = c.execute("""
            SELECT sp.uri, sp.text, s.kind, s.chamber, s.date::text AS data, sp.as_group AS gruppo,
                   coalesce(p.given_name || ' ' || p.family_name, sp.speaker_label) AS oratore
            FROM speech sp
            JOIN agenda_item ai ON ai.uri = sp.item
            JOIN sitting s ON s.uri = ai.sitting
            LEFT JOIN person p ON p.uri = sp.person
            WHERE length(sp.text) >= 300
            ORDER BY random() LIMIT 18000""").fetchall()
    rnd = random.Random(42)
    brani = []
    for r in righe:
        for i, t in enumerate(taglia(r["text"])):
            brani.append({"id": f"{r['uri']}#{i}", "intervento": r["uri"], "resoconto": r["kind"], "ramo": r["chamber"],
                          "data": r["data"], "oratore": r["oratore"], "gruppo": r["gruppo"], "testo": t})
    rnd.shuffle(brani)
    brani = brani[:QUANTI]
    with open(QUI / "brani.jsonl", "w") as f:
        for b in brani:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    print(len(brani), "brani,", sum(len(b["testo"]) for b in brani) // 1000, "mila caratteri")


if __name__ == "__main__":
    main()
