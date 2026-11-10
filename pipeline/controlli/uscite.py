"""Controlli sulle uscite trasformate, prima di caricarle: un file che non passa una regola va in quarantena e non si
carica; gli altri vanno avanti. Si controllano solo i file nuovi o cambiati dall'ultimo caricamento (registro del
caricamento, `carica/registro.py`), più quelli già in quarantena, che a ogni giro si ricontrollano.

Sono le regole dello schema v3 che si possono verificare sui file (le altre girano sul grafo caricato).
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date


# seggi per ramo: più mandati in corso di così vuol dire dati sbagliati
SEGGI = {"camera": 400, "senato": 212}   # Senato: 200 elettivi più i senatori a vita e di diritto


def _regole(righe: list[dict]) -> list[str]:
    errori = []
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    uris = Counter(n.get("uri") or n.get("code") for n in nodi)   # le versioni dei testi si riconoscono dal codice
    doppi = [u for u, k in uris.items() if k > 1]
    if doppi:
        errori.append(f"uri ripetuti: {doppi[:3]}")
    ambito = next((r for r in righe if r["tipo"] == "ambito"), {})
    if ambito.get("kind") == "commissione":
        return errori + _regole_commissione(nodi, [r for r in righe if r["tipo"] == "arco"], {t["ref"] for t in righe if t["tipo"] == "testo"},
                                            ambito.get("source"))
    if ambito.get("kind") == "corrispondenze":
        archi = [r for r in righe if r["tipo"] == "arco"]
        doppi = [u for u, k in Counter(a["to"] for a in archi).items() if k > 1]
        if doppi:
            errori.append(f"più persone della Camera legate alla stessa persona del Senato: {doppi[:3]}")
        if nodi and len(archi) / len(nodi) < 0.9:
            errori.append(f"solo {len(archi)} senatori su {len(nodi)} legati: le fonti hanno cambiato forma?")
        return errori
    if ambito.get("kind") == "governo":
        return errori + _regole_governo(nodi, [r for r in righe if r["tipo"] == "arco"])
    if ambito.get("kind") == "documenti_elenco":
        if any(not n.get("url") or not n.get("body") for n in nodi):
            errori.append("documento senza indirizzo o senza commissione")
        if any(not n.get("third_party") for n in nodi):
            errori.append("documento acquisito non marcato come scritto di terzi")
        return errori
    if ambito.get("kind") == "testo_atto":
        testo = next((r["text"] for r in righe if r["tipo"] == "testo"), "")
        if len(testo) < 200 and not any(n.get("incomplete_at_source") for n in nodi):
            errori.append(f"testo dell'atto troppo corto o vuoto: {ambito.get('code')}")
        return errori
    if ambito.get("kind") == "emendamenti":
        noti = {n["uri"] for n in nodi}
        if any(not n.get("number") or not n.get("act") for n in nodi):
            errori.append("emendamento senza numero o senza atto")
        for a in (r for r in righe if r["tipo"] == "arco"):
            if a["to"] not in noti:
                errori.append(f"firma di un emendamento che non c'è: {a['to']}")
                break
        senza = sum(1 for n in nodi if not n.get("text_ref"))
        if nodi and senza / len(nodi) > 0.05:
            errori.append(f"{senza} emendamenti su {len(nodi)} senza testo")
        return errori
    if ambito.get("kind") == "dossier":
        n = nodi[0] if nodi else {}
        if not n.get("title") or not n.get("date"):
            errori.append(f"dossier senza titolo o senza data: {n.get('uri')}")
        return errori
    if ambito.get("kind") == "documento_testo":
        return errori
    if ambito.get("kind") == "odg":
        sedute = [n for n in nodi if n["label"] == "Sitting"]
        if len(sedute) != 1 or sedute[0].get("status") != "planned" or not sedute[0].get("date"):
            errori.append("l'ordine del giorno deve dare una sola seduta prevista, con la data")
        if not any(n["label"] == "AgendaItem" for n in nodi):
            errori.append("ordine del giorno senza argomenti")
        return errori
    if ambito.get("kind") == "calendario":
        voci = [n for n in nodi if n["label"] == "CalendarItem"]
        if len(voci) < 3:
            errori.append(f"calendario dei lavori con {len(voci)} voci: la pagina è cambiata o è vuota")
        if any(not n.get("date") or not n.get("title") for n in voci):
            errori.append("voce del calendario senza data o senza testo")
        return errori
    if ambito.get("kind") == "video":
        return errori + _regole_video(nodi, [r for r in righe if r["tipo"] == "arco"])
    if ambito.get("kind") == "aic":
        return errori + _regole_aic(nodi, [r for r in righe if r["tipo"] == "arco"])
    if ambito.get("kind") == "atti":
        return errori + _regole_atti(nodi, [r for r in righe if r["tipo"] == "arco"])
    if ambito.get("kind") == "convocazioni":
        voci = [n for n in nodi if n["label"] == "Convocation"]          # una commissione può non avere convocazioni
        if any(not n.get("date") or not n.get("body_name") or not n.get("uri") for n in voci):
            errori.append("convocazione senza data o senza commissione")
        if len({n["uri"] for n in voci}) != len(voci):
            errori.append("convocazioni ripetute")
        if len(voci) > 5 and not any(n.get("text") for n in voci):
            errori.append("convocazioni tutte senza argomenti: la pagina ha cambiato forma")
        return errori
    if ambito.get("kind") == "atti_governo":
        return errori + _regole_atti_governo(nodi, [r for r in righe if r["tipo"] == "arco"], ambito)
    if ambito.get("kind") == "voti":
        return errori + _regole_voti(nodi, [r for r in righe if r["tipo"] == "arco"])
    if ambito.get("kind") == "concetti":
        if len(nodi) < 1000 or any(not n.get("uri") or not n.get("label_it") for n in nodi):
            errori.append(f"thesaurus {ambito.get('scheme')}: {len(nodi)} concetti, o concetti senza nome")
        return errori
    if ambito.get("kind") == "anagrafica":
        return errori + _regole_anagrafica(nodi, [r for r in righe if r["tipo"] == "arco"], ambito)
    sedute = [n for n in nodi if n["label"] == "Sitting"]
    if len(sedute) != 1 or not sedute[0].get("date") or not sedute[0].get("chamber") or not sedute[0].get("kind"):
        errori.append("una e una sola Sitting con data, ramo e tipo")
    noti = set(uris)
    for a in (r for r in righe if r["tipo"] == "arco"):
        for lato in ("from", "to"):
            if lato in a and a[lato] not in noti and not a[lato].startswith("it:person:"):
                errori.append(f"arco {a['type']} verso un nodo che non c'è: {a[lato]}")
                break
    testi = {t["ref"] for t in righe if t["tipo"] == "testo"}
    senza = [n["uri"] for n in nodi if n["label"] == "Speech" and n["text_ref"] not in testi]
    if senza:
        errori.append(f"{len(senza)} interventi senza testo")
    parti = [x for r in righe if r["tipo"] == "arco" and r["type"] == "FROM" for x in r.get("parts") or []]
    if any(x.get("kind") not in ("group", "person", "office", "chair") or not x.get("name") for x in parti):
        errori.append("chi reagisce: parte senza tipo o senza nome")
    return errori[:10]


def _regole_anagrafica(nodi: list[dict], archi: list[dict], ambito: dict) -> list[str]:
    errori, noti = [], {n["uri"] for n in nodi}
    for a in archi:
        if a["type"] == "NAMED":                                # il nome di un gruppo: ha solo «from»
            if a["from"] not in noti:
                errori.append(f"nome di un gruppo che non c'è: {a['from']}")
                break
            continue
        if a["from"] not in noti or (a["to"] not in noti and not a["to"].startswith("it:leg:")):
            errori.append(f"arco {a['type']} fra nodi che non ci sono: {a['from']} -> {a['to']}")
            break
    for a in archi:
        if a["type"] in ("MANDATE", "SITS_ON", "OFFICE") and not a.get("start"):
            errori.append(f"{a['type']} senza data di inizio: {a['from']} -> {a['to']}")
            break
        if a.get("start") and a.get("end") and a["end"] < a["start"]:
            errori.append(f"{a['type']} che finisce prima di iniziare: {a['from']} -> {a.get('to')}")
            break
    persone = {n["uri"] for n in nodi if n["label"] == "Person"}
    con_mandato = {a["from"] for a in archi if a["type"] == "MANDATE"}
    if persone - con_mandato:
        errori.append(f"{len(persone - con_mandato)} persone senza mandato")
    if any(not n.get("family_name") for n in nodi if n["label"] == "Person"):
        errori.append("persone senza cognome")
    oggi = date.today().isoformat()
    in_carica = {a["from"] for a in archi if a["type"] == "MANDATE" and a["start"] <= oggi and (not a.get("end") or a["end"] >= oggi)}
    seggi = SEGGI.get(ambito.get("chamber"), 10_000)
    if not 0.9 * seggi <= len(in_carica) <= seggi:
        errori.append(f"{len(in_carica)} mandati in corso per {seggi} seggi")
    return errori[:10]


TIPO_TESTO = {"camera_bollettino": "summary", "camera_stenografici_commissioni": "verbatim", "senato_sommcomm": "summary"}


def _regole_commissione(nodi: list[dict], archi: list[dict], testi: set, fonte: str | None) -> list[str]:
    errori, noti = [], {n["uri"] for n in nodi}
    sedute = [n for n in nodi if n["label"] == "Sitting"]
    if not sedute:
        errori.append("comunicato senza sedute")
    if any(not s.get("date") or not s.get("body_code") for s in sedute):
        errori.append("seduta senza data o senza commissione")
    for a in archi:
        if a["type"] in ("HAS_ITEM", "HAS_SPEECH") and (a["from"] not in noti or a["to"] not in noti):
            errori.append(f"{a['type']} fra nodi che non ci sono: {a['from']} -> {a['to']}")
            break
        if a["type"] == "BY" and not a["to"].startswith(("it:person:camera:", "it:person:senato:")):
            errori.append(f"intervento di chi non è una persona: {a['to']}")
            break
    senza = [n["uri"] for n in nodi if n["label"] in ("Speech", "Document") and n["text_ref"] not in testi]
    if senza:
        errori.append(f"{len(senza)} paragrafi o allegati senza testo")
    atteso = TIPO_TESTO.get(fonte or "")
    if not atteso:
        errori.append(f"fonte di commissione sconosciuta: {fonte}")
    elif any(n["label"] == "Speech" and n.get("kind") != atteso for n in nodi):
        errori.append(f"testo marcato male: da {fonte} ci si aspetta {atteso} (sommario e verbatim non si devono confondere)")
    return errori[:10]


def _regole_governo(nodi: list[dict], archi: list[dict]) -> list[str]:
    errori, noti = [], {n["uri"] for n in nodi}
    if not any(n["label"] == "Government" for n in nodi):
        errori.append("nessun governo")
    for a in archi:
        if a["from"] not in noti or a["to"] not in noti:
            errori.append(f"incarico fra nodi che non ci sono: {a['from']} -> {a['to']}")
            break
        if not a.get("start") or (a.get("end") and a["end"] < a["start"]):
            errori.append(f"incarico con date sbagliate: {a['from']} {a.get('start')} {a.get('end')}")
            break
    oggi = date.today().isoformat()
    in_carica = [a for a in archi if a["title"] == "prime_minister" and a["start"] <= oggi and (not a.get("end") or a["end"] >= oggi)]
    governi_in_carica = [n for n in nodi if n["label"] == "Government" and (n.get("start") or "") <= oggi and not n.get("end")]
    if governi_in_carica and len(in_carica) != 1:
        errori.append(f"{len(in_carica)} presidenti del Consiglio in carica oggi")
    return errori[:10]


def _regole_video(nodi: list[dict], archi: list[dict]) -> list[str]:
    errori = []
    v = next((n for n in nodi if n["label"] == "Video"), None)
    if not v or not v.get("sitting"):
        errori.append("video senza seduta")
    for a in archi:
        if a.get("start") is not None and a.get("end") is not None and a["end"] < a["start"]:
            errori.append(f"tratto di video che finisce prima di iniziare: {a.get('anchor')}")
            break
    return errori


def _regole_aic(nodi: list[dict], archi: list[dict]) -> list[str]:
    errori, noti = [], {n["uri"] for n in nodi}
    if any(not n.get("date") or not n.get("number") for n in nodi):
        errori.append("atti senza data o senza numero")
    if any(n["kind"] == "other_inspection" for n in nodi):
        errori.append(f"tipi di atto non riconosciuti: {sorted({n['kind_raw'] for n in nodi if n['kind'] == 'other_inspection'})[:5]}")
    for a in archi:
        if a["type"] in ("SPONSORS",) and a["to"] not in noti or a["type"] in ("ADDRESSED_TO", "SUBJECT") and a["from"] not in noti:
            errori.append(f"{a['type']} verso un atto che non c'è")
            break
    # un'interrogazione o una mozione senza testo non serve: se ne mancano molti, la fonte ha cambiato forma
    senza = sum(1 for n in nodi if not n.get("text"))
    if nodi and senza / len(nodi) > 0.05:
        errori.append(f"{senza} atti su {len(nodi)} senza testo")
    return errori[:10]


def _regole_atti(nodi: list[dict], archi: list[dict]) -> list[str]:
    errori, noti = [], {n["uri"] for n in nodi}
    atti = [n for n in nodi if n["label"] == "Act"]
    if not atti:
        errori.append("nessun atto")
    senza = [a["uri"] for a in atti if not a.get("status") or not a.get("number")]
    if senza:
        errori.append(f"{len(senza)} atti senza numero o senza stato dell'iter: {senza[:3]}")
    for a in archi:
        lati = [a.get("to")] + ([a["from"]] if a["type"] in ("HAS_STEP", "HAS_VERSION", "ASSIGNED", "JOINED", "TRANSMITTED") else [])
        if any(x and x.startswith("it:camera:") and ":ac:" in x and x not in noti for x in lati):
            errori.append(f"{a['type']} verso un atto che non c'è: {a}")
            break
        if a["type"] == "SPONSORS" and not (a.get("from") or "").startswith("it:person:"):
            errori.append(f"firmatario che non è una persona: {a}")
            break
    return errori[:10]


def _regole_atti_governo(nodi: list[dict], archi: list[dict], ambito: dict) -> list[str]:
    errori, noti = [], {n["uri"] for n in nodi}
    if len(nodi) < 50:
        errori.append(f"solo {len(nodi)} atti del Governo e nomine: la fonte è cambiata o è arrivata a metà")
    if len(noti) != len(nodi):
        errori.append("atti del Governo con lo stesso numero ripetuti")
    senza = [n["uri"] for n in nodi if not n.get("number") or not n.get("title") or not n.get("status")
             or n.get("kind") not in ("government_act", "appointment")]
    if senza:
        errori.append(f"{len(senza)} atti senza numero, titolo o stato: {senza[:3]}")
    if any(a["type"] != "ASSIGNED" or a["from"] not in noti or not a.get("to") for a in archi):
        errori.append("assegnazione verso un atto che non c'è o senza commissione")
    # alla Camera ogni atto è assegnato almeno a una commissione: se mancano, la pagina ha cambiato forma
    if ambito.get("chamber") == "camera" and len({a["from"] for a in archi}) < 0.9 * len(nodi):
        errori.append(f"assegnazioni per {len({a['from'] for a in archi})} atti su {len(nodi)}")
    return errori[:10]


ESITI = {"favor", "against", "abstain", "absent", "mission", "chair", "voted", "present_not_voting"}


def conti_voti(nodi: list[dict], archi: list[dict]) -> dict[str, tuple]:
    """Per ogni votazione palese: (totali pubblicati, conti dai voti dei singoli)."""
    voti = {n["uri"]: n for n in nodi if n["label"] == "Vote"}
    c: dict[str, Counter] = {u: Counter() for u in voti}
    for a in archi:
        if a["type"] == "VOTED" and a["to"] in c:
            c[a["to"]][a["result"]] += 1
    return {u: ((v.get("favor"), v.get("against"), v.get("abstain")), (c[u]["favor"], c[u]["against"], c[u]["abstain"]))
            for u, v in voti.items() if not v.get("secret")}


def _regole_voti(nodi: list[dict], archi: list[dict]) -> list[str]:
    """Errori di struttura, che bloccano. I totali che non tornano sono un avviso (vedi avvisi_voti): capita nella
    fonte (aprile 2024, sedute 277-282: un favorevole in più del totale pubblicato; seduta 385: voti dei singoli mancanti)."""
    errori, voti = [], {n["uri"]: n for n in nodi if n["label"] == "Vote"}
    for a in archi:
        if a["type"] != "VOTED":
            continue
        if a["to"] not in voti or not a.get("from"):
            errori.append(f"voto senza votazione o senza deputato: {a.get('from')} -> {a['to']}")
            break
        if a["result"] not in ESITI:
            errori.append(f"esito sconosciuto: {a['result']}")
            break
    errori += [f"{u} senza data" for u, v in voti.items() if not v.get("date")]
    return errori[:10]


def avvisi_voti(nodi: list[dict], archi: list[dict]) -> list[str]:
    return [f"{u}: totali {t}, voti {c[0]}/{c[1]}/{c[2]}" for u, (t, c) in conti_voti(nodi, archi).items() if t != c]


SOGLIA_VOTI = 0.02   # oltre il 2% di votazioni che non tornano, l'errore sta nella trasformazione


def errori_file(righe: list[dict]) -> list[str]:
    """Gli errori di un file di uscita: vuoto se si può caricare."""
    return _regole(righe) if righe else ["file vuoto"]


def controlla(ctx) -> dict:
    from ..carica.postgres import destinazione, leggi_uscita
    from ..carica.registro import Registro
    registro = Registro(ctx.cartella, destinazione())
    cartella = ctx.cartella / "uscite" / "v3"
    file_, problemi, avvisi, votazioni, file_voti = 0, {}, [], 0, []
    for f in sorted(cartella.rglob("*.jsonl")):
        h = registro.da_caricare(f)
        if h is None:
            continue
        file_ += 1
        try:
            righe = leggi_uscita(f)
            e = errori_file(righe)
        except Exception as x:
            righe, e = [], [f"file illeggibile: {x}"]
        if e:
            problemi[f.name] = e
            registro.in_quarantena(f, h, "controllo", "; ".join(e), ctx.giro)
            continue
        registro.esci_di_quarantena(f, "controllo")
        if righe[0].get("kind") == "voti":
            nodi, archi = [r for r in righe if r["tipo"] == "nodo"], [r for r in righe if r["tipo"] == "arco"]
            votazioni += sum(1 for n in nodi if n["label"] == "Vote")
            avvisi += avvisi_voti(nodi, archi)
            file_voti.append((f, h))
    if votazioni and len(avvisi) / votazioni > SOGLIA_VOTI:
        # troppe votazioni che non tornano: l'errore sta nella trasformazione, e restano fuori tutti i voti nuovi
        motivo = f"{len(avvisi)} votazioni su {votazioni} non tornano con i totali: troppe per essere errori della fonte"
        for f, h in file_voti:
            registro.in_quarantena(f, h, "controllo", motivo, ctx.giro)
            problemi[f.name] = [motivo]
    r = {"file_controllati": file_, "in_quarantena": len(problemi), "avvisi": len(avvisi), "esempi_avvisi": avvisi[:10]}
    if problemi:
        r["avviso"] = f"{len(problemi)} file in quarantena, non si caricano: {json.dumps(dict(list(problemi.items())[:5]), ensure_ascii=False)[:1500]}"
    return r
