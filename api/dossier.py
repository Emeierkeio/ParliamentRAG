"""Le sezioni tecniche del dossier di un tema (card 284), accanto alle posizioni dei gruppi del fascicolo: gli emendamenti
presentati sul tema con l'esito, gli atti, chi ci lavora (i primi firmatari degli emendamenti), e cosa è in arrivo
(termini per gli emendamenti e audizioni sugli atti trovati). Tutto dalle stesse funzioni della chat e dell'MCP."""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter, defaultdict

import psycopg

from .strumenti import emendamenti, significato

EMENDAMENTI = 40


def sezioni(c: psycopg.Connection, tema: str) -> dict:
    em = emendamenti.cerca(c, testo=tema, limit=EMENDAMENTI * 3)
    # ordini del giorno (G1.9, G/1330/9/5) e questioni pregiudiziali (QP1) stanno fra gli emendamenti del Senato: qui no
    # in Aula lo stesso emendamento si ristampa a ogni seduta in cui l'esame continua: se ne tiene uno
    visti, items = set(), []
    for x in em["items"]:
        k = (x["atto"], x["numero"], x["sede"])
        if re.match(r"^(G\b|G[\d/]|QP|9/)", x["numero"]) or k in visti:
            continue
        visti.add(k)
        items.append(x)
    items = items[:EMENDAMENTI]
    esiti = Counter(x["etichetta"] for x in items)
    persone: dict[str, dict] = {}
    gruppi: dict[str, Counter] = defaultdict(Counter)
    for x in items:
        primo = next((f for f in x["firmatari"] if f["primo"]), x["firmatari"][0] if x["firmatari"] else None)
        if not primo:
            continue
        g = primo["gruppo"] or "non indicato"
        gruppi[g]["presentati"] += 1
        gruppi[g]["approvati"] += x["esito"] in ("approvato", "approvato_riformulato")
        if primo["persona"]:
            p = persone.setdefault(primo["persona"], {"nome": primo["nome"], "gruppo": g, "presentati": 0, "approvati": 0})
            p["presentati"] += 1
            p["approvati"] += x["esito"] in ("approvato", "approvato_riformulato")
    atti = significato.cerca(c, tema, ["atti"], quanti=8)["risultati"]
    uris = list({a["atto"] for a in atti if a.get("atto")} | {x["atto"] for x in items})
    oggi = dt.date.today()
    termini = [{"atto": t["act"], "organo": t["body_name"], "tipo": t["kind"], "scadenza": t["due_date"], "ora": t["due_time"], "frase": t["sentence"]}
               for t in c.execute("""SELECT act, body_name, kind, due_date, due_time, sentence FROM amendment_deadline
                                     WHERE act = ANY(%s) AND due_date >= %s ORDER BY due_date LIMIT 10""", (uris, oggi - dt.timedelta(days=7)))]
    audizioni = [{"atto": f["act"], "data": f["sitting_date"], "organo": f["body_name"], "chi": f["subject"]}
                 for f in c.execute("""SELECT act, sitting_date, body_name, subject FROM committee_fact
                                       WHERE kind = 'hearing' AND act = ANY(%s) ORDER BY sitting_date DESC LIMIT 20""", (uris,))]
    # il quadro in breve: per ogni atto toccato, a che punto è, quanti emendamenti sul tema, la prossima scadenza
    em_atto: dict[str, Counter] = defaultdict(Counter)
    for x in items:
        em_atto[x["atto"]]["presentati"] += 1
        em_atto[x["atto"]]["approvati"] += x["esito"] in ("approvato", "approvato_riformulato")
    scad = {}
    for t in termini:
        if t["scadenza"] >= oggi and t["atto"] not in scad:
            scad[t["atto"]] = t
    ultima_aud = {}
    for a in audizioni:
        ultima_aud.setdefault(a["atto"], a)
    righe = c.execute("""SELECT uri, chamber, number, title, status, status_date, law_number, law_date, card_url, date
                         FROM act WHERE uri = ANY(%s)""", (uris,)).fetchall()
    # titoli come «C. 2750 S. 1689. - "Bilancio di previsione…"»: via le sigle e le virgolette in testa
    pulito = lambda t: re.sub(r'^(?:\s*[CS]\.\s*\d+(?:-\w+)?\.?)*\s*[-–.]?\s*["“]?|["”]\s*$', "", t or "").strip()
    quadro = [{"atto": r["uri"], "sigla": ("C. " if r["chamber"] == "camera" else "S. ") + r["number"], "titolo": pulito(r["title"]),
               "stato": r["status"], "data_stato": r["status_date"], "legge": r["law_number"], "data_legge": r["law_date"],
               "url": r["card_url"], "emendamenti": em_atto[r["uri"]]["presentati"], "approvati": em_atto[r["uri"]]["approvati"],
               "scadenza": scad.get(r["uri"]), "audizione": ultima_aud.get(r["uri"]), "data": r["date"]} for r in righe]
    quadro.sort(key=lambda q: (q["scadenza"] is None, q["legge"] is not None, -q["emendamenti"], -(q["data"] or dt.date.min).toordinal()))
    return {"tema": tema, "quadro": quadro[:12],
            "emendamenti": {"totale_simili": em["total"], "mostrati": len(items), "per_esito": dict(esiti.most_common()), "elenco": items[:20]},
            "atti": atti,
            "chi_ci_lavora": {"gruppi": [{"gruppo": g, **v} for g, v in sorted(gruppi.items(), key=lambda kv: -kv[1]["presentati"])],
                              "persone": sorted(persone.values(), key=lambda p: (-p["approvati"], -p["presentati"]))[:10]},
            "in_arrivo": {"termini": termini, "audizioni": audizioni},
            "nota": f"Emendamenti e atti trovati per vicinanza di significato al tema (i {EMENDAMENTI} più vicini): non sono "
                    "tutti quelli della legislatura. «Chi ci lavora» conta i primi firmatari di questi emendamenti: è un dato "
                    "pubblico sul lavoro parlamentare, non un elenco di contatti."}
