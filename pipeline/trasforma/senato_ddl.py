"""Dai disegni di legge OSR del Senato agli stessi record degli atti della Camera: `Act` (una fase: S. 1468,
S. 1468-B) con stato, natura, legge che ne è nata, firmatari senatori (SPONSORS); i presentatori che non sono
senatori (governo, regioni, CNEL, iniziativa popolare) restano come testo; i deputati presentatori si legano alla
persona della Camera. Le assegnazioni alle commissioni (ASSIGNED, con la sede: referente, redigente, deliberante,
consultiva) e i relatori (RAPPORTEUR), che qui arrivano già con il senatore. Trasformazione pura.
"""

from __future__ import annotations

import html
import re

from .camera_anagrafica import data


def _coda(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _testo(t: str | None) -> str | None:
    """«5&ordf; (Bilancio)» -> «5ª (Bilancio)»."""
    return " ".join(html.unescape(t or "").split()) or None


def uri_ddl(numero: str, leg: int) -> str:
    return f"it:senato:{leg}:ddl:{numero.strip()}"


def trasforma(grezzi: dict[str, list[dict]], leg: int, fonte: dict | None = None) -> dict:
    fonte = fonte or {}
    nodi, uri_di = {}, {}
    presentatori: dict[str, list[str]] = {}
    for r in grezzi.get("presentatori", []):
        presentatori.setdefault(r["ddl"], []).append(" ".join(r["presentatore"].split()))
    for r in grezzi.get("ddl", []):
        u = uri_ddl(r["numero"], leg)
        uri_di[r["ddl"]] = u
        if u in nodi:
            continue
        natura = r.get("natura") or ""
        nodi[u] = {"label": "Act", "uri": u, "chamber": "senato", "legislature": leg, "number": r["numero"].strip(), "kind": "bill",
                   "kind_raw": natura, "constitutional": "costituzional" in natura, "initiative": r.get("iniziativa"),
                   "title": r.get("titolo"), "date": data(r.get("data")),
                   "description": "; ".join(dict.fromkeys(presentatori.get(r["ddl"], []))) or None,
                   "law_number": r.get("legge"), "law_date": data(r.get("dataLegge")), "status": r.get("stato"), "status_date": None,
                   "card_url": f"https://www.senato.it/leg/{leg}/BGT/Schede/Ddliter/{r['idDdl']}.htm" if r.get("idDdl") else None,
                   "text_urls": [], "source": "osr", "source_uri": r["ddl"]}
    firme: dict[tuple, bool] = {}
    for r in grezzi.get("firmatari", []):
        m = re.search(r"/senatore/(\d+)", r["senatore"])
        if r["ddl"] in uri_di and m:
            k = (f"it:person:senato:{m.group(1)}", uri_di[r["ddl"]])
            firme[k] = firme.get(k, False) or r.get("primo") in ("1", "true")
    for r in grezzi.get("presentatori", []):
        m = re.search(r"deputato\.rdf/d(\d+)", r.get("deputato") or "")
        if r["ddl"] in uri_di and m:
            k = (f"it:person:camera:{m.group(1)}", uri_di[r["ddl"]])
            firme[k] = firme.get(k, False) or r.get("primo") in ("1", "true")
    archi = [{"type": "SPONSORS", "from": p, "to": a, "first": primo} for (p, a), primo in firme.items()]
    visti = set()
    for r in grezzi.get("assegnazioni", []):
        if r["ddl"] not in uri_di:
            continue
        etichetta = _testo(r.get("etichetta"))
        organo = f"it:senato:{leg}:body:{_coda(r['organo'])}" if r.get("organo") else etichetta
        # la sede c'è solo per la commissione di merito; per le altre vale il tipo (consultiva)
        sede = (r.get("sede") or r.get("tipo") or "").strip().lower() or None
        k = (uri_di[r["ddl"]], organo, sede, data(r.get("data")))
        if organo and k not in visti:
            visti.add(k)
            archi.append({"type": "ASSIGNED", "from": k[0], "to": organo, "seat": sede, "date": k[3], "title": etichetta})
    for r in grezzi.get("relatori", []):
        if r["ddl"] not in uri_di:
            continue
        etichetta = _testo(r.get("etichetta")) or ""
        nome = re.sub(r"^Sen\.\s*", "", etichetta)
        m = re.search(r"/senatore/(\d+)", r.get("senatore") or "")
        ruolo = "minority" if str(r.get("minoranza")) in ("1", "true") else "rapporteur"
        k = (uri_di[r["ddl"]], nome, ruolo)
        if nome and k not in visti:
            visti.add(k)
            archi.append({"type": "RAPPORTEUR", "from_ref": nome, "to": k[0], "role": ruolo, "raw": etichetta,
                          "person": f"it:person:senato:{m.group(1)}" if m else None})
    return {"nodi": list(nodi.values()), "archi": archi, "testi": [],
            "ambito": {"kind": "atti", "chamber": "senato", "legislature": leg, "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}}
