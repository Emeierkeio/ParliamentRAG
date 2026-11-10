"""Il sito di www.parliamentrag.it: le rotte /api e /dati che chiamano le pagine in `sito/` (servite da main.py). Tutto
viene da questo servizio e dal Postgres v3, nessun altro sistema dietro. Conversazioni condivise e traduzioni si
scrivono nello schema `sito` (schema/sito.sql) con l'utente `sito`; senza SITO_PG_PASSWORD la condivisione non c'è e le
traduzioni non restano in cache."""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Iterator
from typing import Literal

import psycopg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from pipeline.ambiente import env

from . import agente, allegati, conversazioni, pubblico, statistiche
from .db import connessione, connessione_sito as _db_sito
from .pulisci import pulisci
from .rete import ip

log = logging.getLogger("parliamentrag.sito")
router = APIRouter(include_in_schema=False)


# ---------- chat ----------

class Domanda(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=16)
    locale: Literal["it", "en"] = "it"
    conversation: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,64}$")   # id casuale del browser, per il registro
    turn: int | None = Field(default=None, ge=1, le=1000)
    # una bozza allegata (file .docx o .pdf già letto da /api/allegato, o testo lungo incollato): vale 3 domande
    attachment: str | None = Field(default=None, max_length=allegati.CARATTERI_MAX)
    attachment_name: str | None = Field(default=None, max_length=200)


def risposta_ndjson(indirizzo: str, d: Domanda) -> StreamingResponse:
    """La risposta dell'agente in NDJSON, un evento per riga, dopo i limiti per IP e di spesa. La usa anche /v1/chat."""
    motivo = agente.controlla_limiti(indirizzo, allegati.DOMANDE if d.attachment else 1)
    if motivo:
        raise HTTPException(429, motivo)
    misure: dict = {}
    # nel registro la bozza resta, senza IP come ogni domanda (decisione del 10/11/2026)
    registrata = d.prompt + (f"\n\n[allegato: {d.attachment_name or 'testo incollato'}, {len(d.attachment)} caratteri]\n{d.attachment}" if d.attachment else "")
    eventi = conversazioni.registra(agente.rispondi(d.prompt, d.history, d.locale, indirizzo, misure, allegato=d.attachment,
                                                    nome_allegato=d.attachment_name), registrata, d.locale, d.conversation, d.turn, misure)
    righe = (json.dumps(e, ensure_ascii=False, default=str) + "\n" for e in eventi)
    return StreamingResponse(righe, media_type="application/x-ndjson")


