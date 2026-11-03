"""Dai dossier dei Servizi di documentazione ai record dello schema v3: un `Document {kind: dossier}` con titolo,
nota (per esempio «Elementi per la valutazione degli aspetti di legittimità costituzionale»), data, servizio, codice
del documento, atto a cui si riferisce e testo integrale. Trasformazione pura.

Il codice dice l'atto: AC0550 -> C. 550, AS0473b -> S. 473, AG0123 -> atto del Governo 123, D26162a -> decreto-legge
162 del 2026. La lettera finale è la versione (a, b, c… per le diverse fasi dell'esame).
"""

from __future__ import annotations

import hashlib
import html
import re
from html.parser import HTMLParser

MESI = {f"{i:02d}": i for i in range(1, 13)}


class _Testo(HTMLParser):
    """Testo di una pagina HTML: niente script e stili, un a capo per blocco."""

    BLOCCHI = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "td"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parti, self.salta = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.salta += 1
        elif tag in self.BLOCCHI:
            self.parti.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.salta:
            self.salta -= 1

    def handle_data(self, data):
        if not self.salta:
            self.parti.append(data)


def testo_html(corpo: bytes) -> str:
    t = _Testo()
    t.feed(corpo.decode("utf-8", errors="replace"))
    s = re.sub(r"[ \t\r\f\v\xa0]+", " ", "".join(t.parti))
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r" *\n *", "\n", s)).strip()


def metadati_elenco(pagina: bytes) -> dict[str, dict]:
    """Dall'elenco: per ogni dossier data, servizio, titolo e nota."""
    t = pagina.decode("utf-8", errors="replace")
    out = {}
    for blocco in t.split('<a class="dossier-home-link"')[1:]:
        ident = re.search(r"/dossier/(OCD[\d-]+)/", blocco)
        if not ident:
            continue
        campo = lambda c: (lambda m: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip() if m else None)(
            re.search(rf'<div class="{c}">(.*?)</div>', blocco, re.S))
        titolo = re.search(r'<div class="dossier-list-title">(.*?)<div class="dossier-list-mdash"', blocco, re.S)
        g = (campo("dossier-list-date") or "").split()
        out[ident.group(1)] = {"date": f"{g[2]}-{g[1]}-{g[0]}" if len(g) == 3 else None, "service": campo("dossier-list-dep"),
                               "title": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", titolo.group(1)))).strip() if titolo else campo("dossier-list-title"),
                               "note": campo("dossier-list-note")}
    return out


def atto_da_codice(codice: str | None) -> list[str]:
    m = re.match(r"^(AC|AS|AG|D)(\d+)[a-z]*$", codice or "")
    if not m:
        return []
    tipo, n = m.groups()
    if tipo == "D":
        return [f"dl:{int(n[2:])}/20{n[:2]}"] if len(n) >= 3 else []
    return [f"{ {'AC': 'ac', 'AS': 'as', 'AG': 'ag'}[tipo] }:{int(n)}".replace(" ", "")]


def trasforma(scheda: bytes, testo: bytes | None, meta: dict, fonte: dict, leg: int = 19) -> dict:
    ident = re.search(r"-dossier-(OCD[\d-]+)-scheda$", fonte["chiave"]).group(1)
    link = re.search(rb'data-link="https://documenti\.camera\.it/leg\d+/dossier/testi/([^".?]+)\.htm', scheda)
    codice = link.group(1).decode() if link else None
    t = testo_html(testo) if testo else None
    m = meta.get(ident, {})
    if not m.get("title"):
        og = re.search(rb'<meta property="og:title" content="([^"]*)"', scheda)
        m = {**m, "title": html.unescape(og.group(1).decode()) if og else None}
    u = f"it:camera:{leg}:dossier:{ident}"
    nodo = {"label": "Document", "uri": u, "kind": "dossier", "date": m.get("date"), "title": m.get("title"), "hearing": m.get("note"),
            "author_raw": m.get("service"), "code": codice, "acts": atto_da_codice(codice), "url": fonte.get("url"), "format": "html",
            "third_party": False, "hash": hashlib.sha256((t or ident).encode()).hexdigest()[:16], "source": "camera_dossier",
            "text_ref": f"document:{u}" if t else None}
    return {"nodi": [nodo], "archi": [], "testi": [{"ref": f"document:{u}", "text": t, "hash": nodo["hash"]}] if t else [],
            "ambito": {"kind": "dossier", "chamber": "camera", "legislature": leg, "source_key": fonte["chiave"]}}
