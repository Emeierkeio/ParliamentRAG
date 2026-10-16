"""Estrae dal dataset completo la parte che serve ai test (tests/fixtures/dati-hf).

I test girano senza scaricare 50 MB: le tabelle piccole (persone, gruppi,
appartenenze, sedute) sono copiate intere, degli interventi solo quelli citati
dalle risposte vere e dai casi costruiti. Riproducibile da chiunque:

    parliamentrag-verifica --dati ./leg19 --versione fa6566217075741f4100eb1994b90db885c09904 …
    python tests/fixtures/estrai_dati.py ./leg19

Dati: Camera dei deputati, CC BY-SA 4.0, tramite ParliamentRAG
(huggingface.co/datasets/emeierkeio/parliamentrag-leg19).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pyarrow.parquet as pq

QUI = Path(__file__).resolve().parent
USCITA = QUI / "dati-hf"

# Interventi usati dai casi costruiti (costruisci_casi.py), oltre a quelli
# delle risposte vere
EXTRA = [
    "leg19_sed418_tit00080.sub00020.int00040",   # cita un impegno tra «»
    "leg19_sed440_tit00060.sub00220.int00060",   # «la collega Alifano ha detto che…»
    "leg19_sed489_tit00070.sub00010.int00060",   # frase tra “”
    "leg19_sed489_tit00070.sub00010.int00100",   # domande riportate tra “”
    "leg19_sed24_tit00090.sub00050.int00080",    # deputato di Azione-IV prima del 20/11/2023
]


def main(sorgente: str) -> None:
    sorgente = Path(sorgente)
    ids = set(EXTRA)
    for f in sorted((QUI / "risposte").glob("*.json")):
        ids.update(c["speech"] for c in json.loads(f.read_text())["claims"])
    USCITA.mkdir(exist_ok=True)
    for nome in ("sessions", "memberships", "organizations", "persons"):
        shutil.copy(sorgente / f"{nome}.parquet", USCITA / f"{nome}.parquet")
    tabella = pq.read_table(sorgente / "speeches.parquet", filters=[("speech_id", "in", sorted(ids))])
    tabella = tabella.sort_by("speech_id")
    pq.write_table(tabella, USCITA / "speeches.parquet", compression="zstd")
    shutil.copy(sorgente / "export_meta.json", USCITA / "export_meta.json")
    if (sorgente / "versione.json").exists():
        shutil.copy(sorgente / "versione.json", USCITA / "versione.json")
    print(f"{tabella.num_rows} interventi su {len(ids)} richiesti -> {USCITA}")


if __name__ == "__main__":
    main(sys.argv[1])
