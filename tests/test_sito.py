"""Rotte del sito (api/sito.py), chiamate come funzioni. Quelle che leggono il database si saltano se non risponde."""

import unittest
from unittest import mock

from fastapi import HTTPException

from api import sito

try:
    from api.db import connessione
    connessione().close()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    MOTIVO = str(e)[:80]
else:
    MOTIVO = ""


class TestSitoSenzaDatabase(unittest.TestCase):
    def test_autorevolezza_senza_modello(self):
        from starlette.requests import Request
        from api.fascicolo import autorevolezza, modello

        def manca(*a, **k):
            raise modello.ModelloNonDisponibile("manca la chiave del modello")
        req = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)})
        with mock.patch.object(sito, "connessione", mock.MagicMock()), mock.patch.object(autorevolezza, "classifica", manca):
            self.assertEqual(sito.autorevolezza(req, sito.Classifica(topic="salario minimo")).status_code, 503)
        with mock.patch.object(sito, "connessione", mock.MagicMock()), \
                mock.patch.object(autorevolezza, "classifica", lambda c, t, r, ip=None: {"topic": t, "ramo": r}):
            self.assertEqual(sito.autorevolezza(req, sito.Classifica(topic="sanità", chamber="senato")), {"topic": "sanità", "ramo": "senato"})

    def test_condivisa_con_id_non_valido(self):
        with self.assertRaises(HTTPException):
            sito.condivisa("../x")

    def test_senza_schema_del_sito_niente_condivisione(self):
        from api import db
        with mock.patch.object(db, "env", side_effect=KeyError("SITO_PG_PASSWORD")):
            with sito._db_sito() as c:
                self.assertIsNone(c)

    def test_traduzione_illeggibile_o_di_lunghezza_diversa(self):
        def finto(testo):
            r = mock.MagicMock()
            r.__enter__.return_value.read.return_value = (
                '{"output": [{"type": "message", "content": [{"type": "output_text", "text": %s}]}]}' % testo).encode()
            return r
        with mock.patch.object(sito, "env", return_value="x"), mock.patch.object(sito.agente, "_conta"):
            with mock.patch("urllib.request.urlopen", return_value=finto('"```json\\n[\\"A\\", \\"B\\"]\\n```"')):
                self.assertEqual(sito._traduci_col_modello("1.2.3.4", ["a", "b"]), ["A", "B"])
            with mock.patch("urllib.request.urlopen", return_value=finto('"[\\"A\\"]"')):
                self.assertIsNone(sito._traduci_col_modello("1.2.3.4", ["a", "b"]))
            with mock.patch("urllib.request.urlopen", return_value=finto('"non è json"')):
                self.assertIsNone(sito._traduci_col_modello("1.2.3.4", ["a"]))


@unittest.skipIf(MOTIVO, f"Postgres non raggiungibile: {MOTIVO}")
class TestSitoSulDatabase(unittest.TestCase):
    def test_strumento_nella_forma_del_sito(self):
        r = sito._esegui("list_sessions", {"limit": 2})
        self.assertEqual(len(r["dati"]["sessions"]), 2)
        self.assertNotIn("errore", r)

    def test_argomenti_non_validi(self):
        r = sito._esegui("list_sessions", {"limit": "molte"})
        self.assertTrue(r["errore"])

    def test_verifica_nella_forma_del_sito(self):
        r = sito.verifica(sito.Verifica(answer="Nessuna citazione qui.", question="farmaci"))["dati"]
        self.assertEqual(set(r), {"outcome", "groups", "quotes", "authority", "scope"})
        self.assertEqual(r["outcome"]["quotes"], "na")
        self.assertEqual(r["quotes"], [])


if __name__ == "__main__":
    unittest.main()
