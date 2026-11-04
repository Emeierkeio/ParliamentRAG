"""Documenti acquisiti dalle commissioni permanenti della Camera: memorie e contributi scritti depositati nelle
audizioni e sugli atti (associazioni, sindacati, aziende, esperti, enti), in PDF, DOCX, DOC, PPTX.

Per ogni commissione si leggono due pagine (documenti delle audizioni e altra documentazione), che elencano per
seduta i file con il loro titolo («AG 439 - Memoria UIL FP»); poi si scaricano i file nuovi, `massimo_file_per_giro`
per notte. I nomi dei file contengono un identificativo e la data di deposito: un file non cambia, si scarica una volta.
Un file oltre MASSIMO_BYTE non entra nel lago e si annota in `camera_documenti_troppo_grandi.json` (cartella dei dati),
così non si riscarica ogni notte.

Sono scritti di terzi: restano nel lago (privato) e nel database per la ricerca; il sito ne mostra solo estratti con
il link al file ufficiale.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.parse

from ..lago import Lago
from .camera_bollettino import _get

NOME = "camera_documenti"
PAGINE = {"audizioni": "https://www.camera.it/leg{leg}/1347?shadow_organo_parlamentare={organo}&id_tipografico={codice}",
          "altra": "https://www.camera.it/leg{leg}/1425?shadow_organo_parlamentare={organo}&id_tipografico={codice}"}
MASSIMO_BYTE = 30_000_000   # un file più grande di così si salta (si segnala), non si scarica


def elenco(pagina: bytes) -> list[dict]:
    """I file di una pagina: per ogni blocco (seduta o «Ulteriore documentazione»), la descrizione e i link."""
    t = pagina.decode("utf-8", errors="replace")
    out = []
    for blocco in re.split(r'<div class="no_link_bol_seduta">', t)[1:]:
        intestazione = html.unescape(re.sub(r"<[^>]+>", "", blocco.split("</div>", 1)[0])).strip()
        desc = re.search(r'<div class="autore_titolo">(.*?)</div>', blocco, re.S)
        descrizione = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", desc.group(1)))).strip() if desc else None
        for u, titolo in re.findall(r'<li class="documentoLink"><a href="([^"]+)" title="Apri: ([^"]*)"', blocco):
            out.append({"url": html.unescape(u), "titolo": html.unescape(titolo).strip(), "seduta": intestazione, "descrizione": descrizione})
    return out


def chiave_file(url: str, leg: int) -> str:
    """leg19.com01.Audizioni.Memoria.PUBBLICO.ideGes.103199.23-10-2026-14-26-31.054.pdf -> leg19-doc-com01-103199-20261023142631054."""
    nome = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    m = re.search(r"\.(com\d+)\..*?ideGes\.(\d+)\.(\d\d)-(\d\d)-(\d{4})-(\d\d)-(\d\d)-(\d\d)\.(\d+)", nome)
    if not m:
        return f"leg{leg}-doc-" + re.sub(r"[^\w]+", "-", nome)[:120]
    c, ide, g, mm, a, h, mi, s, ms = m.groups()
    return f"leg{leg}-doc-{c}-{ide}-{a}{mm}{g}{h}{mi}{s}{ms}"


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa, massimo = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 1.0)), int(cfg.get("massimo_file_per_giro", 300))
    lago = Lago(ctx.cartella)
    voci, fallite = [], []
    for n in range(1, 15):                                       # le 14 commissioni permanenti
        codice, organo = f"{n:02d}", 3500 + n
        for tipo, url in PAGINE.items():
            u = url.format(leg=leg, organo=organo, codice=codice)
            try:
                corpo = _get(u)
            except Exception as e:
                fallite.append(f"{codice}-{tipo}: {str(e)[:80]}")
                continue
            finally:
                time.sleep(pausa)
            if corpo:
                lago.salva(NOME, f"leg{leg}-doc-elenco-c{codice}-{tipo}", corpo, u, "htm")
                voci += elenco(corpo)
    presenti = set(lago.chiavi(NOME))
    # alcune memorie RISERVATO puntano al server interno della Camera («Ncs03-pool40-server/vol40/…»): non sono pubbliche
    interni = [x for x in voci if not x["url"].startswith("http")]
    voci = [x for x in voci if x["url"].startswith("http")]
    f_grandi = ctx.cartella / "camera_documenti_troppo_grandi.json"
    try:
        grandi = json.loads(f_grandi.read_text())
    except (OSError, ValueError):
        grandi = {}
    mancano = [v for v in dict((x["url"], x) for x in voci).values() if chiave_file(v["url"], leg) not in presenti and v["url"] not in grandi]
    mancano.sort(key=lambda v: chiave_file(v["url"], leg)[-17:], reverse=True)     # dai depositi più recenti
    fatti = saltati = 0
    for v in mancano[:massimo]:
        u = urllib.parse.quote(v["url"], safe=":/?&=%.")
        try:
            corpo = _get(u)
        except Exception as e:
            fallite.append(f"{v['url'][-60:]}: {str(e)[:80]}")
            continue
        finally:
            time.sleep(pausa)
        if not corpo:
            continue
        if len(corpo) > MASSIMO_BYTE:
            saltati += 1
            grandi[v["url"]] = len(corpo)
            f_grandi.write_text(json.dumps(grandi, ensure_ascii=False, indent=0))
            continue
        estensione = v["url"].rsplit(".", 1)[-1].lower()[:5]
        lago.salva(NOME, chiave_file(v["url"], leg), corpo, v["url"], estensione)
        fatti += 1
    rimandati = max(0, len(mancano) - massimo)
    ctx.log(f"{NOME}: {len(voci)} file negli elenchi; {fatti} scaricati, {saltati} troppo grandi ({len(grandi)} in tutto), {rimandati} rimandati, {len(interni)} non pubblici")
    # pochi file persi per la rete non fermano il giro: si riprendono al giro dopo e intanto si trasforma il resto;
    # se ne mancano molti il passo fallisce, perché di solito vuol dire che la Camera sta bloccando
    if fallite and len(fallite) > max(10, 0.05 * (fatti + saltati + len(fallite))):
        raise RuntimeError(f"{len(fallite)} pagine o file non scaricati, si riprendono al giro dopo: {fallite[:5]}")
    if fallite:
        ctx.log(f"{NOME}: {len(fallite)} non scaricati, si riprendono al giro dopo: {fallite[:5]}")
    return {"negli_elenchi": len(voci), "scaricati": fatti, "troppo_grandi": saltati, "rimandati": rimandati, "non_pubblici": len(interni),
            "non_scaricati": len(fallite)}
