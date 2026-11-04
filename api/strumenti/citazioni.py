"""Controllo delle citazioni: ogni testo tra «…» deve stare, parola per parola, nel testo di un intervento verbatim.
Un riassunto delle commissioni (`kind = summary`) non vale come fonte di una citazione."""

from __future__ import annotations

import re

import psycopg

from .comune import brevi

PARTI = re.compile(r"\s*(?:\[…\]|\[\.\.\.\]|…|\.\.\.)\s*")       # i tagli dentro una citazione


def _norm(t: str) -> str:
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


def verifica(c: psycopg.Connection, testo: str) -> dict:
    citazioni = [q.strip() for q in re.findall(r"«([^«»]{8,1500})»", testo)]
    esiti = []
    for q in citazioni:
        pezzi = [p for p in (_norm(x) for x in PARTI.split(q)) if len(p.split()) >= 3]
        if not pezzi:
            esiti.append({"quote": q, "found": False, "reason": "troppo corta per verificarla"})
            continue
        # prima l'indice di ricerca sul pezzo più lungo, poi il confronto esatto di tutti i pezzi, nell'ordine
        # tutte le parole del pezzo, senza la posizione: l'indice risponde da solo, mentre la frase esatta costringe a
        # ricalcolare il testo di ogni candidato (oltre 8 s con parole comuni, 4/11); l'ordine lo controlla il confronto
        lungo = max(pezzi, key=len)
        try:
            with c.transaction():
                c.execute("SET LOCAL statement_timeout = '6s'")
                righe = c.execute("""
                    SELECT s.uri, s.person, s.kind, s.speaker_label, st.uri AS sitting, st.chamber, st.date, s.text
                    FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
                    WHERE to_tsvector('italian', s.text) @@ plainto_tsquery('italian', %s)
                    ORDER BY s.kind = 'summary', st.date DESC LIMIT 200""", (lungo,)).fetchall()
        except psycopg.errors.QueryCanceled:
            esiti.append({"quote": q, "found": False, "unchecked": True, "reason": "controllo non finito in tempo"})
            continue
        trovato = None
        for r in righe:
            t, da = _norm(r["text"]), 0
            for p in pezzi:
                k = t.find(p, da)
                if k < 0:
                    break
                da = k + len(p)
            else:
                trovato = r
                break
        if trovato is None:
            esiti.append({"quote": q, "found": False, "reason": "non si trova, parola per parola, in nessun intervento"})
        elif trovato["kind"] == "summary":
            esiti.append({"quote": q, "found": False, "speech": trovato["uri"], "sitting": trovato["sitting"],
                          "reason": "sta in un resoconto sommario: è il riassunto del funzionario, non parole testuali"})
        else:
            p = brevi(c, [trovato["person"]], trovato["date"]).get(trovato["person"])
            esiti.append({"quote": q, "found": True, "speech": trovato["uri"], "sitting": trovato["sitting"], "chamber": trovato["chamber"],
                          "date": str(trovato["date"]), "speaker": p.name if p else trovato["speaker_label"],
                          "group": (p.group.short_name or p.group.name) if p and p.group else None})
    return {"quotes": len(citazioni), "verified": sum(e["found"] for e in esiti), "results": esiti}
