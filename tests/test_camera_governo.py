"""Governi e incarichi di governo (campione del 30/10/2026: Meloni, Draghi, Salvini, Bernini)."""

import json
import unittest
from pathlib import Path

from pipeline.carica.postgres import script_governo
from pipeline.controlli.uscite import _regole_governo
from pipeline.trasforma.camera_governo import trasforma

GREZZI = json.loads((Path(__file__).parent / "fixtures" / "camera_governo_campione.json").read_text(encoding="utf-8"))


class TestGoverno(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(GREZZI, 19)
        self.nodi = {n["uri"]: n for n in self.r["nodi"]}
        self.chi = {n["family_name"]: n["uri"] for n in self.r["nodi"] if n["label"] == "Person"}

    def incarichi(self, cognome):
        return [a for a in self.r["archi"] if a["from"] == self.chi[cognome]]

    def test_un_solo_presidente_oggi(self):
        self.assertEqual(_regole_governo(self.r["nodi"], self.r["archi"]), [])

    def test_draghi_chiuso_con_il_governo(self):
        pm = next(a for a in self.incarichi("Draghi") if a["title"] == "prime_minister")
        self.assertEqual((pm["end"], pm["end_reason"]), ("2022-10-21", "fine del governo"))

    def test_salvini_due_incarichi(self):
        titoli = {a["title"] for a in self.incarichi("Salvini") if not a["end"]}
        self.assertEqual(titoli, {"minister", "deputy_prime_minister"})
        ministero = next(a["to"] for a in self.incarichi("Salvini") if a["title"] == "minister" and not a["end"])
        self.assertIn("Infrastrutture", self.nodi[ministero]["name"])

    def test_caricamento(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]]
        s = script_governo(righe)
        self.assertIn("coalesce(person.given_name, EXCLUDED.given_name)", s)  # non sovrascrive l'anagrafica della Camera
        self.assertTrue(s.rstrip().endswith("COMMIT;"))


if __name__ == "__main__":
    unittest.main()
