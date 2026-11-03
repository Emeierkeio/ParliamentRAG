"""L'ordine del giorno diventa una seduta prevista con argomenti, orari, atti e relatori (seduta 737, 3/11/2026)."""

import unittest
from pathlib import Path

from pipeline.carica.postgres import script_odg
from pipeline.trasforma.camera_odg import trasforma

CORPO = (Path(__file__).parent / "fixtures" / "odg_seduta_0737.htm").read_bytes()


class TestOdg(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-odg-20261103"})
        self.voci = [n for n in self.r["nodi"] if n["label"] == "AgendaItem"]

    def test_seduta_prevista(self):
        s = self.r["nodi"][0]
        self.assertEqual((s["uri"], s["date"], s["status"], s["start_time"]), ("it:camera:19:sed0737", "2026-11-03", "planned", "10:00"))

    def test_argomenti(self):
        self.assertEqual(len(self.voci), 7)
        dl = self.voci[1]
        self.assertEqual((dl["scheduled_time"], dl["acts"]), ("14:00", ["ac:3148"]))
        self.assertTrue(dl["rapporteurs"].startswith("MILANI"))

    def test_il_resoconto_vince(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]]
        s = script_odg(righe)
        self.assertIn("DELETE FROM sitting WHERE uri = 'it:camera:19:sed0737' AND status = 'planned';", s)
        self.assertIn("WHERE NOT EXISTS (SELECT 1 FROM sitting WHERE uri = 'it:camera:19:sed0737')", s)


if __name__ == "__main__":
    unittest.main()
