"""Bollettino delle Giunte e delle Commissioni della Camera: il resoconto sommario di ogni seduta di commissione,
giunta e comitato, con gli allegati (proposte di parere, emendamenti, risoluzioni).

Per ogni giorno con un Bollettino (elenco da dati.camera.it): l'indice del giorno dice quali commissioni si sono
riunite; per ognuna si scaricano il comunicato e, se c'è, la pagina degli allegati. Tutto HTML statico.
Chiavi nel lago: `leg19-bol-20261028-indice`, `leg19-bol-20261028-c01`, `leg19-bol-20261028-c01-allegati`.

Il Bollettino è un sommario scritto dagli uffici, non le parole esatte dei deputati: non si cita tra virgolette.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request

from ..lago import Lago
from .camera_ocd import ENDPOINT, PREFISSI, leg_uri
from .sparql import interroga

NOME = "camera_bollettino"
UA = "parliamentrag-pipeline (www.parliamentrag.it)"
GIORNI = """SELECT DISTINCT ?data WHERE { ?b a ocd:bollettino ; ocd:rif_leg <{LEG}> ; dc:date ?data } ORDER BY ?data"""
INDICE = ("https://documenti.camera.it/apps/commonServices/getDocumento.ashx?idLegislatura={leg}&sezione=bollettini"
          "&tipoDoc=indiceGenerale&anno={a}&mese={m}&giorno={g}")
PAGINA = "https://documenti.camera.it/leg{leg}/resoconti/commissioni/bollettini/html/{a}/{m}/{g}/{codice}/{file}.htm"


def chiave(giorno: str, leg: int, parte: str) -> str:
    return f"leg{leg}-bol-{giorno}-{parte}"


def _get(url: str, tentativi: int = 3) -> bytes | None:
    """Il contenuto, oppure None se la pagina non esiste (404: per esempio una commissione senza allegati)."""
    for t in range(1, tentativi + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if t == tentativi:
                raise
        except (urllib.error.URLError, TimeoutError):
            if t == tentativi:
                raise
        time.sleep(10 * t)
    return None


def codici(indice: bytes) -> list[str]:
    """I codici delle commissioni riunite quel giorno (01, 0109 per le riunite, 26 …), dall'indice generale."""
    return sorted(set(re.findall(rb"tipoDoc=indice&amp;anno=\d+&amp;mese=\d+&amp;giorno=\d+&amp;idCommissione=(\w+)", indice)
                      + re.findall(rb"tipoDoc=indice&anno=\d+&mese=\d+&giorno=\d+&idCommissione=(\w+)", indice)), key=lambda x: x.decode())


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 1.0))
    ricontrolla, massimo = int(cfg.get("ricontrolla_giorni", 3)), int(cfg.get("massimo_giorni_per_giro", 30))
    lago = Lago(ctx.cartella)
    giorni = [r["data"] for r in interroga(ENDPOINT, PREFISSI + GIORNI.replace("{LEG}", leg_uri(leg)))]
    if not giorni:
        raise RuntimeError("nessun Bollettino nell'elenco di dati.camera.it")
    presenti = set(lago.chiavi(NOME))
    # i giorni mai scaricati, dal più recente; più gli ultimi giorni, che la Camera completa dopo
    mancanti = [g for g in reversed(giorni) if chiave(g, leg, "indice") not in presenti]
    da_fare = list(dict.fromkeys(giorni[-ricontrolla:][::-1] + mancanti))[:massimo]
    pagine = nuove = 0
    fallite = []
    for giorno in da_fare:
        a, m, g = giorno[:4], giorno[4:6], giorno[6:]
        try:
            url = INDICE.format(leg=leg, a=a, m=m, g=g)
            indice = _get(url)
            if indice is None:
                continue
            for codice in codici(indice):
                c = codice.decode()
                for file, parte in (("comunic", f"c{c}"), ("allegato", f"c{c}-allegati")):
                    u = PAGINA.format(leg=leg, a=a, m=m, g=g, codice=c, file=file)
                    corpo = _get(u)
                    time.sleep(pausa)
                    if corpo is not None:
                        nuove += lago.salva(NOME, chiave(giorno, leg, parte), corpo, u, "htm")["nuovo"]
                        pagine += 1
            # l'indice si salva per ultimo: segna il giorno come fatto solo se tutte le pagine sono arrivate
            lago.salva(NOME, chiave(giorno, leg, "indice"), indice, url, "htm")
        except Exception as e:  # un giorno che non risponde non ferma gli altri; il passo fallisce alla fine
            fallite.append(f"{giorno}: {str(e)[:120]}")
    rimandati = max(0, len(mancanti) - massimo)
    ctx.log(f"{NOME}: {len(da_fare)} giorni, {pagine} pagine ({nuove} nuove o cambiate), {rimandati} giorni rimandati")
    if fallite:
        raise RuntimeError(f"{len(fallite)} giorni non scaricati, si riprendono al giro dopo: {fallite[:5]}")
    return {"giorni": len(da_fare), "pagine": pagine, "nuove": nuove, "rimandati": rimandati}
