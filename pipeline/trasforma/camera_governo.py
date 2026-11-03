"""Dai governi OCD ai record dello schema v3: `Government`, `Ministry`, le persone e gli incarichi datati
(`OFFICE` verso il ministero, o verso il governo per presidente e vicepresidenti). Trasformazione pura."""

from __future__ import annotations

import re

from .camera_anagrafica import data, id_persona, leggibile, persona, senza_parentesi

TITOLI = {"PRESIDENTE DEL CONSIGLIO": "prime_minister", "VICEPRESIDENTE DEL CONSIGLIO": "deputy_prime_minister", "MINISTRO": "minister",
          "MINISTRO SENZA PORTAFOGLIO": "minister_without_portfolio", "VICE MINISTRO": "vice_minister", "SOTTOSEGRETARIO DI STATO": "undersecretary"}


def _coda(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def uri_governo(uri: str) -> str:
    """governo.rdf/g202 -> it:gov:202."""
    numero = re.sub(r"\D", "", _coda(uri))
    return f"it:gov:{numero}"


def trasforma(grezzi: dict[str, list[dict]], leg: int, fonte: dict | None = None) -> dict:
    fonte = fonte or {}
    nodi: dict[str, dict] = {}
    archi: list[dict] = []
    for r in grezzi.get("governi", []):
        u = uri_governo(r["governo"])
        nodi[u] = {"label": "Government", "uri": u, "name": senza_parentesi(r["titolo"]), "start": data(r.get("inizio")),
                   "end": data(r.get("fine")), "legislature": leg, "source": "ocd", "source_uri": r["governo"]}
    for r in grezzi.get("ministeri", []):
        u = f"{uri_governo(r['governo'])}:{_coda(r['organo'])}"
        nodi.setdefault(u, {"label": "Ministry", "uri": u, "government": uri_governo(r["governo"]), "name": leggibile(r["nome"]),
                            "portfolio": r.get("dicastero") == "1", "source": "ocd", "source_uri": r["organo"]})
    for r in grezzi.get("persone", []):
        p = persona(r)
        nodi.setdefault(p["uri"], p)
    for r in grezzi.get("incarichi", []):
        g = uri_governo(r["governo"])
        # presidente e vicepresidenti del Consiglio rispondono al governo; gli altri al loro ministero
        tipo = TITOLI.get(r["tipo"], "other")
        bersaglio = f"{g}:{_coda(r['organo'])}" if r.get("organo") and tipo not in ("prime_minister", "deputy_prime_minister") else g
        archi.append({"type": "OFFICE", "from": id_persona(r["persona"]), "to": bersaglio, "title": tipo,
                      "title_raw": senza_parentesi(r["carica"]), "note": r.get("nota"), "interim": r.get("interim") == "1",
                      # un incarico non dura più del suo governo: la Camera a volte non mette la fine (governo Draghi)
                      "start": data(r["inizio"]), "end": data(r.get("fine")) or (nodi.get(g) or {}).get("end"),
                      "end_reason": r.get("motivo") or (None if data(r.get("fine")) or not (nodi.get(g) or {}).get("end") else "fine del governo"),
                      "source_uri": r["membro"]})
    return {"nodi": list(nodi.values()), "archi": archi, "testi": [],
            "ambito": {"kind": "governo", "legislature": leg, "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}}