class Allegato(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    data: str = Field(min_length=10, max_length=7_000_000)        # base64 di un file fino a 5 MB


@router.post("/api/allegato")
def allegato(d: Allegato) -> dict:
    """Il testo di un file .docx o .pdf allegato alla chat. Il file non si conserva."""
    try:
        testo = allegati.testo_da_file(d.name, d.data)
    except allegati.AllegatoNonLeggibile as e:
        raise HTTPException(422, str(e)) from e
    pezzi = allegati.dividi(testo)
    return {"text": testo, "amendments": min(len(pezzi), allegati.EMENDAMENTI_MAX), "more": max(0, len(pezzi) - allegati.EMENDAMENTI_MAX),
            "truncated": len(testo) >= allegati.CARATTERI_MAX}


@router.get("/api/uso")
def uso(req: Request) -> dict:
    return agente.uso(ip(req))


@router.post("/api/agente")
@router.post("/api/chat")
def chat(req: Request, d: Domanda):
    """Le due rotte della chat del sito vanno allo stesso agente."""
    statistiche.registra(req, "domanda")
    return risposta_ndjson(ip(req), d)


class Fascicolo(BaseModel):
    """Il corpo della vecchia /api/query: la domanda e, se il lettore li ha cambiati, i pesi dell'autorevolezza."""
    query: str = Field(min_length=3, max_length=1000)
    authority_weights: dict[str, float] | None = None
    top_k: int | None = Field(default=None, ge=10, le=500)      # accettati per compatibilità, non usati
    date_start: str | None = None
    date_end: str | None = None
    stream: bool = True
    task_id: str | None = None


@router.post("/api/fascicolo")
def fascicolo(req: Request, d: Fascicolo):
    """Il fascicolo di una domanda di tema in SSE (api/fascicolo/servizio.py). Conta come una domanda della chat."""
    from .fascicolo import servizio
    statistiche.registra(req, "fascicolo")
    lingua = "en" if req.headers.get("accept-language", "it").strip()[:2].lower() == "en" else "it"
    pesi = {k: float(v) for k, v in d.authority_weights.items()} if d.authority_weights else None
    return StreamingResponse(servizio.stream(d.query, pesi, lingua, ip(req)), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class Classifica(BaseModel):
    """Il corpo della vecchia /api/authority-ranking."""
    topic: str = Field(min_length=2, max_length=500)
    chamber: Literal["camera", "senato"] = "camera"


@router.post("/api/autorevolezza")
def autorevolezza(req: Request, d: Classifica):
    """Tutti i deputati (o i senatori) per autorevolezza sul tema, nella forma della vecchia /api/authority-ranking."""
    from .fascicolo import autorevolezza as aut, modello
    try:
        with connessione() as c:
            return aut.classifica(c, d.topic, d.chamber, ip=ip(req))
    except modello.ModelloNonDisponibile as e:
        return JSONResponse({"errore": f"la classifica di autorevolezza non è disponibile: {e}"}, status_code=503)


# ---------- strumenti e verifica ----------

@router.post("/api/mcp/{nome}")
async def strumento(nome: str, req: Request):
    """Gli strumenti pubblici nella forma che il sito si aspetta: {dati} se riesce, {errore, testi} se no."""
    if nome not in pubblico.PER_NOME and nome != "verify_answer":
        raise HTTPException(404, "strumento non disponibile")
    try:
        argomenti = json.loads(await req.body() or b"{}")
    except ValueError:
        raise HTTPException(400, "formato non valido")
    return await run_in_threadpool(_esegui, nome, argomenti)


def _esegui(nome: str, argomenti: dict) -> dict:
    try:
        with connessione() as c:
            if nome == "verify_answer":
                return {"dati": pubblico.verify_answer(c, pubblico.VerifyAnswer.model_validate(argomenti)), "testi": [], "immagini": 0}
            return {"dati": pubblico.esegui(c, nome, argomenti), "testi": [], "immagini": 0}
    except ValidationError as e:
        return {"testi": [f"argomenti non validi: {e.errors()[0].get('msg', '')}"], "immagini": 0, "errore": True}
    except pubblico.NonTrovato as e:
        return {"testi": [str(e)], "immagini": 0, "errore": True}


class Verifica(BaseModel):
    answer: str = Field(max_length=60000)
    question: str | None = Field(default=None, max_length=2000)


@router.post("/api/verifica")
def verifica(v: Verifica) -> dict:
    """Le tre garanzie sulla risposta della chat, nella forma che disegna il sito."""
    with connessione() as c:
        r = pubblico.verify_answer(c, pubblico.VerifyAnswer(answer=v.answer[:20000], question=v.question))
    citazioni = [{"quote": x["quote"], "status": x["status"], "closest_passage": None, "url": x.get("record_url")}
                 for x in r["quotes"]]
    return {"dati": {"outcome": r["outcome"], "groups": r["groups"], "quotes": citazioni, "authority": r["authority"],
                     "scope": r["scope"]}}


# ---------- traduzioni ----------

TRADUZIONE = ("Translate each Italian parliamentary text of the JSON array into English. Preserve proper nouns (names, "
              "parties, dates, session and act numbers). Return ONLY a JSON array of the translations, same order and length.")
NUOVE_ORA = 400                                      # testi da tradurre col modello per IP in un'ora: il resto è cache
_tradotte: dict[str, list[float]] = defaultdict(list)


class DaTradurre(BaseModel):
    testi: list[str] = Field(default_factory=list, max_length=40)


def _traduci_col_modello(indirizzo: str, testi: list[str]) -> list[str] | None:
    try:
        chiave = env("OPENAI_API_KEY")
    except KeyError:
        return None
    modello = env("TRADUZIONI_MODELLO", "gpt-5.6-luna")
    corpo = json.dumps({"model": modello, "instructions": TRADUZIONE, "input": json.dumps(testi, ensure_ascii=False),
                        "reasoning": {"effort": "low"}, "store": False}).encode()
    req = urllib.request.Request(agente.OPENAI, corpo, {"Content-Type": "application/json", "Authorization": f"Bearer {chiave}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            risposta = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    agente._conta(indirizzo, 0, agente._costo(modello, risposta.get("usage") or {}))
    testo = "".join(p.get("text", "") for x in risposta.get("output") or [] if x.get("type") == "message"
                    for p in x.get("content") or [] if p.get("type") == "output_text")
    try:
        tradotti = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", testo.strip()))
    except ValueError:
        return None
    return [str(t) for t in tradotti] if isinstance(tradotti, list) and len(tradotti) == len(testi) else None


@router.post("/api/traduci")
def traduci(req: Request, d: DaTradurre) -> dict:
    """Titoli e descrizioni ufficiali in inglese, per la versione inglese del sito. Se il modello non risponde, l'originale."""
    testi = [str(t)[:1500] for t in d.testi]
    memo: dict[str, str] = {}
    with _db_sito() as c:
        if c:
            memo = {r["testo"]: r["tradotto"] for r in c.execute(
                "SELECT testo, tradotto FROM sito.traduzione WHERE lingua = 'en' AND testo = ANY(%s)", (testi,))}
        nuovi = list(dict.fromkeys(t for t in testi if t and t not in memo))
        indirizzo, ora = ip(req), time.time()
        _tradotte[indirizzo] = [x for x in _tradotte[indirizzo] if ora - x < 3600]
        if nuovi and agente.controlla_spesa() and len(_tradotte[indirizzo]) + len(nuovi) <= NUOVE_ORA:
            _tradotte[indirizzo] += [ora] * len(nuovi)
            tradotti = _traduci_col_modello(indirizzo, nuovi)
            if tradotti:
                memo.update(zip(nuovi, tradotti))
                if c:
                    c.cursor().executemany("INSERT INTO sito.traduzione (testo, lingua, tradotto) VALUES (%s, 'en', %s) "
                                           "ON CONFLICT DO NOTHING", list(zip(nuovi, tradotti)))
    return {"tradotti": [memo.get(t, t) for t in testi]}


# ---------- conversazioni condivise ----------

class Turno(BaseModel):
    q: str = ""
    html: str = ""


class Condivisa(BaseModel):
    titolo: str = ""
    lingua: str = "it"
    turni: list[Turno] = Field(default_factory=list)


@router.post("/api/condividi")
async def condividi(req: Request):
    """Istantanea di una conversazione con un identificativo casuale non indovinabile."""
    corpo = await req.body()
    if len(corpo) > 3_000_000:
        raise HTTPException(413, "conversazione troppo grande")
    try:
        d = Condivisa.model_validate_json(corpo or b"{}")
    except ValidationError:
        raise HTTPException(400, "formato non valido")
    ident = secrets.token_urlsafe(12)
    dati = {"titolo": d.titolo[:200], "lingua": "en" if d.lingua == "en" else "it", "creata": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "turni": [{"q": t.q[:1000], "html": pulisci(t.html)} for t in d.turni[:30]]}
    with _db_sito() as c:
        if c is None:
            return JSONResponse({"errore": "condivisione non disponibile"}, status_code=503)
        c.execute("INSERT INTO sito.condivisa (id, conversazione) VALUES (%s, %s)", (ident, json.dumps(dati, ensure_ascii=False)))
    return {"id": ident}


@router.get("/dati/condivisi/{ident}.json")
def condivisa(ident: str):
    if not re.fullmatch(r"[\w-]{8,40}", ident):
        raise HTTPException(404, "conversazione non trovata")
    with _db_sito() as c:
        r = c.execute("SELECT conversazione FROM sito.condivisa WHERE id = %s", (ident,)).fetchone() if c else None
    if not r:
        return JSONResponse({"errore": "conversazione non trovata"}, status_code=404)
    x = r["conversazione"]                              # ripulite anche in lettura: valgono pure per quelle di prima
    return {**x, "turni": [{**t, "html": pulisci(t.get("html") or "")} for t in x.get("turni") or []]}


# ---------- segnalazioni ----------

SEGNALAZIONI_ORA = 5
_segnalazioni: dict[str, list[float]] = defaultdict(list)    # orari dell'ultima ora per IP, solo in memoria


class Segnalazione(BaseModel):
    tipo: str = Field(min_length=1, max_length=80)
    testo: str = ""
    domanda: str = ""
    risposta: str = ""
    link: str = ""
    lingua: str = ""


def _esc(x: str) -> str:
    return x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")


@router.post("/api/segnala")
def segnala(req: Request, s: Segnalazione):
    """Un errore in una risposta arriva per email a segnalazioni@parliamentrag.it, via Brevo. Chi segnala non lascia
    indirizzo; la chiave non si stampa mai."""
    indirizzo, ora = ip(req), time.time()
    _segnalazioni[indirizzo] = [t for t in _segnalazioni[indirizzo] if ora - t < 3600]
    if len(_segnalazioni[indirizzo]) >= SEGNALAZIONI_ORA:
        return JSONResponse({"errore": "troppe segnalazioni in un'ora, riprova più tardi"}, status_code=429)
    chiave = env("BREVO_API_KEY", "")
    if not chiave:
        return JSONResponse({"errore": "invio non configurato"}, status_code=503)
    testo, domanda, risposta = s.testo[:3000], s.domanda[:600], s.risposta[:6000]
    link = s.link[:300] if re.fullmatch(r"https?://[\w.:-]+/#/c/[\w-]+", s.link[:300]) else ""
    riga_link = f"<p><b>Conversazione:</b> <a href='{link}'>{_esc(link)}</a></p>" if link else ""
    html = (f"<p><b>Tipo:</b> {_esc(s.tipo)}</p><p><b>Commento:</b><br>{_esc(testo) or '—'}</p>{riga_link}"
            f"<p><b>Domanda:</b><br>{_esc(domanda)}</p><p><b>Risposta:</b><br>{_esc(risposta)}</p>"
            f"<p style='color:#777'>Lingua {_esc(s.lingua[:5])} · {time.strftime('%d/%m/%Y %H:%M')}</p>")
    corpo = {"sender": {"name": "ParliamentRAG", "email": "news@parliamentrag.it"}, "to": [{"email": "segnalazioni@parliamentrag.it"}],
             "subject": f"Segnalazione: {s.tipo} · {domanda[:70]}", "htmlContent": html}
    try:
        r = urllib.request.Request("https://api.brevo.com/v3/smtp/email", json.dumps(corpo).encode(),
                                   {"api-key": chiave, "Content-Type": "application/json", "accept": "application/json"})
        with urllib.request.urlopen(r, timeout=20) as risposta_brevo:
            risposta_brevo.read()
    except urllib.error.HTTPError as e:
        return JSONResponse({"errore": f"invio non riuscito ({e.code})"}, status_code=502)
    except (urllib.error.URLError, TimeoutError):
        return JSONResponse({"errore": "invio non riuscito"}, status_code=502)
    _segnalazioni[indirizzo].append(ora)
    return {"ok": True}
