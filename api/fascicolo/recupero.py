"""Recupero delle evidenze del fascicolo: i brani degli interventi che servono a rispondere, bilanciati fra tutti i gruppi.

Passi, come nel backend precedente:
1. riscrittura della domanda breve (facoltativa, col modello) e vettore della domanda;
2. canale denso: i brani di interventi più vicini alla domanda nell'ambito (pgvector, `vicini`);
3. canale degli atti: atti sul tema per parole (titolo, temi EuroVoc, testo), riordinati per similarità, e i brani
   vicini alla domanda negli interventi di chi li ha firmati;
4. fusione dei canali (recupero_fusione): punteggio, tetti per persona e partito, minimo per partito;
5. copertura: per ogni partito sotto MINIMO_PER_PARTITO, i suoi brani migliori fra i vicini;
6. dibattiti: il modello giudica i titoli dei dibattiti; un gruppo (o il governo) senza brani da un dibattito sul tema
   prende i suoi migliori da quei dibattiti;
7. perimetro: chi ha parlato del tema in ogni gruppo (alla data), per l'autorevolezza e la verifica.

Regole sui gruppi: un brano conta per il gruppo di chi parla alla data (group_at), e solo se oggi è ancora nello
stesso gruppo (una citazione non va mai a un gruppo che ha lasciato); nel Misto conta per la componente. Il perimetro
usa il gruppo alla data anche se poi l'ha lasciato. I membri del governo stanno a parte (lato «governo»). Chi presiede
e chi non ha una scheda (auditi) non entrano; i resoconti sommari neppure, salvo `sommari=True`.

Non portati: l'espansione ai brani vicini più citabili (nel v3 non c'è il punteggio di citabilità: senza, non sposta
niente) e la bussola ideologica (la fa la generazione)."""

from __future__ import annotations

import datetime as dt
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import psycopg

from ..db import connessione
from . import modello
from .recupero_canali import (atti_per_parole, firmatari, interventi, parole_chiave, similarita_atti,
                              vicini)
from .recupero_commissioni import commissioni
from .recupero_fusione import MINIMO_PER_PARTITO, fondi
from .recupero_gruppi import NOME_GOVERNO, partiti_attesi
from .recupero_modello import SUL_TEMA, giudica_dibattiti, riscrivi

__all__ = ["Ambito", "recupera", "vicini", "brani_di", "statistiche", "commissioni", "risolvi_ambito", "PARAMETRI"]

RAMI = ("camera", "senato")

# i parametri del backend precedente (scala (1 + cos) / 2 per le similarità). Le soglie sulle similarità sono ritarate
# per text-embedding-3-large (con il 3-small di prima stavano più in basso) sulle 35 domande della prova pilota
# (benchmark/pilota-2026-11-02/selezione.json, 5 trappole comprese) più 5 domande fuori dominio (ricette, calcio,
# veterinaria, smartphone, meteo), il 4/11/2026:
# - fra i primi 200 brani densi, le domande sul Parlamento stanno tutte sopra 0,71 (le più deboli: APP-002 e DJ-009, il
#   200° a 0,711), quelle fuori dominio fra 0,62 e 0,67 con al più un brano oltre 0,72 (il migliore 0,74, meteo);
# - i brani dei firmatari (200 per domanda) stanno sopra 0,70, quasi tutti sopra 0,72;
# - il coseno puro fra domanda e atti: 0,43-0,73 per gli atti sul tema, al più 0,37 per le domande fuori dominio.
PARAMETRI = {
    "quanti": 100,                    # brani dopo la fusione
    "denso_k": 200,                   # vicini del canale denso (2 × quanti)
    # sotto, i brani delle domande fuori dominio; sopra, tutti i 200 vicini delle domande della prova (0,55 col 3-small)
    "denso_soglia": 0.68,
    "copertura_vicini": 500,          # fra quanti vicini si cercano i brani di un partito sotto quota
    "copertura_soglia": 0.15,         # di fatto nessuna: la copertura serve a sentire tutti i gruppi
    "perimetro_per_partito": 20,
    "dibattiti_vicini": 1500,
    "dibattiti_per_partito": 3,
    "atti_massimi": 1000,             # atti trovati per parole (100 nel backend precedente: vedi _canale_atti)
    # coseno puro fra domanda e atto: sopra il migliore atto delle domande fuori dominio (0,37), sotto quelli sul tema
    "atti_soglia": 0.4,
    "atti_migliori": 50,
    "firmatari_brani": 200,
    # un brano di chi ha firmato gli atti entra se è vicino quanto la coda del canale denso (0,71): 0,65 col 3-small
    "firmatari_soglia": 0.72,
    # filtro dei temi fuori dominio: almeno `minimo_sopra_soglia` brani densi da qui in su. Le domande della prova ne
    # hanno da 64 (DJ-009) a 200, quelle fuori dominio al più uno. Era 0,78, che col modello nuovo fermava COMU-035
    # (2 brani) e GIO-025 (nessuno)
    "soglia_pertinenza": 0.72,
    "minimo_sopra_soglia": 10,
}


