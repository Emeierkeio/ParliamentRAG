"""Dalla pagina di un evento della WebTV (seduta d'Aula) ai record dello schema v3: un `Video` per la seduta e,
per ogni intervento, il tratto di video (secondi di inizio e fine, ora reale) legato all'intervento del resoconto
stenografico attraverso la sua ancora (`tit00020_int00010` -> it:camera:19:sed0735:tit00020.int00010).
"""

from __future__ import annotations

import gzip
import re

from ..fonti.camera_webtv import SITO, indice


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    testo = gzip.decompress(corpo).decode("utf-8", errors="replace")
    evento = re.search(r"webtv-evento-(\d+)", fonte.get("chiave", "")).group(1)
    # il titolo «AULA, Seduta N» a volte manca (evento 30139); lo script del lettore ha sempre `var nume_sed = N;`
    m = re.search(r"AULA,\s*Seduta\s+(\d+)", testo) or re.search(r"var nume_sed = (\d+);", testo)
    seduta = int(m.group(1)) if m else None
    titolo = re.search(r'<meta property="og:title" content="([^"]*)"', testo) or re.search(r"(AULA, Seduta[^<]{0,200})", testo)
    v_uri = f"it:camera:{leg}:webtv:{evento}"
    s_uri = f"it:camera:{leg}:sed{seduta:04d}" if seduta else None
    righe = indice(corpo)
    ore = [r["ora"] for r in righe if r.get("ora")]
    video = {"label": "Video", "uri": v_uri, "event_id": int(evento), "sitting": s_uri, "kind": "sitting",
             "title": titolo.group(1).strip() if titolo else None, "url": f"{SITO}/evento/{evento}",
             "start_ts": min(ore) if ore else None, "end_ts": max(ore) if ore else None, "source": "camera_webtv"}
    archi = []
    for i, r in enumerate(righe, 1):
        ancora = (r.get("ancora") or "").replace("_", ".")
        archi.append({"type": "HAS_VIDEO", "from": f"{s_uri}:{ancora}" if ancora and s_uri else None, "to": v_uri, "order": i,
                      "anchor": ancora or None, "label": r.get("etichetta"), "start": int(r["inizio"]) if (r.get("inizio") or "").isdigit() else None,
                      "end": int(r["fine"]) if (r.get("fine") or "").isdigit() else None, "clock": r.get("ora")})
    return {"nodi": [video], "archi": archi, "testi": [],
            "ambito": {"kind": "video", "chamber": "camera", "legislature": leg, "source": "camera_webtv", "source_key": fonte.get("chiave")}}
