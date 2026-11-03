"""Gli emendamenti di un progetto di legge diventano proposte per sede con testo, esito e firmatari (C. 3131, ottobre 2026)."""

import unittest
from collections import Counter
from pathlib import Path

from pipeline.carica.postgres import script_emendamenti
from pipeline.trasforma.camera_emendamenti import trasforma

CORPO = (Path(__file__).parent / "fixtures" / "emendamenti_ac3131.xml").read_bytes()


class TestEmendamenti(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-eme-ac3131"})

    def test_proposte(self):
        self.assertEqual(len(self.r["nodi"]), 68)
        self.assertEqual(Counter(n["venue"] for n in self.r["nodi"]), {"referente": 43, "assembly": 25})
        e = next(n for n in self.r["nodi"] if n["uri"] == "it:camera:19:ac:3131:eme:com746:1.1")
        self.assertEqual((e["article"], e["action"], e["committee"], e["sitting_date"]), ("1", "soppressivo", "08", "2026-10-13"))
        self.assertEqual(e["identical"], ["it:camera:19:ac:3131:eme:com746:1.2"])

    def test_firmatari(self):
        firme = [a for a in self.r["archi"] if a["to"] == "it:camera:19:ac:3131:eme:com746:01.07"]
        self.assertEqual((firme[0]["from"], firme[0]["first"]), ("it:person:camera:307459", True))
        self.assertTrue(all(a["from"] for a in self.r["archi"]))

    def test_testi_e_caricamento(self):
        self.assertEqual(len(self.r["testi"]), 68)
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] \
            + [{"tipo": "arco", **a} for a in self.r["archi"]] + [{"tipo": "testo", **t} for t in self.r["testi"]]
        s = script_emendamenti(righe)
        self.assertIn("DELETE FROM amendment WHERE source_key = 'leg19-eme-ac3131';", s)


if __name__ == "__main__":
    unittest.main()
