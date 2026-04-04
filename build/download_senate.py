"""
download_senate.py — AKN XML download utilities for Senate stenografici.

Downloads stenographic AKN files from senato.it.
Discovery strategy: scrape the listing page to extract BGT IDs, then fetch
the corresponding .akn files.

IMPORTANT: A User-Agent header is required — senato.it returns 403 without it.
No Neo4j dependency. No database writes.
"""

from __future__ import annotations

import logging
import os
import re
import time
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

__all__ = ["download_senate_xmls"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SENATE_LISTING_URL = (
    "https://www.senato.it/lavori/assemblea/resoconti-elenco-cronologico"
)

SENATE_AKN_URL = "https://www.senato.it/leg/19/BGT/Testi/Resaula/{bgt_id:08d}.akn"

USER_AGENT = "Mozilla/5.0 (compatible; ParliamentRAG/1.0)"

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def download_senate_xmls(xml_dir: str) -> int:
    """Download Senate AKN stenographic files from senato.it.

    Discovery strategy:
    1. Fetch the listing page to extract BGT IDs from show-doc href links.
    2. For each ID not already on disk, download the .akn file.
    3. Parse FRBRnumber from the downloaded file to name it consistently.

    Args:
        xml_dir: Target directory for downloaded AKN files.

    Returns:
        Number of new files downloaded in this run.
    """
    os.makedirs(xml_dir, exist_ok=True)

    # Step 1: Get existing files to avoid re-downloading
    existing_files = set(os.listdir(xml_dir))

    # Step 2: Fetch listing page to discover BGT IDs
    headers = {"User-Agent": USER_AGENT}
    logger.info("Fetching Senate listing page: %s", SENATE_LISTING_URL)

    try:
        response = requests.get(SENATE_LISTING_URL, headers=headers, timeout=30)
        response.raise_for_status()
        html = response.text
    except Exception as exc:
        logger.error("Failed to fetch Senate listing page: %s", exc)
        return 0

    # Extract BGT IDs from show-doc href links
    bgt_ids = re.findall(
        r'show-doc\?leg=19&tipodoc=Resaula&id=(\d+)', html
    )
    if not bgt_ids:
        logger.warning("No BGT IDs found on listing page — HTML may have changed")
        return 0

    logger.info("Found %d BGT IDs on listing page", len(bgt_ids))

    downloaded = 0
    for bgt_id in bgt_ids:
        bgt_int = int(bgt_id)
        akn_url = SENATE_AKN_URL.format(bgt_id=bgt_int)

        # Fetch the AKN file to determine the session number
        logger.info("Fetching AKN: %s", akn_url)
        try:
            akn_response = requests.get(akn_url, headers=headers, timeout=60)
            akn_response.raise_for_status()
            content = akn_response.text
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", akn_url, exc)
            time.sleep(1)
            continue

        # Parse FRBRnumber to derive session number
        session_num = _extract_session_number(content)
        if session_num is None:
            logger.warning("Could not parse session number from %s — skipping", akn_url)
            time.sleep(1)
            continue

        filename = f"resaula_leg19_{session_num:04d}.akn"
        if filename in existing_files:
            logger.debug("Already on disk: %s", filename)
            time.sleep(1)
            continue

        filepath = os.path.join(xml_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("Downloaded: %s (BGT ID %s)", filename, bgt_id)
            existing_files.add(filename)
            downloaded += 1
        except OSError as exc:
            logger.error("Failed to write %s: %s", filepath, exc)

        # Polite rate limit — 1 second between downloads
        time.sleep(1)

    logger.info("Senate download complete. New files: %d", downloaded)
    return downloaded


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_session_number(akn_content: str) -> int | None:
    """Parse FRBRnumber value from AKN XML content string.

    Returns the session number integer, or None if not parseable.
    """
    try:
        root = ET.fromstring(akn_content)
    except ET.ParseError:
        return None

    # Try namespaced search first
    frbrnum = root.find(
        f".//{{{AKN_NS}}}FRBRnumber"
    )
    if frbrnum is None:
        # Fallback: search without namespace
        frbrnum = root.find(".//FRBRnumber")

    if frbrnum is None:
        return None

    value = frbrnum.get("value", "")
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
