"""Resoconti stenografici delle commissioni della Camera: audizioni formali, indagini conoscitive e altre sedute
trascritte parola per parola (a differenza del Bollettino, che è un sommario).

Gli elenchi mensili (`elencoResoconti`, uno per mese dall'inizio della legislatura) dicono quali stenografici
esistono; ogni stenografico è una pagina HTML. Ogni notte si rileggono il mese corrente e il precedente, e si
riscaricano gli stenografici ancora in bozza («bozza non corretta») degli ultimi 30 giorni.
Chiavi nel lago: `leg19-stc-elenco-202610`, `leg19-stc-03-indag-c03_discriminazioni-20261006-0055`.
"""

from __future__ import annotations

import datetime as dt
import html
import re
import time

from ..lago import Lago
from .camera_bollettino import _get

NOME = "camera_stenografici_commissioni"
ELENCO = ("https://documenti.camera.it/apps/commonServices/getDocumento.ashx?idLegislatura={leg}&sezione=commissioni"
          "&tipoDoc=elencoResoconti&annoMese={mese}&breve=&view=filtered&idCommissione=&tipoElenco=sediCronologico")
LINK = re.compile(r'href="(//documenti\.camera\.it/apps/commonServices/getDocumento\.ashx\?[^"]*tipoDoc=stenografico&amp;[^"]+)"')


def mesi(da: str, fino: dt.date) -> list[str]:
    a, m = int(da[:4]), int(da[4:6])
    out = []
    while (a, m) <= (fino.year, fino.month):
        out.append(f"{a}{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def stenografici(elenco: bytes) -> list[dict]:
    """Dall'elenco mensile: un dizionario per stenografico (commissione, tipologia, data, numero, url)."""
    out = []
    for h in LINK.findall(elenco.decode("utf-8", errors="replace")):
        u = html.unescape(h)
        q = dict(re.findall(r"[?&](\w+)=([^&#]*)", u))
        if not q.get("numero") or not q.get("anno"):
            continue
        out.append({"commissione": q.get("idCommissione", ""), "tipologia": q.get("tipologia", ""), "sottotipologia": q.get("sottotipologia", ""),
                    "data": f"{q['anno']}{q['mese']}{q['giorno']}", "numero": q["numero"], "url": "https:" + u})
    return list({x["url"]: x for x in out}.values())


def chiave(x: dict, leg: int) -> str:
    sotto = f"-{x['sottotipologia']}" if x["sottotipologia"] else ""
    return f"leg{leg}-stc-{x['commissione']}-{x['tipologia']}{sotto}-{x['data']}-{x['numero']}"


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa, massimo = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 1.0)), int(cfg.get("massimo_per_giro", 200))
    lago = Lago(ctx.cartella)
    presenti = set(lago.chiavi(NOME))
    oggi = dt.date.today()
    tutti = mesi(str(cfg["primo_mese"]), oggi)
    # mesi da leggere: quelli mai letti, più il corrente e il precedente (si aggiungono stenografici nei giorni dopo)
    da_leggere = [m for m in tutti if f"leg{leg}-stc-elenco-{m}" not in presenti] + tutti[-2:]
    elenco_tot, fallite = [], []
    for m in dict.fromkeys(da_leggere):
        u = ELENCO.format(leg=leg, mese=m)
        try:
            corpo = _get(u)
        except Exception as e:
            fallite.append(f"elenco {m}: {str(e)[:100]}")
            continue
        if corpo:
            lago.salva(NOME, f"leg{leg}-stc-elenco-{m}", corpo, u, "htm")
        time.sleep(pausa)
    for k in lago.chiavi(NOME):
        if "-stc-elenco-" in k:
            elenco_tot += stenografici(lago.leggi(lago.ultimo(NOME, k)["file"]))
    # da scaricare: quelli che mancano (dal più recente) e quelli recenti ancora in bozza
    limite = (oggi - dt.timedelta(days=30)).strftime("%Y%m%d")
    mancano = sorted((x for x in elenco_tot if chiave(x, leg) not in presenti), key=lambda x: x["data"], reverse=True)
    bozze = [x for x in elenco_tot if x["data"] >= limite and chiave(x, leg) in presenti
             and b'name="bozza" content="true"' in lago.leggi(lago.ultimo(NOME, chiave(x, leg))["file"])[:4000]]
    nuovi = cambiati = 0
    for x in (bozze + mancano)[:massimo]:
        try:
            corpo = _get(x["url"])
        except Exception as e:
            fallite.append(f"{chiave(x, leg)}: {str(e)[:100]}")
            continue
        if corpo:
            esito = lago.salva(NOME, chiave(x, leg), corpo, x["url"], "htm")
            if esito["nuovo"]:
                cambiati += chiave(x, leg) in presenti
                nuovi += chiave(x, leg) not in presenti
        time.sleep(pausa)
    rimandati = max(0, len(bozze) + len(mancano) - massimo)
    ctx.log(f"{NOME}: {len(elenco_tot)} stenografici negli elenchi; {nuovi} nuovi, {cambiati} aggiornati, {rimandati} rimandati")
    if fallite:
        raise RuntimeError(f"{len(fallite)} pagine non scaricate, si riprendono al giro dopo: {fallite[:5]}")
    return {"negli_elenchi": len(elenco_tot), "nuovi": nuovi, "aggiornati": cambiati, "rimandati": rimandati}
