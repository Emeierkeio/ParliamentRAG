"""Dagli emendamenti del Senato in Akoma Ntoso (bulk data su GitHub) agli stessi record della Camera: `Amendment` con
testo e `(Person)-[:SIGNS]->(Amendment)`. Un file del lago contiene tutti gli emendamenti di un ddl in una sede
(A = Assemblea, C = commissione). Trasformazione pura.

Differenze con la Camera: i bulk data non danno l'esito né l'articolo, ma danno la data di presentazione; i
firmatari hanno l'id di dati.senato.it (it:person:senato:32608) e la carica (senatore, governo, relatore).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import xml.etree.ElementTree as ET

AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03}"
SEDI = {"A": "assembly", "C": "committee"}


def _testo(e: ET.Element | None) -> str | None:
    if e is None:
        return None
    blocchi = [x for x in e.iter() if x.tag in (AKN + "p", AKN + "div") and x.find(AKN + "p") is None and x.find(AKN + "div") is None]
    righe = [re.sub(r"\s+", " ", "".join(p.itertext())).strip() for p in blocchi]   # paragrafi o div, i più interni
    t = "\n\n".join(r for r in righe if r)
    return t or None


def numero_ddl(ddl: str) -> str:
    """Il ddl a cui si riferisce: «1101 NT» (nuovo testo della commissione) è il 1101; «1231, 287 NT1» (testo
    unificato di ddl abbinati) è il primo, 1231."""
    m = re.match(r"\s*(\d+(?:-[A-Za-z]+)?)", ddl)
    return m.group(1) if m else ddl.strip()


def variante(ddl: str) -> str:
    """Il testo emendato, se non è quello presentato: «1231, 287 NT1» -> «nt1-287», «1101 NT» -> «nt»; nell'uri,
    perché sul nuovo testo la numerazione degli emendamenti riparte."""
    resto = ddl.strip()[len(numero_ddl(ddl)):]
    parti = re.findall(r"[A-Za-z]+\d*", resto) + re.findall(r"\d+", re.sub(r"[A-Za-z]+\d*", "", resto))
    return "-".join(x.lower() for x in parti)


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    files = json.loads(gzip.decompress(corpo))
    nodi, archi, testi, visti = [], [], [], set()
    ddl = sede = None
    for nome in sorted(files):
        r = ET.fromstring(files[nome].encode("utf-8"))
        uri_fonte = r.find(f".//{AKN}FRBRWork/{AKN}FRBRuri").get("value")
        m = re.search(r"/(\d+)/Emend/S/([^/]+)/([A-Z]+)/(.+)$", uri_fonte)
        if not m:
            continue
        ddl, sede, num = m.group(2).strip(), m.group(3), m.group(4).strip()
        atto = f"it:senato:{leg}:ddl:{numero_ddl(ddl)}"
        # sul nuovo testo della commissione («1101 NT») la numerazione riparte: l'uri lo distingue
        v = variante(ddl)
        u = f"{atto}:eme:{sede.lower()}:{v + ':' if v else ''}{num.replace(' ', '_')}"
        if u in visti:
            continue
        visti.add(u)
        data = r.find(f".//{AKN}FRBRWork/{AKN}FRBRdate")
        testo = _testo(r.find(f".//{AKN}amendmentContent"))
        h = hashlib.sha256((testo or u).encode()).hexdigest()[:16]
        nodi.append({"label": "Amendment", "uri": u, "act": atto, "number": num, "kind": None, "action": None, "article": None,
                     "venue": SEDI.get(sede, sede), "committee": None, "sitting_number": None, "sitting_date": None,
                     "presented": data.get("date") if data is not None else None, "group_title": None, "status": None,
                     "outcome": None, "decree": None, "identical": [], "hash": h, "text_ref": f"amendment:{u}" if testo else None,
                     "source_uri": uri_fonte})
        if testo:
            testi.append({"ref": f"amendment:{u}", "text": testo, "hash": h})
        persone = {e.get("id"): e for e in r.iter(AKN + "TLCPerson")}
        ruoli = {e.get("id"): e.get("showAs") for e in r.iter(AKN + "TLCRole")}
        for i, p in enumerate(r.iter(AKN + "docProponent"), 1):
            chi = persone.get((p.get("refersTo") or "").lstrip("#"))
            # l'id si scrive in due modi (dati.senato.it/32608 e dati.senato.it/senatore/32608); 0 è un organo (il comitato ristretto)
            ide = re.search(r"dati\.senato\.it/(?:senatore/)?([1-9]\d*)$", chi.get("href") or "") if chi is not None else None
            ruolo = ruoli.get((p.get("as") or "").lstrip("#"))
            archi.append({"type": "SIGNS", "from": f"it:person:senato:{ide.group(1)}" if ide else None, "to": u, "order": i,
                          "first": i == 1, "family_raw": re.sub(r"\s+", " ", "".join(p.itertext())).strip() or None,
                          "given_raw": None, "kind_raw": ruolo})
    return {"nodi": nodi, "archi": archi, "testi": testi,
            "ambito": {"kind": "emendamenti", "chamber": "senato", "legislature": leg,
                       "act": f"it:senato:{leg}:ddl:{numero_ddl(ddl)}" if ddl else None, "venue": SEDI.get(sede or "", sede),
                       "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}}
