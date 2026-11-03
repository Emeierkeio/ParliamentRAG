"""Corrispondenza fra le persone delle due fonti: lo stesso senatore ha un id su dati.camera.it
(it:person:camera:309100, usato dagli atti di sindacato ispettivo e dal governo) e uno su dati.senato.it
(it:person:senato:17542, usato da anagrafica e voti del Senato). Nessuna delle due fonti collega l'altra.

Regola prudente, a livelli, sempre con lo stesso genere e solo se il candidato è uno solo: nome e cognome uguali;
poi stesso nome e un cognome che contiene l'altro («ALBERTI» e «Alberti Casellati»); poi un cognome che fra i
senatori della legislatura ce l'ha uno solo (Ignazio / Ignazio Benito Maria La Russa). Trasformazione pura.
"""

from __future__ import annotations

import re
import unicodedata

from .camera_anagrafica import id_persona, leggibile


def _n(t: str | None) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", t).strip()


def trasforma(grezzi: dict[str, list[dict]], leg: int, fonte: dict | None = None) -> dict:
    fonte = fonte or {}
    senato = {}
    for r in grezzi.get("senatori_osr", []):
        u = f"it:person:senato:{r['senatore'].rstrip('/').rsplit('/', 1)[-1]}"
        senato.setdefault(u, {"nome": _n(r.get("nome")), "cognome": _n(r.get("cognome")), "genere": (r.get("genere") or "").upper()[:1]})
    nodi, archi = [], []
    for r in grezzi.get("senatori_camera", []):
        p = id_persona(r["persona"])
        nome, cognome, genere = _n(r.get("nome")), _n(r.get("cognome")), {"male": "M", "female": "F"}.get(r.get("genere") or "", "")
        nodi.append({"label": "Person", "uri": p, "camera_id": p.rsplit(":", 1)[1], "given_name": leggibile(r.get("nome") or ""),
                     "family_name": leggibile(r.get("cognome") or ""), "sort_name": f"{leggibile(r.get('cognome') or '')} {leggibile(r.get('nome') or '')}",
                     "gender": genere or None, "source": "ocd", "source_uri": r["persona"]})
        uguali = [u for u, s in senato.items() if s["nome"] == nome and s["cognome"] == cognome and (not genere or s["genere"] == genere)]
        metodo = "nome e cognome"
        if len(uguali) != 1:
            uguali = [u for u, s in senato.items() if s["nome"] == nome and (not genere or s["genere"] == genere)
                      and (cognome in s["cognome"] or s["cognome"] in cognome) and cognome and s["cognome"]]
            metodo = "nome, cognome contenuto"
        if len(uguali) != 1:  # nomi scritti diversamente (Ignazio / Ignazio Benito Maria, Peppe / Giuseppe): basta il cognome, se è unico
            uguali = [u for u, s in senato.items() if s["cognome"] == cognome and cognome and (not genere or s["genere"] == genere)]
            metodo = "cognome unico"
        if len(uguali) == 1:
            archi.append({"type": "SAME_AS", "from": p, "to": uguali[0], "method": metodo})
    return {"nodi": nodi, "archi": archi, "testi": [],
            "ambito": {"kind": "corrispondenze", "legislature": leg, "source_key": fonte.get("chiave")}}
