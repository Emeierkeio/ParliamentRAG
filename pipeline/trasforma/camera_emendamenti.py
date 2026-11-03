"""Dall'XML degli emendamenti di un progetto di legge ai record dello schema v3: `Amendment` per ogni proposta,
in ogni sede (commissione referente, Aula), con articolo, testo, stato ed esito, e i firmatari (SIGNS) con l'id
del deputato e il primo firmatario. Le proposte identiche restano legate fra loro. Trasformazione pura.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET


def _testo(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    righe = []
    for p in el.iter():
        if p.tag in ("p", "br") and p.tag == "p":
            righe.append(re.sub(r"\s+", " ", "".join(p.itertext())).strip())
    t = "\n".join(r for r in righe if r)
    return t or re.sub(r"\s+", " ", "".join(el.itertext())).strip() or None


def _numero(n: str) -> str:
    """«1.1.» -> «1.1»; «Dis.1.1.» -> «Dis.1.1»."""
    return n.strip().rstrip(".")


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    radice = ET.fromstring(corpo)
    numero_ac = re.search(r"-eme-ac(.+)$", fonte["chiave"]).group(1)
    atto = f"it:camera:{leg}:ac:{numero_ac}"
    nodi, archi, testi = [], [], []
    visti: set[str] = set()
    for blocco in radice.iter("proposteEmendativeInSeduta"):
        s = blocco.find("seduta")
        sede = (s.get("tipo") if s is not None else None) or "altro"                  # commissione | assemblea
        n_seduta = s.get("numero") if s is not None else ""
        data = s.get("data") if s is not None else None
        comm = blocco.find(".//commissione")
        sede_esame = blocco.find(".//commissioni")
        prefisso = f"{atto}:eme:{'ass' if sede == 'assemblea' else 'com'}{n_seduta}"
        for gruppo in blocco.iter("gruppo"):
            titolo_gruppo = (gruppo.findtext("titolo") or "").strip() or None
            for p in gruppo.iter("propostaEmendativa"):
                num = _numero(p.get("numero") or "")
                if not num:
                    continue
                u = f"{prefisso}:{num}"
                if u in visti:
                    continue
                visti.add(u)
                part = p.find("partizione")
                testo = _testo(p.find("testoPropostaEmendativa/xhtml"))
                identiche = [_numero(x.text or "") for x in p.iter("propostaEmendativaIdentica") if (x.text or "").strip()]
                nodi.append({"label": "Amendment", "uri": u, "act": atto, "number": num, "kind": p.get("tipo"), "action": p.get("azioneEmendativa"),
                             "article": part.findtext("numero") if part is not None else None,
                             "venue": "assembly" if sede == "assemblea" else (sede_esame.get("sedeEsame") if sede_esame is not None else sede),
                             "committee": comm.get("idCommissione") if comm is not None else None,
                             "sitting_number": int(n_seduta) if (n_seduta or "").isdigit() else None,
                             "sitting_date": f"{data[:4]}-{data[4:6]}-{data[6:]}" if data and len(data) == 8 else None,
                             "group_title": titolo_gruppo, "status": p.findtext("iter/stato"), "outcome": p.findtext("iter/esitoPropostaEmendativa/esito"),
                             "decree": p.get("numeroDecretoLegge"), "identical": [f"{prefisso}:{x}" for x in identiche if x != num],
                             "hash": hashlib.sha256((testo or u).encode()).hexdigest()[:16], "text_ref": f"amendment:{u}" if testo else None})
                if testo:
                    testi.append({"ref": f"amendment:{u}", "text": testo, "hash": nodi[-1]["hash"]})
                for i, pr in enumerate(p.iter("proponente"), 1):
                    pers = pr.find("persona")
                    ide = pr.get("idProponente")
                    archi.append({"type": "SIGNS", "from": f"it:person:camera:{ide}" if ide and pr.get("tipoProponente") == "deputato" else None,
                                  "to": u, "order": i, "first": pers is not None and pers.get("primoFirmatario") == "1",
                                  "family_raw": pers.findtext("cognome") if pers is not None else None,
                                  "given_raw": pers.findtext("nome") if pers is not None else None, "kind_raw": pr.get("tipoProponente")})
    return {"nodi": nodi, "archi": archi, "testi": testi,
            "ambito": {"kind": "emendamenti", "chamber": "camera", "legislature": leg, "act": atto, "source_key": fonte.get("chiave"),
                       "source_hash": fonte.get("impronta")}}
