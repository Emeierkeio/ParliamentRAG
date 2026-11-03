"""La trasformazione del resoconto della Camera conserva didascalie e struttura (seduta 722, 7/10/2026)."""

import unittest
from collections import Counter
from pathlib import Path

from pipeline.trasforma.camera_resoconto import reazioni, trasforma

XML = (Path(__file__).parent / "fixtures" / "stenografico_leg19_0722.xml").read_bytes()


class TestResoconto(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(XML, {"chiave": "leg19-sed0722"})
        self.label = Counter(n["label"] for n in self.r["nodi"])

    def test_struttura(self):
        self.assertEqual(self.label["Sitting"], 1)
        self.assertEqual(self.label["AgendaItem"], 15)
        self.assertGreater(self.label["Speech"], 250)

    def test_didascalie_non_perse(self):
        tipi = Counter(n["kind"] for n in self.r["nodi"] if n["label"] == "Reaction")
        self.assertGreater(tipi["applause"], 100)
        self.assertGreater(tipi["protests"], 5)

    def test_scontro_ricciardi(self):
        uri = "it:camera:19:sed0722:tit00050.int00020"
        rr = [n for n in self.r["nodi"] if n["label"] == "Reaction" and n["uri"].startswith(uri)]
        self.assertEqual([n["kind"] for n in rr], ["ironic_applause", "applause", "protests"])
        da = {a["to_ref"] for a in self.r["archi"] if a["type"] == "FROM" and a["from"].startswith(uri)}
        self.assertIn("Fratelli d'Italia", da)
        testo = next(t["text"] for t in self.r["testi"] if t["ref"] == f"speech:{uri}")
        self.assertNotIn("Applausi", testo)  # il testo canonico è solo parlato
        self.assertTrue(testo.startswith("Grazie, Presidente."))  # niente «(M5S).» in testa

    def test_reazioni_multiple(self):
        r = reazioni("(Applausi dei deputati del gruppo MoVimento 5 Stelle - Proteste di deputati del gruppo Fratelli d'Italia)")
        self.assertEqual([(x["kind"], x["from"]) for x in r], [("applause", "MoVimento 5 Stelle"), ("protests", "Fratelli d'Italia")])

    def test_note_procedurali(self):
        self.assertEqual(reazioni("(Segue la votazione)")[0]["kind"], "procedure")

    def test_chi_reagisce(self):
        parti = lambda t: [x["parts"] for x in reazioni(t)]
        self.assertEqual(parti("(Applausi dei deputati del gruppo Alleanza Verdi e Sinistra e di deputati del gruppo Partito Democratico-Italia Democratica e Progressista)"),
                         [[{"kind": "group", "name": "Alleanza Verdi e Sinistra"}, {"kind": "group", "name": "Partito Democratico-Italia Democratica e Progressista"}]])
        # l'elenco resta intero: lo divide il caricamento con i nomi dei gruppi
        self.assertEqual(parti("(Applausi dei deputati dei gruppi Fratelli d'Italia, Lega-Salvini Premier e Forza Italia-Berlusconi Presidente-PPE)"),
                         [[{"kind": "group", "name": "Fratelli d'Italia, Lega-Salvini Premier e Forza Italia-Berlusconi Presidente-PPE"}]])
        self.assertEqual(parti("(Proteste dei deputati Fornaro e Casu)"), [[{"kind": "person", "name": "Fornaro"}, {"kind": "person", "name": "Casu"}]])
        self.assertEqual(parti("(Commenti del Ministro Bernini)"), [[{"kind": "office", "name": "Ministro Bernini"}]])
        self.assertEqual(parti("(Il deputato Gribaudo mostra un libro)"), [[{"kind": "person", "name": "Gribaudo"}]])
        self.assertEqual(parti("(Applausi dei deputati Partito Democratico-Italia Democratica e Progressista e Alleanza Verdi e Sinistra)"),
                         [[{"kind": "group", "name": "Partito Democratico-Italia Democratica e Progressista e Alleanza Verdi e Sinistra"}]])
        self.assertEqual(parti("(I deputati del gruppo MoVimento 5 Stelle si levano in piedi)"), [[{"kind": "group", "name": "MoVimento 5 Stelle"}]])
        self.assertEqual(parti("(Commenti di deputati del Partito Democratico-Italia Democratica e Progressista)"),
                         [[{"kind": "group", "name": "Partito Democratico-Italia Democratica e Progressista"}]])

    def test_reazioni_senato(self):
        r = reazioni("(Applausi. I senatori del Gruppo M5S si levano in piedi)")
        self.assertEqual([(x["kind"], x["parts"]) for x in r], [("applause", []), ("action", [{"kind": "group", "name": "M5S"}])])
        self.assertEqual(reazioni("(Commenti della senatrice Paita)")[0]["parts"], [{"kind": "person", "name": "Paita"}])
        self.assertEqual([x["kind"] for x in reazioni("(Applausi. Commenti)")], ["applause", "comments"])
        self.assertEqual([x["kind"] for x in reazioni("(v. Allegato B)")], ["procedure"])


# la sigla di Noi Moderati ha una parentesi dentro (seduta 111, 30/5/2023; seduta 4, 25/10/2022)
NM = """<seduta legislatura="19" numero="111" anno="2023" mese="05" giorno="30" ramo="camera"><dibattito id="tit00060"><titolo>Commemorazione</titolo>
<intervento id="tit00060.int00160"><testoXHTML><nominativo id="300447" cognomeNome="LUPI Maurizio">MAURIZIO LUPI</nominativo> (NM(N-C-U-I)-M). Grazie, signor Presidente. Facciamo bene, qui in Parlamento, a ricordare.</testoXHTML></intervento>
<intervento id="tit00060.int00170"><testoXHTML><nominativo id="308797" cognomeNome="SEMENZATO Martina">MARTINA SEMENZATO</nominativo> (NM(N-C-U-I)M-CP). Grazie, Presidente.</testoXHTML></intervento>
<intervento id="tit00060.int00180"><testoXHTML><nominativo id="301439" cognomeNome="CESA Lorenzo">LORENZO CESA</nominativo> (M-NM(N-C-U-I)-M). Signor Presidente, signora Presidente del Consiglio.</testoXHTML></intervento>
</dibattito></seduta>""".encode()


class TestSiglaAnnidata(unittest.TestCase):
    def test_noi_moderati(self):
        r = trasforma(NM, {"chiave": "leg19-sed0111"})
        testi = {t["ref"]: t["text"] for t in r["testi"]}
        by = {a["from"]: a["as_group"] for a in r["archi"] if a["type"] == "BY"}
        sp = [(n["declared_group"], by[n["uri"]], testi[n["text_ref"]][:14]) for n in r["nodi"] if n["label"] == "Speech"]
        self.assertEqual(sp, [("NM(N-C-U-I)-M", "NM(N-C-U-I)-M", "Grazie, signor"), ("NM(N-C-U-I)M-CP", "NM(N-C-U-I)M-CP", "Grazie, Presid"),
                              ("M-NM(N-C-U-I)-M", "M-NM(N-C-U-I)-M", "Signor Preside")])


if __name__ == "__main__":
    unittest.main()
