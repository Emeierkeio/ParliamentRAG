#!/usr/bin/env python3
"""Group offices (direttivo) from dati.camera.it onto MEMBER_OF_GROUP.role.

The OCD graph exposes office nodes linked to the parliamentary group via
ocd:rif_gruppoParlamentare, with an rdfs:label of the form
"VICEPRESIDENTE del gruppo LEGA - SALVINI PREMIER, ALBERTO BAGNAI
(18.10.2022-15.09.2026)". No structured role property exists, so role,
person and period are parsed from the label. Only offices without an end
date are applied, on the deputy's ACTIVE membership rel; existing role
values are replaced (idempotent).
"""
import argparse
import json
import logging
import re
import urllib.parse
import urllib.request

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("group_offices")

SPARQL_ENDPOINT = "https://dati.camera.it/sparql"

ROLE_MAP = {
    "PRESIDENTE": "president",
    "VICEPRESIDENTE": "vice_president",
    "TESORIERE": "treasurer",
    "SEGRETARIO": "secretary",
}

QUERY = """
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?lab WHERE {
  ?u ocd:rif_gruppoParlamentare ?g ; rdfs:label ?lab .
  ?g ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_%(leg)s> .
  FILTER(REGEX(STR(?lab), "^(PRESIDENTE|VICEPRESIDENTE|TESORIERE|SEGRETARIO) del gruppo"))
}
"""

# "RUOLO del gruppo NOME GRUPPO, NOME PERSONA (dd.mm.yyyy[-dd.mm.yyyy])"
LABEL_RE = re.compile(
    r"^(PRESIDENTE|VICEPRESIDENTE|TESORIERE|SEGRETARIO) del gruppo (.+), ([^,(]+) "
    r"\((\d{2}\.\d{2}\.\d{4})(?:-(\d{2}\.\d{2}\.\d{4}))?\)$"
)


def sparql(query: str) -> list[dict]:
    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode(
        {"query": query, "format": "application/sparql-results+json"}
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "ParliamentRAG/1.0", "Accept": "application/sparql-results+json"}
    )
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["results"]["bindings"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--neo4j-uri", required=True)
    ap.add_argument("--neo4j-user", default="neo4j")
    ap.add_argument("--neo4j-password", required=True)
    ap.add_argument("--legislature", type=int, default=19)
    args = ap.parse_args()

    rows = sparql(QUERY % {"leg": args.legislature})
    offices = []
    for r in rows:
        lab = r["lab"]["value"].strip()
        m = LABEL_RE.match(lab)
        if not m:
            logger.warning("Label non riconosciuta: %s", lab)
            continue
        role_it, group, person, start, end = m.groups()
        if end:  # only current officeholders end up on the active rel
            continue
        offices.append({
            "role": ROLE_MAP[role_it],
            "group": group.strip().upper(),
            "person": person.strip().upper(),
        })
    logger.info("Cariche correnti dal SPARQL: %d", len(offices))

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    applied = missed = 0
    with driver.session() as s:
        # Wipe then reapply: officeholders change, stale roles must not survive
        s.run("MATCH (:Person)-[m:MEMBER_OF_GROUP]->() REMOVE m.role")
        for o in offices:
            res = s.run(
                """
                MATCH (d:Person)-[m:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
                WHERE m.end_date IS NULL
                  AND (toUpper(d.first_name + ' ' + d.last_name) = $person
                       OR toUpper(d.last_name + ' ' + d.first_name) = $person)
                  AND (toUpper(g.name) CONTAINS $group_key OR $group_key CONTAINS toUpper(g.name))
                SET m.role = $role
                RETURN count(m) AS n
                """,
                person=o["person"],
                # first token of the group name survives renames (AZIONE-, LEGA...)
                group_key=o["group"].split(",")[0].split("(")[0].strip(),
                role=o["role"],
            ).single()["n"]
            if not res:
                # Renamed groups (Azione-IV -> Azione, IV-Il Centro -> Casa
                # Riformista): the source keeps the office on the old name,
                # the officeholder presides the successor group they sit in
                res = s.run(
                    """
                    MATCH (d:Person)-[m:MEMBER_OF_GROUP]->(:ParliamentaryGroup)
                    WHERE m.end_date IS NULL
                      AND (toUpper(d.first_name + ' ' + d.last_name) = $person
                           OR toUpper(d.last_name + ' ' + d.first_name) = $person)
                    SET m.role = $role
                    RETURN count(m) AS n
                    """,
                    person=o["person"], role=o["role"],
                ).single()["n"]
            if res:
                applied += 1
            else:
                missed += 1
                logger.warning("Nessun match per %s (%s, %s)", o["person"], o["role"], o["group"][:40])
    driver.close()
    logger.info("Applicate %d cariche, %d senza match.", applied, missed)


if __name__ == "__main__":
    main()
