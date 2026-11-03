"""Dall'anagrafica OCD della Camera ai record dello schema v3: persone, gruppi, componenti del Misto, organi,
e le relazioni datate fra loro (MANDATE, MEMBER_OF, PART_OF, SITS_ON, OFFICE).

Trasformazione pura: stessi grezzi, stessi record. Riceve tutte le query insieme (`grezzi[nome] = righe`),
perché una persona, i suoi gruppi e le sue commissioni stanno in query diverse.

Convenzioni (SCHEMA-V3 §4): date ISO; `end` assente se il rapporto è in corso; `end` è l'ultimo giorno incluso.
I valori della Camera restano anche grezzi (`*_raw`), accanto a quelli normalizzati.
"""

from __future__ import annotations

import re

FONTE = "ocd"

# tipo di organo OCD -> kind dello schema (l'ordine conta: vince la prima regola che combacia)
TIPI_ORGANO = [
    ("INCHIESTA", "inquiry_committee"), ("COMMISSIONE PERMANENTE", "standing_committee"), ("COMMISSIONE SPECIALE", "special_committee"),
    ("BICAMERALE", "bicameral_committee"), ("COMMISSIONE MISTA", "bicameral_committee"), ("GIUNTA", "board"),
    ("DELEGAZIONE", "delegation"), ("CONFERENZA", "conference"), ("PRESIDENZA", "presidency"), ("QUESTORI", "presidency"),
    ("COMITAT", "committee"), ("COMMISSIONE", "committee"),
]
RUOLI_ORGANO = {"Titolare": "member", "Supplente": "substitute", "Sostituto": "replacement"}
CARICHE_ORGANO = {"PRESIDENTE": "chair", "VICEPRESIDENTE": "vice_chair", "SEGRETARIO": "secretary", "QUESTORE": "quaestor",
                  "CAPOGRUPPO": "group_whip", "COORDINATORE INCOMPATIBILITA'": "coordinator", "COORDINATORE INELEGGIBILITA' E DECADENZE": "coordinator"}
CARICHE_GRUPPO = {"PRESIDENTE": "leader", "PRESIDENTE - PORTAVOCE": "leader", "VICEPRES. VICARIO": "deputy_leader", "VICEPRESIDENTE": "deputy_leader",
                  "SEGRETARIO": "secretary", "TESORIERE": "treasurer", "DELEGATO D'AULA": "floor_delegate", "SEGRETARIO D'AULA": "floor_secretary",
                  "RAPPRESENTANTE COMPONENTE GRUPPO MISTO": "component_representative", "MEMBRO DEL C.D.": "board_member"}
STUDI = re.compile(r"^(laurea|diploma|licenza|dottorato|master|maturità|baccalaureato)", re.I)

_MINUSCOLE = {"di", "del", "della", "dello", "dei", "degli", "delle", "e", "ed", "al", "allo", "alla", "ai", "agli", "alle",
              "da", "dal", "con", "per", "in", "sul", "sulla", "sulle", "sui", "nel", "nella", "a", "il", "la", "le", "lo", "gli"}
_SIGLE = {"MAIE", "UDC", "USEI", "AVS", "PPE", "SVP", "PD", "M5S", "FI", "NM", "IV", "UE", "RAI", "ONU", "NATO", "OSCE", "INCE", "UEO", "PSE"}


def data(v: str | None) -> str | None:
    """'20221013' o '2022-10-13' -> '2022-10-13'; tutto il resto -> None."""
    v = (v or "").strip()
    if re.fullmatch(r"\d{8}", v):
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v[:10]):
        return v[:10]
    return None


def leggibile(testo: str) -> str:
    """'ALLEANZA VERDI E SINISTRA' -> 'Alleanza Verdi e Sinistra'; le sigle note restano maiuscole."""
    testo = re.sub(r"\s*-\s*", " - ", testo.strip())
    out = []
    for i, t in enumerate(testo.split()):
        nudo = t.strip("+(),.").upper()
        if t == "-" or nudo in _SIGLE or (re.fullmatch(r"[IVXL]+", nudo) and nudo not in ("IL", "LI")):  # sigle e numeri romani (II Commissione)
            out.append(t.upper() if t != "-" else t)
            continue
        basso = t.lower()
        m = re.match(r"^((?:d|l|dell|dall|nell|sull|all|coll|un)['’])(.+)$", basso)
        if m:  # «dell'agricoltura» -> «dell'Agricoltura», maiuscola solo in testa
            out.append((m.group(1) if i else m.group(1).capitalize()) + m.group(2).capitalize())
        elif i and basso in _MINUSCOLE:
            out.append(basso)
        else:
            out.append(basso[0] + basso[1:].capitalize() if basso.startswith("+") else basso.capitalize())
    return " ".join(out)


