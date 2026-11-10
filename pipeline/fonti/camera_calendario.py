"""Calendario dei lavori dell'Assemblea della Camera: cosa è previsto in Aula, giorno per giorno, per il mese in corso
(e l'inizio del successivo). Serve a rispondere «domani c'è Aula?», «quando si vota il decreto…» prima che esca
l'ordine del giorno, che arriva solo per la seduta successiva.

Ogni notte due richieste: la pagina del calendario, per sapere qual è quello vigente (cambia a ogni aggiornamento
della Conferenza dei capigruppo), e il calendario stesso. Chiave nel lago: `leg19-calendario-vigente`; le versioni
precedenti restano nel lago.
"""

from __future__ import annotations

import re
import time

from ..lago import Lago
from .camera_bollettino import _get

NOME = "camera_calendario"
PAGINA = "https://www.camera.it/leg{leg}/76?active_tab_3806=4184"
FILE = "https://www.camera.it/leg{leg}/proxy{leg}/calendari_assemblea?file={file}"


def vigente(pagina: bytes) -> str | None:
    """Il calendario scelto nella pagina (il primo dell'elenco, il più recente): `lavori.vigente.20261109`."""
    t = pagina.decode("utf-8", errors="replace")
    m = re.search(r'<option selected="selected" value="([\w.]+)"', t) or re.search(r'<option value="(lavori\.vigente\.\d{8})"', t)
    return m.group(1) if m else None


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 2.0))
    pagina = _get(PAGINA.format(leg=leg))
    file = vigente(pagina) if pagina else None
    if not file:
        raise RuntimeError("pagina del calendario dei lavori senza il calendario vigente")
    time.sleep(pausa)
    u = FILE.format(leg=leg, file=file)
    corpo = _get(u)
    if not corpo or b"calendario_punti" not in corpo:
        raise RuntimeError(f"calendario {file} vuoto o senza la tabella dei giorni")
    r = Lago(ctx.cartella).salva(NOME, f"leg{leg}-calendario-vigente", corpo, u, "htm")
    ctx.log(f"{NOME}: {file}, {'nuovo' if r.get('nuovo') else 'invariato'}")
    return {"calendario": file, "nuovo": bool(r.get("nuovo"))}
