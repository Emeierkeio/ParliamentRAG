"""Dal resoconto sommario di una seduta di commissione del Senato (Akoma Ntoso, bulk data su GitHub) agli stessi
record del Bollettino della Camera: `Sitting` di commissione, `AgendaItem` per atto in esame con la sede
(«IN SEDE REFERENTE») e il ddl, `Speech` marcati `summary` (riassunti del funzionario, non citabili tra virgolette)
con la persona di dati.senato.it e la carica. Trasformazione pura.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import xml.etree.ElementTree as ET

from .senato_resoconto import GRUPPO, sigla

AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03}"
FONTE = "senato_sommcomm"


def _h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def _testo(e: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(e.itertext())).strip()


# un cognome in maiuscolo (non «nZEB») e la sigla fra parentesi, anche con una parentesi dentro
ORATORE = re.compile(r"(?<![\w'-])([A-ZÀ-Ý][A-ZÀ-Ý']+(?: [A-ZÀ-Ý][A-ZÀ-Ý']+)*)\s*" + GRUPPO.pattern[1:-1])


def _gruppo(t: str) -> str | None:
    """Il gruppo scritto dopo il primo cognome in maiuscolo: «Il senatore PIRONDINI ( M5S ) chiede…» -> «M5S»,
    «GUIDI ( Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP )» per intero. Non «COM(2025)», «(Atto n. 4)», né «LEP (CLEP)»."""
    for m in ORATORE.finditer(t):
        g = m.group(2).strip()
        if sigla(g) and m.group(1).split()[-1] not in g:      # «LEP (CLEP)»: la sigla che scioglie la parola prima
            return g
    return None


def codice_organo(segmento: str) -> str:
    """«7ªCommissionepermanente» -> «7commissionepermanente»: il codice dell'organo nell'uri della seduta."""
    t = unicodedata.normalize("NFKD", segmento).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", t.lower())


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    r = ET.fromstring(corpo)
    uri_fonte = r.find(f".//{AKN}FRBRWork/{AKN}FRBRuri").get("value")       # …/SOMMCOMM/7ªCommissionepermanente/2026-10-14/344
    m = re.search(r"/SOMMCOMM/([^/]+)/(\d{4}-\d{2}-\d{2})/(\d+)", uri_fonte)
    organo, data, numero = codice_organo(m.group(1)), m.group(2), int(m.group(3))
    nome = next((e.get("showAs") for e in r.iter(AKN + "TLCOrganization") if e.get("id") == "commissione"), m.group(1))
    persone = {e.get("id"): e.get("href") for e in r.iter(AKN + "TLCPerson")}
    ruoli = {e.get("id"): e.get("showAs") for e in r.iter(AKN + "TLCRole")}
    s_uri = f"it:senato:{leg}:som:{organo}:sed{numero:04d}"
    ora = r.find(f".//{AKN}recordedTime")
    seduta = {"label": "Sitting", "uri": s_uri, "chamber": "senato", "body_code": organo, "body_name": nome, "number": numero, "date": data,
              "status": "held", "kind": "committee_summary", "source": FONTE, "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta"),
              "start_time": (ora.get("time") or "")[:5] or None if ora is not None else None}
    nodi, archi, testi = [seduta], [], []
    servizio = {"label": "AgendaItem", "uri": f"{s_uri}:tit00000", "order": 0, "title": None, "stage": None, "acts": [], "service": True}
    punti: list[dict] = []

    def interventi(contenitore: ET.Element, punto: dict) -> None:
        for e in contenitore:
            if e.tag == AKN + "speech":
                chi = persone.get((e.get("by") or "").lstrip("#")) or ""
                ruolo = ruoli.get((e.get("as") or "").lstrip("#"))
                t = "\n\n".join(x for x in (_testo(p) for p in e.findall(AKN + "p")) if x)
                persona = re.search(r"/Persona/(\d+)$", chi)
            elif e.tag == AKN + "narrative":
                t, persona, ruolo = _testo(e), None, None
            else:
                continue
            if not t:
                continue
            punto.setdefault("_n", 0)
            punto["_n"] += 1
            u = f"{punto['uri']}:p{punto['_n']}"
            nodi.append({"label": "Speech", "uri": u, "order": punto["_n"], "kind": "summary", "hash": _h(t), "text_ref": f"speech:{u}",
                         "speaker_label": None, "declared_group": _gruppo(t) if persona else None, "as_office": ruolo if persona and ruolo not in ("senatore", "deputato") else None,
                         "anchor": e.get("id")})
            archi.append({"type": "HAS_SPEECH", "from": punto["uri"], "to": u, "order": punto["_n"]})
            if persona:
                archi.append({"type": "BY", "from": u, "to": f"it:person:senato:{persona.group(1)}", "as_group": None, "as_office": nodi[-1]["as_office"]})
            testi.append({"ref": f"speech:{u}", "text": t, "hash": _h(t)})

    corpo_dibattito = r.find(f".//{AKN}debateBody")
    for sez in corpo_dibattito.findall(AKN + "debateSection"):
        sede = _testo(sez.find(AKN + "heading")) if sez.find(AKN + "heading") is not None else None
        figli = sez.findall(AKN + "debateSection")
        if not figli:                                         # inizio e fine seduta, comunicazioni: punto di servizio
            interventi(sez, servizio)
            continue
        interventi(sez, servizio)
        for x in figli:
            atti = [f"{b.findtext(AKN + 'docType').lower()}:{(b.findtext(AKN + 'docNumber') or '').strip()}"
                    for b in x.findall(AKN + "block") if b.findtext(AKN + "docType") in ("DDL", "Doc") and (b.findtext(AKN + "docNumber") or "").strip()]
            titolo = next((_testo(b.find(AKN + "docTitle")) for b in x.findall(AKN + "block") if b.find(AKN + "docTitle") is not None), None) or x.get("name") or None
            p = {"label": "AgendaItem", "uri": f"{s_uri}:tit{len(punti) + 1:05d}", "order": len(punti) + 1, "title": titolo,
                 "stage": sede, "acts": atti, "service": False}
            punti.append(p)
            interventi(x, p)
    for p in [servizio] + punti:
        if p.get("_n") or p is not servizio:
            p.pop("_n", None)
            nodi.append(p)
            archi.append({"type": "HAS_ITEM", "from": s_uri, "to": p["uri"], "order": p["order"]})
            archi += [{"type": "ABOUT", "from": p["uri"], "to_ref": a} for a in p["acts"]]
    return {"nodi": nodi, "archi": archi, "testi": testi,
            "ambito": {"kind": "commissione", "chamber": "senato", "legislature": leg, "date": data, "body_code": organo,
                       "source": FONTE, "source_key": fonte.get("chiave")}}
