"""Dalle pagine delle convocazioni delle commissioni (Camera e Senato) alle voci `Convocation`: una per commissione,
giorno e blocco orario, con la sede, l'aula, gli argomenti e gli atti. Non sono sedute: la seduta arriva dopo, con il
Bollettino o con il resoconto sommario. Trasformazione pura.
"""

from __future__ import annotations

import datetime as dt
import html
import re

MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
                                     "ottobre", "novembre", "dicembre"], 1)}
# le commissioni permanenti del Senato nell'anagrafica (dati.senato.it): la riforma del 2022 ne ha rinumerate alcune
ORGANI_SENATO = {1: "0-1", 2: "0-2", 3: "0-145", 4: "0-14", 5: "0-5", 6: "0-6", 7: "0-7", 8: "0-146", 9: "0-147", 10: "0-148"}


def _testo(t: str) -> str:
    """HTML -> testo: una riga per blocco o voce d'elenco, spazi puliti."""
    t = re.sub(r"<li[^>]*>", "\n- ", t)
    t = re.sub(r"</?(?:div|p|br|ul|ol|tr|table|h\d)[^>]*>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").replace("​", "")
    righe = [re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"\s+", " ", r)).strip() for r in t.split("\n")]
    return "\n".join(r for r in righe if r and r != "-")


def ora(t: str | None) -> str | None:
    """«Ore 8.30» -> 08:30; «ore 14» -> 14:00; «12:00» -> 12:00; «Al termine» -> None."""
    m = re.search(r"(?:ore\s+)?\b(\d{1,2})(?:[.,:](\d{2}))?\b", t or "", re.I)
    return f"{int(m.group(1)):02d}:{m.group(2) or '00'}" if m and int(m.group(1)) < 24 and re.search(r"ore|\d[.,:]\d", t, re.I) else None


def _ambito(ramo: str, leg: int, chiave: str | None, info: dict) -> dict:
    return {"kind": "convocazioni", "chamber": ramo, "legislature": leg, "source": f"{ramo}_convocazioni", "source_key": chiave,
            "source_hash": info.get("impronta")}


# ---------------------------------------------------------------- Camera
def atti_camera(cella: str) -> list[str]:
    """I riferimenti agli atti dai link della convocazione: progetti di legge (ac:3119), atti del Governo (ag:446),
    nomine (nomina:148), e gli atti di sindacato ispettivo scritti nel testo (aic:5-04321)."""
    atti = [f"ac:{n}" for n in re.findall(r"tipoDoc=pdl&amp;idDocumento=([\w-]+)", cella)]
    for n, tipo in re.findall(r"tipoDoc=attoGoverno&amp;atto=([\w-]+)&amp;tipoatto=(\w+)", cella):
        atti.append(f"{'nomina' if tipo.lower() == 'nomina' else 'ag'}:{n.lstrip('0') or '0'}")
    atti += [f"aic:{n}" for n in re.findall(r"\b(\d-\d{5})\b", re.sub(r"<[^>]+>", " ", cella))]
    return list(dict.fromkeys(atti))


