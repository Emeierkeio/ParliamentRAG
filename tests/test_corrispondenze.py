"""La stessa persona con l'id della Camera e quello del Senato, anche con nomi scritti diversamente (campione 31/10/2026)."""

import json
import unittest
from pathlib import Path

from pipeline.trasforma.corrispondenze import trasforma

GREZZI = json.loads((Path(__file__).parent / "fixtures" / "corrispondenze_campione.json").read_text(encoding="utf-8"))


class TestCorrispondenze(unittest.TestCase):
    def test_tutti_legati_una_volta(self):
        r = trasforma(GREZZI, 19)
        legati = {a["from"] for a in r["archi"]}
        self.assertEqual(legati, {n["uri"] for n in r["nodi"]})
        self.assertEqual(len({a["to"] for a in r["archi"]}), len(r["archi"]))   # niente due persone sulla stessa
        metodi = {a["method"] for a in r["archi"]}
        self.assertTrue({"nome e cognome", "cognome unico"} <= metodi)


if __name__ == "__main__":
    unittest.main()
