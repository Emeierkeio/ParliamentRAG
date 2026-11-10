"""Dal calendario dei lavori dell'Assemblea (HTML) alle voci previste giorno per giorno (`CalendarItem`): la data,
l'orario come lo scrive la Camera, il testo della voce e gli atti collegati.

Una riga del calendario può valere per più giorni («Mercoledì 11 e giovedì 12 novembre»): la voce si ripete per
ognuno, con l'indicazione intera dei giorni. Non sono sedute: il numero della seduta e l'ordine del giorno arrivano
dopo, da camera_odg. Trasformazione pura.
"""

from __future__ import annotations

import datetime as dt
import html
import re

MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                     "settembre", "ottobre", "novembre", "dicembre"], 1)}
GIORNI = r"luned[ìi]|marted[ìi]|mercoled[ìi]|gioved[ìi]|venerd[ìi]|sabato|domenica"


def _pulito(t: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("​", "").replace("\xa0", " ")
    return re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"\(\s+", "(", re.sub(r"\s+", " ", t))).strip()


def date_di(etichetta: str, anno: int, mese_base: int) -> list[dt.date]:
    """I giorni nominati in un'etichetta: «Mercoledì 11 (…) e giovedì 12 novembre (… venerdì 13 novembre)». Un giorno
    senza mese prende il mese scritto dopo; un mese molto prima di quello del calendario è dell'anno dopo."""
    trovati = [(m.start(), int(m.group(1)), (m.group(2) or "").lower()) for m in
               re.finditer(rf"(?:{GIORNI})\s+(\d{{1,2}})°?(?:\s+({'|'.join(MESI)}))?", etichetta, re.I)]
    out, mese_dopo = [], None
    for _, giorno, mese in reversed(trovati):
        mese_dopo = MESI.get(mese) or mese_dopo
        if not mese_dopo:
            continue
        try:
            d = dt.date(anno + (1 if mese_dopo < mese_base - 6 else 0), mese_dopo, giorno)
        except ValueError:
            continue
        if d not in out:
            out.append(d)
    return sorted(out)


def trasforma(corpo: bytes, fonte: dict, leg: int = 19) -> dict:
    t = corpo.decode("utf-8", errors="replace")
    periodo = re.search(r'class="calendario_periodo">\s*\(?\s*([a-zà-ù]+)(?:\s*[-–]\s*[a-zà-ù]+)?\s+(\d{4})', t, re.I)
    if not periodo or periodo.group(1).lower() not in MESI:
        raise ValueError("calendario senza il periodo (mese e anno)")
    mese_base, anno = MESI[periodo.group(1).lower()], int(periodo.group(2))
    numero = re.search(r'class="calendario_protocollo">\s*N\.\s*(\d+)', t)
    aggiornato = re.search(r'class="calendario_intestazione">\s*<p>(.*?)</p>', t, re.S)
    tabella = re.search(r'<table class="calendario_punti">(.*?)</table>', t, re.S)
    if not tabella:
        raise ValueError("calendario senza la tabella dei giorni")
    nome = f"Calendario n. {numero.group(1)}" if numero else "Calendario"
    nodi, ordine = [], {}
    for riga in re.findall(r"<tr>(.*?)</tr>", tabella.group(1), re.S):
        celle = re.findall(r"<td[^>]*>(.*?)</td>", riga, re.S)
        if not celle:
            continue
        etichetta = _pulito(celle[0])
        if len(celle) == 1:                                  # riga unica: il giorno e la voce nella stessa frase
            voci, quando = [(etichetta, celle[0])], None
        else:
            voci = [(_pulito(p), p) for p in re.findall(r"<p[^>]*>(.*?)</p>", celle[1], re.S)]
            quando = etichetta
        for d in date_di(etichetta, anno, mese_base):
            for testo, grezzo in voci:
                if len(testo) < 8:
                    continue
                n = ordine[d] = ordine.get(d, 0) + 1
                atti = [f"ac:{x}" for x in re.findall(r"tipoDoc=pdl&amp;idDocumento=(\d+[\w-]*)", grezzo)]
                atti += [f"aic:{x}" for x in re.findall(r"\bn\.\s*(\d-\d{5})\b", testo)]
                nodi.append({"label": "CalendarItem", "uri": f"it:camera:{leg}:calendario:{d:%Y%m%d}:{n:02d}", "chamber": "camera",
                             "date": d.isoformat(), "order": n, "when": quando, "title": testo[:1500],
                             "acts": list(dict.fromkeys(atti)), "calendar": nome,
                             "updated": _pulito(aggiornato.group(1)) if aggiornato else None})
    return {"nodi": nodi, "archi": [], "testi": [],
            "ambito": {"kind": "calendario", "chamber": "camera", "legislature": leg, "calendar": nome,
                       "source": "camera_calendario", "source_key": fonte.get("chiave")}}
