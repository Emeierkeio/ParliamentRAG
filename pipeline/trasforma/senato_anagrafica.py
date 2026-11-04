"""Dall'anagrafica OSR del Senato agli stessi record della Camera: persone, gruppi, commissioni e le relazioni datate
MANDATE, MEMBER_OF, SITS_ON, OFFICE. Trasformazione pura.

Particolarità del Senato:
- un gruppo ha più denominazioni nel tempo (Forza Italia -> «… - PPE»): il nome è quello in vigore più di recente
  durante la legislatura, le altre restano come alias;
- una commissione ha una denominazione per periodo (la riforma del 2022 ha rinumerato le commissioni: la «7ª» è
  diventata «6ª»): ogni appartenenza prende il nome in vigore alla sua data d'inizio;
- i senatori a vita e di diritto hanno un mandato di tipo `life` o `ex_officio`;
- le componenti del Misto non sono nell'OSR: vengono dalla pagina della composizione storica (grezzo `misto`, senato_misto).
Le persone del Senato hanno un id proprio (it:person:senato:17542); il legame con la stessa persona alla Camera o
al governo (it:person:camera:…) è un lavoro a parte (corrispondenza delle persone).
"""

from __future__ import annotations

from . import senato_misto
from .camera_anagrafica import data, leggibile

CARICHE_GRUPPO = {"Presidente": "leader", "Vicepresidente Vicario": "deputy_leader", "Vicepresidente": "deputy_leader",
                  "Tesoriere": "treasurer", "Segretario": "secretary", "Segretario d'Aula": "floor_secretary"}
CARICHE_COMMISSIONE = {"Presidente": "chair", "Vicepresidente": "vice_chair", "Segretario": "secretary"}


