#!/usr/bin/env python3
"""
Repair SPOKEN_BY relationships in Neo4j.

Re-parses all XML stenographic files to extract speaker info for each speech,
then creates SPOKEN_BY relationships to the correct Deputy or GovernmentMember.

Matching strategy:
1. Deputy by numeric ID suffix (Speech.deputatoId '302764' → Deputy.id containing 'p302764')
2. GovernmentMember by surname (first word of cognome_nome)
3. Deputy by surname

Usage:
    ./backend/venv/bin/python3 build/repair_spoken_by.py --neo4j-password thesis2026
"""
import argparse
import glob
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build.xml_parser import StenograficoParser
from build.senate_parser import SenateStenograficoParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def repair_db(neo4j_uri: str, neo4j_user: str, neo4j_password: str,
              xml_dir: str, senate_xml_dir: str):
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    # ── Step 1: Parse XML to collect speech→speaker mappings ──
    logger.info("Step 1: Parsing XML files...")

    speech_map = {}  # speech_id → {deputatoId, cognome_nome}
    parser = StenograficoParser()

    camera_xmls = sorted(glob.glob(os.path.join(xml_dir, "*.xml")))
    logger.info(f"  {len(camera_xmls)} Camera XML files")

    for i, xml_path in enumerate(camera_xmls):
        try:
            result = parser.parse_xml_file(xml_path)
            for speech in result.get("speeches", []):
                sid = speech.get("id")
                if sid:
                    speech_map[sid] = {
                        "deputatoId": speech.get("deputatoId"),
                        "cognome_nome": speech.get("cognome_nome"),
                    }
        except Exception as e:
            logger.warning(f"  Parse error {os.path.basename(xml_path)}: {e}")

        if (i + 1) % 100 == 0:
            logger.info(f"  {i + 1}/{len(camera_xmls)} Camera ({len(speech_map)} speeches)")

    # Senate
    senate_xmls = sorted(glob.glob(os.path.join(senate_xml_dir, "*.akn")))
    if not senate_xmls:
        senate_xmls = sorted(glob.glob(os.path.join(senate_xml_dir, "*.xml")))
    logger.info(f"  {len(senate_xmls)} Senate files")

    senate_parser = SenateStenograficoParser()
    for xml_path in senate_xmls:
        try:
            result = senate_parser.parse_xml_file(xml_path)
            for speech in result.get("speeches", []):
                sid = speech.get("id")
                if sid:
                    speech_map[sid] = {
                        "deputatoId": speech.get("deputatoId"),
                        "cognome_nome": speech.get("cognome_nome"),
                    }
        except Exception as e:
            logger.warning(f"  Parse error Senate {os.path.basename(xml_path)}: {e}")

    logger.info(f"  Total: {len(speech_map)} speech mappings")

    # ── Step 2: Write speakerId to Speech nodes (transient, for matching) ──
    logger.info("Step 2: Writing speaker IDs to Speech nodes...")

    with driver.session() as session:
        items = list(speech_map.items())
        batch_size = 1000
        updated = 0

        for start in range(0, len(items), batch_size):
            batch = [
                {"id": sid, "deputatoId": info["deputatoId"], "speakerName": info["cognome_nome"]}
                for sid, info in items[start:start + batch_size]
            ]
            session.execute_write(
                lambda tx, b=batch: tx.run("""
                    UNWIND $batch AS row
                    MATCH (sp:Speech {id: row.id})
                    SET sp.deputatoId = row.deputatoId,
                        sp.speakerName = row.speakerName
                """, batch=b).consume()
            )
            updated += len(batch)
            if updated % 10000 == 0:
                logger.info(f"  {updated}/{len(items)} updated")

        logger.info(f"  Done: {updated} nodes")

    # ── Step 3: Delete existing SPOKEN_BY ──
    logger.info("Step 3: Deleting old SPOKEN_BY...")

    with driver.session() as session:
        result = session.execute_write(
            lambda tx: tx.run("MATCH ()-[r:SPOKEN_BY]->() DELETE r RETURN count(r) AS n").single()
        )
        logger.info(f"  Deleted {result['n']}")

    # ── Step 4: Link by numeric ID suffix ──
    # Speech.deputatoId = '302764', Deputy.id = 'http://...persona.rdf/p302764'
    logger.info("Step 4: Linking Speech→Deputy by numeric ID...")

    with driver.session() as session:
        result = session.execute_write(
            lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.deputatoId IS NOT NULL AND sp.deputatoId <> ''
                MATCH (dep:Deputy)
                WHERE dep.id ENDS WITH ('p' + sp.deputatoId)
                MERGE (sp)-[:SPOKEN_BY]->(dep)
                RETURN count(*) AS n
            """).single()
        )
        logger.info(f"  Linked {result['n']} to Deputies by ID")

    # ── Step 5: Link remaining to GovernmentMember by surname ──
    logger.info("Step 5: Linking remaining Speech→GovernmentMember by surname...")

    with driver.session() as session:
        # cognome_nome format: "COGNOME Nome Secondo" → surname = first word uppercase
        result = session.execute_write(
            lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.speakerName IS NOT NULL
                  AND NOT (sp)-[:SPOKEN_BY]->()
                WITH sp, split(sp.speakerName, ' ')[0] AS surname
                WHERE surname <> ''
                MATCH (gm:GovernmentMember)
                WHERE toUpper(gm.last_name) = toUpper(surname)
                WITH sp, gm,
                     toUpper(sp.speakerName) AS full,
                     toUpper(gm.last_name + ' ' + gm.first_name) AS gm_name
                WHERE full STARTS WITH toUpper(gm.last_name)
                MERGE (sp)-[:SPOKEN_BY]->(gm)
                RETURN count(*) AS n
            """).single()
        )
        logger.info(f"  Linked {result['n']} to GovernmentMembers")

    # ── Step 6: Link remaining to Deputy by surname ──
    logger.info("Step 6: Linking remaining Speech→Deputy by surname...")

    with driver.session() as session:
        result = session.execute_write(
            lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.speakerName IS NOT NULL
                  AND NOT (sp)-[:SPOKEN_BY]->()
                WITH sp, split(sp.speakerName, ' ')[0] AS surname
                WHERE surname <> ''
                MATCH (dep:Deputy)
                WHERE toUpper(dep.last_name) = toUpper(surname)
                WITH sp, dep,
                     toUpper(sp.speakerName) AS full,
                     toUpper(dep.last_name) AS dep_surname
                WHERE full STARTS WITH dep_surname
                WITH sp, collect(dep)[0] AS dep
                MERGE (sp)-[:SPOKEN_BY]->(dep)
                RETURN count(*) AS n
            """).single()
        )
        logger.info(f"  Linked {result['n']} to Deputies by surname")

    # ── Step 7: Clean up transient properties ──
    logger.info("Step 7: Cleaning up transient properties...")
    with driver.session() as session:
        session.execute_write(
            lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.speakerName IS NOT NULL
                REMOVE sp.speakerName
            """).consume()
        )

    # ── Step 8: Report ──
    logger.info("Step 8: Verification...")

    with driver.session() as session:
        stats = session.run("""
            MATCH (sp:Speech)
            OPTIONAL MATCH (sp)-[:SPOKEN_BY]->(speaker)
            RETURN
                count(sp) AS total,
                count(speaker) AS linked,
                sum(CASE WHEN speaker IS NULL THEN 1 ELSE 0 END) AS orphaned,
                sum(CASE WHEN 'Deputy' IN labels(speaker) THEN 1 ELSE 0 END) AS to_deputy,
                sum(CASE WHEN 'GovernmentMember' IN labels(speaker) THEN 1 ELSE 0 END) AS to_gov
        """).single()

        logger.info("=" * 60)
        logger.info("REPAIR COMPLETE")
        logger.info("=" * 60)
        logger.info(f"  Total speeches:      {stats['total']}")
        logger.info(f"  → Deputy:            {stats['to_deputy']}")
        logger.info(f"  → GovernmentMember:  {stats['to_gov']}")
        logger.info(f"  → Orphaned:          {stats['orphaned']}")
        pct = 100 * stats['linked'] / max(stats['total'], 1)
        logger.info(f"  Coverage:            {stats['linked']}/{stats['total']} ({pct:.1f}%)")

    driver.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Repair SPOKEN_BY relationships")
    p.add_argument("--neo4j-uri", default="bolt://localhost:7689")
    p.add_argument("--neo4j-user", default="neo4j")
    p.add_argument("--neo4j-password", required=True)
    p.add_argument("--xml-dir", default="data/xml")
    p.add_argument("--senate-xml-dir", default="data/senate_xml")
    args = p.parse_args()

    start = time.time()
    repair_db(args.neo4j_uri, args.neo4j_user, args.neo4j_password,
              args.xml_dir, args.senate_xml_dir)
    logger.info(f"Total: {time.time() - start:.1f}s")
