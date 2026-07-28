"""Sync remote-only data from the demo DB to the local snapshot.

The build pipeline replayed on the local snapshot is deterministic ingest only.
Everything written to the remote DB by other paths never reaches the local copy:

  - AI timeline summaries (build/generate_summaries.py):
      Session.recapIt/En, Debate.recapIt/En,
      SpeakerDebateSummary nodes + HAS_DEBATE_SUMMARY / FOR_DEBATE rels
  - Chunk citability props (build/classify_chunk_citability.py):
      citability_score, citability_class, best_quote, citability_v
  - Runtime nodes written by the prod backend:
      ChatHistory, SurveyEvaluation, SimpleRating
  - Componenti del Gruppo Misto (build/ingest_misto_componenti.py):
      MistoComponent nodes + MEMBER_OF_COMPONENT rels

This script copies all of the above so the snapshot stays a faithful mirror
without paying OpenAI twice. Recaps and Misto componenti are copied wholesale
(small); summaries and runtime nodes incrementally (ids missing on the target);
citability by version (source citability_v newer than target's). Pass --full
to re-copy the incremental sets too, e.g. after regenerating summaries.

MENTIONS/CITES (build/link_refs.py) are NOT synced here: the ordinary ingest
creates them for new chunks on both DBs, and `make link-refs` replays the
backfill on the local snapshot by itself.

Idempotent — safe to run repeatedly. Usage:
    python scripts/sync_local_snapshot.py <source_uri> <target_uri> [--full]
Credentials from NEO4J_USER / NEO4J_PASSWORD in the project .env (same for
both DBs: the local snapshot is restored from a dump of the remote).
"""
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Missing-label notifications are expected (e.g. SimpleRating before the first
# rating ever lands): don't let the driver spam the make output.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

args = [a for a in sys.argv[1:] if a != "--full"]
full = "--full" in sys.argv[1:]
if len(args) != 2:
    sys.exit("Usage: python scripts/sync_local_snapshot.py <source_uri> <target_uri> [--full]")
source_uri, target_uri = args

auth = (os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
src = GraphDatabase.driver(source_uri, auth=auth)
dst = GraphDatabase.driver(target_uri, auth=auth)

BATCH = 500


def batched(rows):
    for i in range(0, len(rows), BATCH):
        yield rows[i:i + BATCH]


def clean(props: dict) -> dict:
    """Make node properties writable as parameters (temporal types -> ISO strings)."""
    return {k: (v.iso_format() if hasattr(v, "iso_format") else v) for k, v in props.items()}


with src.session() as s, dst.session() as d:
    # --- Session / Debate recaps (wholesale, a few thousand tiny rows) -----
    for label in ("Session", "Debate"):
        rows = s.run(
            f"MATCH (n:{label}) WHERE n.recapIt IS NOT NULL "
            "RETURN n.id AS id, n.recapIt AS recapIt, n.recapEn AS recapEn"
        ).data()
        written = 0
        for chunk in batched(rows):
            written += d.run(
                f"UNWIND $rows AS row MATCH (n:{label} {{id: row.id}}) "
                "SET n.recapIt = row.recapIt, n.recapEn = row.recapEn "
                "RETURN count(*) AS n",
                rows=chunk,
            ).single()["n"]
        print(f"[SYNC] {label} recaps: {written}/{len(rows)} synced")

    # --- SpeakerDebateSummary (incremental by id) --------------------------
    existing = set() if full else {
        r["id"] for r in d.run("MATCH (sds:SpeakerDebateSummary) RETURN sds.id AS id")
    }
    rows = s.run("MATCH (sds:SpeakerDebateSummary) RETURN sds{.*} AS props").value()
    new = [p for p in rows if p["id"] not in existing]
    linked_speakers = linked_debates = 0
    for chunk in batched(new):
        d.run(
            "UNWIND $rows AS row "
            "MERGE (sds:SpeakerDebateSummary {id: row.id}) "
            "SET sds = row",
            rows=chunk,
        )
        linked_debates += d.run(
            "UNWIND $rows AS row "
            "MATCH (sds:SpeakerDebateSummary {id: row.id}) "
            "MATCH (deb:Debate {id: row.debateId}) "
            "MERGE (sds)-[:FOR_DEBATE]->(deb) "
            "RETURN count(*) AS n",
            rows=chunk,
        ).single()["n"]
        for label in ("Deputy", "GovernmentMember"):
            linked_speakers += d.run(
                "UNWIND $rows AS row "
                "MATCH (sds:SpeakerDebateSummary {id: row.id}) "
                f"MATCH (sp:{label} {{id: row.speakerId}}) "
                "MERGE (sp)-[:HAS_DEBATE_SUMMARY]->(sds) "
                "RETURN count(*) AS n",
                rows=chunk,
            ).single()["n"]
    orphans = len(new) - linked_speakers
    print(f"[SYNC] SpeakerDebateSummary: {len(new)} new of {len(rows)} on source "
          f"({linked_debates} debate links, {linked_speakers} speaker links"
          + (f", {orphans} without speaker on target)" if orphans else ")"))

    # --- Chunk citability (by classifier version) --------------------------
    target_v = {
        r["id"]: r["v"]
        for r in d.run("MATCH (c:Chunk) WHERE c.citability_v IS NOT NULL "
                       "RETURN c.id AS id, c.citability_v AS v")
    }
    stale = [
        r["id"]
        for r in s.run("MATCH (c:Chunk) WHERE c.citability_v IS NOT NULL "
                       "RETURN c.id AS id, c.citability_v AS v")
        if full or r["v"] > target_v.get(r["id"], -1)
    ]
    synced = 0
    for chunk in batched(stale):
        props = s.run(
            "UNWIND $ids AS cid MATCH (c:Chunk {id: cid}) "
            "RETURN c.id AS id, c.citability_score AS score, c.citability_class AS cls, "
            "c.best_quote AS quote, c.citability_v AS v",
            ids=chunk,
        ).data()
        synced += d.run(
            "UNWIND $rows AS row MATCH (c:Chunk {id: row.id}) "
            "SET c.citability_score = row.score, c.citability_class = row.cls, "
            "c.best_quote = row.quote, c.citability_v = row.v "
            "RETURN count(*) AS n",
            rows=props,
        ).single()["n"]
    print(f"[SYNC] Chunk citability: {synced}/{len(stale)} stale chunks synced "
          f"({len(target_v)} already classified on target)")

    # --- Runtime nodes: ChatHistory, SurveyEvaluation, SimpleRating --------
    # Immutable after CREATE in the backend, so id-diff is enough.
    for label in ("ChatHistory", "SurveyEvaluation", "SimpleRating"):
        existing = set() if full else {
            r["id"] for r in d.run(f"MATCH (n:{label}) RETURN n.id AS id")
        }
        rows = s.run(f"MATCH (n:{label}) RETURN n{{.*}} AS props").value()
        new = [clean(p) for p in rows if p.get("id") not in existing]
        for chunk in batched(new):
            d.run(
                f"UNWIND $rows AS row MERGE (n:{label} {{id: row.id}}) SET n = row",
                rows=chunk,
            )
        print(f"[SYNC] {label}: {len(new)} new of {len(rows)} on source")

    # --- Componenti Gruppo Misto (wholesale, tiny) -------------------------
    comps = [clean(p) for p in s.run("MATCH (mc:MistoComponent) RETURN mc{.*} AS props").value()]
    d.run(
        "UNWIND $rows AS row MERGE (mc:MistoComponent {uri: row.uri}) SET mc = row",
        rows=comps,
    )
    memberships = s.run(
        "MATCH (dep:Deputy)-[m:MEMBER_OF_COMPONENT]->(mc:MistoComponent) "
        "RETURN dep.id AS did, mc.uri AS uri, "
        "toString(m.start_date) AS start_date, toString(m.end_date) AS end_date"
    ).data()
    linked = 0
    for chunk in batched(memberships):
        linked += d.run(
            "UNWIND $rows AS row "
            "MATCH (dep:Deputy {id: row.did}) MATCH (mc:MistoComponent {uri: row.uri}) "
            "MERGE (dep)-[m:MEMBER_OF_COMPONENT {start_date: date(row.start_date)}]->(mc) "
            "SET m.end_date = CASE WHEN row.end_date IS NULL THEN null "
            "                      ELSE date(row.end_date) END "
            "RETURN count(*) AS n",
            rows=chunk,
        ).single()["n"]
    print(f"[SYNC] MistoComponent: {len(comps)} nodes, {linked}/{len(memberships)} memberships synced")

src.close()
dst.close()
