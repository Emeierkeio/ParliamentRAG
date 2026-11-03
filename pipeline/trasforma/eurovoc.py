"""Concetti EuroVoc: una riga per concetto, con il nome in italiano e in inglese e i concetti più generali."""

from __future__ import annotations

import json


def trasforma(corpo: bytes, fonte: dict) -> dict:
    concetti: dict[str, dict] = {}
    for r in json.loads(corpo):
        c = concetti.setdefault(r["concetto"], {"label": "Concept", "uri": r["concetto"], "scheme": "eurovoc", "label_it": r["it"],
                                                "label_en": r.get("en"), "broader": [], "source": "eurovoc"})
        if r.get("generale") and r["generale"] not in c["broader"]:
            c["broader"].append(r["generale"])
    return {"nodi": list(concetti.values()), "archi": [], "testi": [], "ambito": {"kind": "concetti", "scheme": "eurovoc", "source_key": fonte.get("chiave")}}
