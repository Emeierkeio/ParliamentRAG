"""L'agenda del Parlamento, giorno per giorno: sedute d'Aula (previste e tenute, e i giorni del calendario dei lavori
che non hanno ancora una seduta: status «calendar»), sedute di commissione, termini per gli
emendamenti, progetti di legge presentati, votazioni finali e leggi pubblicate. La usano la chat (strumento `agenda`),
il server MCP pubblico (get_parliament_agenda) e la pagina Agenda del sito.

Un termine compare una volta sola anche se il sommario lo ricorda in più sedute (fissato, ricordato, scaduto); un termine
spostato più tardi a un'altra data resta, segnato come superato."""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import defaultdict

import psycopg

TIPI = ("aula", "commissioni", "termini", "atti", "voti", "leggi")
MASSIMO_GIORNI = 62


def _ramo(ramo: str | None) -> str | None:
    return ramo if ramo in ("camera", "senato") else None


def termini(c: psycopg.Connection, start: dt.date, end: dt.date, chamber: str | None = None, act: str | None = None) -> list[dict]:
    """I termini con scadenza fra `start` e `end`, uno per atto, organo, tipo e data, con l'evento più recente."""
    righe = c.execute("""
        SELECT d.uri, d.chamber, d.act, d.act_refs, d.body, d.body_name, d.sitting, d.sitting_date, d.speech, d.kind, d.event,
               d.due_date, to_char(d.due_time, 'HH24:MI') AS due_time, d.presented, d.sentence, a.title AS act_title, a.number AS act_number, a.card_url AS act_url,
               EXISTS (SELECT 1 FROM amendment_deadline n                     -- spostato dopo a un'altra data
                       WHERE n.chamber = d.chamber AND n.body IS NOT DISTINCT FROM d.body AND n.act_refs = d.act_refs AND n.kind = d.kind
                         AND n.event = 'extended' AND n.due_date <> d.due_date AND n.sitting_date > d.sitting_date
                         AND n.sitting_date <= d.due_date) AS superseded
        FROM amendment_deadline d LEFT JOIN act a ON a.uri = d.act
        WHERE d.due_date BETWEEN %(s)s AND %(e)s AND (%(r)s::text IS NULL OR d.chamber = %(r)s)
          AND (%(a)s::text IS NULL OR d.act = %(a)s OR %(a)s = ANY (d.act_refs))
        ORDER BY d.due_date, d.due_time NULLS LAST, d.sitting_date""", {"s": start, "e": end, "r": _ramo(chamber), "a": act}).fetchall()
    # lo stesso termine ricordato in più sedute, o da un'altra commissione («presso la Commissione di merito»), con o
    # senza l'ora: una voce sola, con l'ora se una menzione la dice e tutti gli organi che ne parlano
    uno: dict[tuple, dict] = {}
    for r in righe:
        k = (r["chamber"], tuple(r["act_refs"]) or r["body"], r["kind"].removesuffix(" e ordini del giorno"), r["due_date"])
        if k not in uno:
            uno[k] = {**r, "mentions": 1, "first_sitting": r["sitting_date"], "bodies": [r["body_name"]]}
            continue
        prima = uno[k]
        piu_recente = r if r["sitting_date"] >= prima["sitting_date"] else prima
        uno[k] = {**piu_recente, "kind": max(prima["kind"], r["kind"], key=len), "mentions": prima["mentions"] + 1, "first_sitting": min(prima["first_sitting"], r["sitting_date"]),
                  "due_time": prima["due_time"] or r["due_time"], "presented": r["presented"] or prima["presented"],
                  "superseded": r["superseded"] and prima["superseded"],
                  "body_name": prima["body_name"] if prima["due_time"] or not r["due_time"] else r["body_name"],
                  "bodies": list(dict.fromkeys(prima["bodies"] + [r["body_name"]]))}
    return sorted(uno.values(), key=lambda t: (t["due_date"], t["due_time"] or "99"))


