"""Dallo stenografico di una commissione del Senato (scheda dell'elenco e PDF) a un `Document` con il testo.

È un documento da cercare e da leggere, non una serie di interventi: il testo viene da un PDF, dove gli a capo e le
sillabazioni non garantiscono le parole esatte, quindi non si cita tra virgolette (decisione del 10/11/2026).
Trasformazione pura.
"""

from __future__ import annotations

import hashlib
import json
import re

from .camera_documenti import _testo_pdf
from .convocazioni import ORGANI_SENATO


def _h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def pulisci(t: str) -> str:
    """Il testo del PDF senza le sillabazioni di fine riga («prov-\\nvedimento»), i surrogati isolati e gli spazi doppi."""
    t = re.sub(r"[\ud800-\udfff\x00]", "", t)
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", t)).strip()


def atti(argomento: str | None) -> list[str]:
    """«Disegni di legge nn. 1780, 68, 125, 368 e 608» -> ddl:1780, ddl:68 …; «(n. 450)» di un atto del Governo -> ag:450."""
    t, out = argomento or "", []
    for m in re.finditer(r"[Dd]isegn[oi] di legge\s+(?:n\.|nn\.)\s*([\d\s,e-]+(?:-[A-Z])?)", t):
        out += [f"ddl:{x}" for x in re.findall(r"\d+(?:-[A-Z])?", m.group(1))]
    out += [f"ag:{x}" for x in re.findall(r"[Aa]tt[oi] del Governo\s+n\.\s*(\d+)", t)]
    return list(dict.fromkeys(out))


def trasforma(scheda: bytes, pdf: bytes | None, info: dict, leg: int = 19) -> dict:
    v = json.loads(scheda)
    u = f"it:senato:{leg}:stc:{v['id']}"
    testo = pulisci(_testo_pdf(pdf)) if pdf else None
    organo = v.get("organo") or f"{v['commissione']}ª Commissione"
    titolo = " · ".join(x for x in (organo, v.get("numero") or "Stenografico", v.get("sede")) if x)
    argomento = v.get("argomento") or ""
    if v.get("sede") and argomento.startswith(v["sede"]):
        argomento = argomento[len(v["sede"]):].strip()
    nodo = {"label": "Document", "uri": u, "kind": "verbatim_record", "date": v["data"], "sitting_date": v["data"],
            "title": titolo + (" (bozza)" if v.get("bozza") else ""), "hearing": argomento or None, "author_raw": None,
            "code": f"seduta n. {v['seduta']}" + (f" ({v['turno']})" if v.get("turno") else "") if v.get("seduta") else None,
            "body": f"it:senato:{leg}:body:{ORGANI_SENATO[v['commissione']]}" if v.get("commissione") in ORGANI_SENATO else None,
            "acts": atti(v.get("argomento")), "url": v["url"], "format": "pdf", "third_party": False,
            "hash": _h(testo) if testo else _h(v["url"]), "text_ref": f"document:{u}" if testo else None, "source": "senato_stenografici_commissioni"}
    return {"nodi": [nodo], "archi": [], "testi": [{"ref": f"document:{u}", "text": testo, "hash": _h(testo)}] if testo else [],
            "ambito": {"kind": "dossier", "chamber": "senato", "legislature": leg, "source_key": info.get("chiave")}}
