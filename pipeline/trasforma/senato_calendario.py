"""Dal calendario dei lavori dell'Assemblea del Senato (HTML) alle voci previste giorno per giorno (`CalendarItem`).

La pagina ha un titolo per settimana («Martedì 17 novembre (16,30-22) - Mercoledì 18 novembre (10-22) - Giovedì 19
novembre (10)») seguito dall'elenco degli argomenti, che vale per tutti i giorni del titolo: quando un argomento ha il
suo giorno lo dice fra parentesi («(giovedì 19, ore 15)»). Una settimana senza Aula è una frase («La settimana dal 9
al 13 novembre sarà riservata ai lavori delle Commissioni»): diventa una voce per ogni giorno feriale, così chi chiede
di quel giorno lo sa. L'anno non è scritto: le settimane sono in ordine, la prima è la più vicina a oggi e quando il
mese torna indietro è cambiato l'anno. Trasformazione pura (la data di oggi entra come argomento).
"""

from __future__ import annotations

import datetime as dt
import html
import re

from .camera_calendario import GIORNI, MESI

RISERVATA = re.compile(rf"La settimana dal (\d{{1,2}})°?(?: ({'|'.join(MESI)}))? al (\d{{1,2}})°? ({'|'.join(MESI)}) sarà riservata[^<]*", re.I)


def _pulito(t: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("​", "").replace("\xa0", " ")
    return re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"\(\s+", "(", re.sub(r"\s+", " ", t))).strip()


def _giorni(titolo: str) -> list[tuple[int, int]]:
    """(giorno, mese) nominati in un titolo; un giorno senza mese prende quello scritto dopo."""
    trovati = [(int(m.group(1)), (m.group(2) or "").lower()) for m in
               re.finditer(rf"(?:{GIORNI})\s+(\d{{1,2}})°?(?:\s+({'|'.join(MESI)}))?", titolo, re.I)]
    out, mese = [], None
    for giorno, nome in reversed(trovati):
        mese = MESI.get(nome) or mese
        if mese:
            out.append((giorno, mese))
    return out[::-1]


def trasforma(corpo: bytes, fonte: dict, leg: int = 19, oggi: dt.date | None = None) -> dict:
    oggi = oggi or dt.date.today()
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", corpo.decode("utf-8", errors="replace"), flags=re.S)
    # i blocchi nell'ordine della pagina: una settimana d'Aula (titolo e elenco) o una settimana riservata
    settimane = list(re.finditer(r"<h3[^>]*>(.*?)</h3>\s*<ul>(.*?)</ul>", t, re.S))
    riservate = list(RISERVATA.finditer(html.unescape(t)))
    nodi, ordine, anno, ultimo = [], {}, None, None

    def data(giorno: int, mese: int) -> dt.date | None:
        nonlocal anno, ultimo
        if anno is None:                                 # la prima settimana della pagina: l'anno che la porta più vicina a oggi
            anno = min((oggi.year - 1, oggi.year, oggi.year + 1), key=lambda y: abs((dt.date(y, mese, min(giorno, 28)) - oggi).days))
        elif ultimo and mese < ultimo.month - 6:
            anno += 1
        try:
            d = dt.date(anno, mese, giorno)
        except ValueError:
            return None
        ultimo = d
        return d

    def voce(d: dt.date, quando: str | None, titolo: str, atti: list[str]) -> None:
        n = ordine[d] = ordine.get(d, 0) + 1
        nodi.append({"label": "CalendarItem", "uri": f"it:senato:{leg}:calendario:{d:%Y%m%d}:{n:02d}", "chamber": "senato",
                     "date": d.isoformat(), "order": n, "when": quando, "title": titolo[:1500], "acts": atti,
                     "calendar": "Calendario dei lavori", "updated": None})

    for m in settimane:
        titolo = _pulito(m.group(1))
        date = [d for d in (data(g, me) for g, me in _giorni(titolo)) if d]
        for li in re.findall(r"<li>(.*?)</li>", m.group(2), re.S):
            x = _pulito(li)
            if len(x) < 6:
                continue
            atti = [f"ddl:{n}" for n in re.findall(r"Ddl(?: costituzionale)? n\.\s*<a[^>]*>\s*([\d-]+[A-Za-z-]*)\s*</a>", li)]
            # un argomento con il suo giorno fra parentesi («(giovedì 19, ore 15)») vale solo per quello
            suoi = {int(g) for g in re.findall(rf"\((?:{GIORNI})\s+(\d{{1,2}})", x, re.I)}
            for d in date:
                if not suoi or d.day in suoi:
                    voce(d, titolo, x, list(dict.fromkeys(atti)))
    # le settimane riservate alle commissioni: l'anno è quello della settimana d'Aula più vicina già datata
    date_note = sorted({dt.date.fromisoformat(n["date"]) for n in nodi})
    for m in riservate:
        mese_fine = MESI[m.group(4).lower()]
        mese_inizio = MESI.get((m.group(2) or "").lower(), mese_fine)
        base = min(date_note, key=lambda d: abs((dt.date(d.year, mese_fine, 15) - d).days)) if date_note else oggi
        try:
            inizio, fine = dt.date(base.year, mese_inizio, int(m.group(1))), dt.date(base.year, mese_fine, int(m.group(3)))
        except ValueError:
            continue
        if not dt.timedelta(0) <= fine - inizio <= dt.timedelta(days=13):
            continue
        frase = _pulito(m.group(0))
        d = inizio
        while d <= fine:
            if d.weekday() < 5 and d not in ordine:
                voce(d, None, frase, [])
            d += dt.timedelta(days=1)
    nodi.sort(key=lambda n: (n["date"], n["order"]))
    return {"nodi": nodi, "archi": [], "testi": [],
            "ambito": {"kind": "calendario", "chamber": "senato", "legislature": leg, "calendar": "Calendario dei lavori",
                       "source": "senato_calendario", "source_key": fonte.get("chiave")}}
