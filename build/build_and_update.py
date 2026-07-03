#!/usr/bin/env python3
"""
build_and_update.py — Unified CLI for full build and incremental update of the Neo4j database.

Produces the English-only schema identical to the production database:
  Labels: Deputy, GovernmentMember, ParliamentaryGroup, Committee,
          Session, Debate, Phase, Speech, Chunk, ParliamentaryAct, Vote
  Relationships: SPOKEN_BY, HAS_CHUNK, HAS_DEBATE, HAS_PHASE, CONTAINS_SPEECH,
                 MEMBER_OF_GROUP, MEMBER_OF_COMMITTEE, PRIMARY_SIGNATORY,
                 CO_SIGNATORY, NEXT, IS_PRESIDENT, IS_VICE_PRESIDENT,
                 IS_SECRETARY, GOVERNMENT_REFERENCE, HAS_VOTE, DISCUSSES

Modes:
  build   — Rebuild the DB from scratch (nuke + full ingestion).
  update  — Incremental update: new XMLs, updated CSVs, new atti parlamentari.

Usage:
    python build/build_and_update.py build [--neo4j-uri bolt://localhost:7689]
    python build/build_and_update.py update [--neo4j-uri bolt://localhost:7689] \\
        [--skip-download] [--skip-atti] [--skip-embeddings]
"""

import argparse
import glob
import logging
import os
import re
import subprocess
import sys
import time

from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Path setup — build/ is the scripts dir, project root is one level up
# ---------------------------------------------------------------------------
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, BACKEND_DIR)

from build_config import BuildConfig, load_config
from xml_parser import StenograficoParser
from db_builder import DatabaseBuilder
from csv_loader import GOVERNMENT_GROUPS, parse_date_to_neo4j
from download import download_new_xmls, get_last_xml_id
from ingest_atti_parlamentari import AttiParlamentariIngester
from senate_parser import SenateStenograficoParser
from download_senate import download_senate_xmls
from download_senators_csv import main as download_senators_csv_main

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_NEO4J_URI = "bolt://localhost:7689"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "thesis2026"

