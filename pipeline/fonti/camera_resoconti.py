"""Resoconti stenografici dell'Assemblea della Camera, in XML, da documenti.camera.it.

Scarica le sedute nuove dopo l'ultima nel lago e riscarica le ultime `ricontrolla` sedute:
il resoconto di una seduta recente può essere ancora provvisorio e cambiare. Se il contenuto
non è cambiato il lago non lo riscrive. Prima riempie i buchi sotto l'ultima seduta (sedute
scaricate a mano fuori ordine): contano nel `massimo_per_giro`.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request

from ..lago import Lago

NOME = "camera_resoconti"
FINE_SERIE = "Documento non disponibile"


def chiave(numero: int, legislatura: int) -> str:
    return f"leg{legislatura}-sed{numero:04d}"


def _scarica(url: str, tentativi: int) -> bytes | None:
    for t in range(1, tentativi + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "parliamentrag-pipeline (www.parliamentrag.it)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                corpo = r.read()
            testo = corpo.decode("utf-8", errors="ignore")
            return None if FINE_SERIE in testo or len(testo.strip()) < 100 else corpo
        except (urllib.error.URLError, TimeoutError):
            if t == tentativi:
                raise
            time.sleep(5 * t)
    return None


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa, tentativi = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 0.5)), int(cfg.get("tentativi", 3))
    ricontrolla, massimo = int(cfg.get("ricontrolla", 3)), int(cfg.get("massimo_per_giro", 5000))
    lago = Lago(ctx.cartella)
    prefisso = f"leg{leg}-sed"
    presenti = [int(k[len(prefisso):]) for k in lago.chiavi(NOME) if k.startswith(prefisso)]
    ultimo = max(presenti, default=0)
    nuovi = cambiati = invariati = 0
    buchi = sorted(set(range(1, ultimo - ricontrolla + 1)) - set(presenti))[:massimo]
    for numero in buchi:
        url = cfg["url"].format(num=numero, legislatura=leg)
        corpo = _scarica(url, tentativi)
        if corpo is not None:
            lago.salva(NOME, chiave(numero, leg), corpo, url, "xml")
            nuovi += 1
        time.sleep(pausa)
    massimo -= len(buchi)
    numero = max(1, ultimo - ricontrolla + 1)
    while numero - ultimo <= massimo:
        url = cfg["url"].format(num=numero, legislatura=leg)
        corpo = _scarica(url, tentativi)
        if corpo is None:
            if numero > ultimo:
                break  # fine della serie: la seduta dopo l'ultima pubblicata non c'è ancora
            numero += 1
            continue
        esito = lago.salva(NOME, chiave(numero, leg), corpo, url, "xml")
        if not esito["nuovo"]:
            invariati += 1
        elif numero > ultimo:
            nuovi += 1
        else:
            cambiati += 1
        numero += 1
        time.sleep(pausa)
    ctx.log(f"{NOME}: {nuovi} nuove, {cambiati} cambiate, {invariati} invariate, {len(buchi)} buchi provati (ultima seduta {numero - 1})")
    return {"nuove": nuovi, "cambiate": cambiati, "invariate": invariati, "buchi": len(buchi), "ultima": numero - 1}
