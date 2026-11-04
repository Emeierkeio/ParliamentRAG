"""Pezzi comuni agli strumenti: la persona in breve con il gruppo alla data, il gruppo, la stessa persona con due schede."""

from __future__ import annotations

import datetime as dt
import re
import time

import psycopg

from ..modelli import Group, PersonBrief

LEGISLATURA = 19
RAMI = ("camera", "senato")

# Una persona e il suo gruppo alla data. Le schede segnaposto del Senato (membri del governo senza anagrafica del
# Senato) si mostrano con la scheda della Camera a cui sono legate.
SQL_BREVI = """
WITH x AS (
  SELECT u.uri AS chiesto, coalesce(
           (SELECT s.person FROM person_same_as s JOIN person p0 ON p0.uri = u.uri AND p0.stub WHERE s.same_as = u.uri LIMIT 1),
           u.uri) AS uri
  FROM unnest(%(uris)s::text[]) AS u(uri))
SELECT x.chiesto, p.uri, nullif(trim(concat_ws(' ', p.given_name, p.family_name)), '') AS name, p.photo,
       m.chamber, (m.chamber IS NOT NULL AND m.end_date IS NULL) AS in_office,
       g.uri AS g_uri, g.name AS g_name, g.short_name AS g_short, g.kind AS g_kind, g.part_of AS g_part_of
FROM x JOIN person p ON p.uri = x.uri
LEFT JOIN LATERAL (SELECT chamber, end_date FROM mandate WHERE person = p.uri AND legislature = %(leg)s
                   ORDER BY start_date DESC LIMIT 1) m ON true
LEFT JOIN grp g ON g.uri = group_at(p.uri, coalesce(%(d)s::date, least(current_date, coalesce(m.end_date, current_date))))
"""


def gruppo(r: dict, prefisso: str = "g_") -> Group | None:
    if not r.get(prefisso + "uri"):
        return None
    return Group(uri=r[prefisso + "uri"], name=r[prefisso + "name"], short_name=r[prefisso + "short"],
                 kind=r[prefisso + "kind"], part_of=r[prefisso + "part_of"])


def breve(r: dict) -> PersonBrief:
    return PersonBrief(uri=r["uri"], name=r["name"] or r["uri"], chamber=r["chamber"], in_office=r["in_office"],
                       group=gruppo(r), photo=r["photo"])


def brevi(c: psycopg.Connection, uris: list[str], d: dt.date | None = None) -> dict[str, PersonBrief]:
    """Le persone in breve, per uri chiesto. Il gruppo è quello alla data `d` (oggi, se manca)."""
    uris = sorted({u for u in uris if u})
    if not uris:
        return {}
    return {r["chiesto"]: breve(r) for r in c.execute(SQL_BREVI, {"uris": uris, "leg": LEGISLATURA, "d": d})}


def stessa_persona(c: psycopg.Connection, uri: str) -> list[str]:
    """Tutte le schede della stessa persona, compresa `uri`."""
    righe = c.execute("""SELECT %(u)s AS u UNION SELECT same_as FROM person_same_as WHERE person = %(u)s
                         UNION SELECT person FROM person_same_as WHERE same_as = %(u)s""", {"u": uri})
    return sorted(r["u"] for r in righe)


# ---------- link al resoconto ----------

_colonne: dict[tuple[str, str], tuple[float, bool]] = {}


def ha_colonna(c: psycopg.Connection, tabella: str, colonna: str) -> bool:
    """Se la colonna c'è nel database (si ricontrolla ogni dieci minuti: la pipeline può aggiungerla mentre il servizio
    gira)."""
    k = (tabella, colonna)
    x = _colonne.get(k)
    if x is None or time.monotonic() - x[0] > 600:
        r = c.execute("""SELECT EXISTS (SELECT 1 FROM information_schema.columns
                                        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s) AS ok""",
                      k).fetchone()
        x = _colonne[k] = (time.monotonic(), bool(r["ok"]))
    return x[1]


def url_intervento(uri: str | None, record_url: str | None = None) -> str | None:
    """La pagina del resoconto di un intervento. Camera: lo stenografico con l'ancora dell'intervento. Senato (e ogni
    intervento senza ancora): la pagina del resoconto della seduta (sitting.record_url), se c'è; se no None."""
    m = re.match(r"it:camera:(\d+):sed(\d+):(.+)$", uri or "")
    if m:
        leg, sed, ancora = m.group(1), m.group(2).zfill(4), m.group(3)
        return f"https://www.camera.it/leg{leg}/410?idSeduta={sed}&tipo=stenografico#sed{sed}.stenografico.{ancora}"
    return record_url or None


def url_seduta(uri: str, status: str | None, kind: str | None, record_url: str | None = None) -> str | None:
    """Il resoconto di una seduta tenuta: all'Aula della Camera lo stenografico, altrove sitting.record_url."""
    m = re.match(r"it:camera:(\d+):sed(\d+)$", uri or "")
    if m and status == "held" and kind == "assembly_verbatim":
        return f"https://www.camera.it/leg{m.group(1)}/410?idSeduta={m.group(2).zfill(4)}&tipo=stenografico"
    return record_url or None


def url_sedute(c: psycopg.Connection, sedute: list[str]) -> dict[str, str]:
    """sitting.record_url delle sedute che lo hanno; {} se la colonna non c'è ancora o è vuota."""
    sedute = sorted({s for s in sedute if s})
    if not sedute or not ha_colonna(c, "sitting", "record_url"):
        return {}
    righe = c.execute("SELECT uri, record_url FROM sitting WHERE uri = ANY(%s) AND record_url IS NOT NULL", (sedute,))
    return {r["uri"]: r["record_url"] for r in righe}


def url_interventi(c: psycopg.Connection, uris: list[str]) -> dict[str, str | None]:
    """Il link al resoconto di ogni intervento (url_intervento); per quelli senza ancora si legge la seduta."""
    out = {u: url_intervento(u) for u in dict.fromkeys(u for u in uris if u)}
    senza = [u for u, x in out.items() if x is None]
    if senza and ha_colonna(c, "sitting", "record_url"):
        for r in c.execute("""SELECT s.uri, st.record_url FROM speech s JOIN agenda_item i ON i.uri = s.item
                              JOIN sitting st ON st.uri = i.sitting WHERE s.uri = ANY(%s)""", (senza,)):
            out[r["uri"]] = r["record_url"] or None
    return out
