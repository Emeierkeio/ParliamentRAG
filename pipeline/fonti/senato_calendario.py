"""Calendario dei lavori dell'Assemblea del Senato: cosa è previsto in Aula, settimana per settimana, e le settimane
riservate alle commissioni. Come camera_calendario, serve a rispondere «domani c'è Aula?» prima che esista una seduta.

Una richiesta per notte, con il browser senza interfaccia (senato.it sta dietro il WAF, vedi senato_browser).
Chiave nel lago: `leg19-senato-calendario`; le versioni precedenti restano nel lago.
"""

from __future__ import annotations

from ..lago import Lago
from . import senato_browser

NOME = "senato_calendario"
PAGINA = "https://www.senato.it/lavori/assemblea/calendario-dei-lavori"


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    try:
        with senato_browser.Sessione(pausa=float(cfg.get("pausa_secondi", 3)), massimo=int(cfg.get("massimo_richieste", 3)), ctx=ctx) as sessione:
            corpo = sessione.scarica(PAGINA)
    except senato_browser.Bloccato as e:
        ctx.log(f"{NOME}: senato.it non risponde, resta il calendario di prima ({str(e)[:120]})")
        return {"nuovo": False, "bloccato": True}
    if b"<h3" not in corpo or "Calendario dei lavori".encode() not in corpo:
        raise RuntimeError("pagina del calendario del Senato senza le settimane")
    r = Lago(ctx.cartella).salva(NOME, f"leg{leg}-senato-calendario", corpo, PAGINA, "htm")
    ctx.log(f"{NOME}: {'nuovo' if r.get('nuovo') else 'invariato'}")
    return {"nuovo": bool(r.get("nuovo"))}
