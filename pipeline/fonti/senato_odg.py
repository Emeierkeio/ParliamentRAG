"""Ordine del giorno dell'Assemblea del Senato: la prossima seduta prevista, con il numero, l'ora, gli argomenti, i
disegni di legge e i relatori. Come camera_odg, serve a dire «cosa si discute domani» prima del resoconto.

Una pagina per notte, con il browser senza interfaccia (senato.it sta dietro il WAF), contata nel tetto comune.
Chiave nel lago: `leg19-senato-odg`; gli ordini del giorno precedenti restano come versioni.
"""

from __future__ import annotations

from ..lago import Lago
from . import senato_browser

NOME = "senato_odg"
PAGINA = "https://www.senato.it/lavori/assemblea/ordine-del-giorno"


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    try:
        with senato_browser.Sessione(pausa=float(cfg.get("pausa_secondi", 3)), massimo=int(cfg.get("massimo_richieste", 3)), ctx=ctx) as sessione:
            corpo = sessione.scarica(PAGINA)
    except senato_browser.Bloccato as e:
        ctx.log(f"{NOME}: senato.it non risponde, resta l'ordine del giorno di prima ({str(e)[:120]})")
        return {"nuovo": False, "bloccato": True}
    if b"showdoc-hotodg" not in corpo:
        raise RuntimeError("pagina dell'ordine del giorno del Senato senza il testo dell'ordine del giorno")
    r = Lago(ctx.cartella).salva(NOME, f"leg{leg}-senato-odg", corpo, PAGINA, "htm")
    ctx.log(f"{NOME}: {'nuovo' if r.get('nuovo') else 'invariato'}")
    return {"nuovo": bool(r.get("nuovo"))}
