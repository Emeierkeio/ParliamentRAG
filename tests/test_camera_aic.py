"""Interrogazioni, ordini del giorno e altri atti di sindacato ispettivo diventano atti con testo, firmatari,
ministeri destinatari e temi (campione di ottobre 2026)."""

import unittest
from pathlib import Path

from pipeline.carica.postgres import script_aic
from pipeline.controlli.uscite import _regole_aic
from pipeline.trasforma.camera_aic import _ministero, trasforma, uri_aic

CORPO = (Path(__file__).parent / "fixtures" / "camera_aic_campione.json.gz").read_bytes()


class TestAic(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-aic-202610"})

    def test_atti(self):
        tipi = {n["kind"] for n in self.r["nodi"]}
        self.assertEqual(tipi, {"written_question", "agenda_order", "committee_question"})
        self.assertTrue(all(n["text"] and n["date"] for n in self.r["nodi"]))

    def test_legami(self):
        tipi = {a["type"] for a in self.r["archi"]}
        self.assertTrue({"SPONSORS", "ADDRESSED_TO"} <= tipi)
        self.assertTrue(all(a["to"].startswith("it:gov:") for a in self.r["archi"] if a["type"] == "ADDRESSED_TO"))

    def test_controlli_e_caricamento(self):
        self.assertEqual(_regole_aic(self.r["nodi"], self.r["archi"]), [])
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]]
        s = script_aic(righe)
        self.assertIn("DELETE FROM act WHERE source_key = 'leg19-aic-202610' AND chamber = 'camera';", s)
        self.assertIn("'it:camera:19:aic:' || replace(regexp_replace(v.act_ref, '^aic|_19$', '', 'g'), '_', '-')", s)

    def test_identificativi(self):
        self.assertEqual(uri_aic("9/00080/004", 19), "it:camera:19:aic:9-00080-004")
        self.assertEqual(_ministero("http://dati.camera.it/ocd/organoGoverno.rdf/og202_285"), "it:gov:202:og202_285")


if __name__ == "__main__":
    unittest.main()
