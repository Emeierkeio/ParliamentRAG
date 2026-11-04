"""Le note di lavoro del modello non arrivano a chi legge (4/11/2026, risposta sul salario minimo a 9 euro)."""

import unittest

from api.agente import senza_note_di_lavoro


class TestNoteDiLavoro(unittest.TestCase):
    def test_caso_del_4_novembre(self):
        testo = ("La proposta C. 1275 fu presentata da **Giuseppe Conte e altri deputati**.\n\n"
                 "Era il testo che riuniva le proposte delle opposizioni; tra le abbinate le pdl di Nicola Fratoianni e Maria Mari "
                 "(C. 141), Chiara Gribaudo? Wait correction: from data, Andrea? Need not overclaim.")
        pulito, tolti = senza_note_di_lavoro(testo)
        self.assertEqual(tolti, 1)
        self.assertEqual(pulito, "La proposta C. 1275 fu presentata da **Giuseppe Conte e altri deputati**.")

    def test_risposta_normale_resta(self):
        for testo in ("Alla Camera il ddl è stato approvato con 137 sì.\n\nIl Senato lo ha approvato il 24 giugno.",
                      "The Chamber approved bill C. 2911 on 10 June 2026 with 137 votes in favour.\n\n"
                      "Azione – Renew Europe abstained."):
            self.assertEqual(senza_note_di_lavoro(testo), (testo, 0))


if __name__ == "__main__":
    unittest.main()
