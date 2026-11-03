"""Un dossier del Servizio Studi diventa un documento con data, servizio, codice, atto e testo (OCD18-23818, 30/10/2026)."""

import unittest
from pathlib import Path

from pipeline.trasforma.camera_dossier import atto_da_codice, metadati_elenco, trasforma

F = Path(__file__).parent / "fixtures"


class TestDossier(unittest.TestCase):
    def test_dossier(self):
        meta = metadati_elenco((F / "dossier_elenco_estratto.htm").read_bytes())
        r = trasforma((F / "dossier_OCD18-23818_scheda.htm").read_bytes(), (F / "dossier_OCD18-23818_testo.htm").read_bytes(), meta,
                      {"chiave": "leg19-dossier-OCD18-23818-scheda", "url": "https://temi.camera.it/leg19/dossier/OCD18-23818/x.html"})
        n = r["nodi"][0]
        self.assertEqual((n["kind"], n["code"], n["acts"], n["date"], n["author_raw"]), ("dossier", "D26162a", ["dl:162/2026"], "2026-10-30", "Studi - Finanze"))
        self.assertFalse(n["third_party"])
        self.assertGreater(len(r["testi"][0]["text"]), 50_000)
        self.assertNotIn("<", r["testi"][0]["text"][:2000])

    def test_codici(self):
        self.assertEqual(atto_da_codice("AC0550"), ["ac:550"])
        self.assertEqual(atto_da_codice("AS0473b"), ["as:473"])
        self.assertEqual(atto_da_codice("RI113"), [])


if __name__ == "__main__":
    unittest.main()
