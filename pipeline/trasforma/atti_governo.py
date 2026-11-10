"""Atti del Governo e proposte di nomina sottoposti a parere, dei due rami, come `Act`: `government_act` (schemi di
decreto legislativo, regolamenti, decreti ministeriali) e `appointment` (nomine). Lo stesso atto ha lo stesso numero
alla Camera e al Senato: sono due record, uno per ramo, come per gli altri atti.

Camera (pagina HTML): fase dell'iter, e per ogni commissione l'assegnazione (ASSIGNED) con il tipo (parere, rilievi,
compatibilità UE), la data, il termine, la norma che chiede il parere e il parere espresso con la sua data.
Senato (open data): numero, titolo, data, stato, presentatore e PDF del testo; niente assegnazioni.

L'URI segue il riferimento che i sommari delle commissioni usano già: «Atto n. 439» = `ag:439`. Trasformazione pura.
"""

from __future__ import annotations

import html
import json
import re

from .camera_anagrafica import data

MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
                                     "ottobre", "novembre", "dicembre"], 1)}
TIPO_ASSEGNAZIONE = {"Primaria": "opinion", "DeliberazioneRilievi": "remarks", "UE": "eu_compatibility", "altro": "opinion"}
NATURA = {"decreto_legislativo": "schema di decreto legislativo", "regolamento": "schema di regolamento", "altro": "altro atto"}
SCHEDA = "https://documenti.camera.it/apps/commonServices/getDocumento.ashx?idLegislatura={leg}&sezione=lavori&tipoDoc=attoGoverno&tipoAtto={tipo}&atto={n}"


def _pulito(t: str | None) -> str | None:
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or "")).replace("\xa0", " ")
    return re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"\(\s+", "(", re.sub(r"\s+", " ", t))).strip() or None


def giorno(t: str | None) -> str | None:
    """«(assegnato il 3 novembre 2026» -> 2026-11-03; «1° luglio 2025» -> 2025-07-01."""
    m = re.search(r"(\d{1,2})°?\s+(\w+)\s+(\d{4})", t or "")
    if not m or m.group(2).lower() not in MESI:
        return None
    return f"{m.group(3)}-{MESI[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def uri_atto(ramo: str, leg: int, tipo: str, numero: str) -> str:
    """atto 455 -> it:camera:19:ag:455; nomina 089 -> it:camera:19:nomina:89."""
    n = re.sub(r"^0+(?=\d)", "", numero.strip())
    return f"it:{ramo}:{leg}:{'ag' if tipo == 'atto' else 'nomina'}:{n}"


def _span(blocco: str, classe: str) -> str | None:
    m = re.search(rf'<span class="{classe}">(.*?)</span>', blocco, re.S)
    return _pulito(m.group(1)) if m else None


ROMANO = r"(X{0,3}(?:IX|IV|V?I{0,3}))\b"


def _organi(blocco: str) -> dict[str, str]:
    """Numero romano della commissione permanente -> id dell'organo, dal blocco JSON di ogni atto. Nella pagina il nome
    è scritto in due modi («XIV Politiche UE», «XIV Politiche dell'Unione Europea»): il numero è lo stesso."""
    singole = blocco.split("singole:", 1)[1] if "singole:" in blocco else ""
    out = {}
    for ido, nome in re.findall(r'idAUL:\s*(\d+),\s*nome:\s*"([^"]*)"', singole):
        m = re.match(ROMANO, nome.strip())
        if m and m.group(1):
            out[m.group(1)] = ido
    return out


