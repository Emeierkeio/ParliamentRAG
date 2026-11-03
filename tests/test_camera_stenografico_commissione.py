"""Lo stenografico di una commissione diventa interventi parola per parola, di deputati e auditi (IV Commissione, 21/10/2026)."""

import unittest
from pathlib import Path

from pipeline.controlli.uscite import _regole_commissione
from pipeline.trasforma.camera_stenografico_commissione import trasforma

CORPO = (Path(__file__).parent / "fixtures" / "stenografico_commissione_c04_20261021.htm").read_bytes()


class TestStenograficoCommissione(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-stc-04-indag-c04_quantistiche-20261021-0003"})
        self.testi = {t["ref"]: t["text"] for t in self.r["testi"]}
        self.speech = [n for n in self.r["nodi"] if n["label"] == "Speech"]

    def test_seduta(self):
        s = self.r["nodi"][0]
        self.assertEqual((s["kind"], s["body_code"], s["start_time"], s["end_time"]), ("committee_verbatim", "04", "08:30", "09:10"))

    def test_audito(self):
        a = next(n for n in self.speech if n["speaker_label"] == "DANIELE PAVARIN")
        self.assertTrue(a["guest"])
        self.assertTrue(a["as_office"].startswith("CEO di T4i"))
        self.assertTrue(self.testi[a["text_ref"]].startswith("Signor presidente"))  # senza nome e qualifica in testa

    def test_deputati_e_presidente(self):
        by = {a["from"]: a["to"] for a in self.r["archi"] if a["type"] == "BY"}
        pres = [n for n in self.speech if n["speaker_label"] == "PRESIDENTE"]
        self.assertTrue(pres and all(by.get(n["uri"]) == "it:person:camera:302913" for n in pres))
        self.assertTrue(self.testi[pres[0]["text_ref"]].startswith("Avverto che"))

    def test_verbatim_e_controlli(self):
        self.assertTrue(all(n["kind"] == "verbatim" for n in self.speech))
        refs = set(self.testi)
        self.assertEqual(_regole_commissione(self.r["nodi"], self.r["archi"], refs, "camera_stenografici_commissioni"), [])


if __name__ == "__main__":
    unittest.main()
