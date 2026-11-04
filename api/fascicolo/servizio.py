"""Il fascicolo come flusso SSE, con gli stessi eventi della vecchia /api/query, così il sito non cambia (sito/js/chat.js,
fascicoloVero): progress (step, message), waiting, experts (data), topic_stats, citation_details (citations), chunk
(data), error (code, message), complete.

Il percorso: recupero delle evidenze (recupero.py; un tema fuori dominio si ferma lì, senza testo, e il sito passa
alla chat), autorevolezza degli oratori (autorevolezza.py), una voce autorevole
per gruppo (le prime AUTORITA_PRIME del gruppo fra chi ha parlato del tema; il Misto per componente), generazione a
sezioni (generazione/), poi la verifica: ogni citazione si ricontrolla parola per parola sul testo dell'intervento in
Postgres e quelle che non tornano si tolgono. Ogni citazione porta il link al resoconto.

Pochi fascicoli alla volta (FASCICOLI_INSIEME, uno se non è detto): chi arriva dopo riceve `waiting` e aspetta il suo
turno. Durante i passi lunghi partono righe di commento («: in corso») che il sito ignora e che tengono viva la
connessione."""

from __future__ import annotations

import contextvars
import datetime as dt
import json
import logging
import re
import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from pipeline.ambiente import env

from .. import agente, conversazioni
from ..db import connessione
from ..strumenti.comune import url_intervento
from . import modello
from .generazione import GenerationPipeline, gruppi
from .generazione.contesto import IP, RAMI, in_parallelo
from .generazione.debate_relevance import judge_debates
from .generazione.group_votes import compute_group_votes, set_group_votes
from .generazione.impostazioni import ID_BRANO
from .generazione.traduzione import traduci
from .generazione.verbatim import is_verbatim

log = logging.getLogger("parliamentrag.fascicolo")

AUTORITA_PRIME = 5                 # una voce è autorevole fra le prime cinque del suo gruppo sul tema
BATTITO = 15                       # secondi fra due righe di commento mentre si lavora
PEZZO = 100                        # caratteri per evento chunk, come prima
_posti = threading.BoundedSemaphore(int(env("FASCICOLI_INSIEME", "1")))
_LINK = re.compile(r"\[«([^»]*)»\]\((" + ID_BRANO + r")\)")

MESSAGGI = {
    1: ("Avvio retrieval...", "Query analysis and retrieval..."),
    3: ("Calcolo authority scores...", "Computing authority scores..."),
    4: ("Scelta delle citazioni...", "Choosing the quotes..."),
    5: ("Generazione risposta multi-view...", "Generating multi-view answer..."),
}
ERRORE = {"it": "Non è stato possibile completare la risposta. Riprova tra poco.",
          "en": "The answer could not be completed. Please try again shortly."}
CODA = {"it": "In coda: il sistema prepara poche risposte alla volta. La tua parte appena si libera un posto.",
        "en": "In the queue: the system prepares a few answers at a time. Yours starts as soon as a slot frees up."}
# le chiavi dei pesi che manda il sito → quelle delle componenti dell'autorevolezza
COMPONENTI = {"interventions": "speeches", "acts": "acts", "committee": "committee", "profession": "profession",
              "education": "education", "role": "role"}


def evento(e: dict) -> str:
    return f"data: {json.dumps(e, ensure_ascii=False, default=str)}\n\n"


# ---------- dalle evidenze del recupero al formato della generazione ----------

def id_sito(uri: str | None) -> str:
    """L'id di una persona come lo legge il sito (come autorevolezza.id_sito): la scheda di dati.camera.it
    (…/persona.rdf/p307134) per i deputati, di dati.senato.it (…/senatore/36449) per i senatori."""
    m = re.match(r"it:person:(camera|senato):(\d+)$", uri or "")
    if not m:
        return uri or ""
    return (f"http://dati.camera.it/ocd/persona.rdf/p{m.group(2)}" if m.group(1) == "camera"
            else f"http://dati.senato.it/senatore/{m.group(2)}")


def _parti_nome(nome: str) -> tuple[str, str]:
    parole = (nome or "").split()
    if len(parole) < 2:
        return "", nome or ""
    i = len(parole) - 1
    while i > 1 and parole[i - 1].lower() in {"de", "di", "da", "del", "della", "dalla", "dal", "dei", "degli", "la", "lo", "le", "li"}:
        i -= 1
    return " ".join(parole[:i]), " ".join(parole[i:])


