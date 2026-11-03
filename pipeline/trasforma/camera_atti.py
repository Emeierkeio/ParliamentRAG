"""Dai progetti di legge OCD della Camera ai record dello schema v3: `Act`, `Step` (iter), `TextVersion`, e le
relazioni SPONSORS, HAS_STEP, HAS_VERSION, ASSIGNED, RAPPORTEUR, JOINED, TRANSMITTED.

Trasformazione pura, su tutte le query insieme. I relatori arrivano solo come nome («SCHIFONE Marta, relatore per
la maggioranza»): si legano alla persona al caricamento, confrontando il nome con l'anagrafica.
"""

from __future__ import annotations

import html
import re

from .camera_anagrafica import data, id_persona

FONTE = "ocd"
MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
                                     "ottobre", "novembre", "dicembre"], 1)}


def _coda(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def uri_atto(uri: str, leg: int) -> str | None:
    """attocamera.rdf/ac19_151 -> it:camera:19:ac:151."""
    m = re.search(r"/ac\d+_([\w-]+)$", uri or "")
    return f"it:camera:{leg}:ac:{m.group(1)}" if m else None


def pulito(testo: str | None) -> str | None:
    if not testo:
        return None
    t = html.unescape(html.unescape(testo))
    t = re.sub(r"\^\^http\S+$", "", t)
    return re.sub(r"\s+", " ", t).strip() or None


def legge(descrizione: str | None) -> tuple[str | None, str | None]:
    """'Legge 106 del 18 luglio 2025 pubblicata…' -> ('106', '2025-07-18')."""
    m = re.search(r"Legge (?:costituzionale )?(\d+) dell?['’ ]\s*(\d{1,2})°? (\w+) (\d{4})", descrizione or "", re.I)
    if not m or m.group(3).lower() not in MESI:
        return None, None
    return m.group(1), f"{m.group(4)}-{MESI[m.group(3).lower()]:02d}-{int(m.group(2)):02d}"


def relatore(titolo: str) -> tuple[str, str | None]:
    """'SCHIFONE Marta, relatore per la maggioranza' -> ('SCHIFONE Marta', 'majority')."""
    nome, _, resto = titolo.partition(",")
    ruolo = "majority" if "maggioranza" in resto else "minority" if "minoranza" in resto else "rapporteur"
    return nome.strip(), ruolo


def trasforma(grezzi: dict[str, list[dict]], leg: int, fonte: dict | None = None) -> dict:
    fonte = fonte or {}
    nodi: dict[str, dict] = {}
    archi: list[dict] = []
    for r in grezzi.get("atti", []):
        u = uri_atto(r["atto"], leg)
        if u in nodi:
            n = nodi[u]
        else:
            natura = _coda(r.get("natura") or "")
            numero_legge, data_legge = legge(r.get("descrizione"))
            n = nodi[u] = {"label": "Act", "uri": u, "chamber": "camera", "legislature": leg, "number": r["numero"],
                           "kind": "bill", "kind_raw": natura or r.get("tipo"), "constitutional": "costituzional" in natura,
                           "initiative": r.get("iniziativa"), "title": pulito(r.get("titolo")), "date": data(r.get("data")),
                           "description": pulito(r.get("descrizione")), "law_number": numero_legge, "law_date": data_legge,
                           "card_url": r.get("scheda"), "text_urls": [], "source": FONTE, "source_uri": r["atto"]}
        if r.get("testo") and r["testo"] not in n["text_urls"]:
            n["text_urls"].append(r["testo"])

    for r in grezzi.get("firmatari", []):
        archi.append({"type": "SPONSORS", "from": id_persona(r.get("firmatario") or ""), "to": uri_atto(r["atto"], leg),
                      "first": r["primo"] == "1", "as_office": r.get("carica")})

    passi: dict[str, list] = {}
    for r in grezzi.get("iter", []):
        a = uri_atto(r["atto"], leg)
        s = f"{a}:{_coda(r['stato'])}"
        if s not in nodi:
            nodi[s] = {"label": "Step", "uri": s, "title": pulito(r["titolo"]), "date": data(r.get("data"))}
            passi.setdefault(a, []).append(nodi[s])
    for a, ss in passi.items():
        # ordine dell'iter: per data, a parità per numero del passo nella fonte
        ss.sort(key=lambda x: (x["date"] or "", int(re.sub(r"\D", "", x["uri"].rsplit(":", 1)[1]) or 0)))
        for i, s in enumerate(ss, 1):
            archi.append({"type": "HAS_STEP", "from": a, "to": s["uri"], "order": i})
        if a in nodi:
            nodi[a]["status"], nodi[a]["status_date"] = ss[-1]["title"], ss[-1]["date"]

    for r in grezzi.get("versioni", []):
        a = uri_atto(r["atto"], leg)
        v = f"{a}:{_coda(r['versione'])}"
        if v not in nodi:
            nodi[v] = {"label": "TextVersion", "uri": v, "title": pulito(r.get("titolo")), "date": data(r.get("data")), "url": r.get("url")}
            archi.append({"type": "HAS_VERSION", "from": a, "to": v})

    for r in grezzi.get("assegnazioni", []):
        archi.append({"type": "ASSIGNED", "from": uri_atto(r["atto"], leg), "to": f"it:camera:{leg}:body:{_coda(r['organo'])}",
                      "seat": (r.get("sede") or "").strip().lower() or None, "date": data(r.get("data")), "title": pulito(r.get("titolo"))})
    for r in grezzi.get("relatori", []):
        nome, ruolo = relatore(pulito(r["titolo"]) or "")
        archi.append({"type": "RAPPORTEUR", "from_ref": nome, "to": uri_atto(r["atto"], leg), "role": ruolo, "raw": pulito(r["titolo"])})
    for r in grezzi.get("abbinamenti", []):
        a, p = uri_atto(r["atto"], leg), uri_atto(r["portante"], leg)
        if a != p:
            archi.append({"type": "JOINED", "from": a, "to": p, "text_type": r.get("tipo_testo")})
    for r in grezzi.get("trasmissioni", []):
        t = pulito(r["titolo"]) or ""
        m = re.search(r"\(S\. ([\w-]+)\)", t)
        archi.append({"type": "TRANSMITTED", "from": uri_atto(r["atto"], leg), "to_ref": f"S.{m.group(1)}" if m else None,
                      "date": data(r.get("data")), "title": t, "provenance": r.get("provenienza")})

    visti, unici = set(), []
    for a in archi:
        k = repr(sorted(a.items()))
        if k not in visti:
            visti.add(k)
            unici.append(a)
    return {"nodi": list(nodi.values()), "archi": unici, "testi": [],
            "ambito": {"kind": "atti", "chamber": "camera", "legislature": leg, "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}}
