"""Un soggetto (un'azienda, un'associazione, un ente) e i temi parlamentari che lo riguardano (card 284).

Il legame fra un'azienda e un tema («Coca-Cola» → sugar tax) non sta nei resoconti: lo propone il modello. Qui ogni
proposta si verifica sui dati, e passa all'utente solo con i suoi numeri: interventi, emendamenti e atti per un tema,
audizioni e memorie per un'associazione. Le proposte senza riscontro non passano. L'utente sceglie; il modello propone
soltanto."""

from __future__ import annotations

import psycopg

TETTO = 1000                 # i conteggi si fermano qui: servono a scegliere, non a fare statistiche


def _conta(c: psycopg.Connection, sql: str, p: dict) -> int:
    return c.execute(f"SELECT count(*) AS n FROM ({sql} LIMIT {TETTO}) x", p).fetchone()["n"]


def tema(c: psycopg.Connection, parole: str) -> dict:
    p = {"q": parole}
    return {"interventi": _conta(c, """SELECT 1 FROM speech WHERE kind IS DISTINCT FROM 'summary'
                                      AND to_tsvector('italian', text) @@ websearch_to_tsquery('italian', %(q)s)""", p),
            "emendamenti": _conta(c, """SELECT 1 FROM amendment
                                       WHERE to_tsvector('italian', coalesce(text, '')) @@ websearch_to_tsquery('italian', %(q)s)""", p),
            "atti": _conta(c, """SELECT 1 FROM act
                                WHERE to_tsvector('italian', coalesce(title, '')) @@ websearch_to_tsquery('italian', %(q)s)""", p)}


def soggetto(c: psycopg.Connection, nome: str) -> dict:
    p = {"l": f"%{nome}%"}
    audizioni = c.execute("""SELECT s.date, i.title FROM agenda_item i JOIN sitting s ON s.uri = i.sitting
                             WHERE i.title ILIKE %(l)s AND i.title ~* 'audizion' ORDER BY s.date DESC LIMIT 20""", p).fetchall()
    memorie = c.execute("""SELECT date, title, url FROM document WHERE coalesce(author_raw, '') ILIKE %(l)s
                           OR (kind = 'memorandum' AND coalesce(title, '') ILIKE %(l)s) ORDER BY date DESC NULLS LAST LIMIT 20""", p).fetchall()
    return {"audizioni": len(audizioni), "memorie": len(memorie),
            "interventi": _conta(c, """SELECT 1 FROM speech WHERE kind IS DISTINCT FROM 'summary'
                                       AND to_tsvector('italian', text) @@ websearch_to_tsquery('italian', %(q)s)""", {"q": f'"{nome}"'}),
            "ultime_audizioni": [{"data": a["date"], "titolo": a["title"][:200]} for a in audizioni[:5]],
            "memorie_elenco": [{"data": m["date"], "titolo": (m["title"] or "")[:200], "url": m["url"]} for m in memorie[:5]]}


def proponi(c: psycopg.Connection, nome: str, temi: list[dict], associazioni: list[str]) -> dict:
    """`temi`: [{nome, parole}] con le parole come le scrive il Parlamento («"bevande edulcorate" or "sugar tax"»);
    `associazioni`: i nomi delle associazioni di categoria. Torna le opzioni verificate, con i numeri."""
    diretto = soggetto(c, nome)
    opzioni = []
    for t in temi[:8]:
        n = tema(c, t["parole"])
        if sum(n.values()):
            # un tema che arriva al tetto è troppo generico per un dossier: si mostra, ma non si consiglia
            opzioni.append({"tipo": "tema", "nome": t["nome"], "parole": t["parole"], "conteggi": n, "peso": sum(n.values()),
                            "generico": max(n.values()) >= TETTO})
    for a in associazioni[:4]:
        s = soggetto(c, a)
        if s["audizioni"] or s["memorie"]:
            opzioni.append({"tipo": "associazione", "nome": a, "conteggi": {k: s[k] for k in ("audizioni", "memorie", "interventi")},
                            "peso": s["audizioni"] * 20 + s["memorie"] * 10 + s["interventi"], "ultime_audizioni": s["ultime_audizioni"]})
    temi_ok = [o for o in opzioni if o["tipo"] == "tema" and not o["generico"]]
    if temi_ok:
        max(temi_ok, key=lambda o: o["peso"])["consigliato"] = True
    return {"soggetto": nome, "diretto": diretto, "opzioni": opzioni,
            "scartate": [t["nome"] for t in temi[:8] if t["nome"] not in {o["nome"] for o in opzioni}]
                        + [a for a in associazioni[:4] if a not in {o["nome"] for o in opzioni}],
            "nota": "Temi e associazioni sono proposte del modello, verificate sui dati: l'utente sceglie sopra la casella. "
                    f"I conteggi si fermano a {TETTO}."}