def _giudizio(e: dict) -> str | None:
    for k in ("debate_relevance", "giudizio", "pertinenza_dibattito", "dibattito_sul_tema"):
        v = e.get(k)
        if isinstance(v, bool):
            return "T" if v else None
        if v in ("T", "G", "A"):
            return v
    return None


def evidenze(brani: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """Le evidenze nel formato della generazione, con un id breve (b1, b2…) che il modello copia nei [CIT:…]."""
    out, per_id = [], {}
    for i, b in enumerate(brani, 1):
        s = b.get("speaker") or {}
        governo = bool(b.get("governo")) or s.get("ruolo") == "governo"
        # il partito alla data dell'intervento: chi ha cambiato gruppo da allora parlava per quello di allora
        partito = b.get("partito_data") or b.get("partito") or gruppi.nome_partito(s.get("componente") or s.get("gruppo"))
        nome = s.get("nome") or ""
        primo, ultimo = _parti_nome(nome)
        data = b.get("date")
        if isinstance(data, str):
            try:
                data = dt.date.fromisoformat(data[:10])
            except ValueError:
                pass
        testo = b.get("text") or ""
        e = {
            "evidence_id": f"b{i}", "chunk_id": b.get("chunk_id"), "chunk_text": testo, "quote_text": testo,
            "speech_id": b.get("speech_uri"), "speaker_id": s.get("uri") or "", "speaker_name": nome,
            "speaker_first_name": primo, "speaker_last_name": ultimo,
            "speaker_role": "GovernmentMember" if governo else "Deputy", "institutional_role": s.get("carica"),
            "party": partito or gruppi.MISTO,
            "misto_component": s.get("componente") if gruppi.nome_partito(s.get("gruppo")) == gruppi.MISTO else None,
            "coalition": "governo" if governo else gruppi.parte(partito),
            "date": data, "debate_title": b.get("debate") or "", "session_number": b.get("sitting_number"),
            "doc_id": b.get("sitting"), "chamber": b.get("chamber") or "camera", "url": b.get("url"),
            "similarity": float(b.get("similarita", b.get("score", 0.5)) or 0.5),
            "span_start": b.get("start_char", 0), "span_end": b.get("end_char", 0),
            "debate_relevance": _giudizio(b), "authority_score": 0.0, "speech_text": b.get("speech_text"),
        }
        out.append(e)
        per_id[e["evidence_id"]] = e
    return out, per_id


def giudica_dibattiti(domanda: str, ev: list[dict]) -> None:
    """Se il recupero non ha giudicato i dibattiti, lo fa qui: T sul tema, G generico, A su altro atto."""
    if any(e.get("debate_relevance") for e in ev):
        return
    giudizi = judge_debates(domanda, (e.get("debate_title") or "" for e in ev))
    for e in ev:
        e["debate_relevance"] = giudizi.get((e.get("debate_title") or "").strip())


# ---------- autorevolezza e voci ----------

def _punteggio(x: dict) -> float:
    for k in ("authority_score", "punteggio", "totale", "total_score", "score"):
        if isinstance(x.get(k), (int, float)):
            return float(x[k])
    return 0.0


def _componenti(x: dict) -> dict:
    c = x.get("components") or x.get("componenti") or x.get("score_breakdown") or {}
    alias = {"interventi": "interventions", "speeches": "interventions", "commissione": "committee", "atti": "acts",
             "professione": "profession", "formazione": "education", "ruolo": "role"}
    return {alias.get(k, k): float(v or 0) for k, v in c.items() if isinstance(v, (int, float))}


def autorevolezza(c, domanda: str, ambito, persone: list[str], pesi: dict | None, ip: str) -> dict[str, dict]:
    """{uri: {"score", "components", …}} dal modulo dell'autorevolezza; {} se non c'è o non risponde."""
    try:
        from . import autorevolezza as aut
    except ImportError:
        log.warning("autorevolezza non disponibile: le voci non si controllano")
        return {}
    try:
        righe = aut.punteggi(c, domanda, ambito=ambito, persone=persone, pesi=pesi, ip=ip)
    except Exception as e:                          # noqa: BLE001 — il fascicolo va avanti senza autorevolezza
        log.warning("autorevolezza non calcolata: %s", e)
        return {}
    out = {}
    for x in righe or []:
        uri = x.get("uri") or x.get("persona") or x.get("person") or x.get("id")
        if uri:
            out[uri] = {**x, "score": _punteggio(x), "components": _componenti(x)}
    return out


def classifica_per_gruppo(ev: list[dict], punti: dict[str, dict], perimetro: dict | None = None) -> dict[str, dict]:
    """uri → posto nel suo gruppo (il Misto per componente) fra chi ha parlato del tema, dimensione del gruppo."""
    pool: dict[str, dict[str, float]] = {}
    for e in ev:
        if e.get("speaker_id") and e.get("speaker_role") != "GovernmentMember":
            pool.setdefault(e["party"], {})[e["speaker_id"]] = punti.get(e["speaker_id"], {}).get("score", 0.0)
    for partito, uris in (perimetro or {}).items():
        for u in uris:
            pool.setdefault(partito, {}).setdefault(u, punti.get(u, {}).get("score", 0.0))
    out = {}
    for partito, membri in pool.items():
        for i, (u, s) in enumerate(sorted(membri.items(), key=lambda kv: -kv[1]), 1):
            out[u] = {"rank": i, "pool_size": len(membri), "score": s, "party": partito}
    return out


def _schede(c, uris: list[str]) -> dict[str, dict]:
    """Foto, professione, formazione e commissione di oggi di alcune persone."""
    if not uris:
        return {}
    righe = c.execute("""
        SELECT p.uri, p.given_name, p.family_name, p.photo, p.profession, p.education, p.camera_id,
               (SELECT b.name FROM seat s JOIN body b ON b.uri = s.body
                WHERE s.person = p.uri AND s.end_date IS NULL AND b.kind = 'standing_committee' ORDER BY s.start_date DESC LIMIT 1) AS commissione
        FROM person p WHERE p.uri = ANY(%s)""", (list(uris),)).fetchall()
    out = {}
    for r in righe:
        cam = r["camera_id"] or (re.match(r"it:person:camera:(\d+)$", r["uri"]) or [None, None])[1]
        out[r["uri"]] = {**r, "camera_profile_url": f"https://www.camera.it/deputati/elenco/19-{cam}" if cam else None}
    return out


def posti_della_verifica(c, domanda: str, rami: list[str], persone: list[str], ip: str) -> dict[str, dict] | None:
    """uri -> posto nella sua voce con le regole della verifica (verifica.py): classifica per ramo, fra chi ha parlato
    del tema (chi_ha_parlato) più la persona stessa, come la verifica conta chi è citato. Così il fascicolo cita come
    voci autorevoli le stesse che la verifica delle tre garanzie riconosce. None se non si può calcolare."""
    try:
        from . import autorevolezza as aut, verifica as ver
        pr = aut.profili(c)
        q = aut.vettore(domanda, ip)
        classifica = [d for r in rami for d in aut.punteggi(c, domanda, ver._Ramo((r,)), ip=ip) if r in d["rami"] or not d["rami"]]
        if any("interventi" in d.get("degradato", ()) for d in classifica):
            return None
        pool = ver.chi_ha_parlato(c, q, rami, pr)
        voce_di = ver.voci_delle_persone(ver.persone_in_carica(c, rami, pr))
    except Exception as e:                          # noqa: BLE001 — resta la classifica del fascicolo
        log.warning("posti della verifica non calcolati: %s", e)
        return None
    out = {}
    for u in persone:
        canonico = pr.alias.get(u, u)
        tabella = ver.posizioni(classifica, voce_di, {**pool, canonico: pool.get(canonico)})
        if canonico in tabella:
            out[u] = {**tabella[canonico], "party": tabella[canonico]["ranking_group"]}
    return out


def esperto(e: dict, punti: dict[str, dict], schede: dict[str, dict], n_interventi: int) -> dict:
    sid = e["speaker_id"]
    p, sch = punti.get(sid, {}), schede.get(sid, {})
    comp = p.get("components", {})
    return {
        "id": id_sito(sid), "uri": sid,
        "first_name": e.get("speaker_first_name") or sch.get("given_name") or "",
        "last_name": e.get("speaker_last_name") or sch.get("family_name") or "",
        "group": e["party"], "coalition": gruppi.parte(e["party"]),
        "authority_score": round(p.get("score", 0.0), 2), "relevant_speeches_count": n_interventi,
        "camera_profile_url": sch.get("camera_profile_url"), "photo": sch.get("photo"),
        "profession": sch.get("profession"), "education": sch.get("education"), "committee": sch.get("commissione"),
        "institutional_role": p.get("institutional_role") or p.get("carica") or e.get("institutional_role"),
        "score_breakdown": {COMPONENTI[k]: round(comp.get(k, 0.0), 2) for k in COMPONENTI},
    }


def esperti_iniziali(ev: list[dict], punti: dict[str, dict], schede: dict[str, dict]) -> list[dict]:
    """Per ogni partito l'oratore più autorevole fra le evidenze (il Governo escluso)."""
    migliori: dict[str, dict] = {}
    conti: dict[str, int] = {}
    for e in ev:
        if e.get("speaker_role") == "GovernmentMember" or not e.get("speaker_id"):
            continue
        conti[e["speaker_id"]] = conti.get(e["speaker_id"], 0) + 1
        s = punti.get(e["speaker_id"], {}).get("score", 0.0)
        if e["party"] not in migliori or s > punti.get(migliori[e["party"]]["speaker_id"], {}).get("score", 0.0):
            migliori[e["party"]] = e
    return sorted((esperto(e, punti, schede, conti[e["speaker_id"]]) for e in migliori.values()),
                  key=lambda x: -x["authority_score"])


# ---------- citazioni ----------

def verifica_citazioni(c, testo: str, per_id: dict[str, dict]) -> tuple[str, set[str], int]:
    """Ogni [«…»](id) del testo si ricontrolla sul testo dell'intervento in Postgres (regole di verbatim.py). Un link a
    un id che non c'è perde il link; una citazione che non torna si toglie. Ritorna testo, id verificati, citazioni
    tolte."""
    uris = sorted({per_id[m.group(2)]["speech_id"] for m in _LINK.finditer(testo) if m.group(2) in per_id})
    testi = {r["uri"]: r["text"] for r in c.execute("SELECT uri, text FROM speech WHERE uri = ANY(%s)", (uris,))} if uris else {}
    buoni, tolte = set(), 0

    def controlla(m: re.Match) -> str:
        nonlocal tolte
        q, eid = m.group(1), m.group(2)
        e = per_id.get(eid)
        if e and is_verbatim(q, testi.get(e["speech_id"]) or ""):
            buoni.add(eid)
            return m.group(0)
        tolte += 1
        log.warning("citazione non letterale tolta: %s %r", eid, q[:80])
        return ""
    testo = _LINK.sub(controlla, testo)
    # i link a id inventati perdono il link, le parole restano (com'era per gli id che non esistono)
    testo = re.sub(r"\[([^\]]+)\]\((" + ID_BRANO + r")\)", lambda m: m.group(0) if m.group(2) in buoni else m.group(1), testo)
    if tolte:
        testo = re.sub(r" {2,}", " ", re.sub(r"\s+([.,;:])", r"\1", testo))
    return testo, buoni, tolte


def dettagli_citazioni(citazioni: list[dict], per_id: dict[str, dict], buoni: set[str], schede: dict[str, dict],
                       posti: dict[str, dict]) -> list[dict]:
    """L'evento citation_details: una voce per citazione verificata, con chunk_id uguale all'id del link nel testo."""
    out, visti = [], set()
    for cit in citazioni:
        eid = cit.get("evidence_id")
        if eid not in buoni or eid in visti:
            continue
        visti.add(eid)
        e = per_id[eid]
        governo = e.get("speaker_role") == "GovernmentMember"
        sch = schede.get(e["speaker_id"], {})
        voce = {
            "chunk_id": eid, "deputy_first_name": e["speaker_first_name"], "deputy_last_name": e["speaker_last_name"],
            "text": cit.get("quote_text") or e["chunk_text"], "quote_text": cit.get("quote_text", ""),
            "full_text": e["chunk_text"], "group": "Governo" if governo else e["party"],
            "coalition": "governo" if governo else gruppi.parte(e["party"]), "date": str(e.get("date") or ""),
            "span_start": e.get("span_start", 0), "span_end": e.get("span_end", 0), "debate": e.get("debate_title", ""),
            "intervention_id": e.get("speech_id", ""), "url": e.get("url") or url_intervento(e.get("speech_id")), "speaker_id": id_sito(e["speaker_id"]),
            "camera_profile_url": sch.get("camera_profile_url"), "photo": sch.get("photo"), "verified": True,
            "chamber": e.get("chamber"),
        }
        if governo and e.get("institutional_role"):
            voce["institutional_role"] = e["institutional_role"]
        posto = posti.get(e["speaker_id"])
        if posto and not governo:
            voce["topic_rank"], voce["topic_pool_size"] = posto["rank"], posto["pool_size"]
        out.append(voce)
    return out


def esperti_finali(citazioni: list[dict], per_id: dict[str, dict], buoni: set[str], punti: dict[str, dict],
                   schede: dict[str, dict], ev: list[dict]) -> list[dict]:
    """Dopo la scrittura, la voce di ogni partito è l'oratore citato più autorevole; i partiti senza citazione escono."""
    migliore: dict[str, dict] = {}
    for cit in citazioni:
        e = per_id.get(cit.get("evidence_id"))
        if not e or cit.get("evidence_id") not in buoni or e.get("speaker_role") == "GovernmentMember" or not e["speaker_id"]:
            continue
        s = punti.get(e["speaker_id"], {}).get("score", 0.0)
        if e["party"] not in migliore or s > punti.get(migliore[e["party"]]["speaker_id"], {}).get("score", 0.0):
            migliore[e["party"]] = e
    out = [esperto(e, punti, schede, sum(1 for x in ev if x.get("speaker_id") == e["speaker_id"])) for e in migliore.values()]
    return sorted(out, key=lambda x: -x["authority_score"])


def statistiche(stat: dict, schede: dict[str, dict]) -> dict:
    """L'evento topic_stats: i numeri dell'introduzione e gli elenchi cliccabili, con gli id nella forma del sito."""
    oratori = []
    for s in stat.get("speakers_detail", []):
        sch = schede.get(s.get("speaker_id"), {})
        oratori.append({**s, "speaker_id": id_sito(s.get("speaker_id")), "camera_profile_url": sch.get("camera_profile_url"),
                        "photo": sch.get("photo"), "profession": sch.get("profession"), "education": sch.get("education"),
                        "committee": sch.get("commissione")})
    interventi = [{**i, "speaker_id": id_sito(i.get("speaker_id")), "photo": schede.get(i.get("speaker_id"), {}).get("photo")}
                  for i in stat.get("interventions_detail", [])]
    fmt = lambda d: d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d or "")  # noqa: E731
    return {"type": "topic_stats", "intervention_count": stat.get("intervention_count", 0),
            "speaker_count": stat.get("speaker_count", 0), "first_date": fmt(stat.get("first_date")),
            "last_date": fmt(stat.get("last_date")), "speakers_detail": oratori, "interventions_detail": interventi,
            "sessions_detail": stat.get("sessions_detail", [])}


