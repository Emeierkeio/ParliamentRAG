"""L'HTML delle conversazioni condivise, ripulito: restano solo i tag e gli attributi che le risposte del sito usano.

Chi condivide manda al server l'HTML della pagina (POST /api/condividi) e chi apre il link lo vede inserito nella pagina:
senza questo filtro chiunque potrebbe salvare uno script che gira su www.parliamentrag.it. Via script, stili,
iframe e moduli, ogni attributo «on…», gli indirizzi javascript: e data:, e gli stili con url() o expression().
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

TAG = {
    "a", "abbr", "article", "aside", "b", "blockquote", "br", "button", "caption", "cite", "code", "dd", "del", "details",
    "div", "dl", "dt", "em", "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "i",
    "img", "ins", "kbd", "li", "mark", "nav", "ol", "p", "pre", "q", "s", "section", "small", "span", "strong", "sub",
    "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "time", "tr", "u", "ul",
    # icone e grafici
    "svg", "g", "path", "circle", "ellipse", "line", "polyline", "polygon", "rect", "text", "tspan", "title", "defs",
    "lineargradient", "stop", "clippath", "use",
}
VUOTI = {"br", "hr", "img"}
ATTRIBUTI = {
    "class", "id", "href", "target", "rel", "title", "alt", "src", "width", "height", "style", "role", "tabindex",
    "colspan", "rowspan", "datetime", "open", "hidden", "type", "lang", "translate", "loading", "decoding",
    # svg
    "viewbox", "d", "fill", "fill-opacity", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
    "stroke-dasharray", "stroke-opacity", "opacity", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "x2", "y1", "y2",
    "points", "transform", "text-anchor", "font-size", "font-weight", "dominant-baseline", "offset", "stop-color",
    "preserveaspectratio", "focusable", "xmlns", "gradientunits", "clip-path", "pathlength",
}
INDIRIZZO = re.compile(r"^\s*(https?:|mailto:|#|/(?!/)|\.{0,2}/|[\w.-]+(?:[/?#]|$))", re.I)
STILE_VIETATO = re.compile(r"url\s*\(|expression\s*\(|javascript:|@import|behavior\s*:", re.I)


def _attributo_buono(nome: str, valore: str) -> bool:
    if nome.startswith(("aria-", "data-")):
        return True
    if nome not in ATTRIBUTI:
        return False
    if nome in ("href", "src"):
        v = re.sub(r"[\x00-\x20]", "", html.unescape(valore))
        return bool(INDIRIZZO.match(v)) and not re.match(r"(javascript|data|vbscript):", v, re.I)
    if nome == "style":
        return not STILE_VIETATO.search(html.unescape(valore))
    return True


class _Pulitore(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.fuori: list[str] = []
        self.salta = 0                                   # dentro <script>, <style>, … : si butta anche il contenuto

    def handle_starttag(self, tag, attrs):
        self._apri(tag, attrs, chiudi=False)

    def handle_startendtag(self, tag, attrs):
        self._apri(tag, attrs, chiudi=True)

    def _apri(self, tag, attrs, chiudi):
        if tag in ("script", "style", "iframe", "object", "embed", "template", "noscript", "textarea", "select"):
            if not chiudi:
                self.salta += 1
            return
        if self.salta or tag not in TAG:
            return
        buoni = "".join(f' {n}="{html.escape(v or "", quote=True)}"' for n, v in attrs if _attributo_buono(n.lower(), v or ""))
        self.fuori.append(f"<{tag}{buoni}{' /' if chiudi and tag not in VUOTI else ''}>")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "iframe", "object", "embed", "template", "noscript", "textarea", "select"):
            self.salta = max(0, self.salta - 1)
            return
        if not self.salta and tag in TAG and tag not in VUOTI:
            self.fuori.append(f"</{tag}>")

    def handle_data(self, dati):
        if not self.salta:
            self.fuori.append(html.escape(dati, quote=False))

    def handle_entityref(self, nome):
        if not self.salta:
            self.fuori.append(f"&{nome};")

    def handle_charref(self, nome):
        if not self.salta:
            self.fuori.append(f"&#{nome};")


def pulisci(testo: str) -> str:
    p = _Pulitore()
    p.feed(testo or "")
    p.close()
    return "".join(p.fuori)
