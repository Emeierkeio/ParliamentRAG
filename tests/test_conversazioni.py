"""Registro delle chat: la riga raccoglie risposta, strumenti ed errori, anche quando il client chiude prima della fine."""

import unittest
from unittest import mock

from api import conversazioni


def agente(misure):
    misure["modello"] = "m"
    try:
        yield {"type": "status", "text": "Leggo la domanda"}
        yield {"type": "tool", "id": "1", "state": "start", "name": "cerca_atti", "args": {"q": "salario minimo"}}
        yield {"type": "tool", "id": "1", "state": "done", "name": "cerca_atti", "count": 12}
        yield {"type": "delta", "text": "Risposta "}
        yield {"type": "delta", "text": "completa."}
        yield {"type": "done"}
    finally:
        misure["dollari"] = 0.0123456


class TestRegistro(unittest.TestCase):
    def test_riga_completa(self):
        misure = {}
        with mock.patch.object(conversazioni, "salva") as salva:
            eventi = list(conversazioni.registra(agente(misure), "Chi ha votato?", "it", "abcdefgh12", 2, misure))
        self.assertEqual(len(eventi), 6)
        riga = salva.call_args.args[0]
        self.assertEqual(riga["risposta"], "Risposta completa.")
        self.assertEqual(riga["strumenti"], [{"nome": "cerca_atti", "argomenti": {"q": "salario minimo"}, "risultati": 12}])
        self.assertEqual((riga["conversazione"], riga["turno"], riga["modello"], riga["dollari"]), ("abcdefgh12", 2, "m", 0.01235))
        self.assertNotIn("ip", riga)

    def test_client_che_chiude(self):
        misure = {}
        with mock.patch.object(conversazioni, "salva") as salva:
            g = conversazioni.registra(agente(misure), "Domanda", "it", None, None, misure)
            next(g), next(g)
            g.close()
        riga = salva.call_args.args[0]
        self.assertIsNone(riga["risposta"])
        self.assertEqual(riga["dollari"], 0.01235)    # l'agente è stato chiuso prima di scrivere la riga

    def test_senza_password_non_scrive(self):
        with mock.patch.object(conversazioni, "_password", return_value=None), mock.patch("psycopg.connect") as connetti:
            conversazioni.salva({})
        connetti.assert_not_called()


if __name__ == "__main__":
    unittest.main()
