"""Dai voti OCD di una seduta della Camera ai record dello schema v3: `Vote` e `(Person)-[:VOTED]->(Vote)`.

Trasformazione pura. Il voto di ogni deputato porta il gruppo (o la componente del Misto) che la Camera gli
attribuisce in quella votazione: così il dissenso si conta senza ricostruire le appartenenze.
"""

from __future__ import annotations

import re

from ..fonti.camera_voti import leggi
from .camera_anagrafica import data, id_persona

TIPI = {"Finale atto Camera": "final", "Articolo": "article", "Emendamento": "amendment", "Ordine del Giorno": "agenda_order",
        "Mozione": "motion", "Risoluzione": "resolution", "Pregiudiziali": "preliminary_question", "Sospensiva": "suspensive_question",
        "Note di variazione": "budget_note", "Chiusura della discussione": "closure", "Dimissioni": "resignation", "Altre": "other"}
ESITI = {"Favorevole": "favor", "Contrario": "against", "Astensione": "abstain"}
# «Non ha votato» con la nota della Camera: in missione, presidente di turno, oppure assente
NON_VOTO = {"In missione": "mission", "Presidente di turno": "chair"}


def uri_votazione(uri: str, leg: int) -> str:
    """votazione.rdf/vs19_722_001 -> it:camera:19:sed0722:v001."""
    m = re.search(r"vs\d+_(\d+)_(\d+)$", uri)
    return f"it:camera:{leg}:sed{int(m.group(1)):04d}:v{int(m.group(2)):03d}"


def _intero(v):
    return int(v) if v not in (None, "") and str(v).lstrip("-").isdigit() else None


def _vero(v):
    return None if v in (None, "") else str(v) == "1"


def _gruppo(uri: str | None, leg: int) -> str | None:
    return f"it:camera:{leg}:group:{uri.rstrip('/').rsplit('/', 1)[-1]}" if uri else None


def esito(tipo: str, nota: str | None) -> str:
    if tipo in ESITI:
        return ESITI[tipo]
    if tipo == "Non ha votato":
        return NON_VOTO.get(nota or "", "absent")
    return "voted"  # voto segreto: si sa che ha votato, non come


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    d = leggi(corpo)
    seduta = int(re.search(r"_(\d+)$", d["seduta"]).group(1))
    s_uri = f"it:camera:{leg}:sed{seduta:04d}"
    voti: dict[str, dict] = {}
    for r in d["votazioni"]:
        u = uri_votazione(r["votazione"], leg)
        v = voti.get(u)
        if not v:
            v = voti[u] = {"label": "Vote", "uri": u, "sitting": s_uri, "chamber": "camera", "legislature": leg, "number": int(u[-3:]),
                           "date": data(r["data"]), "title": r.get("titolo"), "description": r.get("descrizione"),
                           "kind": TIPI.get(r.get("tipo") or "", "other"), "kind_raw": r.get("tipo"),
                           "favor": _intero(r.get("favorevoli")), "against": _intero(r.get("contrari")), "abstain": _intero(r.get("astenuti")),
                           "present": _intero(r.get("presenti")), "voting": _intero(r.get("votanti")), "majority": _intero(r.get("maggioranza")),
                           "approved": _vero(r.get("approvato")), "secret": _vero(r.get("segreta")), "final": _vero(r.get("finale")),
                           "confidence": _vero(r.get("fiducia")), "presided_by": id_persona(r.get("presidente") or ""),
                           "source_url": r.get("scheda"), "source_uri": r["votazione"], "acts": [], "aics": [],
                           "source": "ocd", "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}
        for campo, chiave in (("atto", "acts"), ("aic", "aics")):
            x = r.get(campo)
            if x:
                ref = x.rstrip("/").rsplit("/", 1)[-1]
                if ref not in v[chiave]:
                    v[chiave].append(ref)
    archi = []
    for r in d["voti"]:
        u = uri_votazione(r["votazione"], leg)
        archi.append({"type": "VOTED", "from": id_persona(r["deputato"]), "to": u, "result": esito(r["tipo"], r.get("nota")),
                      "result_raw": r["tipo"], "note": r.get("nota"), "group": _gruppo(r.get("componente") or r.get("gruppo"), leg)})
    conti: dict[str, dict] = {}
    for a in archi:
        conti.setdefault(a["to"], {}).setdefault(a["result"], 0)
        conti[a["to"]][a["result"]] += 1
    for v in voti.values():
        c = conti.get(v["uri"], {})
        v["ballots_match"] = None if v["secret"] else (v["favor"], v["against"], v["abstain"]) == (c.get("favor", 0), c.get("against", 0), c.get("abstain", 0))
        for ref in v["acts"]:
            archi.append({"type": "ON", "from": v["uri"], "to_ref": ref})
        for ref in v["aics"]:
            archi.append({"type": "ON", "from": v["uri"], "to_ref": ref})
    return {"nodi": list(voti.values()), "archi": archi, "testi": [],
            "ambito": {"kind": "voti", "chamber": "camera", "legislature": leg, "sitting": s_uri}}
