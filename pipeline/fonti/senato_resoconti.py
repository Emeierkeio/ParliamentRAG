"""Resoconti stenografici dell'Assemblea del Senato in Akoma Ntoso (XML), da senato.it.

senato.it è dietro un WAF che chiede di eseguire JavaScript: le pagine si aprono con il browser senza interfaccia
(senato_browser). L'elenco cronologico dell'anno dà numero e id di ogni seduta: si scaricano quelle che mancano nel lago
e si riscaricano le ultime `ricontrolla`, che il Senato può ancora correggere. Una seduta senza AKN aspetta il giro dopo.

Questo passo importa anche nel lago i resoconti già scaricati dalla pipeline precedente (`cartella_import`, file
`resaula_leg19_0300.akn`): sono gli stessi file della fonte, con la loro data e il loro indirizzo ufficiale. Alcune sedute (XIX: 212, 213, 214, 216, 218,
221, 222) il Senato le ha pubblicate solo come pagina web, senza AKN: per quelle si importa la pagina
`resaula_leg19_0212.html`, che la trasformazione legge a parte.
Chiave nel lago: `leg19-senato-sed0300`.
"""

from __future__ import annotations

import datetime as dt
import re

from ..ambiente import percorso
from ..lago import Lago
from . import senato_browser

NOME = "senato_resoconti"
ELENCO = "https://www.senato.it/lavori/assemblea/resoconti-elenco-cronologico?year={anno}"
AKN = "https://www.senato.it/leg/{leg}/BGT/Testi/Resaula/{id:08d}.akn"


def leggi_elenco(pagina: str, leg: int) -> dict[int, int]:
    """Dall'elenco cronologico: numero della seduta -> id del resoconto."""
    return {int(n): int(i) for n, i in re.findall(
        rf'font-weight:\s*bold[^>]*>\s*(\d+)\s*</td>\s*<td[^>]*>\s*<a href="[^"]*show-doc\?leg={leg}&(?:amp;)?tipodoc=Resaula&(?:amp;)?id=(\d+)',
        pagina)}


def _salva_akn(lago: Lago, k: str, corpo: bytes, url: str) -> dict:
    uri = re.search(rb'<an:FRBRuri value="([^"]+)"', corpo)
    return lago.salva(NOME, k, corpo, uri.group(1).decode() if uri else url, "akn")


def _nuove(ctx, lago: Lago, cfg: dict, leg: int, presenti: set[str]) -> dict:
    """Le sedute dall'elenco di senato.it. Un blocco del sito non ferma il giro: quello che manca si prende al giro dopo."""
    oggi = dt.date.today()
    anni = sorted({oggi.year, (oggi - dt.timedelta(days=30)).year})     # a gennaio anche le sedute di dicembre
    scaricate, cambiate, senza_akn = [], [], []
    try:
        with senato_browser.Sessione(pausa=float(cfg.get("pausa_secondi", 2)), massimo=int(cfg.get("massimo_richieste", 40)), ctx=ctx) as s:
            sedute: dict[int, int] = {}
            for anno in anni:
                sedute.update(leggi_elenco(s.scarica(ELENCO.format(anno=anno)).decode("utf-8", errors="replace"), leg))
            if not sedute:
                raise RuntimeError(f"{NOME}: nessuna seduta nell'elenco: la pagina è cambiata?")
            chiave = lambda n: f"leg{leg}-senato-sed{n:04d}"       # noqa: E731
            mancanti = [n for n in sorted(sedute) if chiave(n) not in presenti]
            ultime = [n for n in sorted(sedute)[-int(cfg.get("ricontrolla", 3)):] if n not in mancanti]
            for n in mancanti + ultime:
                url = AKN.format(leg=leg, id=sedute[n])
                try:
                    nuovo = _salva_akn(lago, chiave(n), s.scarica(url), url)["nuovo"]
                except senato_browser.NonTrovato:
                    if n in mancanti:
                        senza_akn.append(n)
                    continue
                if n in mancanti:
                    scaricate.append(n)
                    presenti.add(chiave(n))
                elif nuovo:
                    cambiate.append(n)
    except senato_browser.Bloccato as e:
        ctx.log(f"{NOME}: fermato da senato.it, si riprende al giro dopo: {e}")
        return {"scaricate": scaricate, "cambiate": cambiate, "senza_akn": senza_akn, "bloccato": True}
    return {"scaricate": scaricate, "cambiate": cambiate, "senza_akn": senza_akn}


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    lago = Lago(ctx.cartella)
    cartella = percorso(cfg["cartella_import"]) if cfg.get("cartella_import") else None
    presenti = set(lago.chiavi(NOME))
    importati = 0
    if cartella and cartella.is_dir():
        # prima gli AKN, poi le pagine web: un HTML entra solo per le sedute senza AKN
        for f in sorted(cartella.glob(f"resaula_leg{leg}_*.akn")) + sorted(cartella.glob(f"resaula_leg{leg}_*.html")):
            numero = int(re.search(r"_(\d+)\.(?:akn|html)$", f.name).group(1))
            k = f"leg{leg}-senato-sed{numero:04d}"
            if k in presenti:
                continue
            corpo = f.read_bytes()
            if f.suffix == ".html":
                doc = re.search(rb"show-doc\?leg=\d+&amp;tipodoc=Resaula&amp;id=(\d+)", corpo)
                url = f"https://www.senato.it/show-doc?leg={leg}&tipodoc=Resaula&id={doc.group(1).decode()}&part=doc_dc" if doc else str(f)
                lago.salva(NOME, k, corpo, url, "html")
            else:
                uri = re.search(rb'<an:FRBRuri value="([^"]+)"', corpo)
                lago.salva(NOME, k, corpo, uri.group(1).decode() if uri else str(f), "akn")
            presenti.add(k)
            importati += 1
    nuove = _nuove(ctx, lago, cfg, leg, presenti)
    ctx.log(f"{NOME}: {importati} importati dalla cartella, {len(nuove['scaricate'])} scaricati, {len(nuove['cambiate'])} cambiati, "
            f"senza AKN {nuove['senza_akn']}")
    avviso = (["senato.it ha fermato il passo"] if nuove.get("bloccato") else []) + ([f"sedute senza AKN: {nuove['senza_akn']}"] if nuove["senza_akn"] else [])
    return {"importati": importati, **nuove, "nel_lago": len([k for k in lago.chiavi(NOME) if "-senato-sed" in k]), **({"avviso": avviso} if avviso else {})}