@dataclass
class Ambito:
    """Dove cercare: i rami (camera, senato) e il periodo delle sedute, estremi inclusi (None = senza limite)."""
    rami: list[str] = field(default_factory=lambda: ["camera", "senato"])
    da: dt.date | None = None
    a: dt.date | None = None

    def __post_init__(self):
        self.rami = [r for r in RAMI if r in set(self.rami or RAMI)]
        if not self.rami:
            raise ValueError("ramo sconosciuto: camera o senato")
        if self.da and self.a and self.da > self.a:
            raise ValueError("periodo vuoto: «da» viene dopo «a»")

    def come_dict(self) -> dict:
        return {"rami": list(self.rami), "da": self.da.isoformat() if self.da else None,
                "a": self.a.isoformat() if self.a else None}


# un ramo nominato nella domanda. «Camera» da sola non basta (camera di commercio, camera iperbarica)
_SENATO = re.compile(r"\b(senato|senator[ei]|senatric[ei]|palazzo madama)\b", re.IGNORECASE)
_CAMERA = re.compile(r"\b((all[ao']|nell[ao']|dell[ao']|in)\s*camera\b(?!\s+di\s+commercio)|camera dei deputati|deputat[ie]|montecitorio)",
                     re.IGNORECASE)
_ANNO = re.compile(r"\b(?:nel|del|durante il)\s+(20\d{2})\b", re.IGNORECASE)
_DALL_ANNO = re.compile(r"\bdal\s+(20\d{2})\b", re.IGNORECASE)


def risolvi_ambito(domanda: str, ambito: Ambito | None = None) -> Ambito:
    """L'ambito di una domanda. Se l'ambito copre i due rami e la domanda ne nomina uno solo, si cerca in quello (come
    il selettore del sito lasciato su «entrambi»); un ambito su un ramo vince sulla domanda. Senza periodo, un anno
    detto nella domanda («nel 2026», «dal 2024») diventa il periodo."""
    ambito = ambito or Ambito()
    rami = list(ambito.rami)
    nominati = [r for r, rx in (("camera", _CAMERA), ("senato", _SENATO)) if rx.search(domanda or "")]
    if len(nominati) == 1 and set(rami) == set(RAMI):
        rami = nominati
    da, a = ambito.da, ambito.a
    if da is None and a is None:
        anni = sorted({int(x) for x in _ANNO.findall(domanda or "")})
        if len(anni) == 1:
            da, a = dt.date(anni[0], 1, 1), dt.date(anni[0], 12, 31)
        elif (m := _DALL_ANNO.search(domanda or "")):
            da = dt.date(int(m.group(1)), 1, 1)
    return Ambito(rami=rami, da=da, a=a)


def _vicini_interventi(c: psycopg.Connection, vettore: str, ambito: Ambito, k: int, sommari: bool,
                       persone: list[str] | None = None) -> list[dict]:
    return vicini(c, vettore, ["speech"], k, rami=ambito.rami, da=ambito.da, a=ambito.a, persone=persone,
                  solo_parlamentari=True, sommari=sommari)


