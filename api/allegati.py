"""Bozze allegate alla chat (card 284): il testo di un file .docx o .pdf, oppure un testo lungo incollato, diviso in
emendamenti e confrontato con quelli già presentati. Il file non si conserva: se ne legge solo il testo. Niente librerie
nuove: un .docx è un archivio zip di XML, i PDF si leggono con pypdf (già fra le dipendenze). Niente OCR: un PDF fatto
di immagini non ha testo, e lo si dice.

Limiti (decisi il 10/11/2026): al più 50.000 caratteri e 20 emendamenti per allegato; un allegato vale 3 domande."""

from __future__ import annotations

import base64
import io
import re
import zipfile
from xml.etree import ElementTree as ET

CARATTERI_MAX = 50_000
EMENDAMENTI_MAX = 20
BYTE_MAX = 5_000_000
DOMANDE = 3                                  # quanto vale un allegato nei limiti per utente

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class AllegatoNonLeggibile(ValueError):
    pass


def _docx(dati: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(dati)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise AllegatoNonLeggibile("il file .docx non si apre") from e
    radice = ET.fromstring(xml)
    righe = []
    for p in radice.iter(f"{W}p"):
        pezzi = []
        for n in p.iter():
            if n.tag == f"{W}t" and n.text:
                pezzi.append(n.text)
            elif n.tag in (f"{W}tab",):
                pezzi.append("\t")
            elif n.tag in (f"{W}br", f"{W}cr"):
                pezzi.append("\n")
        righe.append("".join(pezzi))
    return "\n".join(righe)


def _pdf(dati: bytes) -> str:
    from pypdf import PdfReader
    try:
        r = PdfReader(io.BytesIO(dati))
        if r.is_encrypted:
            r.decrypt("")
        return "\n".join((pg.extract_text() or "") for pg in r.pages[:60])
    except Exception as e:                    # noqa: BLE001 — pypdf alza errori di molti tipi su file rovinati
        raise AllegatoNonLeggibile("il PDF non si apre") from e


def testo_da_file(nome: str, dati_b64: str) -> str:
    """Il testo di un .docx o di un .pdf (in base64), ripulito e tagliato a CARATTERI_MAX."""
    try:
        dati = base64.b64decode(dati_b64, validate=False)
    except ValueError as e:
        raise AllegatoNonLeggibile("il file non è arrivato intero") from e
    if len(dati) > BYTE_MAX:
        raise AllegatoNonLeggibile("il file supera 5 MB")
    basso = nome.lower()
    if basso.endswith(".docx") or dati[:2] == b"PK":
        t = _docx(dati)
    elif basso.endswith(".pdf") or dati[:4] == b"%PDF":
        t = _pdf(dati)
    else:
        raise AllegatoNonLeggibile("si leggono solo file .docx e .pdf")
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t).strip()
    if len(t) < 20:
        raise AllegatoNonLeggibile("nel file non c'è testo da leggere (un PDF fatto di immagini non si legge)")
    return t[:CARATTERI_MAX]


# l'inizio di un emendamento: un numero da solo su una riga («1.1», «Em. 3.0.2», «Art. 5-bis»), oppure le formule con
# cui comincia il testo («Al comma 2…», «Dopo l'articolo 4…», «Sopprimere…», «Sostituire…»)
INIZIO = re.compile(r"""^\s*(?:
      (?:em(?:endamento)?\.?\s*|art(?:icolo)?\.?\s*)?(?:n\.\s*)?\d+(?:[.\-]\d+|[.\-]?[a-z]+)*\.?\s*$
    | (?:emendamento|subemendamento|articolo\s+aggiuntivo)\b.*$
    | (?:al(?:l')?\s*(?:comma|articolo|allegato|capo)|dopo\s+l'articolo|dopo\s+il\s+comma|sopprimer\w*|sostituir\w*|aggiunger\w*|inserir\w*|premetter\w*)\b
    )""", re.I | re.X)


def dividi(testo: str) -> list[str]:
    """Il testo diviso in emendamenti; se non si riconosce una divisione, un pezzo solo. Al più EMENDAMENTI_MAX + 1
    pezzi: l'ultimo dice che ce ne sono altri."""
    righe = testo.splitlines()
    pezzi, corrente = [], []
    for r in righe:
        if INIZIO.match(r) and any(x.strip() for x in corrente):
            # un numero da solo apre un emendamento; una formula lo apre solo se il pezzo precedente ha già una formula
            solo_numero = re.match(r"^\s*(?:em(?:endamento)?\.?\s*|art(?:icolo)?\.?\s*)?(?:n\.\s*)?\d", r, re.I) and len(r.strip()) < 20
            precedente = "\n".join(corrente)
            if solo_numero or re.search(r"sopprimer|sostituir|aggiunger|inserir|premetter|sono sostituit|è inserit|sono aggiunt", precedente, re.I):
                pezzi.append(precedente.strip())
                corrente = []
        corrente.append(r)
    if any(x.strip() for x in corrente):
        pezzi.append("\n".join(corrente).strip())
    # i numeri soli restano attaccati al testo che li segue
    uniti: list[str] = []
    for p in pezzi:
        if uniti and len(uniti[-1]) < 20 and "\n" not in uniti[-1] and re.match(r"^\s*(?:em(?:endamento)?\.?\s*|art(?:icolo)?\.?\s*)?(?:n\.\s*)?\d", uniti[-1], re.I):
            uniti[-1] = f"{uniti[-1]}\n{p}"
        else:
            uniti.append(p)
    # via i titoli e le righe sparse: resta ciò che ha una formula di emendamento o è abbastanza lungo da essere un testo
    formula = re.compile(r"sopprimer|sostituir|aggiunger|inserir|premetter|sono sostituit|è inserit|sono aggiunt|è aggiunt|è soppress", re.I)
    uniti = [p for p in uniti if formula.search(p) or len(p) >= 120] or [testo.strip()]
    return uniti


def confronta(c, testo: str) -> dict:
    """Per ogni emendamento della bozza (al più EMENDAMENTI_MAX), i tre più simili già presentati, con l'esito."""
    from .strumenti import emendamenti
    pezzi = dividi(testo)
    altri = max(0, len(pezzi) - EMENDAMENTI_MAX)
    out = []
    for i, p in enumerate(pezzi[:EMENDAMENTI_MAX], 1):
        r = emendamenti.cerca(c, testo=p[:6000], limit=3)
        out.append({"n": i, "inizio": p[:240], "simili": [
            {k: x.get(k) for k in ("uri", "sigla_atto", "titolo_atto", "link_atto", "numero", "ramo", "sede", "data", "gruppi",
                                   "esito", "etichetta", "fonte", "similarita")} | {"testo": x["testo"][:300]}
            for x in r["items"]]})
    return {"emendamenti": out, "altri_non_controllati": altri, "caratteri": len(testo)}
