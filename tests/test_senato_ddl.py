"""I ddl del Senato con le assegnazioni alle commissioni e i relatori (S. 1110, decreto PNRR, dati del 10/11/2026)."""

import json
import unittest
from pathlib import Path

from pipeline.carica.postgres import script_atti
from pipeline.trasforma.senato_ddl import trasforma

GREZZI = json.loads((Path(__file__).parent / "fixtures" / "senato_ddl_1110.json").read_text(encoding="utf-8"))


class TestDdlSenato(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(GREZZI, 19, {"chiave": "leg19-atti", "impronta": "x"})
        self.archi = self.r["archi"]

    def test_assegnazioni(self):
        a = [x for x in self.archi if x["type"] == "ASSIGNED"]
        self.assertEqual(len(a), 12)
        merito = next(x for x in a if x["seat"] == "referente")
        self.assertEqual((merito["from"], merito["to"], merito["date"], merito["title"]),
                         ("it:senato:19:ddl:1110", "it:senato:19:body:0-5", "2024-04-18", "5ª (Bilancio)"))
        self.assertEqual({x["seat"] for x in a if x is not merito}, {"consultiva"})

    def test_relatore_con_il_senatore(self):
        r, = [x for x in self.archi if x["type"] == "RAPPORTEUR"]
        self.assertEqual((r["from_ref"], r["role"], r["person"], r["to"]),
                         ("Dario Damiani", "rapporteur", "it:person:senato:32747", "it:senato:19:ddl:1110"))

    def test_senza_le_query_nuove(self):
        # un lago che ha solo le query di prima dà gli atti di prima, senza assegnazioni né relatori
        r = trasforma({k: v for k, v in GREZZI.items() if k in ("ddl", "firmatari", "presentatori")}, 19)
        self.assertEqual(len(r["nodi"]), 1)
        self.assertFalse([x for x in r["archi"] if x["type"] in ("ASSIGNED", "RAPPORTEUR")])

    def test_script(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}, *({"tipo": "nodo", **n} for n in self.r["nodi"]),
                 *({"tipo": "arco", **a} for a in self.archi)]
        s = script_atti(righe)
        self.assertIn("COPY act_rapporteur (act, name_raw, role, raw, person)", s)
        self.assertIn("it:senato:19:ddl:1110,Dario Damiani,rapporteur,Sen. Dario Damiani,it:person:senato:32747", s)
        self.assertIn("it:person:senato:32747", s.split("COPY p FROM STDIN")[1].split("\\.")[0])   # la persona entra prima della riga


if __name__ == "__main__":
    unittest.main()
