"""Taglio degli interventi in brani per la ricerca per significato: mai a metà frase, posizioni esatte nel testo."""

import unittest

from pipeline.vettori import LUNGHEZZA, MASSIMO, MINIMO, _frasi, taglia_testo

FRASE = "Il Governo ha presentato il decreto n. 12 all'esame dell'on. Rossi, come previsto dall'art. 72 della Costituzione e dal Doc. XII. "


class TestTaglio(unittest.TestCase):
    def test_corto_escluso(self):
        self.assertEqual(taglia_testo("Chiedo di parlare."), [])

    def test_brani_a_fine_frase_e_contigui(self):
        testo = FRASE * 40
        brani = taglia_testo(testo)
        self.assertGreater(len(brani), 1)
        for a, b in brani:
            self.assertTrue(testo[a:b].startswith("Il Governo") and testo[a:b].endswith("XII."))
            self.assertLessEqual(b - a, LUNGHEZZA)
        self.assertEqual(testo[brani[-1][1]:].strip(), "")
        for (_, b), (a, _) in zip(brani, brani[1:]):
            self.assertEqual(testo[b:a].strip(), "")      # niente testo perso fra due brani

    def test_abbreviazioni_e_sigle_non_tagliano(self):
        testo = ("Sulla proposta A.C. 1234 il collega G. Bianchi ha parlato dell'on. Verdi e dell'art. 5. "
                 "Lo ha fatto nel 2023. Poi basta.")
        self.assertEqual([testo[a:b] for a, b in _frasi(testo)],
                         ["Sulla proposta A.C. 1234 il collega G. Bianchi ha parlato dell'on. Verdi e dell'art. 5. Lo ha fatto nel 2023.",
                          "Poi basta."])

    def test_resto_corto_va_col_brano_prima(self):
        testo = FRASE * 11 + "Grazie."
        brani = taglia_testo(testo)
        self.assertTrue(testo[brani[-1][0]:brani[-1][1]].endswith("Grazie."))
        self.assertGreaterEqual(brani[-1][1] - brani[-1][0], MINIMO)

    def test_testo_senza_punteggiatura_si_spezza(self):
        testo = "parola " * 3000
        brani = taglia_testo(testo)
        self.assertTrue(all(b - a <= MASSIMO for a, b in brani))
        self.assertEqual(sum(len(testo[a:b].split()) for a, b in brani), 3000)


if __name__ == "__main__":
    unittest.main()
