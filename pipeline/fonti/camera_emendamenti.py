"""Emendamenti ai progetti di legge della Camera: un XML per progetto di legge, con tutte le proposte emendative
presentate in commissione e in Aula (numero, articolo, testo, firmatari con l'id del deputato, stato ed esito).

Non c'è un indice dei file: i candidati sono i progetti di legge dell'anagrafica degli atti (camera_atti). Ogni notte:
- i file già nel lago si richiedono con If-Modified-Since: se non sono cambiati il server risponde 304, senza contenuto;
- i progetti senza file si riprovano solo se il loro iter è andato avanti dall'ultimo tentativo (un progetto appena
  assegnato non ha emendamenti; uno in esame in commissione sì).
Chiavi nel lago: `leg19-eme-ac3131`, e `leg19-eme-assenti` (JSON: progetto -> stato dell'iter all'ultimo 404).
"""

from __future__ import annotations

import email.utils
import json
import time
import urllib.error
import urllib.request

from ..lago import Lago
from .camera_bollettino import UA
from .camera_ocd import chiave as chiave_query

NOME = "camera_emendamenti"
URL = "https://documenti.camera.it/leg{leg}/emendamenti/xml/leg.{leg}.eme.ac.{numero}.xml"


def _get_se_cambiato(url: str, dal: float | None, tentativi: int = 3) -> tuple[int, bytes | None]:
    """(200, corpo) se c'è ed è cambiato; (304, None) se non è cambiato dal momento dato; (404, None) se non esiste."""
    h = {"User-Agent": UA}
    if dal:
        h["If-Modified-Since"] = email.utils.formatdate(dal, usegmt=True)
    for t in range(1, tentativi + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
                return 200, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (304, 404):
                return e.code, None
            if t == tentativi:
                raise
        except (urllib.error.URLError, TimeoutError):
            if t == tentativi:
                raise
        time.sleep(10 * t)
    return 0, None


def stati_iter(lago: Lago, leg: int) -> dict[str, str]:
    """Numero del progetto di legge -> ultimo passo dell'iter, dai dati di camera_atti nel lago."""
    atti = lago.ultimo("camera_atti", chiave_query("atti", leg))
    iter_ = lago.ultimo("camera_atti", chiave_query("iter", leg))
    if not atti or not iter_:
        raise RuntimeError("mancano gli atti nel lago: il passo scarica_camera_atti deve girare prima")
    numero = {r["atto"]: r["numero"] for r in json.loads(lago.leggi(atti["file"]))}
    ultimo: dict[str, tuple] = {}
    for r in json.loads(lago.leggi(iter_["file"])):
        n = numero.get(r["atto"])
        if n and (r.get("data") or "", r["stato"]) >= ultimo.get(n, ("", "")):
            ultimo[n] = (r.get("data") or "", r["stato"], r["titolo"])
    return {n: v[2] for n, v in ultimo.items()} | {n: "" for n in numero.values() if n not in ultimo}


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa, massimo = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 0.5)), int(cfg.get("massimo_per_giro", 4000))
    lago = Lago(ctx.cartella)
    stati = stati_iter(lago, leg)
    k_assenti = f"leg{leg}-eme-assenti"
    a = lago.ultimo(NOME, k_assenti)
    assenti = json.loads(lago.leggi(a["file"])) if a else {}
    presenti = {k: lago.ultimo(NOME, k) for k in lago.chiavi(NOME) if k.startswith(f"leg{leg}-eme-ac")}
    candidati = [n for n in sorted(stati, key=lambda x: int("".join(c for c in x if c.isdigit()) or 0), reverse=True)
                 if f"leg{leg}-eme-ac{n}" in presenti or assenti.get(n) != stati[n]]
    nuovi = cambiati = invariati = senza = 0
    fallite = []
    for n in candidati[:massimo]:
        k = f"leg{leg}-eme-ac{n}"
        u = URL.format(leg=leg, numero=n)
        try:
            codice, corpo = _get_se_cambiato(u, presenti[k]["scaricato"] if k in presenti else None)
        except Exception as e:
            fallite.append(f"{n}: {str(e)[:80]}")
            continue
        finally:
            time.sleep(pausa)
        if codice == 404:
            assenti[n] = stati[n]
            senza += 1
        elif codice == 304:
            invariati += 1
        elif corpo:
            esito = lago.salva(NOME, k, corpo, u, "xml")
            assenti.pop(n, None)
            nuovi += esito["nuovo"] and k not in presenti
            cambiati += esito["nuovo"] and k in presenti
    lago.salva(NOME, k_assenti, json.dumps(assenti, sort_keys=True).encode(), "", "json")
    ctx.log(f"{NOME}: {len(candidati)} progetti da controllare; {nuovi} file nuovi, {cambiati} cambiati, {invariati} invariati, {senza} senza emendamenti")
    if fallite:
        raise RuntimeError(f"{len(fallite)} file non scaricati, si riprendono al giro dopo: {fallite[:5]}")
    return {"controllati": min(len(candidati), massimo), "nuovi": nuovi, "cambiati": cambiati, "invariati": invariati, "senza": senza}
