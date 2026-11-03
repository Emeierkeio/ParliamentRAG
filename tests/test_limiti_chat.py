"""Limite della chat: domande nell'ultima ora per impronta dell'IP, mai l'IP nel file; secondi prima che se ne liberi una."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from api import agente


class TestLimiti(unittest.TestCase):
    def setUp(self):
        self.cartella = tempfile.TemporaryDirectory()
        self.qui = mock.patch.object(agente, "QUI", Path(self.cartella.name))
        self.qui.start()
        self.env = mock.patch.object(agente, "env", lambda nome, pred=None: {"AGENTE_DOMANDE_ORA": "3", "AGENTE_DOLLARI_GIORNO": "10",
                                                                              "LIMITE_SALE": "prova"}.get(nome, pred))
        self.env.start()
        agente._SALE = None

    def tearDown(self):
        self.qui.stop(), self.env.stop(), self.cartella.cleanup()
        agente._SALE = None

    def test_finestra_di_un_ora(self):
        with mock.patch.object(agente.time, "time", return_value=1000.0):
            for _ in range(3):
                agente._conta("10.0.0.1", 1, 0.01)
        with mock.patch.object(agente.time, "time", return_value=1600.0):
            self.assertEqual(agente.uso("10.0.0.1"), {"used": 3, "limit": 3, "resets_in": 3000})
            self.assertIn("fra 50 minuti", agente.controlla_limiti("10.0.0.1"))
            self.assertIsNone(agente.controlla_limiti("10.0.0.2"))
        with mock.patch.object(agente.time, "time", return_value=4601.0):
            self.assertEqual(agente.uso("10.0.0.1")["used"], 0)

    def test_nel_file_non_c_e_l_ip(self):
        agente._conta("192.168.77.88", 1, 0.0)
        contenuto = (Path(self.cartella.name) / "dati" / "api" / "spesa.sqlite").read_bytes()
        self.assertNotIn(b"192.168.77.88", contenuto)

    def test_tabella_vecchia_cancellata(self):
        f = Path(self.cartella.name) / "dati" / "api" / "spesa.sqlite"
        f.parent.mkdir(parents=True)
        with sqlite3.connect(f) as db:
            db.execute("CREATE TABLE uso (giorno TEXT, ip TEXT, domande INTEGER, dollari REAL)")
        agente.uso("10.0.0.1")
        with sqlite3.connect(f) as db:
            tabelle = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertEqual(tabelle, {"domande", "spesa"})


if __name__ == "__main__":
    unittest.main()