# ---------- il flusso ----------

def _in_attesa(f: Future) -> Iterator[str]:
    """Righe di commento finché il lavoro non finisce."""
    while True:
        try:
            f.result(timeout=BATTITO)
            return
        except TimeoutError:
            yield ": in corso\n\n"


def _in_thread(pool: ThreadPoolExecutor, funzione) -> Future:
    return pool.submit(contextvars.copy_context().run, funzione)


def fascicolo(domanda: str, pesi: dict | None, lingua: str, ip: str, misure: dict | None = None) -> Iterator[str]:
    """Lo stream SSE del fascicolo. In `misure` lascia spesa, modello, testo, citazioni, tempi e errore, per il registro."""
    misure = {} if misure is None else misure
    en = lingua == "en"
    loc = "en" if en else "it"
    misure.update(modello="fascicolo", dollari=0.0)
    motivo = agente.controlla_limiti(ip)
    if motivo:
        misure["errore"] = motivo
        yield evento({"type": "error", "code": "rate_limited", "message": motivo})
        return
    if not _posti.acquire(blocking=False):
        yield evento({"type": "waiting", "message": CODA[loc]})
        while not _posti.acquire(timeout=BATTITO):
            yield ": in coda\n\n"
    spesa = [0.0]
    t0 = time.monotonic()
    tempi: dict[str, float] = {}
    token_spesa, token_ip = modello.SPESA.set(spesa), IP.set(ip)
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        yield from _fascicolo(domanda, pesi, lingua, ip, en, misure, pool, tempi)
    except Exception as e:                          # noqa: BLE001
        log.exception("fascicolo non riuscito")
        misure["errore"] = f"{type(e).__name__}: {str(e)[:200]}"
        codice = "quota_exhausted" if isinstance(e, modello.ModelloNonDisponibile) and "tetto" in str(e) else "pipeline_error"
        messaggio = ("la chat ha raggiunto il tetto di spesa di oggi: riprova domani" if codice == "quota_exhausted"
                     else ERRORE[loc])
        yield evento({"type": "error", "code": codice, "message": messaggio})
    finally:
        pool.shutdown(wait=False)
        modello.SPESA.reset(token_spesa)
        IP.reset(token_ip)
        _posti.release()
        misure["dollari"] = spesa[0]
        misure["ms"] = int((time.monotonic() - t0) * 1000)
        misure["tempi"] = tempi
        agente._conta(ip, 1, 0)


