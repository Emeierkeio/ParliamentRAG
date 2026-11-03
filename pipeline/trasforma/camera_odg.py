"""Dall'ordine del giorno dell'Assemblea (HTML) a una seduta prevista (`Sitting {status: planned}`) con i suoi
argomenti: titolo, testo, orario, atti collegati (C. 3148, mozioni 1-00599) e relatori.

La seduta prevista ha lo stesso uri di quella che poi si tiene (it:camera:19:sed0737): quando arriva il resoconto,
il caricamento del resoconto la sostituisce. Trasformazione pura.
"""

from __future__ import annotations

import html
import re

MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                     "settembre", "ottobre", "novembre", "dicembre"], 1)}


def _pulito(t: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("​", "")
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\s*\n\s*", "\n", t)).strip()


def _ora(t: str) -> str | None:
    m = re.search(r"ore (\d{1,2})(?:[,.](\d{2}))?", t, re.I)
    return f"{int(m.group(1)):02d}:{m.group(2) or '00'}" if m else None


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    t = corpo.decode("utf-8", errors="replace")
    testa = re.search(r"<h5>\s*(\d+)\^\s*SEDUTA[^<]*<br\s*/?>\s*<em>([^<]*)</em>", t)
    if not testa:
        raise ValueError("ordine del giorno senza intestazione della seduta")
    numero, quando = int(testa.group(1)), _pulito(testa.group(2))
    d = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", quando)
    data = f"{d.group(3)}-{MESI[d.group(2).lower()]:02d}-{int(d.group(1)):02d}"
    s_uri = f"it:camera:{leg}:sed{numero:04d}"
    seduta = {"label": "Sitting", "uri": s_uri, "chamber": "camera", "body": f"it:camera:{leg}:aula", "number": numero, "date": data,
              "status": "planned", "kind": "assembly_agenda", "start_time": _ora(quando), "source": "camera_odg",
              "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}
    corpo_odg = t[testa.end():]
    corpo_odg = corpo_odg[corpo_odg.find("<ol"):]
    nodi, archi = [seduta], []
    for i, li in enumerate(re.findall(r"<li>(.*?)</li>", corpo_odg, re.S), 1):
        titolo = re.search(r'<p class="titolo argomento">(.*?)</p>', li, re.S)
        if not titolo:
            continue
        testi = [_pulito(x) for x in re.findall(r'<p class="testo_argomento">(.*?)</p>', li, re.S)]
        orario = re.search(r'<p class="orario_argomento">(.*?)</p>', li, re.S)
        relatori = re.findall(r"Relator[ei]: ([^<]+)", li)
        atti = [f"ac:{x}" for x in re.findall(r"tipoDoc=pdl&amp;idDocumento=(\d+[\w-]*)", li)]
        atti += [f"aic:{x}" for x in re.findall(r"tipoDoc=si&amp;idDocumento=(\d-\d+(?:-\w+)?)", li)]
        p = {"label": "AgendaItem", "uri": f"{s_uri}:odg{i:02d}", "order": i, "title": _pulito(titolo.group(1)).rstrip(":"),
             "text": "\n".join(x for x in testi if x) or None, "scheduled_time": _ora(_pulito(orario.group(1))) if orario else None,
             "rapporteurs": _pulito(relatori[0]).rstrip(". ") if relatori else None, "acts": list(dict.fromkeys(atti))}
        nodi.append(p)
        archi.append({"type": "HAS_ITEM", "from": s_uri, "to": p["uri"], "order": i})
        archi += [{"type": "ABOUT", "from": p["uri"], "to_ref": a} for a in p["acts"]]
    return {"nodi": nodi, "archi": archi, "testi": [],
            "ambito": {"kind": "odg", "chamber": "camera", "legislature": leg, "sitting": s_uri, "date": data,
                       "source": "camera_odg", "source_key": fonte.get("chiave")}}
