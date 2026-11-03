"""Ordine del giorno dell'Assemblea della Camera: le sedute previste, con gli argomenti, gli orari, gli atti e i
relatori. Serve a rispondere «cosa si discute domani» prima che esista il resoconto.

Ogni notte si leggono gli elenchi del mese corrente e del successivo (i giorni con un ordine del giorno) e si
scaricano gli ordini del giorno da ieri in avanti: possono cambiare fino alla seduta. Lo storico dei mesi passati
si scarica una volta, `massimo_giorni_per_giro` per notte. Chiave nel lago: `leg19-odg-20261103`.
"""

from __future__ import annotations

import datetime as dt
import re
import time

from ..lago import Lago
from .camera_bollettino import _get
from .camera_stenografici_commissioni import mesi

NOME = "camera_odg"
URL = ("https://documenti.camera.it/apps/commonServices/getDocumento.ashx?idLegislatura={leg}&sezione=assemblea&tipoDoc=odg"
       "&idSeduta=&slAnnoMese={mese}&slGiorno={giorno}")


def giorni(pagina: bytes, mese: str) -> list[str]:
    """I giorni del mese che hanno un ordine del giorno (dall'indice in testa alla pagina)."""
    t = pagina.decode("utf-8", errors="replace")
    return [mese + g for g in re.findall(rf"slAnnoMese={mese}&amp;slGiorno=(\d\d)\"", t)]


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa, massimo = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 1.0)), int(cfg.get("massimo_giorni_per_giro", 60))
    lago = Lago(ctx.cartella)
    presenti = set(lago.chiavi(NOME))
    oggi = dt.date.today()
    prossimo = (oggi.replace(day=28) + dt.timedelta(days=5)).strftime("%Y%m")
    tutti = mesi(str(cfg["primo_mese"]), oggi) + [prossimo]
    da_leggere = [m for m in tutti if f"leg{leg}-odg-mese-{m}" not in presenti] + tutti[-2:]
    elenco: list[str] = []
    for m in dict.fromkeys(da_leggere):
        u = URL.format(leg=leg, mese=m, giorno="")
        corpo = _get(u)
        time.sleep(pausa)
        if corpo:
            lago.salva(NOME, f"leg{leg}-odg-mese-{m}", corpo, u, "htm")
    for k in sorted(lago.chiavi(NOME)):
        if "-odg-mese-" in k:
            elenco += giorni(lago.leggi(lago.ultimo(NOME, k)["file"]), k.rsplit("-", 1)[-1])
    ieri = (oggi - dt.timedelta(days=1)).strftime("%Y%m%d")
    futuri = [g for g in elenco if g >= ieri]                                   # cambiano fino alla seduta
    mancanti = [g for g in reversed(elenco) if g < ieri and f"leg{leg}-odg-{g}" not in presenti]
    fatti, fallite = 0, []
    for g in list(dict.fromkeys(futuri + mancanti))[:massimo + len(futuri)]:
        u = URL.format(leg=leg, mese=g[:6], giorno=g[6:])
        try:
            corpo = _get(u)
        except Exception as e:
            fallite.append(f"{g}: {str(e)[:100]}")
            continue
        finally:
            time.sleep(pausa)
        if corpo and b"SEDUTA" in corpo:
            lago.salva(NOME, f"leg{leg}-odg-{g}", corpo, u, "htm")
            fatti += 1
    ctx.log(f"{NOME}: {len(elenco)} giorni con ordine del giorno, {len(futuri)} da ieri in avanti, {fatti} scaricati")
    if fallite:
        raise RuntimeError(f"{len(fallite)} ordini del giorno non scaricati: {fallite[:5]}")
    return {"giorni": len(elenco), "futuri": len(futuri), "scaricati": fatti}