def _fascicolo(domanda: str, pesi: dict | None, lingua: str, ip: str, en: bool, misure: dict,
               pool: ThreadPoolExecutor, tempi: dict) -> Iterator[str]:
    from . import recupero
    passo = lambda n, it=None, eng=None: evento({"type": "progress", "step": n, "message": (eng or MESSAGGI[n][1]) if en else (it or MESSAGGI[n][0])})  # noqa: E731
    ambito = recupero.risolvi_ambito(domanda)       # il ramo o l'anno che la domanda nomina
    rami = list(ambito.rami)
    token_rami = RAMI.set(tuple(rami))
    try:
        yield passo(1)
        with connessione() as c:
            t = time.monotonic()
            f = _in_thread(pool, lambda: recupero.recupera(c, domanda, ambito, ip=ip))
            yield from _in_attesa(f)
            ris = f.result()
            tempi["recupero"] = time.monotonic() - t
            pertinenza = (ris.get("metadata") or {}).get("relevance") or {}
            if pertinenza and not pertinenza.get("passa", True):
                # tema fuori dominio (recupero.PARAMETRI, soglia_pertinenza): niente fascicolo, il sito passa alla chat
                log.info("fascicolo fermato: tema fuori dominio (%s brani sopra %s)", pertinenza.get("chunks_above_floor"),
                         pertinenza.get("floor"))
                yield evento({"type": "complete", "metadata": {"evidence": 0, "out_of_domain": True}})
                misure["risposta"] = None
                return
            ev, per_id = evidenze(ris.get("evidenze") or [])
            yield passo(2, f"Trovate {len(ev)} evidenze", f"Found {len(ev)} evidence pieces")
            if not ev:
                yield evento({"type": "complete", "metadata": {"evidence": 0}})
                misure["risposta"] = None
                return

            yield passo(3)
            t = time.monotonic()
            persone = sorted({e["speaker_id"] for e in ev if e["speaker_id"]})
            f = _in_thread(pool, lambda: in_parallelo(
                lambda: autorevolezza(c, domanda, ambito, persone, pesi, ip),
                lambda: giudica_dibattiti(domanda, ev)))
            yield from _in_attesa(f)
            punti = f.result()[0]
            # i posti con le regole della verifica (una connessione sua: la verifica usa più query)
            with connessione() as cv:
                verificati = posti_della_verifica(cv, domanda, rami, persone, ip) if punti and not pesi else None
            tempi["autorevolezza"] = time.monotonic() - t
            for e in ev:
                e["authority_score"] = punti.get(e["speaker_id"], {}).get("score", 0.0)
            posti = verificati if verificati is not None else classifica_per_gruppo(ev, punti, ris.get("perimetro"))
            if punti:                               # senza classifica le voci non si filtrano, come prima
                for e in ev:
                    e["authoritative"] = (e.get("speaker_role") == "GovernmentMember"
                                          or posti.get(e["speaker_id"], {}).get("rank", 99) <= AUTORITA_PRIME)
            schede = _schede(c, persone)
            yield evento({"type": "experts", "data": esperti_iniziali(ev, punti, schede)})

            yield passo(4)
            yield passo(5)
            t = time.monotonic()
            set_group_votes(compute_group_votes(c, ev, tuple(rami)))
            partiti = gruppi.nomi(rami)
            f = _in_thread(pool, lambda: GenerationPipeline().generate(
                query=domanda, evidence_list=ev, query_context=(ris.get("metadata") or {}).get("rewritten_query"),
                parties=partiti, scope=tuple((r, 19) for r in rami)))
            yield from _in_attesa(f)
            gen = f.result()
            tempi["generazione"] = time.monotonic() - t

            stat = gen.get("topic_statistics")
            if stat:
                yield evento(statistiche(stat, schede))
            testo, buoni, tolte = verifica_citazioni(c, gen.get("text", ""), per_id)
            citazioni = gen.get("citations", [])
            tracciate = {x.get("evidence_id") for x in citazioni}
            citazioni += [{"evidence_id": i, "quote_text": per_id[i]["quote_text"]} for i in buoni - tracciate]
            dettagli = dettagli_citazioni(citazioni, per_id, buoni, schede, posti)
            yield evento({"type": "citation_details", "citations": dettagli})
            finali = esperti_finali(citazioni, per_id, buoni, punti, schede, ev)
            if finali:
                yield evento({"type": "experts", "data": finali})
        if en:
            t = time.monotonic()
            f = _in_thread(pool, lambda: traduci(testo, "en"))
            yield from _in_attesa(f)
            testo = f.result()
            tempi["traduzione"] = time.monotonic() - t
        for i in range(0, len(testo), PEZZO):
            yield evento({"type": "chunk", "data": testo[i:i + PEZZO]})
        misure.update(risposta=testo, citazioni=len(dettagli), tolte=tolte,
                      gruppi=sorted({d["group"] for d in dettagli}),
                      integrita=(gen.get("metadata") or {}).get("citation_integrity", {}).get("verbatim"))
        yield evento({"type": "complete", "metadata": {
            "evidence": len(ev), "citations": len(dettagli), "citations_removed": tolte, "chambers": rami,
            "stages": (gen.get("metadata") or {}).get("stages"), "timings_s": {k: round(v, 1) for k, v in tempi.items()},
            **({"authority_weights": pesi} if pesi else {})}})
    finally:
        RAMI.reset(token_rami)


