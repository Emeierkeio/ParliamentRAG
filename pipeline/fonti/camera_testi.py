"""Testi stampati dei progetti di legge della Camera, versione per versione (presentato, testo della commissione,
trasmesso dal Senato…), in HTML. Gli indirizzi delle versioni vengono dagli atti (camera_atti, query «versioni»).

Un testo stampato non cambia: ogni versione si scarica una volta, `massimo_per_giro` per notte, dalle più recenti.
Chiave nel lago: `leg19-testo-<codice>` (per esempio `leg19-testo-leg.19.pdl.camera.3148.19PDL0218420`).
"""

from __future__ import annotations

import json
import re
import time

from ..lago import Lago
from .camera_bollettino import _get
from .camera_ocd import chiave as chiave_query

NOME = "camera_testi"


def versioni(lago: Lago, leg: int) -> list[dict]:
    v = lago.ultimo("camera_atti", chiave_query("versioni", leg))
    if not v:
        raise RuntimeError("mancano le versioni degli atti nel lago: il passo scarica_camera_atti deve girare prima")
    out = {}
    for r in json.loads(lago.leggi(v["file"])):
        m = re.search(r"codice=([\w.]+)", r.get("url") or "")
        if m:
            out[m.group(1)] = {"codice": m.group(1), "url": r["url"].replace("http://", "https://"), "versione": r["versione"],
                               "atto": r["atto"], "data": r.get("data") or ""}
    return sorted(out.values(), key=lambda x: (x["data"], x["codice"]), reverse=True)


ASSENTE = b"Documento non disponibile"


def segnaposto(lago: Lago) -> set[str]:
    """Chiavi la cui ultima versione nel lago è la pagina «Documento non disponibile» (circa 5 kB): vanno richieste di nuovo."""
    piccoli = lago.db.execute("SELECT chiave, file FROM grezzi g WHERE fonte = ? AND byte < 6000 AND scaricato = "
                              "(SELECT max(scaricato) FROM grezzi WHERE fonte = g.fonte AND chiave = g.chiave)", (NOME,))
    return {k for k, rel in piccoli if ASSENTE in lago.leggi(rel) and b'id="DC"' not in lago.leggi(rel)}


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa, massimo = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 1.0)), int(cfg.get("massimo_per_giro", 500))
    lago = Lago(ctx.cartella)
    presenti = set(lago.chiavi(NOME)) - segnaposto(lago)
    mancano = [v for v in versioni(lago, leg) if f"leg{leg}-testo-{v['codice']}" not in presenti]
    fatti, assenti, fallite = 0, 0, []
    for v in mancano[:massimo]:
        try:
            corpo = _get(v["url"])
        except Exception as e:
            fallite.append(f"{v['codice']}: {str(e)[:80]}")
            continue
        finally:
            time.sleep(pausa)
        # dal 2026 il vecchio indirizzo rimanda al visualizzatore di www.camera.it. Gli stampati con gli articoli hanno
        # «DC»; quelli senza articoli (relazione orale, proposta popolare non presentata) solo frontespizio e pareri:
        # si salvano anche quelli, altrimenti si richiederebbero ogni notte. Una pagina senza nessuno dei due è un errore.
        if corpo and ASSENTE in corpo and b'id="DC"' not in corpo:
            assenti += 1                                   # versione annunciata ma non ancora pubblicata: si richiede al giro dopo
        elif corpo and (b'id="DC"' in corpo or b'id="docviewer_full_content"' in corpo):
            lago.salva(NOME, f"leg{leg}-testo-{v['codice']}", corpo, v["url"], "htm")
            fatti += 1
        else:
            fallite.append(f"{v['codice']}: pagina senza testo")
    rimandati = max(0, len(mancano) - massimo)
    ctx.log(f"{NOME}: {fatti} testi scaricati, {assenti} non ancora pubblicati, {rimandati} rimandati")
    if fallite:
        raise RuntimeError(f"{len(fallite)} testi non scaricati, si riprendono al giro dopo: {fallite[:5]}")
    return {"scaricati": fatti, "non_pubblicati": assenti, "rimandati": rimandati}
