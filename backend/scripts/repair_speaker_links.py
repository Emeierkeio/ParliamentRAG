"""Repair SPOKEN_BY links after a data update.

The v2 ingest pipeline resolves speakers to Deputy nodes with `persona.rdf/p<N>`
ids, but this database's canonical deputies use `deputato.rdf/d<N>_19` ids
(the persona.rdf nodes are dormant duplicates with broken photo/card props).
After each update, speeches from newly ingested sessions end up attached to the
duplicates: broken photos, 404 profile links, and authority scores split across
two nodes.

This script:
  1. Re-links every Speech from a persona.rdf Deputy to the matching
     deputato.rdf twin (numeric id match: p305586 -> d305586_19).
  2. For persona-only deputies (no twin — e.g. members who entered parliament
     after the original build), normalizes photo/deputy_card to working URLs.
  3. Syncs MEMBER_OF_GROUP and MEMBER_OF_COMMITTEE memberships from
     persona.rdf duplicates to the canonical twins: the v2 ingest writes
     group switches (e.g. a deputy moving to Misto) on the persona node
     only, leaving the canonical node with a stale open-ended membership.
  4. Deletes persona.rdf duplicates that have a canonical twin once they
     carry no speeches or acts (everything relinked/synced above) — they
     would otherwise show up as ghost rows in ranking and search
     (e.g. two "Edoardo Ziello", 778 deputies instead of ~390).
     Persona-only deputies (no twin) are kept.
  5. Attaches orphan Speech nodes to their Debate via a synthetic Phase
     (<debateId>.sub00000): the ingest only creates Phases from stenographic
     sottotitoli, so debates without subsections (interventi di fine seduta,
     ordine dei lavori, richiami al Regolamento...) leave their speeches
     disconnected and invisible to the timeline.

Idempotent — safe to run repeatedly. Usage:
    python scripts/repair_speaker_links.py [neo4j_uri]
Defaults to NEO4J_URI from the project .env.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

uri = sys.argv[1] if len(sys.argv) > 1 else os.environ["NEO4J_URI"]
driver = GraphDatabase.driver(uri, auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))

with driver.session() as s:
    relinked = s.run("""
        MATCH (sp:Speech)-[r:SPOKEN_BY]->(bad:Deputy)
        WHERE bad.id CONTAINS 'persona.rdf'
        WITH sp, r, bad, 'http://dati.camera.it/ocd/deputato.rdf/d' + split(bad.id, 'persona.rdf/p')[1] + '_19' AS goodId
        MATCH (good:Deputy {id: goodId})
        MERGE (sp)-[:SPOKEN_BY]->(good)
        DELETE r
        RETURN count(*) AS n
    """).single()["n"]
    fixed = s.run("""
        MATCH (sp:Speech)-[:SPOKEN_BY]->(bad:Deputy)
        WHERE bad.id CONTAINS 'persona.rdf'
        WITH DISTINCT bad, split(bad.id, 'persona.rdf/p')[1] AS num
        SET bad.photo = 'https://documenti.camera.it/_dati/leg19/schededeputatinuovosito/fotoDefinitivo/big/d' + num + '.jpg',
            bad.deputy_card = 'https://www.camera.it/deputati/elenco/19-' + num
        RETURN count(bad) AS n
    """).single()["n"]

    synced = s.run("""
        MATCH (p:Deputy)-[pmg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WHERE p.id CONTAINS 'persona.rdf/p' AND pmg.start_date >= date('2022-10-01')
        WITH p, pmg, g, split(p.id, 'persona.rdf/p')[1] AS num
        MATCH (c:Deputy) WHERE c.id ENDS WITH ('deputato.rdf/d' + num + '_19')
        MERGE (c)-[cmg:MEMBER_OF_GROUP {start_date: pmg.start_date}]->(g)
        SET cmg.end_date = pmg.end_date
        RETURN count(*) AS n
    """).single()["n"]

    synced_committees = s.run("""
        MATCH (p:Deputy)-[pmc:MEMBER_OF_COMMITTEE]->(c:Committee)
        WHERE p.id CONTAINS 'persona.rdf/p'
        WITH p, pmc, c, split(p.id, 'persona.rdf/p')[1] AS num
        MATCH (canon:Deputy) WHERE canon.id ENDS WITH ('deputato.rdf/d' + num + '_19')
        MERGE (canon)-[cmc:MEMBER_OF_COMMITTEE {start_date: pmc.start_date}]->(c)
        SET cmc.end_date = pmc.end_date
        RETURN count(*) AS n
    """).single()["n"]

    deleted = s.run("""
        MATCH (p:Deputy) WHERE p.id CONTAINS 'persona.rdf/p'
        WITH p, split(p.id, 'persona.rdf/p')[1] AS num
        MATCH (canon:Deputy) WHERE canon.id ENDS WITH ('deputato.rdf/d' + num + '_19')
        AND NOT (:Speech)-[:SPOKEN_BY]->(p)
        AND NOT (p)-[:PRIMARY_SIGNATORY|CO_SIGNATORY]->()
        DETACH DELETE p
        RETURN count(*) AS n
    """).single()["n"]

    attached = s.run("""
        MATCH (sp:Speech) WHERE NOT (()-[:CONTAINS_SPEECH]->(sp))
        WITH sp, split(sp.id, '.int')[0] AS debateId
        MATCH (d:Debate {id: debateId})
        MERGE (p:Phase {id: debateId + '.sub00000'})
        MERGE (d)-[:HAS_PHASE]->(p)
        MERGE (p)-[:CONTAINS_SPEECH]->(sp)
        RETURN count(DISTINCT sp) AS n
    """).single()["n"]

driver.close()
print(f"[REPAIR] speeches re-linked to canonical deputies: {relinked}")
print(f"[REPAIR] persona-only deputies with normalized photo/card: {fixed}")
print(f"[REPAIR] group memberships synced persona -> canonical: {synced}")
print(f"[REPAIR] committee memberships synced persona -> canonical: {synced_committees}")
print(f"[REPAIR] persona.rdf twin duplicates deleted: {deleted}")
print(f"[REPAIR] orphan speeches attached via synthetic phase: {attached}")
