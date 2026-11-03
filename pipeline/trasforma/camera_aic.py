"""Dagli atti di sindacato ispettivo e di indirizzo (OCD) ai record dello schema v3: `Act` con il testo, firmatari
(SPONSORS), ministeri destinatari (ADDRESSED_TO), temi EuroVoc (SUBJECT). Un mese di presentazione per volta.

L'uri segue il numero dell'atto: «5/04321» -> it:camera:19:aic:5-04321, come i riferimenti del Bollettino
(«aic:5-04321») e dei voti (aic9_00080_004_19 -> ordine del giorno 9-00080-004).
"""

from __future__ import annotations

import html
import re

from ..fonti.camera_aic import leggi
from .camera_anagrafica import data, id_persona

TIPI = {"INTERROGAZIONE A RISPOSTA SCRITTA": "written_question", "INTERROGAZIONE A RISPOSTA ORALE": "oral_question",
        "INTERROGAZIONE A RISPOSTA IN COMMISSIONE": "committee_question", "INTERROGAZIONE A RISPOSTA IMMEDIATA": "question_time",
        "INTERPELLANZA": "interpellation", "INTERPELLANZA URGENTE": "urgent_interpellation", "MOZIONE": "motion",
        "RISOLUZIONE IN ASSEMBLEA": "resolution", "RISOLUZIONE IN COMMISSIONE": "committee_resolution",
        "RISOLUZIONE CONCLUSIVA": "concluding_resolution", "ODG - ORDINE DEL GIORNO IN ASSEMBLEA": "agenda_order",
        "ODG - ORDINE DEL GIORNO IN COMMISSIONE": "committee_agenda_order"}


def uri_aic(numero: str, leg: int, ramo: str = "camera") -> str:
    return f"it:{ramo}:{leg}:aic:{numero.strip().replace('/', '-')}"


def _persona(uri: str) -> str | None:
    """Deputati come alla Camera; i senatori hanno su dati.camera.it un id della Camera (senatore.rdf/s308972_19):
    si tiene quello, it:person:camera:308972, finché la corrispondenza con l'id di dati.senato.it non li unisce."""
    m = re.search(r"/senatore\.rdf/s(\d+)", uri or "")
    return f"it:person:camera:{m.group(1)}" if m else id_persona(uri)


def _ministero(uri: str) -> str | None:
    """organoGoverno.rdf/og202_285 -> it:gov:202:og202_285 (come in camera_governo)."""
    m = re.search(r"/(og(\d+)_\d+)$", uri or "")
    return f"it:gov:{m.group(2)}:{m.group(1)}" if m else None


def _testo(t: str | None) -> str | None:
    if not t:
        return None
    return re.sub(r"\s+", " ", html.unescape(html.unescape(t))).strip()


def trasforma(corpo: bytes, fonte: dict, leg: int = 19, ramo: str = "camera") -> dict:
    d = leggi(corpo)
    nodi: dict[str, dict] = {}
    numero_di: dict[str, str] = {}
    for r in d["atti"]:
        u = uri_aic(r["numero"], leg, ramo)
        numero_di[r["aic"]] = u
        if u in nodi:
            continue
        nodi[u] = {"label": "Act", "uri": u, "chamber": ramo, "legislature": leg, "number": r["numero"].strip(),
                   "kind": TIPI.get(r["tipo"], "other_inspection"), "kind_raw": r["tipo"], "title": _testo(r.get("titolo")),
                   "text": _testo(r.get("testo")), "date": data(r.get("inizio")), "closed_date": data(r.get("fine")),
                   "concluded": None if r.get("concluso") in (None, "") else r["concluso"] == "1",
                   "card_url": r.get("url"), "source": "ocd", "source_uri": r["aic"]}
    archi = []
    firme: dict[tuple, bool] = {}   # la stessa persona può comparire come primo e come altro firmatario: vince «primo»
    for r in d["firmatari"]:
        if r["aic"] in numero_di and _persona(r["deputato"]):
            k = (_persona(r["deputato"]), numero_di[r["aic"]])
            firme[k] = firme.get(k, False) or r["primo"] == "1"
    archi += [{"type": "SPONSORS", "from": p, "to": a, "first": primo} for (p, a), primo in firme.items()]
    for r in d["destinatari"]:
        if r["aic"] in numero_di and _ministero(r["destinatario"]):
            archi.append({"type": "ADDRESSED_TO", "from": numero_di[r["aic"]], "to": _ministero(r["destinatario"])})
    for r in d["temi"]:
        if r["aic"] in numero_di:
            archi.append({"type": "SUBJECT", "from": numero_di[r["aic"]], "to": r["tema"]})
    visti, unici = set(), []
    for a in archi:
        k = (a["type"], a["from"], a["to"], a.get("first"))
        if k not in visti:
            visti.add(k)
            unici.append(a)
    return {"nodi": list(nodi.values()), "archi": unici, "testi": [],
            "ambito": {"kind": "aic", "chamber": ramo, "legislature": leg, "source_key": fonte.get("chiave")}}


def trasforma_senato(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    return trasforma(corpo, fonte, leg, "senato")