DATA_DIR = os.path.join(BASE_DIR, "data")
XML_DIR = os.path.join(DATA_DIR, "xml")
SENATE_XML_DIR = os.path.join(DATA_DIR, "senate_xml")
CONFIG_PATH = os.path.join(SCRIPTS_DIR, "config.yaml")


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def run_subprocess(
    script_name: str,
    neo4j_uri: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
) -> int:
    """Run a build sub-script as a child process, forwarding Neo4j credentials."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        SCRIPTS_DIR + os.pathsep + BACKEND_DIR + os.pathsep + env.get("PYTHONPATH", "")
    )
    if neo4j_uri:
        env["NEO4J_URI"] = neo4j_uri
    if neo4j_user:
        env["NEO4J_USER"] = neo4j_user
    if neo4j_password:
        env["NEO4J_PASSWORD"] = neo4j_password
    start = time.time()
    result = subprocess.run([sys.executable, script_path], check=True, env=env)
    logger.info("%s completed in %.1fs", script_name, time.time() - start)
    return result.returncode


# ---------------------------------------------------------------------------
# Atti parlamentari ingestion helper
# ---------------------------------------------------------------------------

def _ingest_atti(driver, uri: str, user: str, password: str) -> None:
    """Ingest parliamentary acts using AttiParlamentariIngester."""
    ingester = AttiParlamentariIngester(uri, user, password)
    try:
        ingester.create_constraints()
        ingester.create_indexes()

        with driver.session() as neo_session:
            result = neo_session.run(
                "MATCH (d:Deputy) RETURN d.id AS uri, d.first_name AS nome, d.last_name AS cognome"
            )
            deputati = [dict(r) for r in result]

        logger.info("Found %d deputies for atti ingestion.", len(deputati))
        total_primo = 0
        total_altro = 0
        atti_unici: set[str] = set()

        for i, dep in enumerate(deputati):
            dep_uri = dep["uri"]
            dep_nome = f"{dep.get('nome', '')} {dep.get('cognome', '')}"
            logger.debug("[%d/%d] %s...", i + 1, len(deputati), dep_nome)

            atti = ingester.get_atti_deputato(dep_uri)
            n_primo = len(atti["primo_firmatario"])
            n_altro = len(atti["altro_firmatario"])

            if n_primo > 0 or n_altro > 0:
                logger.info(
                    "[%d/%d] %s -> %d primo, %d altro",
                    i + 1, len(deputati), dep_nome, n_primo, n_altro,
                )

            for atto in atti["primo_firmatario"]:
                atti_unici.add(atto["uri"])
                _save_atto(driver, atto, dep_uri, "PRIMARY_SIGNATORY")
                total_primo += 1

            for atto in atti["altro_firmatario"]:
                atti_unici.add(atto["uri"])
                _save_atto(driver, atto, dep_uri, "CO_SIGNATORY")
                total_altro += 1

        logger.info(
            "Atti unici: %d, Primo: %d, Altro: %d",
            len(atti_unici), total_primo, total_altro,
        )
    finally:
        ingester.close()


def _save_atto(driver, atto: dict, deputato_uri: str, rel_type: str) -> None:
    """Upsert a single ParliamentaryAct node and its signatory relationship."""
    with driver.session() as neo_session:
        neo_session.run(
            """
            MERGE (a:ParliamentaryAct {uri: $uri})
            SET a.type = $type, a.title = $title, a.description = $description,
                a.presentation_date = $presentation_date, a.number = $number,
                a.recipient = $recipient, a.eurovoc = $eurovoc
            """,
            uri=atto.get("uri", ""),
            type=atto.get("tipo", ""),
            title=atto.get("titolo", ""),
            description=atto.get("descrizione", ""),
            presentation_date=atto.get("dataPresentazione", ""),
            number=atto.get("numero", ""),
            recipient=atto.get("destinatario", ""),
            eurovoc=atto.get("eurovoc", ""),
        )
        neo_session.run(
            f"""
            MATCH (d:Deputy {{id: $dep_uri}})
            MATCH (a:ParliamentaryAct {{uri: $atto_uri}})
            MERGE (d)-[:{rel_type}]->(a)
            """,
            dep_uri=deputato_uri,
            atto_uri=atto["uri"],
        )


# ---------------------------------------------------------------------------
# BUILD mode
# ---------------------------------------------------------------------------

def do_build(
    uri: str,
    user: str,
    password: str,
    skip_download: bool = False,
    skip_atti: bool = False,
    skip_embeddings: bool = False,
    legislature: int = 19,
) -> None:
    """Rebuild the database from scratch (nuke + full ingestion)."""
    config = load_config(CONFIG_PATH)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    builder = DatabaseBuilder(driver, config)
    parser = StenograficoParser(config)

    try:
        # 1. Nuke
        logger.info("Step 1: Clearing database")
        builder.nuke_database()

        # 2. Constraints + indexes
        logger.info("Step 2: Creating constraints and indexes")
        builder.create_constraints()
        builder.create_indexes()

        # 3. Download XMLs
        if skip_download:
            logger.info("Step 3: Skipping XML download (--skip-download)")
        else:
            logger.info("Step 3: Downloading new XMLs")
            download_new_xmls(XML_DIR)

        # 4. Load CSVs (deputies, groups, committees, government members)
        logger.info("Step 4: Loading CSV data")
        builder.load_deputies(DATA_DIR, legislature=legislature)
        builder.load_groups(DATA_DIR, legislature=legislature)
        builder.load_committees(DATA_DIR, legislature=legislature)
        builder.load_government_members_from_path(DATA_DIR, legislature=legislature)

        # 5. Ingest stenografici
        logger.info("Step 5: Ingesting stenografici")
        logger.info("  NER enrichment will run on chunks (requires it_core_news_lg)")
        xml_files = sorted(glob.glob(os.path.join(XML_DIR, f"stenografico_leg{legislature}_*.xml")))
        logger.info("  Found %d XML files", len(xml_files))
        for i, xml_path in enumerate(xml_files, 1):
            logger.info("  [%d/%d] %s", i, len(xml_files), os.path.basename(xml_path))
            parsed = parser.parse_xml_file(xml_path)
            builder.ingest_session(parsed)

        # 6. Load roles
        logger.info("Step 6: Loading roles")
        builder.load_roles()

        # 7. Atti parlamentari
        if skip_atti:
            logger.info("Step 7: Skipping atti parlamentari (--skip-atti)")
        else:
            logger.info("Step 7: Ingesting atti parlamentari")
            _ingest_atti(driver, uri, user, password)

        # 8. Vector index
        logger.info("Step 8: Creating vector index")
        builder.create_vector_index()

        # 8b. Full-text index for BM25 sparse retrieval
        logger.info("Step 8b: Creating full-text index")
        builder.create_fulltext_index()

        # 9. Embeddings
        if skip_embeddings:
            logger.info("Step 9: Skipping embeddings (--skip-embeddings)")
        else:
            logger.info("Step 9: Pre-calculating embeddings")
            run_subprocess("precalculate_embeddings.py", uri, user, password)

        logger.info("Build complete!")
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# UPDATE mode
# ---------------------------------------------------------------------------

def do_update(
    uri: str,
    user: str,
    password: str,
    skip_download: bool = False,
    skip_atti: bool = False,
    skip_embeddings: bool = False,
    legislature: int = 19,
) -> None:
    """Incremental update: new XMLs, refreshed CSVs, new atti parlamentari."""
    config = load_config(CONFIG_PATH)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    builder = DatabaseBuilder(driver, config)
    parser = StenograficoParser(config)

    try:
        # 1. Refresh CSV data
        logger.info("Step 1: Refreshing CSV data")
        builder.create_constraints()
        builder.load_deputies(DATA_DIR, legislature=legislature)
        builder.load_groups(DATA_DIR, legislature=legislature)
        builder.load_committees(DATA_DIR, legislature=legislature)
        builder.load_government_members_from_path(DATA_DIR, legislature=legislature)

        # 2. Download new XMLs
        if skip_download:
            logger.info("Step 2: Skipping XML download (--skip-download)")
        else:
            logger.info("Step 2: Downloading new XMLs")
            download_new_xmls(XML_DIR)

        # 3. Ingest new stenografici only
        logger.info("Step 3: Ingesting new stenografici")
        existing = builder.get_existing_session_numbers(chamber="camera", legislature=legislature)
        xml_files = sorted(glob.glob(os.path.join(XML_DIR, f"stenografico_leg{legislature}_*.xml")))
        new_files = []
        for f in xml_files:
            match = re.search(rf'stenografico_leg{legislature}_(\d+)\.xml$', f)
            if match:
                num = int(match.group(1))
                if num not in existing:
                    new_files.append(f)
        if new_files:
            logger.info("  Found %d new XML files to ingest", len(new_files))
            for i, xml_path in enumerate(new_files, 1):
                logger.info("  [%d/%d] %s", i, len(new_files), os.path.basename(xml_path))
                parsed = parser.parse_xml_file(xml_path)
                builder.ingest_session(parsed)
        else:
            logger.info("  No new stenografici found.")

        # 4. Atti parlamentari
        if skip_atti:
            logger.info("Step 4: Skipping atti parlamentari (--skip-atti)")
        else:
            logger.info("Step 4: Updating atti parlamentari")
            _ingest_atti(driver, uri, user, password)

        # 5. Roles
        logger.info("Step 5: Updating roles")
        builder.load_roles()

        # 5b. Full-text index for BM25 sparse retrieval (idempotent: IF NOT EXISTS)
        logger.info("Step 5b: Ensuring full-text index exists")
        builder.create_fulltext_index()

        # 6. Embeddings
        if skip_embeddings:
            logger.info("Step 6: Skipping embeddings (--skip-embeddings)")
        else:
            logger.info("Step 6: Pre-calculating embeddings (incremental)")
            run_subprocess("precalculate_embeddings.py", uri, user, password)

        logger.info("Update complete!")
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# BUILD-SENATE mode
# ---------------------------------------------------------------------------


def do_build_senate(
    uri: str,
    user: str,
    password: str,
    skip_download: bool = False,
    skip_embeddings: bool = False,
    legislature: int = 19,
) -> None:
    """Build Senate portion of the database (additive — no nuke)."""
    config = load_config(CONFIG_PATH)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    builder = DatabaseBuilder(driver, config)
    parser = SenateStenograficoParser(config, legislature=legislature)
    try:
        # 1. Download senator biographical CSVs
        if skip_download:
            logger.info("Skipping senator CSV download")
        else:
            logger.info("Downloading senator biographical data from dati.senato.it")
            download_senators_csv_main()

        # 2. Load senator CSVs (Deputy nodes with chamber='senato')
        logger.info("Loading senator CSV data")
        builder.create_constraints()
        builder.load_senators(DATA_DIR, legislature=legislature)
        builder.load_senator_groups(DATA_DIR, legislature=legislature)
        builder.load_senator_committees(DATA_DIR, legislature=legislature)

        # 3. Download Senate AKN files
        if skip_download:
            logger.info("Skipping Senate XML download")
        else:
            logger.info("Downloading Senate AKN files")
            os.makedirs(SENATE_XML_DIR, exist_ok=True)
            count = download_senate_xmls(SENATE_XML_DIR)
            logger.info("Downloaded %d new Senate files", count)

        # 4. Ingest Senate stenografici
        logger.info("Ingesting Senate stenografici")
        akn_files = sorted(glob.glob(os.path.join(SENATE_XML_DIR, f"resaula_leg{legislature}_*.akn")))
        logger.info("Found %d AKN files", len(akn_files))
        for i, akn_path in enumerate(akn_files, 1):
            logger.info("[%d/%d] %s", i, len(akn_files), os.path.basename(akn_path))
            parsed = parser.parse_xml_file(akn_path)
            builder.ingest_session(parsed)

        # 4b. Link any orphan Senate speeches to senators/government members
        logger.info("Relinking Senate speeches to speakers")
        builder.relink_senate_speeches()

        # 5. Embeddings for new Senate chunks
        if skip_embeddings:
            logger.info("Skipping Senate embeddings")
        else:
            logger.info("Pre-calculating Senate embeddings")
            run_subprocess("precalculate_embeddings.py", uri, user, password)

        logger.info("Senate build complete!")
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# UPDATE-SENATE mode
# ---------------------------------------------------------------------------


def do_update_senate(
    uri: str,
    user: str,
    password: str,
    skip_download: bool = False,
    skip_embeddings: bool = False,
    legislature: int = 19,
) -> None:
    """Incremental Senate update: new AKNs, refreshed senator CSVs, relink."""
    config = load_config(CONFIG_PATH)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    builder = DatabaseBuilder(driver, config)
    parser = SenateStenograficoParser(config, legislature=legislature)
    try:
        # 1. Refresh senator biographical CSVs and load them
        if skip_download:
            logger.info("Step 1: Skipping senator CSV download (--skip-download)")
        else:
            logger.info("Step 1: Refreshing senator biographical data")
            download_senators_csv_main()
        builder.create_constraints()
        builder.load_senators(DATA_DIR, legislature=legislature)
        builder.load_senator_groups(DATA_DIR, legislature=legislature)
        builder.load_senator_committees(DATA_DIR, legislature=legislature)

        # 2. Download new Senate AKN files
        if skip_download:
            logger.info("Step 2: Skipping Senate AKN download (--skip-download)")
        else:
            logger.info("Step 2: Downloading Senate AKN files")
            os.makedirs(SENATE_XML_DIR, exist_ok=True)
            count = download_senate_xmls(SENATE_XML_DIR)
            logger.info("Downloaded %d new Senate files", count)

        # 3. Ingest only sessions not yet in Neo4j
        logger.info("Step 3: Ingesting new Senate stenografici")
        existing = builder.get_existing_session_numbers(chamber="senato", legislature=legislature)
        akn_files = sorted(glob.glob(os.path.join(SENATE_XML_DIR, f"resaula_leg{legislature}_*.akn")))
        new_files = []
        for f in akn_files:
            match = re.search(rf'resaula_leg{legislature}_(\d+)\.akn$', f)
            if match and int(match.group(1)) not in existing:
                new_files.append(f)
        if new_files:
            logger.info("  Found %d new AKN files to ingest", len(new_files))
            for i, akn_path in enumerate(new_files, 1):
                logger.info("  [%d/%d] %s", i, len(new_files), os.path.basename(akn_path))
                parsed = parser.parse_xml_file(akn_path)
                builder.ingest_session(parsed)
        else:
            logger.info("  No new Senate stenografici found.")

        # 4. Link orphan Senate speeches (covers legacy ingests too)
        logger.info("Step 4: Relinking Senate speeches to speakers")
        builder.relink_senate_speeches()

        # 5. Embeddings for new chunks
        if skip_embeddings:
            logger.info("Step 5: Skipping embeddings (--skip-embeddings)")
        else:
            logger.info("Step 5: Pre-calculating embeddings (incremental)")
            run_subprocess("precalculate_embeddings.py", uri, user, password)

        logger.info("Senate update complete!")
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description=(
            "Full build or incremental update of the Neo4j ParliamentRAG database "
            "(English schema)"
        )
    )
    arg_parser.add_argument(
        "mode",
        choices=["build", "update", "build-senate", "update-senate"],
        help=(
            "build = rebuild from scratch; update = incremental Camera update; "
            "build-senate = additive Senate ingestion; "
            "update-senate = incremental Senate update"
        ),
    )
    arg_parser.add_argument(
        "--neo4j-uri",
        default=DEFAULT_NEO4J_URI,
        help=f"Neo4j URI (default: {DEFAULT_NEO4J_URI})",
    )
    arg_parser.add_argument("--neo4j-user", default=DEFAULT_NEO4J_USER)
    arg_parser.add_argument("--neo4j-password", default=DEFAULT_NEO4J_PASSWORD)
    arg_parser.add_argument(
        "--skip-download", action="store_true", help="Skip XML download step"
    )
    arg_parser.add_argument(
        "--skip-atti", action="store_true", help="Skip atti parlamentari ingestion"
    )
    arg_parser.add_argument(
        "--skip-embeddings", action="store_true", help="Skip embedding pre-calculation"
    )
    arg_parser.add_argument(
        "--legislature", type=int, default=19,
        help="Legislature number to build/update (default: 19)",
    )

    args = arg_parser.parse_args()
    start_time = time.time()

    if args.mode == "build":
        do_build(
            args.neo4j_uri,
            args.neo4j_user,
            args.neo4j_password,
            args.skip_download,
            args.skip_atti,
            args.skip_embeddings,
            legislature=args.legislature,
        )
    elif args.mode == "build-senate":
        do_build_senate(
            args.neo4j_uri,
            args.neo4j_user,
            args.neo4j_password,
            args.skip_download,
            args.skip_embeddings,
            legislature=args.legislature,
        )
    elif args.mode == "update-senate":
        do_update_senate(
            args.neo4j_uri,
            args.neo4j_user,
            args.neo4j_password,
            args.skip_download,
            args.skip_embeddings,
            legislature=args.legislature,
        )
    else:
        do_update(
            args.neo4j_uri,
            args.neo4j_user,
            args.neo4j_password,
            args.skip_download,
            args.skip_atti,
            args.skip_embeddings,
            legislature=args.legislature,
        )

    total = time.time() - start_time
    logger.info("Total time: %.1fs (%.1f minutes)", total, total / 60)


if __name__ == "__main__":
    main()
