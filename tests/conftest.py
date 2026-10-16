import json
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[1]
FIXTURES = RADICE / "tests" / "fixtures"
sys.path.insert(0, str(RADICE))


@pytest.fixture(scope="session")
def dati():
    from verifica.dati import DatiHF
    return DatiHF(FIXTURES / "dati-hf")


def carica(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


RISPOSTE = sorted((FIXTURES / "risposte").glob("*.json"))
