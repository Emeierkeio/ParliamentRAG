"""I progetti di legge OCD diventano atti con iter, firmatari (anche ministri), relatori e leggi (campione del 30/10/2026)."""

import json
import unittest
from pathlib import Path

from pipeline.carica.postgres import script_atti
from pipeline.controlli.uscite import _regole_atti
from pipeline.trasforma.camera_atti import legge, pulito, relatore, trasforma, uri_atto

GREZZI = json.loads((Path(__file__).parent / "fixtures" / "camera_atti_leg19_campione.json").read_text(encoding="utf-8"))


class TestAtti(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(GREZZI, 19)
        self.nodi = {n["uri"]: n for n in self.r["nodi"]}

    def test_legge(self):
        a = self.nodi["it:camera:19:ac:1305"]
        self.assertTrue(a["law_number"] and a["law_date"].endswith("-01"))  # «del 1° …»

    def test_ministri_firmatari(self):
        firme = [x for x in self.r["archi"] if x["type"] == "SPONSORS" and x["to"] == "it:camera:19:ac:1001"]
        self.assertTrue(firme and all(x["from"].startswith("it:person:camera:") for x in firme))
        self.assertTrue(any((x.get("as_office") or "").startswith("Ministro") for x in firme))

    def test_iter_ordinato(self):
        passi = sorted((x["order"], self.nodi[x["to"]]["date"]) for x in self.r["archi"] if x["type"] == "HAS_STEP" and x["from"] == "it:camera:19:ac:151")
        date = [d for _, d in passi]
        self.assertEqual(date, sorted(date))
        self.assertEqual(self.nodi["it:camera:19:ac:151"]["status_date"], date[-1])

    def test_controlli_e_caricamento(self):
        self.assertEqual(_regole_atti(self.r["nodi"], self.r["archi"]), [])
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]]
        s = script_atti(righe)
        self.assertIn("DELETE FROM act WHERE chamber = 'camera' AND legislature = 19 AND kind = 'bill';", s)  # non tocca il sindacato ispettivo
        self.assertTrue(s.rstrip().endswith("COMMIT;"))

    def test_funzioni(self):
        self.assertEqual(uri_atto("http://dati.camera.it/ocd/attocamera.rdf/ac19_151", 19), "it:camera:19:ac:151")
        self.assertEqual(legge("Legge 51 dell'8 aprile 2024 pubblicata"), ("51", "2024-04-08"))
        self.assertEqual(relatore("SCHIFONE Marta, relatore per la maggioranza"), ("SCHIFONE Marta", "majority"))
        self.assertEqual(pulito(' "maternit&agrave;" ^^http://www.w3.org/2001/XMLSchema#string'), '"maternità"')


if __name__ == "__main__":
    unittest.main()