def _canale_atti(c: psycopg.Connection, testo: str, vettore: str, ambito: Ambito, attesi: dict, sommari: bool,
                 tempi: dict) -> tuple[list[dict], dict]:
    """Canale degli atti: atti per parole, riordino per similarità, brani dei firmatari vicini alla domanda."""
    t = time.perf_counter()
    parole = parole_chiave(testo)
    info = {"parole": parole, "atti": 0, "atti_scelti": 0, "firmatari": 0}
    atti = atti_per_parole(c, parole, ambito.rami, PARAMETRI["atti_massimi"]) if parole else []
    info["atti"] = len(atti)
    sim = similarita_atti(c, vettore, [a["uri"] for a in atti])
    for a in atti:
        a["similarita"] = sim.get(a["uri"], 0.5)             # un atto senza vettore resta col valore neutro
    scelti = sorted((a for a in atti if a["similarita"] >= PARAMETRI["atti_soglia"]), key=lambda a: -a["similarita"])
    scelti = scelti[:PARAMETRI["atti_migliori"]]
    info["atti_scelti"] = len(scelti)
    info["esempi"] = [{"uri": a["uri"], "title": (a["title"] or "")[:120], "similarita": round(a["similarita"], 3)}
                      for a in scelti[:5]]
    persone = firmatari(c, [a["uri"] for a in scelti])
    info["firmatari"] = len(persone)
    tempi["atti_ms"] = round((time.perf_counter() - t) * 1000)
    if not persone:
        return [], info
    t = time.perf_counter()
    brani = _vicini_interventi(c, vettore, ambito, PARAMETRI["firmatari_brani"], sommari, persone)
    brani = [b for b in brani if b["similarita"] >= PARAMETRI["firmatari_soglia"]]
    righe = [r for r in interventi(c, brani, attesi) if r["partito"]]
    for r in righe:
        r["canali"] = ["grafo"]
    tempi["firmatari_ms"] = round((time.perf_counter() - t) * 1000)
    return righe, info


def _canale_atti_a_parte(testo, vettore, ambito, attesi, sommari, tempi) -> tuple[list[dict], dict] | None:
    """Il canale degli atti su una connessione nuova; None se non si apre (allora va sulla connessione della domanda)."""
    try:
        conn = connessione()
    except psycopg.Error:
        return None
    with conn:
        return _canale_atti(conn, testo, vettore, ambito, attesi, sommari, tempi)


def _lato_o_partito(r: dict) -> str:
    return NOME_GOVERNO if r["governo"] else r["partito"]


