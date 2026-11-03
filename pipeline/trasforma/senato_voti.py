"""Dai voti OSR di una seduta del Senato agli stessi record della Camera: `Vote` e `(Person)-[:VOTED]->(Vote)`.

Differenze con la Camera: il Senato non dà il gruppo del senatore nel voto (si ricava dall'anagrafica alla data),
non nomina gli assenti senza giustificazione, e non ha indicatori per voto finale o fiducia: si ricavano
dall'etichetta («Votazione finale», «… questione di fiducia»). Trasformazione pura.
"""

from __future__ import annotations

import re

from ..fonti.senato_voti import leggi

ESITI = {"favorevole": "favor", "contrario": "against", "astenuto": "abstain", "inCongedoMissione": "mission", "presenteNonVotante": "present_not_voting"}


def _intero(v):
    return int(v) if v not in (None, "") and str(v).lstrip("-").isdigit() else None


def _tipo(label: str) -> str:
    l = label.lower()
    if "fiducia" in l and "sfiducia" not in l:
        return "confidence"
    if "finale" in l or "nel suo complesso" in l:
        return "final"
    if "emendament" in l:
        return "amendment"
    if "ordine del giorno" in l:
        return "agenda_order"
    if "articolo" in l:
        return "article"
    if "mozione" in l:
        return "motion"
    if "risoluzione" in l:
        return "resolution"
    return "other"


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    d = leggi(corpo)
    numero = int(d["seduta"]["numero"])
    s_uri = f"it:senato:{leg}:sed{numero:04d}"
    voti = {}
    for r in d["votazioni"]:
        n = _intero(r.get("numero"))
        if n is None:
            continue
        if n in voti:                                     # più righe per votazione: una per ddl votato
            if r.get("atto") and r["atto"] not in voti[n]["acts"]:
                voti[n]["acts"].append(r["atto"])
            continue
        label = r.get("label") or ""
        voti[n] = {"label": "Vote", "uri": f"{s_uri}:v{n:03d}", "sitting": s_uri, "chamber": "senato", "legislature": leg, "number": n,
                   "date": (d["seduta"].get("data") or "")[:10] or None, "title": label, "description": None, "kind": _tipo(label), "kind_raw": label,
                   "favor": _intero(r.get("favorevoli")), "against": _intero(r.get("contrari")), "abstain": _intero(r.get("astenuti")),
                   "present": _intero(r.get("presenti")), "voting": _intero(r.get("votanti")), "majority": _intero(r.get("maggioranza")),
                   "approved": {"approvato": True, "respinto": False}.get((r.get("esito") or "").strip().lower()),
                   "secret": "segret" in (r.get("tipo") or "").lower() or "scrutinio segreto" in label.lower(),
                   "final": _tipo(label) == "final", "confidence": _tipo(label) == "confidence", "presided_by": None,
                   "source_url": None, "source_uri": r["votazione"], "acts": [r["atto"]] if r.get("atto") else [], "aics": [], "source": "osr",
                   "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}
    archi = []
    for r in d["voti"]:
        n = _intero(r.get("n"))
        p = r["p"].rsplit("/", 1)[-1]
        m = re.search(r"/senatore/(\d+)", r["senatore"])
        if n in voti and m and p in ESITI:
            archi.append({"type": "VOTED", "from": f"it:person:senato:{m.group(1)}", "to": voti[n]["uri"], "result": ESITI[p],
                          "result_raw": p, "note": None, "group": None})
    conti: dict[str, dict] = {}
    for a in archi:
        conti.setdefault(a["to"], {}).setdefault(a["result"], 0)
        conti[a["to"]][a["result"]] += 1
    for v in voti.values():
        c = conti.get(v["uri"], {})
        v["ballots_match"] = None if v["secret"] else (v["favor"], v["against"], v["abstain"]) == (c.get("favor", 0), c.get("against", 0), c.get("abstain", 0))
    for v in voti.values():
        archi += [{"type": "ON", "from": v["uri"], "to_ref": a} for a in v["acts"]]
    return {"nodi": list(voti.values()), "archi": archi, "testi": [],
            "ambito": {"kind": "voti", "chamber": "senato", "legislature": leg, "sitting": s_uri, "source": "osr"}}
