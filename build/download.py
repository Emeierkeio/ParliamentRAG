"""
download.py — XML download utilities for the ParliamentRAG build pipeline.

Downloads stenografico XML files from the Camera dei Deputati API.
Handles resumption (starts from the last local ID + 1), retries, and
consecutive-failure limits.

No Neo4j dependency. No database writes.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import time

import requests

logger = logging.getLogger(__name__)

__all__ = [
    "download_new_xmls",
    "get_last_xml_id",
]

# ---------------------------------------------------------------------------
# Camera API endpoint
# ---------------------------------------------------------------------------

XML_BASE_URL = (
    "https://documenti.camera.it/apps/commonServices/getDocumento.ashx"
    "?sezione=assemblea&tipoDoc=formato_xml&tipologia=stenografico"
    "&idNumero={:04d}&idLegislatura=19"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_last_xml_id(xml_dir: str | None = None) -> int:
    """Return the numeric ID of the highest-numbered XML already on disk.

    Scans *xml_dir* for files matching ``stenografico_leg19_NNNN.xml`` and
    returns the largest NNNN found, or 0 if the directory is empty or missing.

    Args:
        xml_dir: Directory containing the XML files. When None the caller is
            responsible for passing the correct path (no default is assumed
            here to keep this module path-agnostic).
    """
    if xml_dir is None:
        raise ValueError("xml_dir must be provided")
    os.makedirs(xml_dir, exist_ok=True)
    xml_files = sorted(glob.glob(os.path.join(xml_dir, "stenografico_leg19_*.xml")))
    if not xml_files:
        return 0
    match = re.search(r'(\d+)\.xml$', xml_files[-1])
    return int(match.group(1)) if match else 0


def download_new_xmls(xml_dir: str | None = None) -> int:
    """Download stenografico XMLs from the Camera API, starting after the last local ID.

    Stops automatically when the API returns a "Documento non disponibile"
    response or after *max_consecutive_failures* consecutive network errors.

    Args:
        xml_dir: Target directory for downloaded files. Must not be None.

    Returns:
        Number of files successfully downloaded in this run.
    """
    if xml_dir is None:
        raise ValueError("xml_dir must be provided")

    last_id = get_last_xml_id(xml_dir)
    start_id = last_id + 1
    logger.info("Last XML on disk: ID %d. Downloading from ID %d...", last_id, start_id)

    downloaded = 0
    consecutive_failures = 0
    max_consecutive_failures = 5
    max_retries = 3
    current_id = start_id

    while True:
        url = XML_BASE_URL.format(current_id)
        filename = f"stenografico_leg19_{current_id:04d}.xml"
        filepath = os.path.join(xml_dir, filename)

        success = False
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, timeout=60)
                if response.status_code == 200:
                    content = response.text
                    if "Documento non disponibile" in content or len(content.strip()) < 100:
                        logger.info("[%04d] End of series.", current_id)
                        logger.info("Download complete. New files: %d", downloaded)
                        return downloaded
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info("[%04d] Downloaded: %s", current_id, filename)
                    downloaded += 1
                    consecutive_failures = 0
                    success = True
                    break
                else:
                    logger.warning(
                        "[%04d] HTTP %d (attempt %d/%d)",
                        current_id, response.status_code, attempt, max_retries,
                    )
            except Exception as exc:
                logger.warning(
                    "[%04d] Error (attempt %d/%d): %s",
                    current_id, attempt, max_retries, exc,
                )
                if attempt < max_retries:
                    time.sleep(5 * attempt)

        if not success:
            consecutive_failures += 1
            logger.warning("[%04d] Skipped after %d attempts.", current_id, max_retries)
            if consecutive_failures >= max_consecutive_failures:
                logger.warning(
                    "Too many consecutive failures (%d). Stopping.",
                    max_consecutive_failures,
                )
                break

        current_id += 1
        time.sleep(0.5)

    logger.info("Download complete. New files: %d", downloaded)
    return downloaded