def agenda(c: psycopg.Connection, start: dt.date, end: dt.date, chamber: str | None = None, types: list[str] | None = None) -> dict:
    """Gli eventi fra `start` e `end` (al più MASSIMO_GIORNI), divisi per giorno e tipo."""
    if end < start:
        start, end = end, start
    end = min(end, start + dt.timedelta(days=MASSIMO_GIORNI - 1))
    tipi = [t for t in (types or TIPI) if t in TIPI]
    p = {"s": start, "e": end, "r": _ramo(chamber)}
    giorni: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    if "aula" in tipi:
        for r in c.execute("""
            SELECT s.uri, s.chamber, s.number, s.date, s.status, s.start_time, s.record_url,
                   (SELECT array_agg(i.title ORDER BY i.ord) FILTER (WHERE i.title IS NOT NULL AND NOT coalesce(i.procedural, false))
                    FROM agenda_item i WHERE i.sitting = s.uri) AS items,
                   (SELECT count(*) FROM vote v WHERE v.sitting = s.uri) AS votes
            FROM sitting s WHERE s.body LIKE '%%:aula' AND s.date BETWEEN %(s)s AND %(e)s AND (%(r)s::text IS NULL OR s.chamber = %(r)s)
            ORDER BY s.date, s.chamber, s.number""", p):
            giorni[r["date"].isoformat()]["aula"].append({**r, "items": (r["items"] or [])[:8], "items_total": len(r["items"] or [])})
        # il calendario dei lavori dell'Assemblea: per i giorni da oggi in poi che non hanno ancora una seduta (né
        # l'ordine del giorno né il resoconto), quello che il calendario prevede
        if _c_e_il_calendario(c):
            con_seduta = {(g, x["chamber"]) for g, ev in giorni.items() for x in ev.get("aula", [])}
            per_giorno: dict[tuple, list] = defaultdict(list)
            for r in c.execute("""SELECT chamber, date, when_text, title, acts, calendar, updated FROM calendar_item
                                  WHERE date BETWEEN %(s)s AND %(e)s AND date >= current_date AND (%(r)s::text IS NULL OR chamber = %(r)s)
                                  ORDER BY date, chamber, ord""", p):
                per_giorno[(r["date"].isoformat(), r["chamber"])].append(r)
            for (g, ramo), voci in per_giorno.items():
                if (g, ramo) in con_seduta:
                    continue
                quando = list(dict.fromkeys(v["when_text"] for v in voci if v["when_text"]))
                giorni[g]["aula"].append({
                    "uri": None, "chamber": ramo, "number": None, "date": g, "status": "calendar", "start_time": _inizio(quando, int(g[-2:])),
                    "record_url": None, "items": [v["title"] for v in voci][:8], "items_total": len(voci), "votes": 0, "schedule": quando[:4],
                    "acts": sorted({a for v in voci for a in (v["acts"] or [])}), "calendar": voci[0]["calendar"], "updated": voci[0]["updated"]})
    if "commissioni" in tipi:
        for r in c.execute("""
            SELECT s.date, s.chamber, s.body, coalesce(nullif(trim(s.body_name), ''), b.name) AS body_name, count(*) AS sittings,
                   array_remove(array_agg(DISTINCT initcap(lower(s.seat))), NULL) AS seats,
                   (SELECT array_agg(DISTINCT i.title) FROM agenda_item i JOIN sitting s2 ON s2.uri = i.sitting
                    WHERE s2.body = s.body AND s2.date = s.date AND i.title IS NOT NULL AND NOT coalesce(i.procedural, false)) AS items
            FROM sitting s LEFT JOIN body b ON b.uri = s.body
            WHERE s.body NOT LIKE '%%:aula' AND s.date BETWEEN %(s)s AND %(e)s AND (%(r)s::text IS NULL OR s.chamber = %(r)s)
            GROUP BY s.date, s.chamber, s.body, 4 ORDER BY s.date, s.chamber, 4""", p):
            giorni[r["date"].isoformat()]["commissioni"].append({**r, "items": sorted(r["items"] or [])[:6], "items_total": len(r["items"] or [])})
    if "termini" in tipi:
        for t in termini(c, start, end, chamber):
            giorni[t["due_date"].isoformat()]["termini"].append(t)
    if "atti" in tipi:
        for r in c.execute("""
            SELECT a.uri, a.chamber, a.number, a.title, a.date, a.initiative, a.card_url
            FROM act a WHERE a.kind = 'bill' AND a.date BETWEEN %(s)s AND %(e)s AND (%(r)s::text IS NULL OR a.chamber = %(r)s)
            ORDER BY a.date, a.chamber, a.number""", p):
            giorni[r["date"].isoformat()]["atti"].append(r)
    if "voti" in tipi:
        for r in c.execute("""
            SELECT v.uri, v.chamber, v.date, v.number, v.title, v.approved, v.favor, v.against, v.abstain, v.confidence, v.source_url,
                   (SELECT a.title FROM vote_act x JOIN act a ON a.uri = x.act WHERE x.vote = v.uri LIMIT 1) AS act_title
            FROM vote v WHERE v.final AND v.date BETWEEN %(s)s AND %(e)s AND (%(r)s::text IS NULL OR v.chamber = %(r)s)
            ORDER BY v.date, v.chamber, v.number""", p):
            giorni[r["date"].isoformat()]["voti"].append(r)
    if "leggi" in tipi:
        for r in c.execute("""
            SELECT a.uri, a.chamber, a.number, a.title, a.law_number, a.law_date
            FROM act a WHERE a.law_date BETWEEN %(s)s AND %(e)s AND (%(r)s::text IS NULL OR a.chamber = %(r)s)
            ORDER BY a.law_date, a.law_number""", p):
            giorni[r["law_date"].isoformat()]["leggi"].append(r)
    conti = {t: sum(len(g.get(t, [])) for g in giorni.values()) for t in tipi}
    fuori = {"start": start.isoformat(), "end": end.isoformat(), "types": tipi, "counts": conti,
             "days": {d: dict(g) for d, g in sorted(giorni.items())}}
    if "aula" in tipi:                                      # prima dei giorni: un periodo lungo non deve tagliarla via
        fuori = {k: v for k, v in fuori.items() if k != "days"} | {"coverage": _copertura(c, end, _ramo(chamber)), "days": fuori["days"]}
    return json.loads(json.dumps(fuori, default=str))      # date e ore come testo, per la chat, l'MCP e il sito


