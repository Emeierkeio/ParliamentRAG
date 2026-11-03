"""Documenti acquisiti: metadati dagli elenchi (chi, per cosa, quando) e testo dai file (estratti veri del 30/10/2026)."""

import unittest
from pathlib import Path

from pipeline.controlli.uscite import _regole
from pipeline.fonti.camera_documenti import chiave_file
from pipeline.trasforma.camera_documenti import _autore, trasforma_elenco, trasforma_file

F = Path(__file__).parent / "fixtures"


class TestDocumenti(unittest.TestCase):
    def test_elenco(self):
        r = trasforma_elenco((F / "documenti_c01_estratto.htm").read_bytes(), {"chiave": "leg19-doc-elenco-c01-audizioni"})
        self.assertTrue(r["nodi"])
        n = r["nodi"][0]
        self.assertEqual((n["body"], n["third_party"]), ("it:camera:19:body:o19_3501", True))
        self.assertTrue(n["uri"].startswith("it:camera:19:doc:com01-"))
        righe = [{"tipo": "ambito", **r["ambito"]}] + [{"tipo": "nodo", **x} for x in r["nodi"]]
        self.assertEqual(_regole(righe), [])

    def test_testo_pdf(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf non installata: lanciare i test con .venv/bin/python")
        r = trasforma_file((F / "documento_com07.pdf").read_bytes(), {"chiave": "leg19-doc-com07-104296-20261030150906678", "file": "x.pdf"})
        self.assertGreater(len(r["testi"][0]["text"]), 500)

    def test_surrogati(self):
        from unittest import mock
        with mock.patch("pipeline.trasforma.camera_documenti.testo", return_value="Audizione\udd00 del\x00 22 gennaio"):
            r = trasforma_file(b"", {"chiave": "leg19-doc-com10-54093-20250122091539442", "file": "x.pdf"})
        self.assertEqual(r["testi"][0]["text"], "Audizione del 22 gennaio")
        r["testi"][0]["text"].encode("utf-8")

    def test_nomi(self):
        u = "https://documenti.camera.it/leg19/documentiAcquisiti/COM01/Audizioni/leg19.com01.Audizioni.Memoria.PUBBLICO.ideGes.103199.23-10-2026-14-26-31.054.pdf"
        self.assertEqual(chiave_file(u, 19), "leg19-doc-com01-103199-20261023142631054")
        self.assertEqual(_autore("AG 439 - Memoria UIL FP"), "UIL FP")
        self.assertEqual(_autore("C. 2562 - Contributo scritto AGIA (27/10/2026)"), "AGIA")


if __name__ == "__main__":
    unittest.main()
