"""Correzioni del controllo del 25/11/2026: tempo massimo del fascicolo e livello del titolo di studio."""

import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from api.fascicolo import servizio
from api.strumenti.persone import _livello_studio


class TestTempoFascicolo(unittest.TestCase):
    def test_oltre_la_scadenza_si_ferma(self):
        pool = ThreadPoolExecutor(max_workers=1)
        f = pool.submit(time.sleep, 2)
        token = servizio._SCADENZA.set(time.monotonic() - 1)
        try:
            with self.assertRaises(servizio.TempoScaduto):
                list(servizio._in_attesa(f))
        finally:
            servizio._SCADENZA.reset(token)
            pool.shutdown(wait=False)

    def test_senza_scadenza_aspetta_la_fine(self):
        pool = ThreadPoolExecutor(max_workers=1)
        f = pool.submit(lambda: 1)
        self.assertEqual(list(servizio._in_attesa(f)), [])
        pool.shutdown()


class TestLivelloStudio(unittest.TestCase):
    def test_livelli(self):
        self.assertEqual(_livello_studio("Laurea in giurisprudenza"), "laurea o titolo superiore")
        self.assertEqual(_livello_studio("DOTTORATO di ricerca"), "laurea o titolo superiore")
        self.assertEqual(_livello_studio("Diploma di liceo classico"), "diploma o licenza")
        self.assertEqual(_livello_studio(None), "non indicato")
        self.assertEqual(_livello_studio("  "), "non indicato")
        self.assertEqual(_livello_studio("Giornalista"), "altro")


if __name__ == "__main__":
    unittest.main()
