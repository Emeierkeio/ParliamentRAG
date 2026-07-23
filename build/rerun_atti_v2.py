#!/usr/bin/env python3
"""One-shot recovery runner (2026-07-22): re-ingest acts on the v2 DB.

Perché esiste: la build notturna ha ingerito gli atti con URI persona.rdf
(bug pre-esistente, 489 atti spuri di legislature sbagliate). Questo runner:
1. elimina gli atti reali stale (i placeholder da XML restano)
2. ri-esegue _ingest_atti con il fix persona→deputato URI
Va eseguito con cwd = root ParliamentRAG (per data/eurovoc.csv).
Eliminabile dopo il cutover v2 (PLAN_code_organization).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from neo4j import GraphDatabase
from build_and_update import _ingest_atti

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7692")
USER = os.environ.get("NEO4J_USER", "neo4j")
PWD = os.environ.get("NEO4J_PASSWORD", "thesis2026")


def main():
    driver = GraphDatabase.driver(URI, auth=(USER, PWD))
    try:
        with driver.session() as s:
            n = s.run("""
                MATCH (a:ParliamentaryAct) WHERE a.uri STARTS WITH 'http'
                DETACH DELETE a
                RETURN count(*) AS c
            """).single()["c"]
            print(f"Cleanup: {n} atti stale eliminati (placeholder preservati)")
        _ingest_atti(driver, URI, USER, PWD, legislature=19)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