NOMI_RAMO = {"camera": "Camera", "senato": "Senato"}


def _c_e_il_calendario(c: psycopg.Connection) -> bool:
    """La tabella nasce con il primo giro dopo il rilascio: fino ad allora l'agenda resta com'era."""
    return bool(c.execute("SELECT to_regclass('calendar_item') IS NOT NULL AS c").fetchone()["c"])


def _inizio(quando: list[str], giorno: int) -> str | None:
    """L'ora d'inizio di un giorno fra le indicazioni del calendario: quella scritta accanto al giorno; se un'indicazione
    vale per più giorni e per questo non dà l'ora, niente (meglio nessuna ora che quella di un altro giorno)."""
    for q in quando:
        if re.search(rf"\b{giorno}°?(?:\s+[a-zà-ù]+)?\s*\(\s*(?:ore\s+)?\d", q, re.I):
            return _ora(q, giorno)
    una = [q for q in quando if len(re.findall(r"luned|marted|mercoled|gioved|venerd|sabato|domenica", q, re.I)) <= 1]
    return _ora(una[0]) if una else None


def _ora(t: str, giorno: int | None = None) -> str | None:
    """L'ora d'inizio in un'indicazione del calendario: «(ore 12)», «(ore 9,30-13,30 …)», «(16,30-22)». Con più giorni
    nella stessa indicazione («Martedì 17 novembre (16,30-22) - Mercoledì 18 novembre (10-22)»), quella del giorno chiesto."""
    ora = r"\(\s*(?:ore\s+)?(\d{1,2})(?:[,.](\d{2}))?"
    m = (re.search(rf"\b{giorno}°?(?:\s+[a-zà-ù]+)?\s*{ora}", t, re.I) if giorno else None) or re.search(ora, t, re.I)
    return f"{int(m.group(1)):02d}:{m.group(2) or '00'}" if m and int(m.group(1)) < 24 else None


def _copertura(c: psycopg.Connection, fine: dt.date, ramo: str | None) -> dict:
    """Fin dove arrivano nei dati le sedute d'Aula di ogni ramo. Delle sedute future c'è solo l'ordine del giorno già
    pubblicato (di solito la seduta successiva), non il calendario dei lavori: oltre quella data un giorno senza
    sedute non dice che l'Aula non si riunisce (10/11/2026: «domani c'è Aula?» riceveva un no)."""
    righe = {r["chamber"]: r for r in c.execute("""
        SELECT chamber, max(date) FILTER (WHERE status = 'held') AS tenuta, max(date) FILTER (WHERE status <> 'held') AS prevista
        FROM sitting WHERE body LIKE '%%:aula' GROUP BY 1""")}
    calendario = ({r["chamber"]: r["fino"] for r in c.execute("SELECT chamber, max(date) AS fino FROM calendar_item GROUP BY 1")}
                  if _c_e_il_calendario(c) else {})
    out, scoperti = {}, []
    for r in ([ramo] if ramo else ["camera", "senato"]):
        x = righe.get(r) or {"tenuta": None, "prevista": None}
        fino = max([d for d in (x["tenuta"], x["prevista"], calendario.get(r)) if d], default=None)
        out[r] = {"last_held": x["tenuta"], "last_planned": x["prevista"], "calendar_until": calendario.get(r), "known_until": fino}
        if fino is None or fine > fino:
            scoperti.append(f"{NOMI_RAMO[r]} dopo il {fino.strftime('%d/%m/%Y')}" if fino else NOMI_RAMO[r])
    if scoperti:
        out["note"] = ("Sedute d'Aula non ancora nei dati: " + "; ".join(scoperti) + ". Dei giorni futuri i dati hanno l'ordine del giorno "
                       "già pubblicato e, dove c'è (calendar_until), il calendario dei lavori dell'Assemblea: oltre quelle date non dire che l'Aula non si riunisce, di' che "
                       "il calendario non è ancora nei dati e rimanda a www.camera.it e www.senato.it.")
    return out
