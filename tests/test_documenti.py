"""I riferimenti ai documenti parlamentari nei testi e i titoli delle schede (pipeline/documenti.py)."""

import unittest

from pipeline import documenti as D


class TestDocumenti(unittest.TestCase):
    def test_riferimenti(self):
        self.assertEqual(D.chiavi("Doc. IV-ter, n. 13-A"), [("IV-ter", "13")])
        self.assertEqual(D.chiavi("(DOC. XVIII-BIS, n. 10)"), [("XVIII-bis", "10")])
        self.assertEqual(D.chiavi("Doc. XXII, nn. 11-14-16"), [("XXII", "11"), ("XXII", "14"), ("XXII", "16")])
        self.assertEqual(D.chiavi("Doc. LVII, n. 1.bis"), [("LVII", "1-bis")])
        self.assertEqual(D.chiavi("Docc. LVII, n. 01-bis"), [("LVII", "01-bis")])
        self.assertEqual(D.chiavi("Relazione sui documenti LXXXVI, n. 1, e LXXXVII, n. 1"), [("LXXXVI", "1"), ("LXXXVII", "1")])
        self.assertEqual(D.chiavi("Doc. n. 98"), [])
        self.assertEqual(D.chiavi(None), [])

    def test_titolo_dal_dibattito(self):
        t = "Discussione congiunta dei documenti: Conto consuntivo della Camera (Doc. VIII, n. 1); Progetto di bilancio della Camera (Doc. VIII, n. 2)"
        self.assertEqual(D.titolo_prima(t, ("VIII", "2")), "Progetto di bilancio della Camera")
        self.assertIsNone(D.titolo_prima("Emendamento 1.102 SIMIANI (Doc. XXII, n. 11)", ("XXII", "11")))

    def test_titolo_della_scheda(self):
        self.assertEqual(D.titolo_scheda("D'iniziativa dei deputati: BICCHIELLI ed altri Istituzione di una Commissione d'inchiesta"),
                         "Istituzione di una Commissione d'inchiesta")
        self.assertIsNone(D.titolo_scheda("Anno 2021 Presentata dal Ministro dell'economia: GIORGETTI"))

    def test_pdf_della_camera(self):
        self.assertTrue(D.pdf_camera(("IV-ter", "13")).endswith("/004ter/013/INTERO.pdf"))
        self.assertTrue(D.pdf_camera(("LVII", "1-bis")).endswith("/057/001bis/INTERO.pdf"))


if __name__ == "__main__":
    unittest.main()
