"""Dallo stenografico di una seduta di commissione (HTML) ai record dello schema v3: `Sitting`, `AgendaItem`, e
`Speech` parola per parola (`verbatim`), citabili. Chi parla è un deputato (con l'id della Camera) oppure un
audito, con il nome e la qualifica scritti nel resoconto («rappresentante del Palestinian Centre…»).

Trasformazione pura; usa il lettore HTML del Bollettino, che ha la stessa struttura a paragrafi.
"""

from __future__ import annotations

import re

from .camera_bollettino import _fase, _h, _ore, _spazi, atti, leggi

CORPO = "stenograficoCommissione."   # i paragrafi con questo id sono il resoconto; quelli con «indice_…» sono l'indice


def _testo_parlato(testo: str, etichetta: str, ruolo: str | None) -> str:
    """«PRESIDENTE. Avverto che…» -> «Avverto che…»; «HAMDI SHAQQURA, rappresentante del PCHR. Grazie…» -> «Grazie…»."""
    resto = testo[len(etichetta):] if testo.startswith(etichetta) else testo
    resto = re.sub(r"^\s*\([^)]{1,40}\)", "", resto)                 # gruppo: «(PD-IDP)»
    if ruolo and resto.lstrip(" ,").startswith(ruolo):
        resto = resto.lstrip(" ,")[len(ruolo):]
    return re.sub(r"^\s*[.,:]\s*", "", resto).strip()


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    l = leggi(corpo)
    m = l.meta
    giorno, codice = m.get("date", ""), (m.get("commissione") or "").replace("commissione.", "")
    tipo, sotto, numero = m.get("tipoResoconto", ""), m.get("sottoTipoResoconto", ""), int(m.get("resoconto.numero") or 0)
    data = f"{giorno[:4]}-{giorno[4:6]}-{giorno[6:]}"
    comitato = _spazi(" ".join(l.campi.get("comitatoDescrizione", []))) or None
    commissione = _spazi(" ".join(l.campi.get("commissioneNumero", []))) or None
    s_uri = f"it:camera:{leg}:stc:{codice}:{tipo}{':' + sotto if sotto else ''}:{giorno}:{numero:04d}"
    seduta = {"label": "Sitting", "uri": s_uri, "chamber": "camera", "body_code": codice, "body_name": comitato or commissione,
              "number": numero, "date": data, "status": "held", "kind": "committee_verbatim", "seat": f"{tipo}{' ' + sotto if sotto else ''}",
              "provisional": m.get("bozza") == "true", "source": "camera_stenografici_commissioni",
              "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}
    nodi, archi, testi = [seduta], [], []
    punto, n_punto, n_par = None, 0, 0
    for p in l.paragrafi:
        if not (p["id"] or "").startswith(CORPO):
            continue
        testo, cls = _spazi(p["testo"]), p["class"].split()
        if "presidenza" in cls:
            seduta["presidency"] = testo
            continue
        if "avviso" in cls:
            o = re.search(r"(comincia|termina|inizia)\D+(\d{1,2}(?:[.,]\d{2})?)", testo)
            if o:
                seduta["start_time" if o.group(1) != "termina" else "end_time"] = _ore(o.group(2))
            continue
        if "titolo" in cls:
            n_punto += 1
            n_par = 0
            fase = next((c for c in reversed(p["corsivi"]) if c.strip().startswith("(")), None)
            punto = {"label": "AgendaItem", "uri": f"{s_uri}:{p['id'].rsplit('.', 1)[-1]}", "order": n_punto,
                     "title": _spazi(" ".join(p["grassetti"])) or testo, "stage": _fase(fase), "acts": atti(testo)}
            nodi.append(punto)
            archi.append({"type": "HAS_ITEM", "from": s_uri, "to": punto["uri"], "order": n_punto})
            archi += [{"type": "ABOUT", "from": punto["uri"], "to_ref": ref} for ref in punto["acts"]]
            continue
        if "intervento" not in cls or not testo:
            continue
        if punto is None:
            punto = {"label": "AgendaItem", "uri": f"{s_uri}:tit00000", "order": 0, "title": None, "stage": None, "acts": [], "service": True}
            nodi.append(punto)
            archi.append({"type": "HAS_ITEM", "from": s_uri, "to": punto["uri"], "order": 0})
        pid, etichetta = (p["persone"][0] if p["persone"] else [None, ""])
        etichetta = _spazi(etichetta)
        ruolo = _spazi(p["corsivi"][0]) if p["corsivi"] and _spazi(p["corsivi"][0]) and testo.find(_spazi(p["corsivi"][0])) < len(etichetta) + 60 else None
        ruolo = ruolo or (p.get("title") or None)
        parlato = _testo_parlato(testo, etichetta, ruolo)
        if not parlato:                                    # solo il nome («PRESIDENTE.»), senza parole: anche alla fonte
            continue
        n_par += 1
        sp = f"{punto['uri']}:{p['id'].rsplit('.', 1)[-1]}"
        nodi.append({"label": "Speech", "uri": sp, "order": n_par, "kind": "verbatim", "hash": _h(parlato), "text_ref": f"speech:{sp}",
                     "speaker_label": etichetta or None, "declared_group": None, "as_office": ruolo, "anchor": p["id"],
                     "guest": pid is None})
        archi.append({"type": "HAS_SPEECH", "from": punto["uri"], "to": sp, "order": n_par})
        if pid:
            archi.append({"type": "BY", "from": sp, "to": f"it:person:camera:{pid}", "as_office": ruolo})
        testi.append({"ref": f"speech:{sp}", "text": parlato, "hash": _h(parlato)})
    return {"nodi": nodi, "archi": archi, "testi": testi,
            "ambito": {"kind": "commissione", "chamber": "camera", "legislature": leg, "date": data, "body_code": codice,
                       "source": "camera_stenografici_commissioni", "source_key": fonte.get("chiave")}}