def recupera(c: psycopg.Connection, domanda: str, ambito: Ambito | None = None, ip: str | None = None, *,
             quanti: int | None = None, riscrittura: bool = True, giudizio: bool = True, sommari: bool = False,
             autorevolezza: dict[str, float] | None = None, con_commissioni: bool = True,
             vettore: list[float] | None = None, parallelo: bool = True) -> dict:
    """Le evidenze per una domanda nell'ambito dato (rami e periodo; vedi risolvi_ambito per la domanda che nomina un
    ramo o un anno).

    Restituisce un dict con:
    - `evidenze`: un dict per brano, nell'ordine della fusione (poi i brani di copertura e dei dibattiti):
      chunk_id («<uri dell'intervento>#<ord>»), speech_uri, text (il brano: speech_text[start_char:end_char]),
      speech_text, start_char, end_char, kind (verbatim | summary), speaker {uri, nome, gruppo (il gruppo alla data:
      «Misto» per una componente), sigla, componente (del Misto, o None), ruolo (deputato | senatore | governo),
      carica}, partito (per chi conta: la componente nel Misto, «Governo» per un membro del governo senza gruppo),
      lato (maggioranza | opposizione | misto | governo), governo, chamber, date (ISO), sitting (uri), sitting_number,
      sitting_kind, body, debate (titolo del dibattito), debate_relevance (T | G | A | None), url (pagina del
      resoconto: Camera con l'ancora dell'intervento; Senato la pagina della seduta, sitting.record_url, o None),
      similarita (scala (1 + cos) / 2), score (della
      fusione; per i brani aggiunti dopo, la similarità), score_components, canali (denso, grafo, copertura,
      dibattito);
    - `statistiche`: i conti per l'introduzione e il frontend (statistiche());
    - `perimetro`: {partito: {uri della persona: ramo}} di chi ha parlato del tema, alla data, senza il governo;
    - `partiti`: {partito: {lato, rami, gruppi}} attesi nell'ambito;
    - `commissioni`: le commissioni del tema per ramo (recupero_commissioni.commissioni);
    - `vettore`: il vettore della domanda (riscritta), da riusare (autorevolezza, `brani_di`);
    - `metadata`: ambito usato, domanda riscritta, pertinenza (max_similarity, chunks_above_floor, floor, passa),
      conti per canale, party_coverage, canale degli atti, tempi in millisecondi.

    `autorevolezza` ({uri della persona: punteggio}) entra nella fusione col suo peso; senza, vale 0,5. `vettore`
    salta il calcolo del vettore (prove, domande già viste). Con `parallelo` il canale degli atti apre una seconda
    connessione (api.db.connessione) e corre insieme al canale denso."""
    t0 = time.perf_counter()
    tempi: dict[str, int] = {}
    ambito = risolvi_ambito(domanda, ambito)
    quanti = quanti or PARAMETRI["quanti"]

    t = time.perf_counter()
    testo = riscrivi(domanda, ip) if riscrittura else domanda
    tempi["riscrittura_ms"] = round((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    v = vettore or modello.vettori([testo], ip)[0]
    lettera = modello.letterale(v)
    tempi["vettore_ms"] = round((time.perf_counter() - t) * 1000)

    attesi = partiti_attesi(c, ambito.rami)
    partiti = sorted(attesi)

    # il canale degli atti va in parallelo, su una connessione sua (la connessione di psycopg serve una query alla volta)
    ex = ThreadPoolExecutor(max_workers=1)
    atti_f = ex.submit(_canale_atti_a_parte, testo, lettera, ambito, attesi, sommari, tempi) if parallelo else None

    # un solo giro sull'indice per denso, copertura, perimetro e dibattiti: sono tutti «i primi N vicini nell'ambito»
    t = time.perf_counter()
    vicini_n = max(PARAMETRI["denso_k"], PARAMETRI["copertura_vicini"], PARAMETRI["dibattiti_vicini"])
    brani = _vicini_interventi(c, lettera, ambito, vicini_n, sommari)
    tempi["vicini_ms"] = round((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    pool = interventi(c, brani, attesi)
    tempi["interventi_ms"] = round((time.perf_counter() - t) * 1000)
    rango = {b["uri"] + "#" + str(b["ord"]): i for i, b in enumerate(brani)}
    for r in pool:
        r["_rango"] = rango.get(r["chunk_id"], len(rango))

    def primi(n: int) -> list[dict]:
        return [r for r in pool if r["_rango"] < n]

    densi = [dict(r, canali=["denso"]) for r in primi(PARAMETRI["denso_k"])
             if r["similarita"] >= PARAMETRI["denso_soglia"] and r["partito"]]
    sim_densi = [r["similarita"] for r in densi]

    risposta_atti = atti_f.result() if atti_f else None
    ex.shutdown(wait=False)
    grafo, info_atti = risposta_atti or _canale_atti(c, testo, lettera, ambito, attesi, sommari, tempi)

    t = time.perf_counter()
    fusi = fondi(densi, grafo, quanti, partiti, autorevolezza)

    # copertura: i partiti sotto quota (contano i parlamentari, non i membri del governo)
    conti = Counter(r["partito"] for r in fusi if r["partito"] and not r["governo"])
    sotto = [p for p in partiti if conti.get(p, 0) < MINIMO_PER_PARTITO]
    presi = {r["chunk_id"] for r in fusi}
    copertura = []
    for p in sotto:
        cand = [r for r in primi(PARAMETRI["copertura_vicini"])
                if r["partito"] == p and r["similarita"] >= PARAMETRI["copertura_soglia"] and r["chunk_id"] not in presi]
        for r in cand[:MINIMO_PER_PARTITO]:
            copertura.append(dict(r, canali=["copertura"]))
            presi.add(r["chunk_id"])
    risultati = fusi + copertura

    # perimetro: chi ha parlato del tema in ogni partito, col gruppo alla data
    perimetro: dict[str, dict[str, str]] = {}
    per_partito: Counter = Counter()
    for r in primi(PARAMETRI["copertura_vicini"]):
        p = r["partito_data"]
        if not p or r["governo"] or per_partito[p] >= PARAMETRI["perimetro_per_partito"]:
            continue
        per_partito[p] += 1
        perimetro.setdefault(p, {}).setdefault(r["speaker"]["uri"], r["chamber"])
    tempi["fusione_ms"] = round((time.perf_counter() - t) * 1000)

    # dibattiti: il giudizio (col modello) mentre si cercano le commissioni
    t = time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as ex:
        giudizio_f = ex.submit(giudica_dibattiti, domanda, sorted({r["debate"] for r in risultati if r["debate"]}), ip) \
            if giudizio else None
        tc = time.perf_counter()
        comm = commissioni(c, domanda, lettera, tuple(ambito.rami), testo if testo != domanda else None) \
            if con_commissioni else []
        tempi["commissioni_ms"] = round((time.perf_counter() - tc) * 1000)
        giudizi = giudizio_f.result() if giudizio_f else {}
    tempi["dibattiti_ms"] = round((time.perf_counter() - t) * 1000)
    dibattito = []
    if giudizi:
        for r in risultati:
            r["debate_relevance"] = giudizi.get((r["debate"] or "").strip())
        sul_tema = {k for k, x in giudizi.items() if x == SUL_TEMA}
        coperti = {_lato_o_partito(r) for r in risultati if r.get("debate_relevance") == SUL_TEMA}
        voluti = (set(partiti) | {NOME_GOVERNO}) - coperti
        per_lato: Counter = Counter()
        voci: set = set()
        for r in primi(PARAMETRI["dibattiti_vicini"]):
            if not r["partito"] or (r["debate"] or "").strip() not in sul_tema or r["chunk_id"] in presi:
                continue
            lato = _lato_o_partito(r)
            if lato not in voluti or per_lato[lato] >= PARAMETRI["dibattiti_per_partito"]:
                continue
            if (lato, r["speaker"]["uri"]) in voci and per_lato[lato] >= 1:
                continue                                    # prima una voce per persona: voci diverse del gruppo
            dibattito.append(dict(r, canali=["dibattito"], debate_relevance=SUL_TEMA))
            presi.add(r["chunk_id"])
            voci.add((lato, r["speaker"]["uri"]))
            per_lato[lato] += 1
    risultati += dibattito

    for r in risultati:
        r.pop("_rango", None)
        r.setdefault("debate_relevance", None)
        if "score" not in r:
            r["score"], r["score_components"] = r["similarita"], None

    pertinenza = {"max_similarity": max(sim_densi, default=0.0),
                  "chunks_above_floor": sum(s >= PARAMETRI["soglia_pertinenza"] for s in sim_densi),
                  "floor": PARAMETRI["soglia_pertinenza"]}
    pertinenza["passa"] = pertinenza["chunks_above_floor"] >= PARAMETRI["minimo_sopra_soglia"]
    tempi["totale_ms"] = round((time.perf_counter() - t0) * 1000)
    return {
        "evidenze": risultati,
        "statistiche": statistiche(risultati),
        "perimetro": perimetro,
        "partiti": attesi,
        "commissioni": comm,
        "vettore": v,
        "metadata": {
            "ambito": ambito.come_dict(),
            "rewritten_query": testo if testo != domanda else None,
            "relevance": pertinenza,
            "dense_channel_count": len(densi),
            "graph_channel_count": len(grafo),
            "merged_count": len(fusi),
            "coverage_fill_count": len(copertura),
            "debate_fill_count": len(dibattito),
            "debates_judged": len(giudizi),
            "party_coverage": dict(Counter(r["partito"] for r in risultati)),
            "missing_parties": [p for p in partiti if p not in {r["partito"] for r in risultati}],
            "graph_channel": info_atti,
            "processing_time_ms": tempi["totale_ms"],
            "tempi": tempi,
        },
    }


def brani_di(c: psycopg.Connection, vettore: list[float] | str, persone: list[str], ambito: Ambito | None = None,
             per_persona: int = 3, vicini_n: int = 3000, sommari: bool = False) -> list[dict]:
    """I brani più vicini al tema di alcune persone, al più `per_persona` ciascuna: le voci autorevoli di un gruppo
    che non hanno brani fra le evidenze. Stesse righe di `recupera` (gruppo alla data e ancora oggi), canale
    «autorevolezza»."""
    if not persone:
        return []
    ambito = ambito or Ambito()
    lettera = vettore if isinstance(vettore, str) else modello.letterale(vettore)
    attesi = partiti_attesi(c, ambito.rami)
    brani = _vicini_interventi(c, lettera, ambito, vicini_n, sommari, list(persone))
    out, conti = [], Counter()
    for r in interventi(c, brani, attesi):
        if not r["partito"] or conti[r["speaker"]["uri"]] >= per_persona:
            continue
        conti[r["speaker"]["uri"]] += 1
        out.append(dict(r, canali=["autorevolezza"], score=r["similarita"], score_components=None,
                        debate_relevance=None))
    return out


def statistiche(evidenze: list[dict]) -> dict:
    """I conti sul tema dalle evidenze, come li vuole il frontend: interventi, persone, dibattiti, sedute, periodo, per
    ramo, e gli elenchi cliccabili (speakers_detail, interventions_detail, sessions_detail)."""
    vuoto = {"intervention_count": 0, "speaker_count": 0, "debate_count": 0, "first_date": None, "last_date": None,
             "debate_title": None, "session_numbers": [], "by_chamber": {}, "speakers_detail": [],
             "interventions_detail": [], "sessions_detail": []}
    if not evidenze:
        return vuoto
    date = [e["date"] for e in evidenze if e.get("date")]
    titoli = Counter(e["debate"] for e in evidenze if e.get("debate"))
    persone: dict[str, dict] = {}
    for e in evidenze:
        s = e["speaker"]
        voce = persone.setdefault(s["uri"], {"speaker_id": s["uri"], "speaker_name": s["nome"], "party": e["partito"],
                                             "coalition": e["lato"], "chamber": e["chamber"], "speech_ids": set()})
        voce["speech_ids"].add(e["speech_uri"])
    speakers = sorted(({**{k: x for k, x in v.items() if k != "speech_ids"}, "intervention_count": len(v["speech_ids"])}
                       for v in persone.values()), key=lambda x: -x["intervention_count"])
    interventi_d: dict[str, dict] = {}
    sedute: dict[str, dict] = {}
    per_ramo: dict[str, dict[str, set]] = {}
    for e in evidenze:
        interventi_d.setdefault(e["speech_uri"], {
            "speech_id": e["speech_uri"], "chamber": e["chamber"], "url": e["url"], "speaker_id": e["speaker"]["uri"],
            "speaker_name": e["speaker"]["nome"], "party": e["partito"], "coalition": e["lato"], "date": e["date"],
            "debate_title": e["debate"], "session_number": e["sitting_number"]})
        sedute.setdefault(e["sitting"], {"session_number": e["sitting_number"], "session_id": e["sitting"],
                                         "chamber": e["chamber"], "url": None, "date": e["date"],
                                         "debate_title": e["debate"]})
        x = per_ramo.setdefault(e["chamber"], {"speeches": set(), "speakers": set()})
        x["speeches"].add(e["speech_uri"])
        x["speakers"].add(e["speaker"]["uri"])
    return {
        "intervention_count": len(interventi_d),
        "speaker_count": len(persone),
        "debate_count": len(titoli),
        "first_date": min(date) if date else None,
        "last_date": max(date) if date else None,
        "debate_title": titoli.most_common(1)[0][0] if titoli else None,
        "session_numbers": sorted({e["sitting_number"] for e in evidenze if e.get("sitting_number")}),
        "by_chamber": {r: {"intervention_count": len(x["speeches"]), "speaker_count": len(x["speakers"])}
                       for r, x in per_ramo.items()},
        "speakers_detail": speakers,
        "interventions_detail": sorted(interventi_d.values(), key=lambda x: x["date"], reverse=True),
        "sessions_detail": sorted(sedute.values(), key=lambda x: (x["chamber"], x["session_number"])),
    }
