"""I voti OCD di una seduta diventano votazioni e voti dei singoli, e i conti tornano (seduta 8, 2 votazioni)."""

import unittest
from collections import Counter
from pathlib import Path

from pipeline.carica.postgres import script_voti
from pipeline.controlli.uscite import _regole_voti, avvisi_voti
from pipeline.trasforma.camera_voti import esito, trasforma, uri_votazione

CORPO = (Path(__file__).parent / "fixtures" / "camera_voti_leg19_sed0008.json.gz").read_bytes()


class TestVoti(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-voti-sed0008"})
        self.voti = [a for a in self.r["archi"] if a["type"] == "VOTED"]

    def test_struttura(self):
        self.assertEqual(len(self.r["nodi"]), 2)
        self.assertEqual(len(self.voti), 798)
        self.assertTrue(all(a["from"].startswith("it:person:camera:") for a in self.voti))
        self.assertEqual(self.r["ambito"]["sitting"], "it:camera:19:sed0008")

    def test_totali_tornano(self):
        self.assertEqual(_regole_voti(self.r["nodi"], self.r["archi"]), [])

    def test_totali_sbagliati_sono_un_avviso(self):
        nodi = [dict(n) for n in self.r["nodi"]]
        nodi[0]["favor"] += 1
        self.assertEqual(_regole_voti(nodi, self.r["archi"]), [])
        self.assertEqual(len(avvisi_voti(nodi, self.r["archi"])), 1)
        self.assertTrue(all(n["ballots_match"] for n in self.r["nodi"]))

    def test_gruppo_al_voto(self):
        self.assertTrue(all(a["group"] and a["group"].startswith("it:camera:19:group:") for a in self.voti))

    def test_esiti(self):
        self.assertEqual(esito("Non ha votato", "In missione"), "mission")
        self.assertEqual(esito("Non ha votato", "Presidente di turno"), "chair")
        self.assertEqual(esito("Non ha votato", "Non ha partecipato"), "absent")
        self.assertEqual(esito("Favorevole", "Presidente di turno"), "favor")
        self.assertEqual(uri_votazione("http://dati.camera.it/ocd/votazione.rdf/vs19_722_001", 19), "it:camera:19:sed0722:v001")
        self.assertGreater(Counter(a["result"] for a in self.voti)["mission"], 0)

    def test_caricamento(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]]
        s = script_voti(righe)
        self.assertIn("DELETE FROM vote WHERE sitting = 'it:camera:19:sed0008' AND source = 'ocd';", s)
        self.assertTrue(s.rstrip().endswith("COMMIT;"))


if __name__ == "__main__":
    unittest.main()
