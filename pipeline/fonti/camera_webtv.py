"""WebTV della Camera: il video di ogni seduta d'Aula e, per ogni intervento, il secondo di inizio e di fine con
l'ancora del resoconto stenografico. Così ogni citazione può portare al punto esatto del video.

L'elenco degli eventi d'Aula viene dal servizio dell'archivio (`/ws/archivio`, XML, 20 eventi per pagina, con il
numero di seduta); la pagina di ogni evento contiene l'indice degli interventi. I video non si scaricano
(robots.txt lo vieta): solo le pagine, una ogni 10 secondi come chiede il sito (`Crawl-delay: 10`).
Chiavi nel lago: `leg19-webtv-elenco` (JSON compresso), `leg19-webtv-evento-32715` (HTML compresso, ~1 MB in chiaro).
"""

from __future__ import annotations

import gzip
import json
import re
import time
import urllib.parse
import urllib.request

from ..lago import Lago
from .camera_bollettino import UA, _get

NOME = "camera_webtv"
SITO = "https://webtv.camera.it"


def _elenco_pagina(leg: int, pagina: int) -> tuple[int, list[dict]]:
    corpo = urllib.parse.urlencode({"filter_label_sez_1": 1, f"filter_label_leg_{leg}": leg, "page": pagina}).encode()
    req = urllib.request.Request(f"{SITO}/ws/archivio", corpo, {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                                                                "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dati = json.loads(r.read())
    totale = int(dati.get("tot_records") or 0)
    campi = ("id", "titolo", "dataora_evento", "dataora_fine", "numero_seduta", "legislatura")
    eventi = [{k: str(e.get(k) or "") for k in campi} for e in dati.get("list") or []]
    return totale, [e for e in eventi if e.get("id")]


def chiave_evento(ident: str, leg: int) -> str:
    return f"leg{leg}-webtv-evento-{ident}"


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 10))
    massimo, ricontrolla = int(cfg.get("massimo_per_giro", 100)), int(cfg.get("ricontrolla", 3))
    lago = Lago(ctx.cartella)
    k_elenco = f"leg{leg}-webtv-elenco"
    prima = lago.ultimo(NOME, k_elenco)
    noti = {e["id"]: e for e in json.loads(gzip.decompress(lago.leggi(prima["file"])))} if prima else {}
    # l'elenco è dal più recente: ci si ferma alla prima pagina tutta già nota (o si legge tutto la prima volta)
    pagina, eventi = 1, dict(noti)
    while True:
        totale, blocco = _elenco_pagina(leg, pagina)
        time.sleep(pausa)
        nuovi_qui = [e for e in blocco if e["id"] not in noti]
        eventi.update({e["id"]: e for e in blocco})
        if not blocco or (noti and not nuovi_qui) or pagina * 20 >= totale:
            break
        pagina += 1
    ordinati = sorted(eventi.values(), key=lambda e: int(e["id"]))
    lago.salva(NOME, k_elenco, gzip.compress(json.dumps(ordinati, ensure_ascii=False).encode(), mtime=0), f"{SITO}/ws/archivio", "json.gz")
    presenti = set(lago.chiavi(NOME))
    recenti = [e for e in ordinati if e.get("numero_seduta")][-ricontrolla:]     # l'indice degli interventi si completa dopo
    mancano = [e for e in reversed(ordinati) if e.get("numero_seduta") and chiave_evento(e["id"], leg) not in presenti]
    fatti, fallite = 0, []
    for e in list({x["id"]: x for x in recenti + mancano}.values())[:massimo]:
        u = f"{SITO}/evento/{e['id']}"
        try:
            corpo = _get(u)
        except Exception as err:
            fallite.append(f"{e['id']}: {str(err)[:100]}")
            continue
        finally:
            time.sleep(pausa)
        if corpo:
            lago.salva(NOME, chiave_evento(e["id"], leg), gzip.compress(corpo, mtime=0), u, "htm.gz")
            fatti += 1
    rimandati = max(0, len(mancano) - massimo)
    ctx.log(f"{NOME}: {len(ordinati)} eventi d'Aula, {fatti} pagine scaricate, {rimandati} rimandate")
    if fallite:
        raise RuntimeError(f"{len(fallite)} eventi non scaricati, si riprendono al giro dopo: {fallite[:5]}")
    return {"eventi": len(ordinati), "scaricati": fatti, "rimandati": rimandati}


def indice(pagina: bytes) -> list[dict]:
    """Dalla pagina di un evento: gli interventi con id WebTV, ancora dello stenografico, secondi, ora, deputato."""
    t = gzip.decompress(pagina).decode("utf-8", errors="replace")
    out = []
    for tag, ident in re.findall(r'(<a id="ora_resoc_(\d+)"[^>]*>)', t):
        a = dict(re.findall(r'data-(\w+)="([^"]*)"', tag))
        # ident: l'id dell'intervento nella WebTV, che nel link /evento/<evento>/<ident> fa partire il video da lì
        out.append({"id": int(ident), "ancora": a.get("steno_map", ""), "inizio": a.get("tc_start"), "fine": a.get("tc_end"), "ora": a.get("dataora_c"),
                    "persona": a.get("id_anagr"), "etichetta": a.get("etichetta"), "titolo": a.get("tit_id")})
    return out