def trasforma_camera(grezzo: bytes, info: dict) -> dict:
    t = grezzo.decode("utf-8", errors="replace")
    leg = int(re.search(r"leg(\d+)", info.get("chiave") or "leg19").group(1))
    nodi, archi = [], []
    for m in re.finditer(r'<li tipo="(atto|nomina)" id="(?:atto|nomina)_([\w-]+)"[^>]*>(.*?)</script>\s*</li>', t, re.S):
        tipo, numero, blocco = m.group(1), m.group(2), m.group(3)
        u = uri_atto("camera", leg, tipo, numero)
        titolo = _pulito(re.search(r'<div class="titolo">(.*?)</div>', blocco, re.S).group(1)) or ""
        titolo = re.sub(r"\s*\(\d+(?:-\w+)?\)\.?$", "", titolo).strip()            # il numero ripetuto in coda: «… (455)»
        fase = re.search(r"Fase Iter:</span><span>([^<]*)", blocco)
        proponente = re.search(r"Proponente:</span><span>([^<]*)", blocco)
        natura = re.search(r'natura:\s*"([^"]*)"', blocco)
        organi, date_, pareri = _organi(blocco), [], []
        for a in re.finditer(r'<li class="assegnazione_(\w+)">(.*?)(?=<li class="assegnazione_|</ul></div>\s*<script>)', blocco, re.S):
            for c in re.finditer(r'<div class="commissione">(.*?)</div>(\s*<div class="pareriEspressi">(.*?)</div>)?', a.group(2), re.S):
                nome = _span(c.group(1), "nomeCommissione")
                if not nome:
                    continue
                parere = _pulito(re.sub(r'-\s*<span class="dataParere">.*', "", c.group(3) or "", flags=re.S))
                # una commissione permanente si lega all'organo dell'anagrafica; le riunite restano col nome
                romano = re.match(ROMANO, nome)
                organo = organi.get(romano.group(1)) if romano and romano.group(1) else None
                arco = {"type": "ASSIGNED", "from": u, "to": f"it:camera:{leg}:body:o{leg}_{organo}" if organo else nome,
                        "seat": TIPO_ASSEGNAZIONE.get(a.group(1), "opinion"), "date": giorno(_span(c.group(1), "dataAssegnazione")),
                        "deadline": giorno(_span(c.group(1), "dataTermine")), "title": nome,
                        "basis": _span(c.group(1), "articolo") or (_span(c.group(1), "nota") or "").strip(" ,)") or None,
                        "opinion": parere, "opinion_date": giorno(_span(c.group(3) or "", "dataParere"))}
                archi.append(arco)
                date_.append(arco["date"])
                pareri.append(arco["opinion_date"])
        nodi.append({"label": "Act", "uri": u, "chamber": "camera", "legislature": leg, "number": re.sub(r"^0+(?=\d)", "", numero),
                     "kind": "government_act" if tipo == "atto" else "appointment",
                     "kind_raw": NATURA.get(natura.group(1) if natura else "", "proposta di nomina" if tipo == "nomina" else "altro atto"),
                     "constitutional": False, "initiative": "Governo", "title": titolo,
                     "date": min((d for d in date_ if d), default=None),
                     "description": _pulito(proponente.group(1)) if proponente else None, "law_number": None, "law_date": None,
                     "status": _pulito(fase.group(1)) if fase else None, "status_date": max((d for d in pareri if d), default=None),
                     "card_url": SCHEDA.format(leg=leg, tipo=tipo, n=numero), "text_urls": [],
                     "source": "camera_atti_governo", "source_uri": f"{tipo}_{numero}"})
    return {"nodi": nodi, "archi": archi, "testi": [],
            "ambito": {"kind": "atti_governo", "chamber": "camera", "legislature": leg, "source_key": info.get("chiave"),
                       "source_hash": info.get("impronta")}}


def trasforma_senato(grezzi: dict[str, list[dict]], leg: int, fonte: dict | None = None) -> dict:
    fonte, nodi = fonte or {}, {}
    for nome, tipo in (("atti", "atto"), ("nomine", "nomina")):
        presentatori: dict[str, list[str]] = {}
        for r in grezzi.get(nome, []):
            if r.get("presentatore"):
                presentatori.setdefault(r["doc"], []).append(" ".join(r["presentatore"].split()))
        for r in grezzi.get(nome, []):
            u = uri_atto("senato", leg, tipo, r["numero"])
            if u in nodi:
                if r.get("url") and r["url"] not in nodi[u]["text_urls"]:
                    nodi[u]["text_urls"].append(r["url"])
                continue
            nodi[u] = {"label": "Act", "uri": u, "chamber": "senato", "legislature": leg, "number": r["numero"].strip(),
                       "kind": "government_act" if tipo == "atto" else "appointment",
                       "kind_raw": "atto del Governo sottoposto a parere" if tipo == "atto" else "proposta di nomina",
                       "constitutional": False, "initiative": "Governo", "title": " ".join((r.get("titolo") or r.get("breve") or "").split()) or None,
                       "date": data(r.get("data")), "description": "; ".join(dict.fromkeys(presentatori.get(r["doc"], []))) or None,
                       "law_number": None, "law_date": None, "status": r.get("stato"), "status_date": None,
                       # la scheda su senato.it ha lo stesso id del documento negli open data (verificato sui link delle convocazioni)
                       "card_url": f"https://www.senato.it/leg/{leg}/BGT/Schede/docnonleg/{r['doc'].rstrip('/').rsplit('/', 1)[-1]}.htm",
                       "text_urls": [r["url"]] if r.get("url") else [], "source": "osr", "source_uri": r["doc"]}
    return {"nodi": list(nodi.values()), "archi": [], "testi": [],
            "ambito": {"kind": "atti_governo", "chamber": "senato", "legislature": leg, "source_key": fonte.get("chiave"),
                       "source_hash": fonte.get("impronta")}}
