"""I controlli sui fatti letti dal modello: frase copiata, esito ammesso, ente scritto, atti normalizzati."""

import unittest

from pipeline.fatti import riferimento, verifica

ARG = {"item": "it:camera:19:x", "acts": [{"ref": "ac:3120", "act": "it:camera:19:ac:3120"}], "paragrafi": [
    {"uri": "p1", "text": "Audizione informale di rappresentanti di Confimprese e di Assopetroli-Assoenergia, nell'ambito dell'esame del disegno di legge C. 3120."},
    {"uri": "p2", "text": "La Commissione approva la proposta di parere favorevole con osservazioni formulata dal relatore."}]}


class TestVerifica(unittest.TestCase):
    def test_audizione_buona(self):
        r, m = verifica(ARG, {"tipo": "audizione", "quando": "in questa seduta", "paragrafo": 1, "evidenza": "Audizione informale di rappresentanti di Confimprese",
                              "atti": ["C. 3120"], "soggetto": "Confimprese", "esito": None, "emendamenti": []})
        self.assertIsNone(m)
        self.assertEqual((r["kind"], r["act"], r["act_refs"], r["speech"]), ("hearing", "it:camera:19:ac:3120", ["ac:3120"], "p1"))

    def test_frase_inventata(self):
        _, m = verifica(ARG, {"tipo": "audizione", "quando": "in questa seduta", "paragrafo": 1, "evidenza": "Audizione formale del ministro delle imprese",
                              "atti": [], "soggetto": "Confimprese", "esito": None, "emendamenti": []})
        self.assertEqual(m, "frase non copiata dal sommario")

    def test_ente_non_scritto(self):
        _, m = verifica(ARG, {"tipo": "audizione", "quando": "in questa seduta", "paragrafo": 1, "evidenza": "Audizione informale di rappresentanti di Confimprese",
                              "atti": [], "soggetto": "Confindustria", "esito": None, "emendamenti": []})
        self.assertEqual(m, "ente dell'audizione non scritto nel sommario")

    def test_esito_non_ammesso(self):
        _, m = verifica(ARG, {"tipo": "parere", "quando": "in questa seduta", "paragrafo": 2, "evidenza": "La Commissione approva la proposta di parere favorevole",
                              "atti": [], "soggetto": "X", "esito": "soddisfatto", "emendamenti": []})
        self.assertEqual(m, "esito non ammesso")

    def test_atto_unico_dell_argomento(self):
        r, m = verifica(ARG, {"tipo": "parere", "quando": "in questa seduta", "paragrafo": 2, "evidenza": "approva la proposta di parere favorevole con osservazioni",
                              "atti": [], "soggetto": "X Commissione", "esito": "favorevole con osservazioni", "emendamenti": []})
        self.assertEqual((m, r["act"]), (None, "it:camera:19:ac:3120"))

    def test_auditi_nel_titolo(self):
        a = {**ARG, "title": "Audizione informale di rappresentanti di Coldiretti e Confagricoltura",
             "paragrafi": [{"uri": "p1", "text": "L'audizione informale è stata svolta dalle 10.55 alle 11.15."}]}
        r, m = verifica(a, {"tipo": "audizione", "quando": "in questa seduta", "paragrafo": 1, "atti": [], "emendamenti": [],
                            "evidenza": "L'audizione informale è stata svolta dalle 10.55 alle 11.15.", "soggetto": "Coldiretti", "esito": None})
        self.assertEqual((m, r["subject"]), (None, "Coldiretti"))

    def test_fatto_ricordato(self):
        _, m = verifica(ARG, {"tipo": "parere", "quando": "prima", "paragrafo": 2, "evidenza": "approva la proposta di parere favorevole con osservazioni",
                              "atti": [], "soggetto": "X", "esito": "favorevole con osservazioni", "emendamenti": []})
        self.assertEqual(m, "fatto ricordato o annunciato, non della seduta")

    def test_replica_senza_esito(self):
        a = {**ARG, "paragrafi": [{"uri": "p1", "text": "Il sottosegretario Luigi D'ERAMO risponde all'interrogazione in titolo nei termini riportati in allegato."}]}
        r, m = verifica(a, {"tipo": "interrogazione", "quando": "in questa seduta", "paragrafo": 1, "atti": ["5-05950"], "emendamenti": [],
                            "evidenza": "Il sottosegretario Luigi D'ERAMO risponde all'interrogazione in titolo", "soggetto": "Luigi D'ERAMO", "esito": "soddisfatto"})
        self.assertEqual((m, r["outcome"], r["act_refs"]), (None, None, ["aic:5-05950"]))

    def test_riferimenti(self):
        self.assertEqual([riferimento(x) for x in ("C. 3120", "S. 2074", "5-01234", "Atto n. 312", "Doc. XVI")],
                         ["ac:3120", "ddl:2074", "aic:5-01234", "ag:312", None])


if __name__ == "__main__":
    unittest.main()