def registra(eventi: Iterator[str], domanda: str, lingua: str, misure: dict) -> Iterator[str]:
    """Passa lo stream così com'è e alla fine scrive la riga nel registro delle chat, anche se il client chiude prima."""
    try:
        yield from eventi
    finally:
        getattr(eventi, "close", lambda: None)()
        conversazioni.salva({"conversazione": None, "turno": None, "lingua": lingua, "domanda": domanda,
                             "risposta": misure.get("risposta"),
                             "strumenti": [{"nome": "fascicolo", "argomenti": {"tempi": {k: round(v, 1) for k, v in (misure.get("tempi") or {}).items()}},
                                            "risultati": misure.get("citazioni")}],
                             "errore": misure.get("errore"), "ms": misure.get("ms", 0),
                             "dollari": round(misure.get("dollari", 0.0), 5), "modello": misure.get("modello")})


def in_un_contesto(eventi: Iterator[str]) -> Iterator[str]:
    """Ogni passo del generatore nello stesso Context. StreamingResponse chiama ogni next() in un thread con una copia
    nuova del contesto: senza questo, le variabili di contesto (rami, IP, spesa) messe al primo passo spariscono ai passi
    dopo, e il loro reset fallisce («created in a different Context»), lasciando occupato il posto del fascicolo."""
    ctx = contextvars.copy_context()
    try:
        while True:
            try:
                e = ctx.run(next, eventi)
            except StopIteration:
                return
            yield e
    finally:
        ctx.run(getattr(eventi, "close", lambda: None))


def stream(domanda: str, pesi: dict | None, lingua: str, ip: str) -> Iterator[str]:
    misure: dict[str, Any] = {}
    return in_un_contesto(registra(fascicolo(domanda, pesi, lingua, ip, misure), domanda, lingua, misure))
