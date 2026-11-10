"""Convocazioni delle commissioni permanenti del Senato: la pagina di ogni commissione dà la settimana in corso, giorno
per giorno, con l'ora, la sede (plenaria, ufficio di presidenza, sottocommissione), il numero della seduta, l'aula, gli
argomenti con i disegni di legge, gli auditi e le sedute sconvocate.

senato.it sta dietro il WAF: le pagine si aprono con il browser senza interfaccia, una per commissione (dieci per notte,
contate nel tetto comune). Chiave nel lago: `leg19-senato-conv-05`; le settimane precedenti restano come versioni.
"""

from __future__ import annotations

from ..lago import Lago
from . import senato_browser

NOME = "senato_convocazioni"
PAGINA = "https://www.senato.it/commissioni-e-giunte/commissioni-permanenti/{n}a-commissione-permanente/convocazioni"
COMMISSIONI = range(1, 11)                        # le dieci commissioni permanenti dalla riforma del 2022


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    lago, lette, nuove = Lago(ctx.cartella), 0, 0
    try:
        with senato_browser.Sessione(pausa=float(cfg.get("pausa_secondi", 4)), massimo=int(cfg.get("massimo_richieste", 12)), ctx=ctx) as sessione:
            for n in COMMISSIONI:
                u = PAGINA.format(n=n)
                try:
                    corpo = sessione.scarica(u)
                except senato_browser.NonTrovato:
                    continue
                if b"commission-meetings" not in corpo:
                    ctx.log(f"{NOME}: pagina della {n}ª commissione senza il blocco delle convocazioni, saltata")
                    continue
                lette += 1
                nuove += bool(lago.salva(NOME, f"leg{leg}-senato-conv-{n:02d}", corpo, u, "htm").get("nuovo"))
    except senato_browser.Bloccato as e:
        ctx.log(f"{NOME}: senato.it non risponde dopo {lette} commissioni, restano le convocazioni di prima ({str(e)[:120]})")
        if not lette:
            return {"commissioni": 0, "bloccato": True}
    ctx.log(f"{NOME}: {lette} commissioni, {nuove} nuove o cambiate")
    return {"commissioni": lette, "nuove": nuove}
