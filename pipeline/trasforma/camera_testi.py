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


def _testo_a_fronte(t: str) -> list[dict]:
    """Stampato «A» con il testo a fronte: una tabella a due colonne, a sinistra il testo presentato e a destra quello
    della commissione, con i titoli d'articolo in <p class="articolo" title="art.1">. Gli articoli sono quelli di destra;
    dove la commissione non ha cambiato niente la cella dice solo «Identico» (o «1. Identico:») e vale quella di sinistra."""
    destra = ""
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        celle = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(re.findall(r'<td[^>]*width="50%"', r)) != 2 or len(celle) != 2:
            continue
        identico = re.fullmatch(r"(?:[\w-]+[.)]\s*)?Identic[oa]\s*[.:]?", _pulito(celle[1]).strip())
        destra += celle[0] if identico else celle[1]
    titoli = list(re.finditer(r'<p class="articolo" title="art\.([\w-]+)"', destra))
    return [{"anchor": f"art{m.group(1)}", "number": m.group(1),
             "text": _pulito(destra[m.start():titoli[i + 1].start() if i + 1 < len(titoli) else len(destra)])}
            for i, m in enumerate(titoli)]


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
    if not articoli:
        articoli = _testo_a_fronte(t)
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
