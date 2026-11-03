"""Dal testo stampato di un progetto di legge (HTML) al testo della versione, ai suoi articoli e alle norme citate
(i link a Normattiva, con l'URN: urn:nir:stato:decreto.legge:2026-09-10;157). Trasformazione pura.

La versione è la stessa riga di `act_version` creata dagli atti: si riconosce dal codice nell'indirizzo.
"""

from __future__ import annotations

import hashlib
import html
import re

from .camera_dossier import testo_html


def _pulito(frammento: str) -> str:
    return testo_html(frammento.encode("utf-8"))


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    t = corpo.decode("utf-8", errors="replace")
    codice = re.search(r"-testo-([\w.]+)$", fonte["chiave"]).group(1)
    i = t.find('id="DC"')
    if i < 0:                                              # stampato senza articoli: frontespizio e pareri del visualizzatore
        i = t.find('id="docviewer_full_content"')
    testo_intero = _pulito(t[t.rfind("<div", 0, i):]) if i > 0 else _pulito(t)
    for coda in ("Torna alla pagina di provenienza", "Per tornare alla pagina di provenienza", "Camera dei deputati ©"):
        testo_intero = testo_intero.split(coda)[0].rstrip()
    articoli = []
    for m in re.finditer(r'<div class="articolo" id="([^"]+)">(.*?)(?=<div class="articolo"|<div id="AL|</body>)', t, re.S):
        articoli.append({"anchor": m.group(1), "number": (re.search(r"Art\.\s*([\w-]+)", m.group(2)) or [None, None])[1],
                         "text": _pulito(m.group(2))})
    citazioni = {}
    for u, testo in re.findall(r'<a href="https?://www\.normattiva\.it/uri-res/N2Ls\?(urn:nir:[^"#]+)"[^>]*>(.*?)</a>', t, re.S):
        citazioni.setdefault(html.unescape(u), re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", testo))).strip())
    nodo = {"label": "TextVersion", "code": codice, "hash": hashlib.sha256(testo_intero.encode()).hexdigest()[:16],
            "articles": articoli, "citations": [{"urn": k, "label": v} for k, v in citazioni.items()]}
    # pagina «Documento non disponibile»: la versione c'è ma il testo non ancora, e non si carica come testo
    assente = not articoli and testo_intero.strip() == "Documento non disponibile"
    if assente:
        nodo["incomplete_at_source"] = True
    return {"nodi": [nodo], "archi": [], "testi": [] if assente else [{"ref": f"version:{codice}", "text": testo_intero, "hash": nodo["hash"]}],
            "ambito": {"kind": "testo_atto", "chamber": "camera", "legislature": leg, "code": codice, "source_key": fonte.get("chiave")}}
