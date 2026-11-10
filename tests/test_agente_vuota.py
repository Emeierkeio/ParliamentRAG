"""Una risposta del modello senza testo non arriva vuota a chi legge (10/11/2026, riga 441 del registro: dopo una
ricerca senza risultati il modello ha chiuso senza scrivere niente)."""

import datetime as dt
import unittest
from contextlib import contextmanager
from unittest import mock

from api import agente


def _messaggio(testo: str) -> dict:
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": testo}]}], "usage": {}}


class _Db:
    def execute(self, *a, **k):
        return self

    def fetchone(self):
        return {"d": dt.date(2026, 11, 9)}


@contextmanager
def _connessione():
    yield _Db()


class TestRispostaVuota(unittest.TestCase):
    def _rispondi(self, risposte: list[dict]) -> tuple[str, mock.Mock]:
        modello = mock.Mock(side_effect=risposte)
        with mock.patch.object(agente, "chiama_openai", modello), mock.patch.object(agente, "connessione", _connessione), \
                mock.patch.object(agente, "_conta"), mock.patch.object(agente, "env", lambda n, d=None: d or "x"):
            eventi = list(agente.rispondi("Cosa c'è su Acme?", [], "it", "127.0.0.1"))
        return "".join(e["text"] for e in eventi if e["type"] == "delta"), modello

    def test_riprova_una_volta(self):
        testo, modello = self._rispondi([_messaggio("SEGUITI: a | b"), _messaggio("Non risulta nei dati.")])
        self.assertEqual(testo, "Non risulta nei dati.")
        self.assertEqual(modello.call_count, 2)
        self.assertTrue(any(v.get("content") == agente.RISPOSTA_VUOTA for v in modello.call_args.args[2]))

    def test_vuota_due_volte(self):
        testo, modello = self._rispondi([_messaggio(""), _messaggio("")])
        self.assertIn("Non sono riuscito a chiudere la risposta", testo)
        self.assertEqual(modello.call_count, 2)

    def test_risposta_normale_una_chiamata(self):
        testo, modello = self._rispondi([_messaggio("Il ddl è in Commissione.\nSEGUITI: a | b")])
        self.assertEqual((testo, modello.call_count), ("Il ddl è in Commissione.", 1))


if __name__ == "__main__":
    unittest.main()
