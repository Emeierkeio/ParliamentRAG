"""Thesaurus EuroVoc dall'Ufficio delle pubblicazioni dell'UE: nome in italiano e in inglese di ogni concetto e il
concetto più generale (skos:broader). Serve a dare un nome ai temi degli atti: dati.camera.it dà solo l'indirizzo
(`http://eurovoc.europa.eu/659` -> «economia pubblica»).
Circa 7.500 concetti, due richieste. EuroVoc cambia poche volte l'anno: se non cambia, il lago non riscrive niente.
Licenza: riuso libero con citazione della fonte (decisione 2011/833/UE). Chiave nel lago: `eurovoc-concetti`.
"""

from __future__ import annotations

import json

from ..lago import Lago
from .sparql import interroga

NOME = "eurovoc"
ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
SCHEMA = "http://eurovoc.europa.eu/100141"
QUERY = f"""PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
SELECT ?concetto ?it ?en ?generale WHERE {{
 ?concetto skos:inScheme <{SCHEMA}> ; skos:prefLabel ?it . FILTER(lang(?it) = "it")
 OPTIONAL {{ ?concetto skos:prefLabel ?en FILTER(lang(?en) = "en") }}
 OPTIONAL {{ ?concetto skos:broader ?generale }} }} ORDER BY ?concetto ?generale"""


def scarica(ctx) -> dict:
    righe = interroga(ENDPOINT, QUERY, pausa=float(ctx.config["fonti"][NOME].get("pausa_secondi", 1.0)))
    if len(righe) < 5000:
        raise RuntimeError(f"solo {len(righe)} righe da EuroVoc: l'endpoint potrebbe avere un problema")
    righe.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
    s = Lago(ctx.cartella).salva(NOME, "eurovoc-concetti", json.dumps(righe, ensure_ascii=False, indent=0).encode("utf-8"), ENDPOINT, "json")
    ctx.log(f"eurovoc: {len(righe)} righe{' (nuove)' if s['nuovo'] else ''}")
    return {"righe": len(righe), "nuovo": s["nuovo"]}
