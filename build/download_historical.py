#!/usr/bin/env python3
"""
download_historical.py — Download all raw data for a past legislature.

Fetches, for the given legislature (e.g. 18 = XVIII, 2018-2022):
  1. Camera stenographic XMLs   -> data/xml/stenografico_leg{N}_NNNN.xml
  2. Senate AKN stenographics   -> data/senate_xml/resaula_leg{N}_NNNN.akn
  3. Deputy biographical CSVs   -> data/deputati_{roman}*.csv
  4. Senator biographical CSVs  -> data/senatori_{roman}*.csv

Download only — no Neo4j writes. Ingestion of a past legislature is a
separate decision (embeddings cost, app-level legislature selection).

Usage:
    python build/download_historical.py --legislature 18
    python build/download_historical.py --legislature 18 --only camera
    python build/download_historical.py --legislature 18 --only senato
    python build/download_historical.py --legislature 18 --only csv
"""

import argparse
import logging
import os
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

from download import download_new_xmls
from download_senate import download_senate_xmls
import download_deputies_csv
import download_senators_csv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(BASE_DIR, "data")
XML_DIR = os.path.join(DATA_DIR, "xml")
SENATE_XML_DIR = os.path.join(DATA_DIR, "senate_xml")


def main() -> None:
    ap = argparse.ArgumentParser(description="Download all data for a past legislature")
    ap.add_argument("--legislature", type=int, required=True, help="e.g. 18 for XVIII")
    ap.add_argument(
        "--only",
        choices=["camera", "senato", "csv"],
        default=None,
        help="Restrict to one source (default: all)",
    )
    args = ap.parse_args()
    leg = args.legislature

    if args.only in (None, "csv"):
        logger.info("=== Deputy CSVs (legislature %d) ===", leg)
        download_deputies_csv.main(leg)
        logger.info("=== Senator CSVs (legislature %d) ===", leg)
        download_senators_csv.main(leg)

    if args.only in (None, "camera"):
        logger.info("=== Camera stenografici (legislature %d) ===", leg)
        n = download_new_xmls(XML_DIR, legislature=leg)
        logger.info("Camera: %d new files", n)

    if args.only in (None, "senato"):
        logger.info("=== Senate stenografici (legislature %d) ===", leg)
        n = download_senate_xmls(SENATE_XML_DIR, legislature=leg)
        logger.info("Senato: %d new files", n)

    logger.info("Historical download for legislature %d complete.", leg)


if __name__ == "__main__":
    main()
