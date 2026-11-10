"""L'ordine del giorno dell'Assemblea del Senato diventa una seduta prevista con i suoi argomenti (pagina del 10/11/2026)."""

import unittest
from pathlib import Path

from pipeline.carica.postgres import script_odg
from pipeline.controlli.uscite import _regole
from pipeline.trasforma.senato_odg import trasforma

PAGINA = (Path(__file__).parent / "fixtures" / "senato_odg.htm").read_bytes()


class TestOdgSenato(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(PAGINA, {"chiave": "leg19-senato-odg", "impronta": "x"})
        self.seduta, *self.voci = self.r["nodi"]

    def test_seduta_prevista(self):
        s = self.seduta
        self.assertEqual((s["uri"], s["number"], s["date"], s["start_time"], s["status"], s["kind"], s["chamber"]),
                         ("it:senato:19:sed0475", 475, "2026-11-11", "10:30", "planned", "assembly_agenda", "senato"))

    def test_argomenti_con_ddl_e_relatori(self):
        self.assertEqual(len(self.voci), 3)
        primo, _, terzo = self.voci
        self.assertTrue(primo["title"].startswith("Conversione in legge, con modificazioni, del decreto-legge 17 settembre 2026, n. 162"))
        self.assertFalse(primo["title"].endswith(")") and "2085" in primo["title"])          # il numero del ddl sta in acts
        self.assertEqual((primo["text"], primo["acts"], primo["rapporteurs"]),
                         ("Seguito della discussione dei disegni di legge", ["ddl:2085"], "SALVITTI"))
        self.assertEqual((terzo["text"], terzo["acts"], terzo["rapporteurs"]),
                         ("Discussione dalla sede redigente del disegno di legge", ["ddl:1997"], "COSENZA Giulia e LEONARDI Elena"))

    def test_controlli_e_script(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}, *({"tipo": "nodo", **n} for n in self.r["nodi"]),
                 *({"tipo": "arco", **a} for a in self.r["archi"])]
        self.assertEqual(_regole(righe), [])
        s = script_odg(righe)
        self.assertIn("DELETE FROM sitting WHERE uri = 'it:senato:19:sed0475' AND status = 'planned';", s)
        self.assertIn("lega_argomenti('it:senato:19:sed0475', 19)", s)

    def test_pagina_senza_ordine_del_giorno(self):
        with self.assertRaises(ValueError):
            trasforma(b"<html><body>manutenzione</body></html>", {})


if __name__ == "__main__":
    unittest.main()
