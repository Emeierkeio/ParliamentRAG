"""
csv_loader.py — CSV helper functions for the ParliamentRAG build pipeline.

Provides date parsing, label cleaning, and group/committee utilities used
when loading deputy, group, and committee data from Camera CSV exports.

No Neo4j dependency. No database writes. Pure data-transformation helpers.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

import pandas as pd
from neo4j.time import Date as Neo4jDate

logger = logging.getLogger(__name__)

__all__ = [
    "parse_date_to_neo4j",
    "format_date_ddmmyyyy",
    "clean_generic_label",
    "extract_group_info",
    "GOVERNMENT_GROUPS",
    "SIGLA_FALLBACKS",
]

# ---------------------------------------------------------------------------
# Government group membership map: "LAST FIRST" -> group name
# ---------------------------------------------------------------------------

GOVERNMENT_GROUPS: dict[str, str] = {
    "MELONI GIORGIA": "FRATELLI D'ITALIA",
    "FOTI TOMMASO": "FRATELLI D'ITALIA",
    "TAJANI ANTONIO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "SALVINI MATTEO": "LEGA - SALVINI PREMIER",
    "CIRIANI LUCA": "FRATELLI D'ITALIA",
    "ZANGRILLO PAOLO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "CALDEROLI ROBERTO": "LEGA - SALVINI PREMIER",
    "MUSUMECI NELLO": "FRATELLI D'ITALIA",
    "ABODI ANDREA": "MISTO",
    "ROCCELLA EUGENIA": "FRATELLI D'ITALIA",
    "LOCATELLI ALESSANDRA": "LEGA - SALVINI PREMIER",
    "ALBERTI CASELLATI MARIA ELISABETTA": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "PIANTEDOSI MATTEO": "MISTO",
    "NORDIO CARLO": "FRATELLI D'ITALIA",
    "CROSETTO GUIDO": "FRATELLI D'ITALIA",
    "GIORGETTI GIANCARLO": "LEGA - SALVINI PREMIER",
    "URSO ADOLFO": "FRATELLI D'ITALIA",
    "LOLLOBRIGIDA FRANCESCO": "FRATELLI D'ITALIA",
    "PICHETTO FRATIN GILBERTO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "VALDITARA GIUSEPPE": "LEGA - SALVINI PREMIER",
    "BERNINI ANNA MARIA": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "GIULI ALESSANDRO": "FRATELLI D'ITALIA",
    "SCHILLACI ORAZIO": "MISTO",
    "SANTANCHE' DANIELA": "FRATELLI D'ITALIA",
    "CALDERONE MARINA ELVIRA": "MISTO",
    "MANTOVANO ALFREDO": "MISTO",
    "FAZZOLARI GIOVANBATTISTA": "FRATELLI D'ITALIA",
    "BUTTI ALESSIO": "FRATELLI D'ITALIA",
    "BARACHINI ALBERTO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "MORELLI ALESSANDRO": "LEGA - SALVINI PREMIER",
    "SBARRA LUIGI": "MISTO",
    "CASTIELLO GIUSEPPINA": "LEGA - SALVINI PREMIER",
    "SIRACUSANO MATILDE": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "CIRIELLI EDMONDO": "FRATELLI D'ITALIA",
    "SILLI GIORGIO": "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC, ITALIA AL CENTRO)-MAIE",
    "TRIPODI MARIA": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "FERRO WANDA": "FRATELLI D'ITALIA",
    "MOLTENI NICOLA": "LEGA - SALVINI PREMIER",
    "PRISCO EMANUELE": "FRATELLI D'ITALIA",
    "SISTO FRANCESCO PAOLO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "DELMASTRO DELLE VEDOVE ANDREA": "FRATELLI D'ITALIA",
    "OSTELLARI ANDREA": "LEGA - SALVINI PREMIER",
    "PEREGO DI CREMNAGO MATTEO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "RAUTI ISABELLA": "FRATELLI D'ITALIA",
    "LEO MAURIZIO": "FRATELLI D'ITALIA",
    "ALBANO LUCIA": "FRATELLI D'ITALIA",
    "FRENI FEDERICO": "LEGA - SALVINI PREMIER",
    "SAVINO SANDRA": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "VALENTINI VALENTINO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "BERGAMOTTO FAUSTA": "FRATELLI D'ITALIA",
    "IANNONE ANTONIO": "FRATELLI D'ITALIA",
    "D'ERAMO LUIGI": "LEGA - SALVINI PREMIER",
    "LA PIETRA PATRIZIO GIACOMO": "FRATELLI D'ITALIA",
    "GAVA VANNIA": "LEGA - SALVINI PREMIER",
    "BARBARO CLAUDIO": "FRATELLI D'ITALIA",
    "RIXI EDOARDO": "LEGA - SALVINI PREMIER",
    "FERRANTE TULLIO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "BELLUCCI MARIA TERESA": "FRATELLI D'ITALIA",
    "DURIGON CLAUDIO": "LEGA - SALVINI PREMIER",
    "FRASSINETTI PAOLA": "FRATELLI D'ITALIA",
    "MONTARULI AUGUSTA": "FRATELLI D'ITALIA",
    "MAZZI GIANMARCO": "FRATELLI D'ITALIA",
    "BORGONZONI LUCIA": "LEGA - SALVINI PREMIER",
    "GEMMATO MARCELLO": "FRATELLI D'ITALIA",
}

# ---------------------------------------------------------------------------
# Acronym fallbacks for groups whose label has no parenthesised sigla
# ---------------------------------------------------------------------------

SIGLA_FALLBACKS: dict[str, str] = {
    "FRATELLI D'ITALIA": "FDI",
    "PARTITO DEMOCRATICO": "PD",
    "MOVIMENTO 5 STELLE": "M5S",
    "LEGA": "LEGA",
    "FORZA ITALIA": "FI",
    "AZIONE": "AZ",
    "ITALIA VIVA": "IV",
}


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_date_to_neo4j(date_str) -> Optional[Neo4jDate]:
    """Convert a YYYYMMDD (or YYYYMMDD.0) string to a neo4j.time.Date.

    Returns None if the input is NaN, empty, or not a valid 8-digit string.
    """
    if pd.isna(date_str) or date_str == "":
        return None
    s = str(date_str).split('.')[0].strip()
    if len(s) == 8:
        return Neo4jDate(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def format_date_ddmmyyyy(date_str) -> Optional[str]:
    """Convert YYYYMMDD to DD/MM/YYYY string (used for term_of_office_start).

    Returns None if the input is NaN or empty. Returns the raw string as-is
    if it is not a valid 8-digit date.
    """
    if pd.isna(date_str) or date_str == "":
        return None
    s = str(date_str).split('.')[0].strip()
    if len(s) == 8:
        return f"{s[6:8]}/{s[4:6]}/{s[:4]}"
    return s


# ---------------------------------------------------------------------------
# Label cleaning helpers
# ---------------------------------------------------------------------------

def clean_generic_label(label) -> Optional[str]:
    """Remove trailing date-range suffixes from committee or group labels.

    Example: "Commissione Bilancio (dal 01.01.2022)" -> "Commissione Bilancio"
    Returns None for NaN inputs.
    """
    if pd.isna(label):
        return None
    return re.sub(r'\s*\([^)]*\d{2}\.\d{2}\.\d{4}.*$', '', str(label)).strip()


def extract_group_info(raw_label) -> tuple[Optional[str], Optional[str]]:
    """Return (name, acronym) extracted from a raw parliamentary group label.

    Handles the special NM(N-C-U-I)M-CP sigla pattern and the standard
    "Name (SIGLA)" format. Returns (None, None) for empty/NaN input.
    """
    clean_label = clean_generic_label(raw_label)
    if not clean_label:
        return None, None
    if "NM(N-C-U-I)M-CP" in clean_label:
        return clean_label.replace("(NM(N-C-U-I)M-CP)", "").strip(), "NM(N-C-U-I)M-CP"
    match = re.search(r'^(.*?)\s+\(([^)]+)\)$', clean_label)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return clean_label, None
