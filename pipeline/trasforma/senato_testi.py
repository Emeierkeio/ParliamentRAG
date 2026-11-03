"""Dai testi dei ddl del Senato in Akoma Ntoso (bulk data su GitHub) agli stessi record dei testi della Camera: il
testo della versione e i suoi articoli. Tre versioni: il testo presentato (`ddlpres`), il testo della commissione con
la relazione (`ddlcomm`), il messaggio trasmesso alla Camera (`ddlmess`). Trasformazione pura.

Il codice della versione è l'id del testo nella banca dati del Senato (`senato.19.01496679`); la versione si lega
all'atto con `act` (il primo ddl nominato: «1695 e 762-A» è il 1695) e porta il tipo in `kind`.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03}"
TIPI = {"ddlpres": "presented", "ddlcomm": "committee", "ddlmess": "message"}
BLOCCHI = {AKN + t for t in ("p", "heading", "num", "td", "docTitle", "docProponent", "docStatus", "docNumber")}


def _riga(e: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(e.itertext())).strip()


def _righe(e: ET.Element) -> list[str]:
    """Le righe di testo nell'ordine del documento: i blocchi più esterni fra paragrafi, titoli e celle."""
    out = []

    def giu(x: ET.Element) -> None:
        if x.tag in BLOCCHI:
            t = _riga(x)
            if t:
                out.append(t)
            return
        for c in x:
            giu(c)
    giu(e)
    # il numero del comma o della lettera sta in un elemento a parte: va in testa alla riga dopo («1. Nel rispetto…»)
    unite: list[str] = []
    for t in out:
        if unite and re.fullmatch(r"\d+(-\w+)?\.|[a-z]{1,2}\)", unite[-1]):
            unite[-1] = f"{unite[-1]} {t}"
        else:
            unite.append(t)
    return unite


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    m = re.search(r"-testo-(ddl\w+)-(\d+)$", fonte["chiave"])
    tipo, idtesto = m.group(1), m.group(2)
    r = ET.fromstring(corpo)
    uri_fonte = r.find(f".//{AKN}FRBRWork/{AKN}FRBRuri").get("value")         # …/osr/Ddl/2026-03-05/1695 e 762-A
    numero = re.search(r"/Ddl/\d{4}-\d{2}-\d{2}/\s*(\d+(?:-bis|-ter)?)", uri_fonte)
    codice = f"senato.{leg}.{idtesto}"
    righe = []
    for parte in r.iter():
        if parte.tag in (AKN + "coverPage", AKN + "preface", AKN + "mainBody", AKN + "body"):
            righe += _righe(parte)
    if sum(len(x) for x in righe) < 200:                  # fuori dalle parti note (i messaggi brevi): tutti i paragrafi
        righe += [t for t in (_riga(p) for p in r.iter(AKN + "p")) if t]
    testo = "\n\n".join(dict.fromkeys(righe)) if righe else ""
    articoli = []
    for a in r.iter(AKN + "article"):
        num = a.find(AKN + "num")
        n = re.search(r"Art\.\s*([\w-]+)", _riga(num)) if num is not None else None
        articoli.append({"anchor": a.get("id"), "number": n.group(1) if n else None, "text": "\n\n".join(_righe(a))})
    h = hashlib.sha256(testo.encode()).hexdigest()[:16]
    nodo = {"label": "TextVersion", "code": codice, "hash": h, "articles": articoli, "citations": [],
            "act": f"it:senato:{leg}:ddl:{numero.group(1)}" if numero else None, "kind": TIPI.get(tipo, tipo), "source_uri": uri_fonte,
            # alcuni messaggi alla Camera nel bulk hanno solo l'attestazione, senza il testo: è così anche alla fonte
            "incomplete_at_source": len(testo) < 200 and not articoli and "Attesto che il Senato" in testo}
    return {"nodi": [nodo], "archi": [], "testi": [{"ref": f"version:{codice}", "text": testo, "hash": h}],
            "ambito": {"kind": "testo_atto", "chamber": "senato", "legislature": leg, "code": codice, "source_key": fonte.get("chiave")}}
