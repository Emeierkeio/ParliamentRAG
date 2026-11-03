"""Interrogazioni SPARQL agli endpoint pubblici (dati.camera.it, dati.senato.it), a pagine e con nuovi tentativi.

Le query devono avere ORDER BY: a pagine, senza un ordine fisso, l'endpoint può restituire righe doppie o saltarne.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "parliamentrag-pipeline (www.parliamentrag.it)"


def _richiesta(endpoint: str, q: str, tentativi: int) -> list[dict]:
    url = endpoint + "?" + urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    for t in range(1, tentativi + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                dati = json.load(r)
            return [{k: v["value"] for k, v in b.items()} for b in dati["results"]["bindings"]]
        except urllib.error.HTTPError as e:
            if e.code < 500 or t == tentativi:   # un 4xx non cambia riprovando, e con senato.it le richieste sbagliate pesano
                raise
            time.sleep(10 * t)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if t == tentativi:
                raise
            time.sleep(10 * t)


def per_chiave(endpoint: str, query: str, chiave: str, pagina: int = 8000, tentativi: int = 3, pausa: float = 0.5) -> list[dict]:
    """Paginazione per chiave: la query contiene `{FILTRO}` nel WHERE e finisce con ORDER BY ?<chiave>.

    Ogni pagina riparte dopo l'ultima chiave completa: le righe dell'ultima chiave della pagina si scartano e si
    richiedono alla pagina dopo, così una chiave con più righe non resta mai a metà. Serve dove OFFSET dà errore 500."""
    righe, ultima = [], ""
    while True:
        filtro = f'FILTER (STR(?{chiave}) > "{ultima}")' if ultima else ""
        blocco = _richiesta(endpoint, query.replace("{FILTRO}", filtro) + f"\nLIMIT {pagina}", tentativi)
        if len(blocco) < pagina:
            return righe + blocco
        coda = blocco[-1][chiave]
        completi = [r for r in blocco if r[chiave] != coda]
        if not completi:
            raise RuntimeError(f"una sola chiave ({coda}) supera la pagina di {pagina} righe")
        righe += completi
        ultima = completi[-1][chiave]
        time.sleep(pausa)


def interroga(endpoint: str, query: str, pagina: int = 5000, tentativi: int = 3, pausa: float = 0.5) -> list[dict]:
    """Tutte le righe della query, come dizionari di stringhe; le variabili assenti mancano dalla riga.

    dati.camera.it restituisce al massimo 10 mila righe per risposta e dà errore 500 se si pagina con OFFSET una query
    ordinata molto pesante: in quei casi si spezza la query (vedi camera_voti) e si controlla il totale con un COUNT."""
    righe, offset = [], 0
    while True:
        q = f"{query}\nLIMIT {pagina} OFFSET {offset}"
        url = endpoint + "?" + urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"})
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
        for t in range(1, tentativi + 1):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    dati = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code < 500 or t == tentativi:
                    raise
                time.sleep(10 * t)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                if t == tentativi:
                    raise
                time.sleep(10 * t)
        blocco = [{k: v["value"] for k, v in b.items()} for b in dati["results"]["bindings"]]
        righe.extend(blocco)
        if len(blocco) < pagina:
            return righe
        offset += pagina
        time.sleep(pausa)