def _id(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _tipo_mandato(t: str | None) -> str:
    t = (t or "").lower()
    return "ex_officio" if "di diritto" in t else "life" if "a vita" in t else "elected"


def _tipo_organo(titolo: str) -> str:
    t = titolo.lower()
    if "inchiesta" in t:
        return "inquiry_committee"
    if "commissione permanente" in t:
        return "standing_committee"
    if "giunta" in t:
        return "board"
    if "bicamerale" in t or "parlamentare" in t:
        return "bicameral_committee"
    if "presidenza" in t or "questori" in t:
        return "presidency"
    return "committee"


def trasforma(grezzi: dict[str, list[dict]], leg: int, fonte: dict | None = None) -> dict:
    fonte = fonte or {}
    ramo = "senato"
    nodi: dict[str, dict] = {}
    archi: list[dict] = []
    for r in grezzi.get("persone", []):
        u = f"it:person:senato:{_id(r['senatore'])}"
        if u in nodi:
            if r.get("professione") and r["professione"] not in (nodi[u]["profession"] or ""):
                nodi[u]["profession"] = "; ".join(x for x in (nodi[u]["profession"], r["professione"]) if x)
            continue
        nome, cognome = r.get("nome") or "", r.get("cognome") or ""
        if not (nome and cognome):
            parti = (r.get("etichetta") or "").split(" ", 1)
            nome, cognome = (parti + [""])[:2]
        nodi[u] = {"label": "Person", "uri": u, "senato_id": _id(r["senatore"]), "given_name": nome, "family_name": cognome,
                   "sort_name": f"{cognome} {nome}", "gender": r.get("genere"), "photo": r.get("foto"), "profession": r.get("professione"),
                   "source": "osr", "source_uri": r["senatore"]}

    for r in grezzi.get("mandati", []):
        archi.append({"type": "MANDATE", "from": f"it:person:senato:{_id(r['senatore'])}", "to": f"it:leg:{leg}", "chamber": ramo,
                      "legislature": leg, "kind": _tipo_mandato(r.get("tipo")), "start": data(r.get("inizio")), "end": data(r.get("fine")),
                      "end_reason": r.get("motivo"), "constituency": r.get("regione"), "college": r.get("collegio"),
                      "system": "majoritarian" if "uninominale" in (r.get("elezione") or "").lower() else
                                "proportional" if "plurinominale" in (r.get("elezione") or "").lower() else None,
                      "list": None, "source_uri": r["mandato"]})

    # gruppi: il nome è la denominazione in vigore più di recente durante la legislatura
    inizio_leg = min((a["start"] for a in archi if a["type"] == "MANDATE" and a.get("start")), default="")
    denominazioni: dict[str, list[dict]] = {}
    for r in grezzi.get("denominazioni", []):
        if not r.get("fine") or r["fine"][:10] >= inizio_leg:
            denominazioni.setdefault(r["gruppo"], []).append(r)
    for g, ds in denominazioni.items():
        ds.sort(key=lambda d: d["inizio"])
        u = f"it:{ramo}:{leg}:group:{_id(g)}"
        ultima = ds[-1]
        nodi[u] = {"label": "Group", "uri": u, "chamber": ramo, "legislature": leg, "kind": "group", "name": leggibile(ultima["titolo"]) if ultima["titolo"].isupper() else ultima["titolo"],
                   "short_name": ultima.get("breve"), "start": None, "end": data(ultima.get("fine")),
                   "aliases": list(dict.fromkeys(d["titolo"] for d in ds)), "source": "osr", "source_uri": g}
        if len(ds) > 1:                                 # il nome in vigore in ogni periodo della legislatura
            archi.extend({"type": "NAMED", "from": u, "name": leggibile(d["titolo"]) if d["titolo"].isupper() else d["titolo"],
                          "short_name": d.get("breve"), "start": data(d["inizio"]), "end": data(d.get("fine"))} for d in ds)

    for r in grezzi.get("adesioni", []):
        u = f"it:{ramo}:{leg}:group:{_id(r['gruppo'])}"
        p = f"it:person:senato:{_id(r['senatore'])}"
        if u not in nodi or p not in nodi:
            continue
        archi.append({"type": "MEMBER_OF", "from": p, "to": u, "role": "member", "start": data(r["inizio"]), "end": data(r.get("fine")), "end_reason": None})
        if r.get("carica") and r["carica"] != "Membro":
            archi.append({"type": "OFFICE", "from": p, "to": u, "title": CARICHE_GRUPPO.get(r["carica"], "other"), "title_raw": r["carica"],
                          "start": data(r["inizio"]), "end": data(r.get("fine"))})

    if grezzi.get("misto"):
        misto = next((u for u, n in nodi.items() if n.get("kind") == "group" and (n["name"] or "").lower() == "misto"), None)
        if misto is None:
            raise ValueError("nell'anagrafica del Senato manca il Gruppo Misto")
        persone = {u for u, n in nodi.items() if n["label"] == "Person"}
        componenti, adesioni = senato_misto.trasforma(grezzi["misto"], leg, misto, persone, (fonte or {}).get("misto_url"))
        nodi.update({n["uri"]: n for n in componenti})
        archi.extend(adesioni)

    # commissioni: il nome in vigore alla data d'inizio dell'appartenenza
    for r in grezzi.get("commissioni", []):
        inizio = data(r.get("inizio"))
        valida = r.get("titolo") and (r.get("dinizio") or "")[:10] <= (inizio or "9999") and (not r.get("dfine") or r["dfine"][:10] >= (inizio or ""))
        u = f"it:{ramo}:{leg}:body:{_id(r['commissione'])}"
        if valida:
            nome = r["titolo"] + (f" ({r['materia']})" if r.get("materia") and r["materia"].lower() not in r["titolo"].lower() else "")
            vecchio = nodi.get(u)
            if not vecchio or (r.get("dinizio") or "") > vecchio.get("_dinizio", ""):
                nodi[u] = {"label": "Body", "uri": u, "chamber": ramo, "legislature": leg, "kind": _tipo_organo(r["titolo"]), "kind_raw": None,
                           "name": nome, "start": None, "end": None, "part_of": None, "source": "osr", "source_uri": r["commissione"],
                           "_dinizio": r.get("dinizio") or ""}
    for r in grezzi.get("commissioni", []):
        u = f"it:{ramo}:{leg}:body:{_id(r['commissione'])}"
        p = f"it:person:senato:{_id(r['senatore'])}"
        if u not in nodi or p not in nodi or not r.get("inizio"):
            continue
        ruolo = r.get("carica") or "Membro"
        archi.append({"type": "SITS_ON", "from": p, "to": u, "role": "member", "role_raw": ruolo, "start": data(r["inizio"]),
                      "end": data(r.get("fine")), "end_reason": None})
        if ruolo != "Membro":
            archi.append({"type": "OFFICE", "from": p, "to": u, "title": CARICHE_COMMISSIONE.get(ruolo, "other"), "title_raw": ruolo,
                          "start": data(r["inizio"]), "end": data(r.get("fine"))})
    for n in nodi.values():
        n.pop("_dinizio", None)
    visti, unici = set(), []
    for a in archi:
        k = repr(sorted(a.items()))
        if k not in visti:
            visti.add(k)
            unici.append(a)
    return {"nodi": list(nodi.values()), "archi": unici, "testi": [],
            "ambito": {"chamber": ramo, "legislature": leg, "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}}