def trasforma_camera(grezzo: bytes, info: dict) -> dict:
    t = grezzo.decode("utf-8", errors="replace")
    chiave = info.get("chiave") or ""
    m = re.search(r"leg(\d+)-conv-(\d+)-(\d{8})", chiave)
    leg, organo = (int(m.group(1)), m.group(2)) if m else (19, "0")
    tabella = re.search(r'<table class="tabellaXHTML".*?</table>', t, re.S)
    nodi = []
    if tabella:
        tab = tabella.group(0)
        nome = re.search(r"<strong>Convocazione dell[ae']\s*(.*?)</strong>(?:.*?<em>\((.*?)\)</em>)?", tab, re.S)
        organo_nome = " ".join(x for x in (_testo(nome.group(1)), f"({_testo(nome.group(2)).capitalize()})" if nome.group(2) else "") if x) if nome else ""
        g = re.search(r'class="dataconvocazione"[^>]*>\s*\S+\s+(\d{1,2})°?\s+(\w+)\s+(\d{4})', tab)
        giorno = dt.date(int(g.group(3)), MESI[html.unescape(g.group(2)).lower()], int(g.group(1))).isoformat() if g else None
        blocco = None
        for riga in re.findall(r"<tr>(.*?)</tr>", tab, re.S):
            celle = re.findall(r'<td class="(cellsx|celldx)"[^>]*>(.*?)</td>', riga, re.S)
            if len(celle) != 2:
                continue
            prima, seconda = _testo(celle[0][1]), _testo(celle[1][1])
            # un blocco comincia con l'ora (o «Al termine») a sinistra e la sede a destra, tutte e due nella colonna larga
            if celle[1][0] == "cellsx" and re.match(r"(?i)(ore\s+\d|al termine|a seguire|\d{1,2}[.,]\d{2})", prima):
                sede = re.match(r"(.*?)\s*(?:\((.*)\))?$", seconda, re.S)
                blocco = {"label": "Convocation", "chamber": "camera", "body": f"it:camera:{leg}:body:o{leg}_{organo}",
                          "body_name": organo_nome, "date": giorno, "start_time": ora(prima), "when": prima,
                          "seat": sede.group(1).strip().capitalize().replace(" governo", " Governo") or None, "place": sede.group(2), "number": None, "righe": [],
                          "acts": [], "published": None, "url": info.get("url")}
                nodi.append(blocco)
            elif prima.upper().startswith("AVVISO"):
                blocco = None                              # avvisi di servizio: non sono una convocazione
            elif blocco is not None and seconda:
                blocco["righe"].append(f"{prima} {seconda}".strip())
                blocco["acts"] += atti_camera(celle[1][1])
    for i, n in enumerate(nodi, 1):
        testo = "\n".join(n.pop("righe"))
        n.update({"uri": f"it:camera:{leg}:conv:{organo}:{n['date']}:{i:02d}", "order": i, "text": testo or None,
                  "acts": list(dict.fromkeys(n["acts"])), "cancelled": bool(re.search(r"(?i)sconvocat", f"{n['seat']} {testo}"))})
    return {"nodi": nodi, "archi": [], "testi": [], "ambito": _ambito("camera", leg, chiave, info)}


# ---------------------------------------------------------------- Senato
def settimana(t: str) -> tuple[dt.date, dt.date] | None:
    """«Settimana dal 9 al 15 novembre 2026», «dal 30 novembre al 6 dicembre 2026», «dal 28 dicembre 2026 al 3 gennaio 2027»."""
    m = re.search(r"Settimana dal (\d{1,2})°?(?:\s+(\w+))?(?:\s+(\d{4}))?\s+al (\d{1,2})°?\s+(\w+)\s+(\d{4})", t)
    if not m or m.group(5).lower() not in MESI:
        return None
    fine = dt.date(int(m.group(6)), MESI[m.group(5).lower()], int(m.group(4)))
    mese = MESI.get((m.group(2) or "").lower(), fine.month)
    anno = int(m.group(3)) if m.group(3) else fine.year - (1 if mese > fine.month else 0)
    return dt.date(anno, mese, int(m.group(1))), fine


def atti_senato(cella: str) -> list[str]:
    """I riferimenti agli atti dai link della convocazione: disegni di legge (ddl:550), atti del Governo (ag:450) e
    nomine (nomina:147). Gli altri documenti non legislativi (Doc., COM) non hanno un atto nei dati."""
    atti = [f"ddl:{x}" for x in re.findall(r'Schede/Ddliter/\d+\.htm"[^>]*>\s*([\w-]+)\s*</a>', cella)]
    for testo in re.findall(r'Schede/docnonleg/\d+\.htm"[^>]*>(.*?)</a>', cella, re.S):
        t = _testo(testo)
        if re.fullmatch(r"\d+", t):
            atti.append(f"ag:{t}")
        elif (m := re.fullmatch(r"(?i)nomina n\.\s*(\d+)", t)):
            atti.append(f"nomina:{m.group(1)}")
    return list(dict.fromkeys(atti))


