#!/usr/bin/env python3
"""
Repair SPOKEN_BY relationships in Neo4j.

Re-parses all XML stenographic files to extract deputatoId and cognome_nome
for each speech, then creates SPOKEN_BY relationships to the correct
Deputy or GovernmentMember node.

Usage:
    python build/repair_spoken_by.py --neo4j-uri bolt://localhost:7689 \
                                      --neo4j-user neo4j \
                                      --neo4j-password thesis2026
"""
import argparse
import glob
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path so we can import build modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from build.xml_parser import StenograficoParser
from build.senate_parser import SenateStenograficoParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def repair_db(neo4j_uri: str, neo4j_user: str, neo4j_password: str, xml_dir: str, senate_xml_dir: str):
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    # --- Step 1: Collect speech→speaker mappings from XML ---
    logger.info("Step 1: Parsing XML files to extract speech→speaker mappings...")

    speech_map = {}  # speech_id → {deputatoId, cognome_nome}
    parser = StenograficoParser()

    camera_xmls = sorted(glob.glob(os.path.join(xml_dir, "*.xml")))
    if not camera_xmls:
        logger.warning(f"  No .xml files in {xml_dir}")
    logger.info(f"  Found {len(camera_xmls)} Camera XML files")

    for i, xml_path in enumerate(camera_xmls):
        try:
            result = parser.parse(xml_path)
            for speech in result.get("speeches", []):
                sid = speech.get("id")
                if sid:
                    speech_map[sid] = {
                        "deputatoId": speech.get("deputatoId"),
                        "cognome_nome": speech.get("cognome_nome"),
                    }
        except Exception as e:
            logger.warning(f"  Failed to parse {os.path.basename(xml_path)}: {e}")

        if (i + 1) % 50 == 0:
            logger.info(f"  Parsed {i + 1}/{len(camera_xmls)} Camera XMLs ({len(speech_map)} speeches)")

    # Senate XMLs
    # Senate uses .akn extension
    senate_xmls = sorted(glob.glob(os.path.join(senate_xml_dir, "*.akn")))
    if not senate_xmls:
        # Fallback to .xml
        senate_xmls = sorted(glob.glob(os.path.join(senate_xml_dir, "*.xml")))
    logger.info(f"  Found {len(senate_xmls)} Senate XML files")

    senate_parser = SenateStenograficoParser()
    for i, xml_path in enumerate(senate_xmls):
        try:
            result = senate_parser.parse(xml_path)
            for speech in result.get("speeches", []):
                sid = speech.get("id")
                if sid:
                    speech_map[sid] = {
                        "deputatoId": speech.get("deputatoId"),
                        "cognome_nome": speech.get("cognome_nome"),
                    }
        except Exception as e:
            logger.warning(f"  Failed to parse Senate {os.path.basename(xml_path)}: {e}")

    logger.info(f"  Total speech mappings collected: {len(speech_map)}")

    # --- Step 2: Set properties on Speech nodes ---
    logger.info("Step 2: Writing deputatoId and cognomeNome to Speech nodes...")

    with driver.session() as session:
        # Batch update in chunks of 500
        items = list(speech_map.items())
        batch_size = 500
        updated = 0

        for start in range(0, len(items), batch_size):
            batch = [
                {"id": sid, "deputatoId": info["deputatoId"], "cognomeNome": info["cognome_nome"]}
                for sid, info in items[start:start + batch_size]
            ]
            result = session.execute_write(
                lambda tx, b=batch: tx.run("""
                    UNWIND $batch AS row
                    MATCH (sp:Speech {id: row.id})
                    SET sp.deputatoId = row.deputatoId,
                        sp.cognomeNome = row.cognomeNome
                """, batch=b).consume()
            )
            updated += len(batch)
            if updated % 5000 == 0:
                logger.info(f"  Updated {updated}/{len(items)} speeches")

        logger.info(f"  Done: {updated} Speech nodes updated with speaker info")

    # --- Step 3: Delete existing SPOKEN_BY and re-link ---
    logger.info("Step 3: Removing existing SPOKEN_BY relationships...")

    with driver.session() as session:
        result = session.execute_write(
            lambda tx: tx.run("""
                MATCH ()-[r:SPOKEN_BY]->()
                DELETE r
                RETURN count(r) AS deleted
            """).single()
        )
        logger.info(f"  Deleted {result['deleted']} old SPOKEN_BY relationships")

    # --- Step 4: Create SPOKEN_BY to Deputy (primary, by URI) ---
    logger.info("Step 4: Linking Speech→Deputy by deputatoId (URI match)...")

    with driver.session() as session:
        result = session.execute_write(
            lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.deputatoId IS NOT NULL
                MATCH (dep:Deputy {id: sp.deputatoId})
                MERGE (sp)-[:SPOKEN_BY]->(dep)
                RETURN count(*) AS linked
            """).single()
        )
        deputy_linked = result["linked"]
        logger.info(f"  Linked {deputy_linked} speeches to Deputies by URI")

    # --- Step 5: Fallback — link to GovernmentMember by name ---
    logger.info("Step 5: Linking remaining Speech→GovernmentMember by name...")

    with driver.session() as session:
        result = session.execute_write(
            lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.cognomeNome IS NOT NULL
                  AND NOT (sp)-[:SPOKEN_BY]->()
                MATCH (gm:GovernmentMember)
                WHERE toUpper(gm.last_name + ' ' + gm.first_name) = toUpper(sp.cognomeNome)
                   OR toUpper(gm.first_name + ' ' + gm.last_name) = toUpper(sp.cognomeNome)
                MERGE (sp)-[:SPOKEN_BY]->(gm)
                RETURN count(*) AS linked
            """).single()
        )
        gov_linked = result["linked"]
        logger.info(f"  Linked {gov_linked} speeches to GovernmentMembers by name")

    # --- Step 6: Second fallback — link to Deputy by name ---
    logger.info("Step 6: Linking remaining Speech→Deputy by name...")

    with driver.session() as session:
        result = session.execute_write(
            lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.cognomeNome IS NOT NULL
                  AND NOT (sp)-[:SPOKEN_BY]->()
                MATCH (dep:Deputy)
                WHERE toUpper(dep.last_name + ' ' + dep.first_name) = toUpper(sp.cognomeNome)
                   OR toUpper(dep.first_name + ' ' + dep.last_name) = toUpper(sp.cognomeNome)
                WITH sp, dep LIMIT 1
                MERGE (sp)-[:SPOKEN_BY]->(dep)
                RETURN count(*) AS linked
            """).single()
        )
        dep_name_linked = result["linked"]
        logger.info(f"  Linked {dep_name_linked} speeches to Deputies by name")

    # --- Step 7: Report ---
    logger.info("Step 7: Verification...")

    with driver.session() as session:
        stats = session.run("""
            MATCH (sp:Speech)
            OPTIONAL MATCH (sp)-[:SPOKEN_BY]->(speaker)
            RETURN
                count(sp) AS total_speeches,
                count(speaker) AS linked_speeches,
                sum(CASE WHEN speaker IS NULL THEN 1 ELSE 0 END) AS orphan_speeches,
                sum(CASE WHEN 'Deputy' IN labels(speaker) THEN 1 ELSE 0 END) AS to_deputy,
                sum(CASE WHEN 'GovernmentMember' IN labels(speaker) THEN 1 ELSE 0 END) AS to_gov
        """).single()

        logger.info("=" * 60)
        logger.info("REPAIR COMPLETE")
        logger.info("=" * 60)
        logger.info(f"  Total speeches:        {stats['total_speeches']}")
        logger.info(f"  Linked to Deputy:      {stats['to_deputy']}")
        logger.info(f"  Linked to GovMember:   {stats['to_gov']}")
        logger.info(f"  Still orphaned:        {stats['orphan_speeches']}")
        logger.info(
            f"  Coverage: {stats['linked_speeches']}/{stats['total_speeches']} "
            f"({100 * stats['linked_speeches'] / max(stats['total_speeches'], 1):.1f}%)"
        )

    driver.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Repair SPOKEN_BY relationships")
    p.add_argument("--neo4j-uri", default="bolt://localhost:7689")
    p.add_argument("--neo4j-user", default="neo4j")
    p.add_argument("--neo4j-password", required=True)
    p.add_argument("--xml-dir", default="data/xml",
                   help="Directory with Camera XML stenographic files")
    p.add_argument("--senate-xml-dir", default="data/senate_xml",
                   help="Directory with Senate AKN stenographic files")
    args = p.parse_args()

    start = time.time()
    repair_db(args.neo4j_uri, args.neo4j_user, args.neo4j_password,
              args.xml_dir, args.senate_xml_dir)
    logger.info(f"Total time: {time.time() - start:.1f}s")
