"""Dall'ordine del giorno dell'Assemblea del Senato (HTML) a una seduta prevista (`Sitting {status: planned}`) con i
suoi argomenti: il titolo dell'atto, la sezione («Seguito della discussione dei disegni di legge»), i relatori e i
ddl collegati. Stessi record di camera_odg: la seduta prevista ha l'uri di quella che poi si tiene
(it:senato:19:sed0475), e il resoconto, quando arriva, la sostituisce. Trasformazione pura.
"""

from __future__ import annotations

import html
import re

MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                     "settembre", "ottobre", "novembre", "dicembre"], 1)}
ROMANO = r"[IVXL]+"


def _pulito(t: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    return re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"\(\s+", "(", re.sub(r"\s+", " ", t))).strip()


def _ora(t: str) -> str | None:
    m = re.search(r"ore (\d{1,2})(?:[,.](\d{2}))?", t, re.I)
    return f"{int(m.group(1)):02d}:{m.group(2) or '00'}" if m else None


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    t = corpo.decode("utf-8", errors="replace")
    i = t.find('class="showdoc-hotodg"')
    if i < 0:
        raise ValueError("pagina senza l'ordine del giorno")
    blocco = t[i:t.find('<div class="node_view">', i) if '<div class="node_view">' in t[i:] else len(t)]
    testa = re.search(r'<h2 class="odg">(.*?)</h2>', blocco, re.S)
    quando = _pulito(testa.group(1)) if testa else ""
    d = re.search(r"(\d{1,2})°?\s+(\w+)\s+(\d{4})", quando)
    n = re.search(r"(\d+)\s*a?\s*Seduta", quando, re.I)
    if not d or not n or d.group(2).lower() not in MESI:
        raise ValueError(f"ordine del giorno senza data o numero di seduta: {quando[:80]}")
    numero, data = int(n.group(1)), f"{d.group(3)}-{MESI[d.group(2).lower()]:02d}-{int(d.group(1)):02d}"
    s_uri = f"it:senato:{leg}:sed{numero:04d}"
    seduta = {"label": "Sitting", "uri": s_uri, "chamber": "senato", "body": f"it:senato:{leg}:aula", "number": numero, "date": data,
              "status": "planned", "kind": "assembly_agenda", "start_time": _ora(quando), "source": "senato_odg",
              "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}
    nodi, archi, sezione, voci = [seduta], [], None, []
    for par in re.findall(r"<p[^>]*>(.*?)</p>", blocco[testa.end():] if testa else blocco, re.S):
        testo = _pulito(par)
        if not testo:
            continue
        capo = re.match(rf"({ROMANO})\.\s*(.+)", testo)
        if capo and re.match(rf"\s*<b>\s*{ROMANO}\s*</b>", par):
            sezione = capo.group(2).rstrip(": ")
            voci.append({"sezione": sezione, "titolo": None, "par": par})          # resta sola se la sezione non ha voci sotto
            continue
        voce = {"sezione": sezione, "titolo": testo, "par": par}
        if voci and voci[-1]["titolo"] is None and voci[-1]["sezione"] == sezione:
            voci[-1] = voce
        else:
            voci.append(voce)
    for k, v in enumerate(voci, 1):
        par = v["par"]
        atti = [f"ddl:{x}" for x in re.findall(r"tipodoc=sddliter&amp;id=\d+\"[^>]*>\s*(?:<b>)?\s*([\w-]+)", par)]
        relatori = re.search(r"Relator[ei]\w*\s*(?:</i>)?(.*?)(?:<i>\(|<b>\s*\(|$)", par, re.S)
        titolo = v["titolo"] or v["sezione"] or ""
        # dal titolo si tolgono il numero d'ordine, i relatori e il numero del ddl in coda: restano nei loro campi
        titolo = re.sub(r"^\d+\.\s*", "", titolo)
        titolo = re.sub(r"\s*-\s*Relator[ei]\w*\b.*$", "", titolo).strip()
        titolo = re.sub(r"\s*\(\s*[\w-]+\s*\)\s*$", "", titolo).strip() if atti else titolo
        p = {"label": "AgendaItem", "uri": f"{s_uri}:odg{k:02d}", "order": k, "title": titolo.rstrip(": "),
             "text": v["sezione"] if v["titolo"] else None, "scheduled_time": None,
             "rapporteurs": _pulito(relatori.group(1)).strip(" .-") or None if relatori else None, "acts": list(dict.fromkeys(atti))}
        nodi.append(p)
        archi.append({"type": "HAS_ITEM", "from": s_uri, "to": p["uri"], "order": k})
        archi += [{"type": "ABOUT", "from": p["uri"], "to_ref": a} for a in p["acts"]]
    return {"nodi": nodi, "archi": archi, "testi": [],
            "ambito": {"kind": "odg", "chamber": "senato", "legislature": leg, "sitting": s_uri, "date": data,
                       "source": "senato_odg", "source_key": fonte.get("chiave")}}