NOMI_PRIMA = {
    "gr4135": ["Azione-Italia Viva-Renew Europe"],
    "gr4211": ["Italia Viva-il Centro-Renew Europe"],
    "gr4152": ["Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC, Italia al Centro)-MAIE"],
    "cgm4139": ["Misto-+Europa"],
    "cgm4148": ["Misto-Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro)-MAIE"],
}


def senza_parentesi(titolo: str) -> str:
    """Toglie sigle e date fra parentesi, anche annidate o non chiuse in fondo ('AVS (27.10.2022')."""
    prima = None
    while prima != titolo:
        prima, titolo = titolo, re.sub(r"\([^()]*\)", "", titolo)
    return re.sub(r"\([^()]*$", "", titolo).strip(" -–")


def id_persona(uri: str) -> str | None:
    """persona.rdf/p308421 e deputato.rdf/d308421_19 sono la stessa persona."""
    m = re.search(r"/(?:persona\.rdf/p|deputato\.rdf/d)(\d+)", uri or "")
    return f"it:person:camera:{m.group(1)}" if m else None


def _coda(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _studi_lavoro(descrizione: str | None) -> tuple[str | None, str | None]:
    """'Laurea in economia; Dottore commercialista' -> (studi, professione)."""
    if not descrizione:
        return None, None
    parti = [p.strip() for p in descrizione.split(";") if p.strip()]
    if len(parti) >= 2:
        return parti[0], "; ".join(parti[1:])
    return (parti[0], None) if STUDI.match(parti[0]) else (None, parti[0])


def _luogo(etichetta: str | None) -> str | None:
    """'nato a SAN BENEDETTO DEL TRONTO, ASCOLI PICENO, MARCHE, il 11.02.1965' -> 'San Benedetto del Tronto'."""
    m = re.match(r"^nat[oa] a (.+?),", etichetta or "")
    return leggibile(m.group(1)) if m else None


def _tipo_organo(tipo: str | None) -> str:
    t = (tipo or "").upper()
    return next((k for chiave, k in TIPI_ORGANO if chiave in t), "other")


def persona(r: dict) -> dict:
    """Una riga della query delle persone (OCD) -> nodo Person. La usano anche i governi."""
    p = id_persona(r["persona"])
    studi, lavoro = _studi_lavoro(r.get("descrizione"))
    nome, cognome = leggibile(r["nome"]), leggibile(r["cognome"])
    return {"label": "Person", "uri": p, "camera_id": p.rsplit(":", 1)[1], "given_name": nome, "family_name": cognome,
            "sort_name": f"{cognome} {nome}", "gender": {"male": "M", "female": "F"}.get((r.get("genere") or "").lower()),
            "birth_date": data(r.get("nascita")), "birth_place": _luogo(r.get("luogo")), "photo": r.get("foto"),
            "education": studi, "profession": lavoro, "source": FONTE, "source_uri": r["persona"]}


def trasforma(grezzi: dict[str, list[dict]], leg: int, fonte: dict | None = None) -> dict:
    """Restituisce {'nodi', 'archi', 'testi'} per l'anagrafica di una legislatura della Camera."""
    fonte = fonte or {}
    nodi: dict[str, dict] = {}
    archi: list[dict] = []
    camera, leg_uri = "camera", f"it:leg:{leg}"

    def nodo(n: dict) -> None:
        nodi.setdefault(n["uri"], n)

    for r in grezzi.get("persone", []):
        nodo(persona(r))

    for r in grezzi.get("mandati", []):
        archi.append({"type": "MANDATE", "from": id_persona(r["persona"]), "to": leg_uri, "chamber": camera, "legislature": leg,
                      "start": data(r["inizio"]), "end": data(r.get("fine")), "end_reason": r.get("motivo") or None,
                      "validated": data(r.get("convalida")), "constituency": r.get("circoscrizione"), "college": r.get("collegio"),
                      "system": {"proporzionale": "proportional", "maggioritario": "majoritarian", "uninominale": "majoritarian"}.get((r.get("sistema") or "").lower(), r.get("sistema")),
                      "list": r.get("lista"), "source_uri": r["mandato"]})

    misto = None
    # gli altri nomi con cui il resoconto scrive il gruppo: il titolo intero della fonte (con le parentesi) e i nomi di prima,
    # che dati.camera.it non dà più. Stesso gruppo: nei resoconti le sigle A-IV-RE, IV-C-RE, MISTO-+EUROPA e NM(N-C-U-I
    # appartengono ai deputati di gr4135, gr4211, cgm4139 e gr4152 (controllo del 2/11/2026)
    def alias(r: dict, codice: str) -> list[str]:
        intero = r["titolo"].rsplit(f" ({r['sigla']})", 1)[0] if r.get("sigla") else senza_parentesi(r["titolo"])
        return list(dict.fromkeys([leggibile(intero), *NOMI_PRIMA.get(codice, [])]))

    for r in grezzi.get("gruppi", []):
        u = f"it:{camera}:{leg}:group:{_coda(r['gruppo'])}"
        nome = senza_parentesi(r["titolo"])
        if nome.upper().startswith("MISTO"):
            misto = u
        nodo({"label": "Group", "uri": u, "chamber": camera, "legislature": leg, "kind": "group", "name": leggibile(nome),
              "short_name": r.get("sigla"), "start": data(r.get("inizio")), "end": data(r.get("fine")), "source": FONTE, "source_uri": r["gruppo"],
              "aliases": alias(r, _coda(r["gruppo"]))})

    for r in grezzi.get("adesioni", []):
        archi.append({"type": "MEMBER_OF", "from": id_persona(r["deputato"]), "to": f"it:{camera}:{leg}:group:{_coda(r['gruppo'])}",
                      "role": "member", "start": data(r["inizio"]), "end": data(r.get("fine")), "end_reason": r.get("motivo") or None})

    for r in grezzi.get("componenti_misto", []):
        u = f"it:{camera}:{leg}:group:{_coda(r['componente'])}"
        titolo = senza_parentesi(r["titolo"])
        titolo = re.sub(r"^MISTO\s*-\s*", "", titolo, flags=re.I)
        if u not in nodi:
            nodo({"label": "Group", "uri": u, "chamber": camera, "legislature": leg, "kind": "misto_component", "name": leggibile(titolo),
                  "short_name": r.get("sigla"), "start": data(r.get("cinizio")), "end": data(r.get("cfine")), "source": FONTE, "source_uri": r["componente"],
                  "aliases": alias(r, _coda(r["componente"]))})
            if misto:
                archi.append({"type": "PART_OF", "from": u, "to": misto})
        archi.append({"type": "MEMBER_OF", "from": id_persona(r["deputato"]), "to": u, "role": "member",
                      "start": data(r.get("inizio")), "end": data(r.get("fine")), "end_reason": None})

    for r in grezzi.get("organi", []):
        u = f"it:{camera}:{leg}:body:{_coda(r['organo'])}"
        nodo({"label": "Body", "uri": u, "chamber": camera, "legislature": leg, "kind": _tipo_organo(r.get("tipo")), "kind_raw": r.get("tipo"),
              "name": leggibile(senza_parentesi(r["titolo"])), "start": data(r.get("inizio")), "end": data(r.get("fine")),
              "part_of": f"it:{camera}:{leg}:body:{_coda(r['parte'])}" if r.get("parte") else None, "source": FONTE, "source_uri": r["organo"]})

    for r in grezzi.get("membri_organi", []):
        archi.append({"type": "SITS_ON", "from": id_persona(r["deputato"]), "to": f"it:{camera}:{leg}:body:{_coda(r['organo'])}",
                      "role": RUOLI_ORGANO.get(r.get("tipo") or "", "member"), "role_raw": r.get("tipo"),
                      "start": data(r["inizio"]), "end": data(r.get("fine")), "end_reason": r.get("motivo") or None})

    for r in grezzi.get("uffici", []):
        archi.append({"type": "OFFICE", "from": id_persona(r["deputato"]), "to": f"it:{camera}:{leg}:body:{_coda(r['organo'])}",
                      "title": CARICHE_ORGANO.get(r["carica"], "other"), "title_raw": r["carica"], "start": data(r["inizio"]), "end": data(r.get("fine"))})

    for r in grezzi.get("incarichi_gruppo", []):
        archi.append({"type": "OFFICE", "from": id_persona(r["deputato"]), "to": f"it:{camera}:{leg}:group:{_coda(r['gruppo'])}",
                      "title": CARICHE_GRUPPO.get(r["ruolo"], "other"), "title_raw": r["ruolo"], "start": data(r["inizio"]), "end": data(r.get("fine"))})

    # le stesse righe possono arrivare due volte dalla fonte: si tiene un arco per contenuto
    visti, unici = set(), []
    for a in archi:
        k = tuple(sorted((k, str(v)) for k, v in a.items()))
        if k not in visti:
            visti.add(k)
            unici.append(a)
    # la stessa carica arriva a volte due volte, una con la data di fine e una senza: vale quella chiusa
    # (prima la copia aperta lasciava in carica chi aveva lasciato: XIII commissione con tre presidenti)
    chiuse = {(a["from"], a["to"], a.get("title"), a.get("start")) for a in unici if a["type"] == "OFFICE" and a.get("end")}
    unici = [a for a in unici if not (a["type"] == "OFFICE" and not a.get("end") and (a["from"], a["to"], a.get("title"), a.get("start")) in chiuse)]
    return {"nodi": list(nodi.values()), "archi": unici, "testi": [],
            "ambito": {"chamber": camera, "legislature": leg, "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}}
