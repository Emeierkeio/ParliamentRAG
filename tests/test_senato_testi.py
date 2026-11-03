"""Il testo della commissione di un ddl del Senato diventa testo e articoli legati all'atto (1695 e 762-A, marzo 2026)."""

import unittest
from pathlib import Path

from pipeline.carica.postgres import script_testo_atto
from pipeline.controlli.uscite import _regole
from pipeline.trasforma.senato_testi import trasforma

CORPO = (Path(__file__).parent / "fixtures" / "senato_testo_ddlcomm_1695.akn.xml").read_bytes()


class TestSenatoTesti(unittest.TestCase):
    def test_testo(self):
        r = trasforma(CORPO, {"chiave": "leg19-senato-testo-ddlcomm-01496679"})
        n = r["nodi"][0]
        self.assertEqual((n["code"], n["act"], n["kind"]), ("senato.19.01496679", "it:senato:19:ddl:1695", "committee"))
        self.assertEqual([a["number"] for a in n["articles"]], ["1", "2", "3", "4", "5"])
        self.assertIn("1. Nel rispetto dei princìpi", n["articles"][0]["text"])
        righe = [{"tipo": "ambito", **r["ambito"]}, {"tipo": "nodo", **n}, {"tipo": "testo", **r["testi"][0]}]
        self.assertEqual(_regole(righe), [])
        self.assertIn("it:senato:19:ddl:1695", script_testo_atto(righe))


if __name__ == "__main__":
    unittest.main()
