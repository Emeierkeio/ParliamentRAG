"""Documenti acquisiti dalle commissioni: dagli elenchi i metadati (chi l'ha mandato, per quale audizione o atto,
quando), dai file il testo. Due trasformazioni pure che riempiono la stessa riga di `document`.

Testo: PDF con pypdf (via di Mirko del 31/10/2026; cryptography per i PDF cifrati, 2/11/2026), DOCX e PPTX con la libreria
standard (sono zip di XML). DOC, PPT, XLSX e firmati p7m restano senza testo: il documento c'è, il testo no.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET

from ..fonti.camera_documenti import chiave_file, elenco

ATTI = [(re.compile(r"\bAG\s*(\d+)"), "ag"), (re.compile(r"\bC\.\s*(\d+[\w-]*)"), "ac"), (re.compile(r"\bDoc\.\s*([IVXLC]+[-\w]*\s*n\.\s*\d+)"), "doc")]


def _h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def uri_documento(chiave: str) -> str:
    """leg19-doc-com01-103199-20261023142631054 -> it:camera:19:doc:com01-103199-20261023142631054."""
    m = re.match(r"leg(\d+)-doc-(.+)$", chiave)
    return f"it:camera:{m.group(1)}:doc:{m.group(2)}"


def _data(chiave: str) -> str | None:
    m = re.search(r"-(\d{4})(\d\d)(\d\d)\d{9}$", chiave)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _autore(titolo: str) -> str | None:
    """«AG 439 - Memoria UIL FP» -> «UIL FP»; «C. 2562 - Contributo scritto AGIA» -> «AGIA»."""
    t = re.sub(r"^(AG\s*\d+|C\.\s*[\d\w-]+(?:\s*e\s*abb\.)?|Doc\.[^-]+)\s*-?\s*", "", titolo.strip(), flags=re.I)
    t = re.sub(r"^(Memoria|Contributo scritto|Documentazione|Nota|Documento|Presentazione)\s*(di|del|della|dell'|dei|degli)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*\(\d{2}/\d{2}/\d{4}\)\s*$", "", t).strip(" -")
    return t or None


def trasforma_elenco(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    codice = re.search(r"-c(\d{2})-", fonte.get("chiave", "")).group(1)
    nodi = {}
    for v in elenco(corpo):
        k = chiave_file(v["url"], leg)
        if not k.startswith(f"leg{leg}-doc-com") or not v["url"].startswith("http"):
            continue                                              # link che non sono file della commissione, o al server interno
        nome = v["url"].rsplit("/", 1)[-1]
        tipo = "memorandum" if ".Memoria." in nome else "written_contribution" if "Contributo" in nome else "document"
        seduta = re.search(r"(\d{2})/(\d{2})/(\d{4})", v["seduta"] or "")
        atti = [f"{t}:{m.group(1).strip()}" for rx, t in ATTI for m in rx.finditer(v["titolo"] + " " + (v["descrizione"] or "")[:300])]
        u = uri_documento(k)
        nodi[u] = {"label": "Document", "uri": u, "kind": tipo, "date": _data(k), "body_code": codice,
                   "body": f"it:camera:{leg}:body:o{leg}_35{codice}", "title": v["titolo"], "author_raw": _autore(v["titolo"]),
                   "hearing": v["descrizione"], "sitting_date": f"{seduta.group(3)}-{seduta.group(2)}-{seduta.group(1)}" if seduta else None,
                   "acts": list(dict.fromkeys(atti)), "url": v["url"], "format": nome.rsplit(".", 1)[-1].lower(), "third_party": True,
                   "source": "camera_documenti"}
    return {"nodi": list(nodi.values()), "archi": [], "testi": [],
            "ambito": {"kind": "documenti_elenco", "chamber": "camera", "legislature": leg, "source_key": fonte.get("chiave")}}


def _testo_pdf(corpo: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # la pipeline gira con .venv/bin/python, dove pypdf è installata
        raise RuntimeError("manca pypdf: lanciare la pipeline con .venv/bin/python (vedi requirements.txt)") from e
    lettore = PdfReader(io.BytesIO(corpo))     # i PDF cifrati con AES chiedono cryptography (requirements.txt)
    return "\n\n".join((p.extract_text() or "").strip() for p in lettore.pages)


def _testo_zip(corpo: bytes, parti: str) -> str:
    """DOCX (word/document.xml) e PPTX (ppt/slides/slideN.xml): il testo dei nodi <w:t> o <a:t>, un paragrafo per riga."""
    with zipfile.ZipFile(io.BytesIO(corpo)) as z:
        nomi = sorted((n for n in z.namelist() if re.fullmatch(parti, n)), key=lambda n: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", n)])
        righe = []
        for n in nomi:
            radice = ET.fromstring(z.read(n))
            for par in radice.iter():
                if par.tag.endswith("}p"):
                    riga = "".join(x.text or "" for x in par.iter() if x.tag.endswith("}t"))
                    if riga.strip():
                        righe.append(riga.strip())
        return "\n".join(righe)


def testo(corpo: bytes, formato: str) -> str | None:
    if formato == "pdf":
        return _testo_pdf(corpo)
    if formato == "docx":
        return _testo_zip(corpo, r"word/document\.xml")
    if formato == "pptx":
        return _testo_zip(corpo, r"ppt/slides/slide\d+\.xml")
    return None


def trasforma_file(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    k = fonte["chiave"]
    formato = (fonte.get("file") or fonte.get("url") or "").rsplit(".", 1)[-1].lower()
    t = testo(corpo, formato)
    # pypdf a volte restituisce surrogati isolati, che non si codificano in UTF-8
    t = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", re.sub(r"[\ud800-\udfff\x00]", "", t))).strip() if t else None
    u = uri_documento(k)
    nodo = {"label": "Document", "uri": u, "format": formato, "pages_text": bool(t), "text_ref": f"document:{u}" if t else None,
            "hash": _h(t) if t else hashlib.sha256(corpo).hexdigest()[:16]}
    return {"nodi": [nodo], "archi": [], "testi": [{"ref": f"document:{u}", "text": t, "hash": _h(t)}] if t else [],
            "ambito": {"kind": "documento_testo", "chamber": "camera", "legislature": leg, "source_key": k}}
