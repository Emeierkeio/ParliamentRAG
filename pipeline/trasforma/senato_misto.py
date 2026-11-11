"""Dalla composizione storica del Gruppo Misto del Senato (pagina di senato.it) alle componenti partitiche e alle
adesioni datate, negli stessi record della Camera: Group con kind misto_component, PART_OF il Misto, MEMBER_OF.
Trasformazione pura.

La legenda in fondo alla pagina dà ogni componente con la sigla, la data di costituzione e i cambi di nome
(«dal 13 novembre 2023 la denominazione muta in Azione-Renew Europe (Az-RE)»): il nome è l'ultimo, gli altri restano
alias, e ogni sigla porta alla stessa componente. Le righe della tabella danno la sigla con le date («AVS dal 24 ottobre
2022», «Az fino al 17 settembre 2024») e l'ingresso e l'uscita dal gruppo. Date di un'adesione: inizio = la più tarda fra
«dal …», ingresso nel gruppo e costituzione della componente; fine = «fino al …» o «al …», altrimenti l'uscita dal
gruppo, altrimenti in corso. Un senatore compare una volta per carica (Presidente, Tesoriere) e una come membro: le
adesioni uguali si tengono una volta, quella con la fine se l'altra non ce l'ha.
"""

from __future__ import annotations

import datetime as dt
import html
import re

from .camera_anagrafica import leggibile

MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                     "settembre", "ottobre", "novembre", "dicembre"], start=1)}
DATA = r"(\d{1,2})[º°]?\s+([a-zà]+)\s+(\d{4})"
ART = r"(?:l['’]\s*|\s+)"                                  # «dal 9», «dall'8», «fino all'8»


def data_it(testo: str) -> str | None:
    """«9 novembre 2023» (anche «1º») -> '2023-11-09'."""
    m = re.search(DATA, testo or "", re.I)
    if not m or m.group(2).lower() not in MESI:
        return None
    return dt.date(int(m.group(3)), MESI[m.group(2).lower()], int(m.group(1))).isoformat()


def _testo(x: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def legenda(pagina: str) -> dict[str, dict]:
    """Chiave (la prima sigla) -> {nomi, sigle, costituita}, dalla lista «Componenti partitiche del Gruppo Misto»."""
    i = pagina.find("Componenti partitiche")
    if i < 0:
        raise ValueError("pagina senza «Componenti partitiche del Gruppo Misto»")
    j = pagina.find('<ul class="schede">', i)
    blocco = pagina[j:pagina.find("</h3>", j) if pagina.find("</h3>", j) > 0 else len(pagina)]
    out = {}
    # una voce per componente: <li><strong>NOME (SIGLA)</strong><span>costituita il …</span> [<ul> cambi di nome </ul>]
    for voce in re.split(r'<li>\s*(?=<strong>)', blocco)[1:]:
        testa = re.match(r"<strong>(.*?)</strong>\s*<span>(.*?)</span>", voce, re.S)
        if not testa:
            continue
        m = re.match(r"(.+?)\s*\(([^()]+)\)\s*$", _testo(testa.group(1)))
        if not m:
            raise ValueError(f"componente senza sigla nella legenda: {_testo(testa.group(1))!r}")
        nomi, sigle = [m.group(1)], [m.group(2).strip()]
        for c in re.finditer(r"la denominazione muta in\s*<strong>(.*?)</strong>\s*\(\s*<strong>(.*?)</strong>\s*\)", voce, re.S):
            nomi.append(_testo(c.group(1)))
            sigle.append(_testo(c.group(2)))
        out[sigle[0]] = {"nomi": [leggibile(n) if n.isupper() else n for n in nomi], "sigle": sigle,
                         "costituita": data_it(testa.group(2))}
    if not out:
        raise ValueError("legenda delle componenti vuota")
    return out


def righe(pagina: str) -> list[dict]:
    """Una voce per (senatore, sigla con le sue date) nelle righe della tabella."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", pagina, re.S):
        celle = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        link = re.search(r"scheda-attivita\?did=(\d+)\"?>\s*(.*?)\s*</a>", tr, re.S)
        if not link or len(celle) < 2:
            continue
        gruppo = _testo(celle[1])
        entra = re.search(r"Entra nel gruppo (?:il |l')\s*" + DATA, gruppo, re.I)
        esce = re.search(r"Esce dal gruppo (?:il |l')\s*" + DATA, gruppo, re.I)
        # anche <span class="annotazione">: la componente successiva di chi ne ha cambiata una
        for span in re.findall(r"<span[^>]*>(.*?)</span>", celle[0], re.S):
            t = _testo(span)
            if not t:
                continue
            dal = re.search(r"\bdal" + ART + DATA, t, re.I)
            al = re.search(r"\b(?:fino\s+)?al" + ART + DATA, t, re.I)
            out.append({"did": link.group(1), "nome": _testo(link.group(2)), "sigla": re.split(r"\s+(?:dal|fino\s+al|al)" + ART, t, flags=re.I)[0].strip(),
                        "dal": data_it(dal.group(0)) if dal else None, "al": data_it(al.group(0)) if al else None,
                        "entra": data_it(entra.group(0)) if entra else None, "esce": data_it(esce.group(0)) if esce else None})
    return out


def trasforma(pagina: str, leg: int, misto: str, persone: set[str], fonte_uri: str) -> tuple[list[dict], list[dict]]:
    """Nodi delle componenti e archi PART_OF e MEMBER_OF. `misto` è l'uri del Gruppo Misto, `persone` gli uri dei
    senatori dell'anagrafica: chi non c'è resta fuori."""
    comp = legenda(pagina)
    per_sigla = {s: k for k, c in comp.items() for s in c["sigle"]}
    nodi, archi = [], []
    for k, c in comp.items():
        u = f"it:senato:{leg}:group:misto-{re.sub(r'[^A-Za-z0-9]+', '-', k).strip('-').lower()}"
        c["uri"] = u
        nodi.append({"label": "Group", "uri": u, "chamber": "senato", "legislature": leg, "kind": "misto_component",
                     "name": c["nomi"][-1], "short_name": c["sigle"][-1], "start": c["costituita"], "end": None,
                     "aliases": list(dict.fromkeys(c["nomi"] + c["sigle"])), "source": "senato.it", "source_uri": fonte_uri})
        archi.append({"type": "PART_OF", "from": u, "to": misto})
    adesioni: dict[tuple, dict] = {}
    for r in righe(pagina):
        k = per_sigla.get(r["sigla"])
        if k is None:
            raise ValueError(f"sigla {r['sigla']!r} di {r['nome']} non è nella legenda delle componenti")
        p = f"it:person:senato:{r['did']}"
        if p not in persone:
            continue
        date = [d for d in (r["dal"], r["entra"], comp[k]["costituita"]) if d]
        if not date:
            raise ValueError(f"nessuna data d'inizio per {r['nome']} ({r['sigla']})")
        inizio, fine = max(date), r["al"] or r["esce"]
        prima = adesioni.get((p, k, inizio))
        if prima is None or (fine and not prima["end"]):
            adesioni[(p, k, inizio)] = {"type": "MEMBER_OF", "from": p, "to": comp[k]["uri"], "role": "member",
                                        "start": inizio, "end": fine, "end_reason": None}
    return nodi, archi + list(adesioni.values())
