"""
Source-inspection tests for build/db_builder.py.

Uses source-file inspection (NOT live import) to avoid pulling neo4j/pandas
into the test environment (scipy/NumPy 2.x incompatibility in anaconda Python 3.12).
Follows the pattern established in test_timeline.py.
"""
from pathlib import Path

DB_BUILDER = Path(__file__).parent.parent.parent / "build" / "db_builder.py"


def test_db_builder_exists():
    assert DB_BUILDER.exists(), "build/db_builder.py must exist"


def test_existing_session_numbers_by_legislature():
    src = DB_BUILDER.read_text()
    # Signature must accept legislature param so leg18 dedup is not masked by leg19 numbers
    assert "legislature: int = 19" in src, "get_existing_session_numbers must accept legislature"
    # Dedup query must filter by legislature to avoid cross-legislature masking
    assert "AND s.legislature = $legislature" in src, "dedup query must filter by legislature"


def test_roman_map_defined():
    src = DB_BUILDER.read_text()
    assert 'ROMAN_MAP = {17: "xvii", 18: "xviii", 19: "xix"' in src, "ROMAN_MAP constant must be defined"
