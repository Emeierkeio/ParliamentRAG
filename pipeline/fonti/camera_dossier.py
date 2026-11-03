"""Dossier dei Servizi di documentazione della Camera (Servizio Studi, Bilancio, Biblioteca…) da temi.camera.it:
schede e testo integrale in HTML. Licenza CC BY-SA 4.0 (piè di pagina di temi.camera.it).

L'elenco (circa 3.600 nella XIX) si legge a pagine di 200 dal modulo di ricerca, dal più recente; ogni notte le
prime pagine bastano per i nuovi. Per ogni dossier nuovo si scaricano la scheda (data, servizio, codice del
documento, link) e il testo HTML. Un dossier non cambia: si scarica una volta. `massimo_per_giro` dossier per notte.
Chiavi nel lago: `leg19-dossier-elenco-0000`, `leg19-dossier-OCD18-23810-scheda`, `leg19-dossier-OCD18-23810-testo`.
"""

from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request

from ..lago import Lago
from .camera_bollettino import UA, _get

NOME = "camera_dossier"
SITO = "https://temi.camera.it"
PAGINA = 200


def _elenco(leg: int, inizio: int) -> bytes:
    corpo = urllib.parse.urlencode({"start": inizio, "length": PAGINA, "facets": "", "facetsValues": "", "query": "", "scrollTo": ""}).encode()
    req = urllib.request.Request(f"{SITO}/leg{leg}/dossier.html", corpo, {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def voci(pagina: bytes) -> list[dict]:
    t = pagina.decode("utf-8", errors="replace")
    return [{"id": i, "url": SITO + h} for h, i in re.findall(r'href="(/leg\d+/dossier/(OCD[\d-]+)/[^"]+)"', t)]


def totale(pagina: bytes) -> int:
    m = re.search(rb'id="tot-results">(\d+) dossier', pagina)
    return int(m.group(1)) if m else 0


def testo_link(scheda: bytes) -> str | None:
    m = re.search(rb'data-link="(https://documenti\.camera\.it/leg\d+/dossier/testi/[^"?]+)', scheda)
    return m.group(1).decode() if m else None


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa, massimo = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 1.0)), int(cfg.get("massimo_per_giro", 300))
    lago = Lago(ctx.cartella)
    presenti = set(lago.chiavi(NOME))
    noti = {k.split("-dossier-")[1].rsplit("-", 1)[0] for k in presenti if k.endswith("-scheda")}
    # elenco: tutte le pagine la prima volta; poi solo finché compaiono dossier nuovi
    tutti, inizio, n_tot = {}, 0, None
    while n_tot is None or inizio < n_tot:
        pagina = _elenco(leg, inizio)
        time.sleep(pausa)
        n_tot = totale(pagina) if n_tot is None else n_tot
        lago.salva(NOME, f"leg{leg}-dossier-elenco-{inizio:04d}", pagina, f"{SITO}/leg{leg}/dossier.html", "htm")
        blocco = voci(pagina)
        tutti.update({v["id"]: v for v in blocco})
        if not blocco or (noti and all(v["id"] in noti for v in blocco)):
            break
        inizio += PAGINA
    for k in presenti:                                      # i dossier già visti nelle pagine vecchie restano in elenco
        if "-dossier-elenco-" in k:
            tutti.update({v["id"]: v for v in voci(lago.leggi(lago.ultimo(NOME, k)["file"]))})
    mancano = sorted((v for v in tutti.values() if v["id"] not in noti), key=lambda v: [int(x) for x in re.findall(r"\d+", v["id"])], reverse=True)
    fatti, fallite = 0, []
    for v in mancano[:massimo]:
        try:
            scheda = _get(v["url"])
            time.sleep(pausa)
            if not scheda:
                continue
            link = testo_link(scheda)
            testo = _get(link) if link else None
            time.sleep(pausa)
            if testo:
                lago.salva(NOME, f"leg{leg}-dossier-{v['id']}-testo", testo, link, "htm")
            lago.salva(NOME, f"leg{leg}-dossier-{v['id']}-scheda", scheda, v["url"], "htm")   # per ultima: segna il dossier come fatto
            fatti += 1
        except Exception as e:
            fallite.append(f"{v['id']}: {str(e)[:100]}")
    rimandati = max(0, len(mancano) - massimo)
    ctx.log(f"{NOME}: {len(tutti)} dossier in elenco (su {n_tot}); {fatti} scaricati, {rimandati} rimandati")
    if fallite:
        raise RuntimeError(f"{len(fallite)} dossier non scaricati, si riprendono al giro dopo: {fallite[:5]}")
    return {"in_elenco": len(tutti), "scaricati": fatti, "rimandati": rimandati}