def trasforma_senato(grezzo: bytes, info: dict) -> dict:
    t = grezzo.decode("utf-8", errors="replace")
    chiave = info.get("chiave") or ""
    m = re.search(r"leg(\d+)-senato-conv-(\d+)", chiave)
    leg, n = (int(m.group(1)), int(m.group(2))) if m else (19, 0)
    i = t.find('class="commission-meetings"')
    corpo = t[i:t.find("</article>", i)] if i >= 0 else ""
    titoli = re.findall(r"csc-header-title'><b>(.*?)</b>", corpo, re.S)
    organo_nome = re.sub(r"\s+", " ", _testo(titoli[1]).replace("COMMISSIONE", "Commissione")) if len(titoli) > 1 else f"{n}ª Commissione"
    sett = settimana(_testo(corpo[:3000]))
    pubblicato = re.search(r"pubblicato alle ore[^<]+", corpo)
    nodi = []
    for gruppo in corpo.split('<div class="csc-day-group"')[1:] if sett else []:
        g = re.search(r'class="day-full">\s*\S+\s+(\d{1,2})', gruppo)
        if not g:
            continue
        giorno = next((d for d in (sett[0] + dt.timedelta(days=k) for k in range((sett[1] - sett[0]).days + 1)) if d.day == int(g.group(1))), None)
        if not giorno:
            continue
        for riga in re.split(r'<div class="csc-row(?=[ "])', gruppo)[1:]:
            classi, _, resto = riga.partition('"')
            quando = re.search(r'time-column"[^>]*>(.*?)</div>', resto, re.S)
            struttura = re.search(r'class="sottostruttura">(.*?)</span>', resto, re.S)
            numero = re.search(r"\(n\.\s*(\d+)\)", resto)
            aula = re.search(r"<small>(.*?)</small>", resto, re.S)
            testo = resto.split('testo-convocazione-column"', 1)[1].split(">", 1)[1] if 'testo-convocazione-column"' in resto else ""
            sedi = [_testo(x) for x in re.findall(r'class="csc-titolo-sede[^"]*">(.*?)</div>', testo, re.S)]
            quando_t = _testo(quando.group(1)) if quando else ""
            nodi.append({"label": "Convocation", "chamber": "senato",
                         "body": f"it:senato:{leg}:body:{ORGANI_SENATO[n]}" if n in ORGANI_SENATO else None, "body_name": organo_nome,
                         "date": giorno.isoformat(), "start_time": ora(quando_t), "when": quando_t or None,
                         "seat": "; ".join(dict.fromkeys(x for x in [_testo(struttura.group(1)) if struttura else "", *sedi] if x)) or None,
                         "place": re.sub(r"\s+", " ", _testo(aula.group(1))) if aula else None, "number": numero.group(1) if numero else None,
                         "text": _testo(testo) or None,
                         "acts": atti_senato(testo),
                         "cancelled": "sconvocata" in classi or bool(re.search(r"(?i)\bsconvocat", _testo(resto))),
                         "published": pubblicato.group(0).strip() if pubblicato else None, "url": info.get("url")})
    for i, x in enumerate(nodi, 1):
        x.update({"uri": f"it:senato:{leg}:conv:{n:02d}:{x['date']}:{i:02d}", "order": i})
    # la chiave del caricamento porta la settimana: le convocazioni delle settimane passate restano nel database
    return {"nodi": nodi, "archi": [], "testi": [], "ambito": _ambito("senato", leg, f"{chiave}-{sett[0]:%Y%m%d}" if sett else chiave, info)}
