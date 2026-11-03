"""Pezzi comuni agli strumenti: la persona in breve con il gruppo alla data, il gruppo, la stessa persona con due schede."""

from __future__ import annotations

import datetime as dt

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
