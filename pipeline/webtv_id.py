"""Una volta sola, per i video già caricati prima della colonna video_segment.webtv_id (card 270): rilegge dal lago le
pagine degli eventi WebTV e scrive l'SQL che riempie webtv_id dei tratti, abbinati per video, ordine e ancora.
I giri dopo il 5/11/2026 la scrivono da soli (pipeline/trasforma/camera_webtv.py).

    .venv/bin/python -m pipeline.webtv_id > webtv_id.sql
    psql ... -v ON_ERROR_STOP=1 -f webtv_id.sql
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

from .fonti.camera_webtv import NOME
from .lago import Lago
from .trasforma.camera_webtv import trasforma


def main(cartella: Path = Path("dati")) -> None:
    lago = Lago(cartella)
    righe = io.StringIO()
    w = csv.writer(righe, lineterminator="\n")
    for chiave in lago.chiavi(NOME):
        if "-webtv-evento-" not in chiave:
            continue
        r = trasforma(lago.leggi(lago.ultimo(NOME, chiave)["file"]), {"chiave": chiave})
        for a in r["archi"]:
            w.writerow([a["to"], a["order"], a["anchor"] or "", a["webtv_id"]])
    out = sys.stdout
    out.write("BEGIN;\nALTER TABLE video_segment ADD COLUMN IF NOT EXISTS webtv_id int;\n"
              "CREATE TEMP TABLE t_webtv (video text, ord int, anchor text, webtv_id int) ON COMMIT DROP;\n"
              "COPY t_webtv FROM STDIN WITH (FORMAT csv, NULL '');\n")
    out.write(righe.getvalue())
    out.write("\\.\n"
              # l'ancora deve coincidere: se il grezzo nel lago non è quello caricato, il tratto resta senza id
              "UPDATE video_segment s SET webtv_id = t.webtv_id FROM t_webtv t\n"
              " WHERE s.video = t.video AND s.ord = t.ord AND s.anchor IS NOT DISTINCT FROM t.anchor;\n"
              "SELECT count(*) AS tratti, count(webtv_id) AS con_id FROM video_segment;\n"
              "COMMIT;\n")


if __name__ == "__main__":
    main()
