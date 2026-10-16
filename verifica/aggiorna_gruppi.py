"""Rigenera gruppi_ufficiali.json dagli endpoint SPARQL di Camera e Senato.

Il dataset pubblico dà i gruppi per nome, senza URI: questa tabella collega
ogni nome (con tutte le denominazioni che il gruppo ha avuto nella XIX
legislatura) all'URI ufficiale. Le componenti del Misto hanno già l'URI nel
dataset e qui non servono.

    python -m verifica.aggiorna_gruppi

Va rilanciato quando nasce un gruppo o un gruppo cambia nome. Il file
generato fa parte della libreria: due copie della stessa versione danno lo
stesso rapporto.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

LEGISLATURA = 19
INIZIO_LEGISLATURA = "2022-10-13"
FILE = Path(__file__).with_name("gruppi_ufficiali.json")
INTESTAZIONI = {
    # dati.senato.it rifiuta lo User-Agent predefinito di Python
    "User-Agent": "Mozilla/5.0 (compatible; ParliamentRAG/1.0; +https://www.parliamentrag.it)",
    "Accept": "application/sparql-results+json",
}

# Tutti i gruppi della Camera hanno un'etichetta "NOME (SIGLA) (gg.mm.aaaa-gg.mm.aaaa)".
# Il filtro su ocd:rif_leg fa scadere l'endpoint: si filtra sulla data in Python.
CAMERA = """
SELECT DISTINCT ?g ?l WHERE {
  ?g a <http://dati.camera.it/ocd/gruppoParlamentare> ;
     <http://www.w3.org/2000/01/rdf-schema#label> ?l .
}
"""

# Le denominazioni precedenti di ogni gruppo ("già AZIONE - ITALIA VIVA - RENEW
# EUROPE fino a 20.11.2023"): dc:title è il vecchio nome, dc:date la fine.
CAMERA_DENOMINAZIONI = """
SELECT DISTINCT ?g ?t ?d WHERE {
  ?g a <http://dati.camera.it/ocd/gruppoParlamentare> ;
     <http://dati.camera.it/ocd/denominazione> ?den .
  ?den <http://purl.org/dc/elements/1.1/title> ?t ;
       <http://purl.org/dc/elements/1.1/date> ?d .
  FILTER(?g IN (%s))
}
"""

SENATO = """
SELECT DISTINCT ?gruppo ?titolo ?inizio ?fine WHERE {
  ?ades <http://dati.senato.it/osr/legislatura> %d ;
        <http://dati.senato.it/osr/gruppo> ?gruppo .
  ?gruppo <http://dati.senato.it/osr/denominazione> ?den .
  ?den <http://dati.senato.it/osr/titolo> ?titolo .
  OPTIONAL { ?den <http://dati.senato.it/osr/inizio> ?inizio }
  OPTIONAL { ?den <http://dati.senato.it/osr/fine> ?fine }
}
""" % LEGISLATURA

_ETICHETTA_CAMERA = re.compile(r"^(?P<nome>.+?) \((?:[^()]|\([^()]*\))*\) \((?P<da>\d{2}\.\d{2}\.\d{4})(?:-(?P<a>\d{2}\.\d{2}\.\d{4}))?\)?$")


def _sparql(endpoint: str, query: str, formato: str) -> list:
    url = endpoint + "?" + urllib.parse.urlencode({"query": query, "format": formato})
    req = urllib.request.Request(url, headers=INTESTAZIONI)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["results"]["bindings"]


def _iso(data_it: str | None) -> str | None:
    if not data_it:
        return None
    g, m, a = data_it.split(".")
    return f"{a}-{m}-{g}"


def gruppi_camera() -> list:
    out = []
    for b in _sparql("https://dati.camera.it/sparql", CAMERA, "application/sparql-results+json"):
        m = _ETICHETTA_CAMERA.match(b["l"]["value"].strip())
        if not m:
            continue
        da, a = _iso(m.group("da")), _iso(m.group("a"))
        if (a or "9999") < INIZIO_LEGISLATURA or da < "2022-10-01":
            continue
        out.append({"uri": b["g"]["value"], "chamber": "camera",
                    "names": [{"name": m.group("nome"), "from": da, "to": a}]})
    per_uri = {g["uri"]: g for g in out}
    elenco = ", ".join(f"<{u}>" for u in sorted(per_uri))
    for b in _sparql("https://dati.camera.it/sparql", CAMERA_DENOMINAZIONI % elenco, "application/sparql-results+json"):
        fine = b["d"]["value"]
        fine = f"{fine[:4]}-{fine[4:6]}-{fine[6:8]}"
        nomi = per_uri[b["g"]["value"]]["names"]
        if not any(n["name"] == b["t"]["value"] for n in nomi):
            nomi.append({"name": b["t"]["value"].strip(), "from": None, "to": fine})
    return out


def gruppi_senato() -> list:
    per_uri: dict = {}
    for b in _sparql("https://dati.senato.it/sparql", SENATO, "json"):
        fine = (b.get("fine") or {}).get("value")
        if fine and fine[:10] < INIZIO_LEGISLATURA:
            continue
        uri = b["gruppo"]["value"]
        per_uri.setdefault(uri, {"uri": uri, "chamber": "senato", "names": []})["names"].append(
            {"name": b["titolo"]["value"].strip(), "from": (b.get("inizio") or {}).get("value", "")[:10] or None,
             "to": fine[:10] if fine else None})
    return list(per_uri.values())


def main() -> None:
    gruppi = gruppi_camera() + gruppi_senato()
    for g in gruppi:
        g["names"].sort(key=lambda n: n["from"] or "")
    gruppi.sort(key=lambda g: (g["chamber"], g["uri"]))
    FILE.write_text(json.dumps({"legislature": LEGISLATURA, "groups": gruppi}, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(gruppi)} gruppi -> {FILE}")


if __name__ == "__main__":
    main()
