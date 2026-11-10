"""Resoconti stenografici delle commissioni del Senato: si redigono solo per le sedi deliberante e redigente, per alcune
procedure informative (audizioni del Governo, indagini conoscitive) e per la sessione di bilancio. Esistono solo in PDF.

Per ogni commissione permanente la pagina dell'anno elenca le sedute con lo stenografico: commissione (anche riunite o
congiunte con la Camera), data, numero della seduta, sede e argomento, e il link al PDF. Ogni notte si rileggono gli
elenchi dell'anno in corso (dieci richieste); gli anni passati una volta sola. Una commissione senza stenografici in un
anno risponde 500: si segna come anno vuoto e si va avanti. I PDF nuovi si scaricano, al più
`massimo_file_per_giro` per notte. senato.it sta dietro il WAF: tutto con il browser, nel tetto comune delle richieste.

Nel lago: l'elenco (`leg19-senato-stc-elenco-05-2026`), per ogni stenografico la scheda con i dati dell'elenco
(`leg19-senato-stc-450147-scheda`, JSON) e il PDF (`leg19-senato-stc-450147-file`).
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re

from ..lago import Lago
from . import senato_browser

NOME = "senato_stenografici_commissioni"
PAGINA = "https://www.senato.it/commissioni-e-giunte/commissioni-permanenti/{n}a-commissione-permanente/resoconti-stenografici?mode=t&year={anno}"
COMMISSIONI = range(1, 11)
MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
                                     "ottobre", "novembre", "dicembre"], 1)}


def _testo(t: str) -> str:
    t = re.sub(r"<br\s*/?>|</(?:div|p|li)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t.replace("&ordf ", "ª "))).replace("\xa0", " ")
    return "\n".join(r for r in (re.sub(r"\s+", " ", x).strip() for x in t.split("\n")) if r)


def elenco(pagina: bytes, commissione: int) -> list[dict]:
    """Le sedute con lo stenografico elencate nella pagina di una commissione per un anno, una voce per PDF."""
    t = pagina.decode("utf-8", errors="replace")
    voci = []
    for li in re.findall(r'<li class="tab\d+">(.*?)<span class="clear"></span>\s*</li>', t, re.S):
        organo = re.search(r"<h4[^>]*>(.*?)</h4>", li, re.S)
        quando = re.search(r'class="data_ora_inizio">\s*<strong[^>]*>(.*?)</strong>', li, re.S)
        g = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", _testo(quando.group(1))) if quando else None
        seduta = re.search(r'class="numero">\s*n\.\s*(\d+)\s*(?:\(([^)]*)\))?', li)
        argomento = re.search(r'class="resoconti_stenografici__content">(.*?)<div class="resoconti_stenografici_pdf">', li, re.S)
        sede = re.search(r"<em>(.*?)</em>", argomento.group(1), re.S) if argomento else None
        for m in re.finditer(r'href="(?:https?:)?//www\.senato\.it/service/PDF/PDFServer/DF/(\d+)\.pdf"[^>]*>\s*\(?([^<)]*)\)?\s*</a>\s*(?:<em>\s*\(?([^<)]*)\)?\s*</em>)?', li):
            if not g or g.group(2).lower() not in MESI:
                continue
            voci.append({"id": m.group(1), "url": f"https://www.senato.it/service/PDF/PDFServer/DF/{m.group(1)}.pdf",
                         "commissione": commissione, "organo": _testo(organo.group(1)) if organo else None,
                         "data": f"{g.group(3)}-{MESI[g.group(2).lower()]:02d}-{int(g.group(1)):02d}",
                         "seduta": seduta.group(1) if seduta else None, "turno": (seduta.group(2) or None) if seduta else None,
                         "sede": _testo(sede.group(1)) if sede else None, "argomento": _testo(argomento.group(1)) if argomento else None,
                         "numero": m.group(2).strip() or None, "bozza": "bozza" in (m.group(3) or "").lower()})
    return voci


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, primo_anno = int(cfg["legislatura"]), int(cfg.get("primo_anno", 2022))
    massimo_file = int(cfg.get("massimo_file_per_giro", 40))
    lago, anno = Lago(ctx.cartella), dt.date.today().year
    noti = set(lago.chiavi(NOME))
    elenchi = nuovi = file_ = di_fila = 0
    voci: dict[str, dict] = {}
    try:
        with senato_browser.Sessione(pausa=float(cfg.get("pausa_secondi", 5)), massimo=int(cfg.get("massimo_richieste", 80)), ctx=ctx) as sessione:
            for n in COMMISSIONI:
                for a in range(anno, primo_anno - 1, -1):
                    k = f"leg{leg}-senato-stc-elenco-{n:02d}-{a}"
                    if a != anno and k in noti:
                        corpo = lago.leggi(lago.ultimo(NOME, k)["file"])       # un anno chiuso non cambia più
                    else:
                        try:
                            corpo = sessione.scarica(PAGINA.format(n=n, anno=a))
                            di_fila = 0
                        except senato_browser.NonTrovato:
                            continue
                        except senato_browser.Bloccato as e:
                            # una commissione senza stenografici in quell'anno risponde 500: non è un blocco (verificato
                            # l'11/11/2026 sulla 6ª, 2026). Tre di fila invece sì: il sito non sta rispondendo
                            di_fila += 1
                            if "HTTP 500" not in str(e) or di_fila >= 3:
                                raise
                            corpo = b""
                        lago.salva(NOME, k, corpo or b"<!-- nessuno stenografico -->", PAGINA.format(n=n, anno=a), "htm")
                        elenchi += 1
                    for v in elenco(corpo, n):
                        voci.setdefault(v["id"], v)                             # una seduta congiunta sta negli elenchi di più commissioni
            for i, v in sorted(voci.items(), key=lambda x: x[1]["data"], reverse=True):
                scheda = json.dumps(v, ensure_ascii=False, sort_keys=True).encode()
                nuovi += bool(lago.salva(NOME, f"leg{leg}-senato-stc-{i}-scheda", scheda, v["url"], "json").get("nuovo"))
                if f"leg{leg}-senato-stc-{i}-file" in noti or file_ >= massimo_file:
                    continue
                try:
                    pdf = sessione.scarica(v["url"])
                except senato_browser.NonTrovato:
                    continue
                if pdf[:4] == b"%PDF":
                    lago.salva(NOME, f"leg{leg}-senato-stc-{i}-file", pdf, v["url"], "pdf")
                    file_ += 1
    except senato_browser.Bloccato as e:
        ctx.log(f"{NOME}: senato.it non risponde dopo {elenchi} elenchi e {file_} file, si riprende al giro dopo ({str(e)[:120]})")
    mancano = sum(1 for i in voci if f"leg{leg}-senato-stc-{i}-file" not in set(lago.chiavi(NOME)))
    ctx.log(f"{NOME}: {elenchi} elenchi letti, {len(voci)} stenografici, {file_} PDF scaricati, {mancano} da scaricare")
    return {"elenchi": elenchi, "stenografici": len(voci), "file": file_, "da_scaricare": mancano, "schede_nuove": nuovi}
