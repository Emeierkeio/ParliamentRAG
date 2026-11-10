"""Convocazioni delle commissioni permanenti della Camera: per ogni commissione e giorno, a che ora si riunisce, in quale
sede (referente, consultiva, atti del Governo, audizioni…) e su che cosa, con gli atti e gli auditi. Serve a rispondere
«cosa c'è domani in commissione» prima che esista il Bollettino.

La pagina di una commissione mostra un giorno alla volta (il primo con una convocazione) e l'elenco dei giorni del mese
che ne hanno una. Ogni notte, per ogni commissione: la pagina, poi i giorni da oggi in poi; dal 20 del mese anche il
mese dopo. Circa 60 richieste. Chiave nel lago: `leg19-conv-3505-20261110`; i giorni passati restano come sono.
"""

from __future__ import annotations

import datetime as dt
import re
import time

from ..lago import Lago
from .camera_bollettino import _get

NOME = "camera_convocazioni"
PAGINA = "https://www.camera.it/leg{leg}/1099?shadow_organo_parlamentare={organo}"
GIORNO = PAGINA + "&slAnnoMese={mese}&slGiorno={giorno:02d}&primaConvUtile=ok"
MESE = PAGINA + "&slAnnoMese={mese}"
ORGANI = range(3501, 3515)                        # le quattordici commissioni permanenti della XIX (o19_3501 … o19_3514)
MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
                                     "ottobre", "novembre", "dicembre"], 1)}


def giorni(pagina: bytes) -> list[dt.date]:
    """I giorni con una convocazione elencati nella pagina (i link «giorno» del mese scelto)."""
    t = pagina.decode("utf-8", errors="replace")
    return sorted({dt.date(int(m[:4]), int(m[4:]), int(g)) for m, g in re.findall(r"slAnnoMese=(\d{6})&amp;slGiorno=(\d{2})", t)})


def giorno_mostrato(pagina: bytes) -> dt.date | None:
    """Il giorno della convocazione mostrata: «Martedì 10 novembre 2026»."""
    m = re.search(r'class="dataconvocazione"[^>]*>\s*\S+\s+(\d{1,2})°?\s+(\w+)\s+(\d{4})', pagina.decode("utf-8", errors="replace"))
    return dt.date(int(m.group(3)), MESI[m.group(2).lower()], int(m.group(1))) if m and m.group(2).lower() in MESI else None


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 1.0))
    massimo = int(cfg.get("massimo_per_giro", 150))
    lago, oggi = Lago(ctx.cartella), dt.date.today()
    richieste = nuovi = salvati = 0

    def salva(organo: int, pagina: bytes, url: str) -> None:
        nonlocal nuovi, salvati
        g = giorno_mostrato(pagina)
        if g and g >= oggi:
            salvati += 1
            nuovi += bool(lago.salva(NOME, f"leg{leg}-conv-{organo}-{g:%Y%m%d}", pagina, url, "htm").get("nuovo"))

    for organo in ORGANI:
        pagine = [PAGINA.format(leg=leg, organo=organo)]
        if oggi.day >= 20:                          # a fine mese le convocazioni della settimana dopo stanno nel mese dopo
            dopo = (oggi.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
            pagine.append(MESE.format(leg=leg, organo=organo, mese=f"{dopo:%Y%m}"))
        visti: set[dt.date] = set()
        for u in pagine:
            if richieste >= massimo:
                break
            corpo = _get(u)
            richieste += 1
            time.sleep(pausa)
            if not corpo:
                continue
            mostrato = giorno_mostrato(corpo)
            if mostrato and mostrato not in visti:
                visti.add(mostrato)
                salva(organo, corpo, u)
            for g in giorni(corpo):
                if g < oggi or g in visti or richieste >= massimo:
                    continue
                visti.add(g)
                ug = GIORNO.format(leg=leg, organo=organo, mese=f"{g:%Y%m}", giorno=g.day)
                pagina = _get(ug)
                richieste += 1
                time.sleep(pausa)
                if pagina:
                    salva(organo, pagina, ug)
    if not richieste:
        raise RuntimeError("nessuna pagina delle convocazioni letta")
    ctx.log(f"{NOME}: {richieste} richieste, {salvati} convocazioni da oggi in poi, {nuovi} nuove o cambiate")
    return {"richieste": richieste, "convocazioni": salvati, "nuove": nuovi}
