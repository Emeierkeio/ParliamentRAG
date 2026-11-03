"""L'anagrafica OSR del Senato diventa gli stessi record della Camera (campione del 31/10/2026: Malan, Segre, Romeo)."""

import json
import unittest
from pathlib import Path

from pipeline.trasforma.senato_anagrafica import trasforma

GREZZI = json.loads((Path(__file__).parent / "fixtures" / "senato_osr_campione.json").read_text(encoding="utf-8"))


def in_corso(a, giorno="2026-10-31"):
    return a.get("start") and a["start"] <= giorno and (not a.get("end") or a["end"] >= giorno)


class TestSenato(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(GREZZI, 19)
        self.nodi = {n["uri"]: n for n in self.r["nodi"]}
        self.chi = {n["family_name"]: n["uri"] for n in self.r["nodi"] if n["label"] == "Person"}

    def test_persone_e_mandati(self):
        self.assertTrue(all(u.startswith("it:person:senato:") for u in self.chi.values()))
        tipi = {self.nodi[a["from"]]["family_name"]: a["kind"] for a in self.r["archi"] if a["type"] == "MANDATE"}
        self.assertEqual((tipi["Segre"], tipi["Malan"]), ("life", "elected"))

    def test_capogruppo(self):
        cariche = [a for a in self.r["archi"] if a["type"] == "OFFICE" and a["from"] == self.chi["Malan"] and in_corso(a)]
        self.assertTrue(any(a["title"] == "leader" and self.nodi[a["to"]]["short_name"] == "FdI" for a in cariche))


if __name__ == "__main__":
    unittest.main()
