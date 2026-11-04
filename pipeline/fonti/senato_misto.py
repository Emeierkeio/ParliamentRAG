"""Composizione storica del Gruppo Misto del Senato, con le componenti partitiche (Alleanza Verdi e Sinistra, Azione,
Avanti PSI). dati.senato.it non le pubblica: stanno solo in una pagina di senato.it, dietro il WAF che chiede di eseguire
JavaScript: si apre con il browser senza interfaccia (senato_browser), una richiesta per giro. Se senato.it non la
serve, vale l'ultima nel lago; solo se il lago non ne ha nessuna, la pagina salvata a mano in `file_import`
(«Salva pagina», solo HTML), che col tempo invecchia.
Chiave nel lago: `leg19-senato-misto`.
"""

from __future__ import annotations

from ..ambiente import percorso
from ..lago import Lago
from . import senato_browser

NOME = "senato_misto"
# did = il Gruppo Misto della legislatura su senato.it
PAGINA = "https://www.senato.it/composizione/gruppi-parlamentari/riepilogo-della-composizione/composizione?did={did}&tipo=storica"


def chiave(leg: int) -> str:
    return f"leg{leg}-senato-misto"


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    url = PAGINA.format(did=cfg["did"])
    lago = Lago(ctx.cartella)
    try:
        with senato_browser.Sessione(pausa=1, massimo=2, ctx=ctx) as s:
            corpo = s.scarica(url)
    except (senato_browser.Bloccato, senato_browser.NonTrovato) as e:
        f = percorso(cfg["file_import"]) if cfg.get("file_import") else None
        if lago.ultimo(NOME, chiave(leg)) or not (f and f.is_file()):
            ctx.log(f"{NOME}: {e}; le componenti restano quelle dell'ultima pagina nel lago")
            return {"importati": 0, "motivo": str(e)[:200]}
        corpo = f.read_bytes()
    if b"Componenti partitiche" not in corpo:
        raise RuntimeError("la pagina non è la composizione storica del Gruppo Misto (manca «Componenti partitiche»)")
    r = lago.salva(NOME, chiave(leg), corpo, url, "html")
    return {"importati": int(r.get("nuovo", False))}
