"""Il resoconto sommario di una commissione del Senato diventa una seduta di commissione come il Bollettino della Camera
(7ª Commissione, seduta 344 del 14/10/2026)."""

import unittest
from pathlib import Path

from pipeline.carica.postgres import script_commissione
from pipeline.controlli.uscite import _regole
from pipeline.trasforma.senato_sommario import _gruppo, trasforma

CORPO = (Path(__file__).parent / "fixtures" / "senato_sommario_7a_0344.akn.xml").read_bytes()


class TestSenatoSommario(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-senato-som-7acommissionepermanente-sed0344"})
        self.righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **x} for x in self.r["nodi"]] + \
                     [{"tipo": "arco", **x} for x in self.r["archi"]] + [{"tipo": "testo", **x} for x in self.r["testi"]]

    def test_seduta_e_punti(self):
        s = self.r["nodi"][0]
        self.assertEqual((s["uri"], s["date"], s["body_name"]), ("it:senato:19:som:7acommissionepermanente:sed0344", "2026-10-14", "7ª Commissione permanente"))
        punti = [n for n in self.r["nodi"] if n["label"] == "AgendaItem" and n["acts"]]
        self.assertEqual((punti[0]["stage"], punti[0]["acts"]), ("IN SEDE REFERENTE", ["ddl:2035"]))

    def test_interventi(self):
        by = {a["from"]: a["to"] for a in self.r["archi"] if a["type"] == "BY"}
        sp = [n for n in self.r["nodi"] if n["label"] == "Speech"]
        self.assertTrue(all(n["kind"] == "summary" for n in sp))
        pirondini = next(n for n in sp if n["declared_group"] == "M5S")
        self.assertEqual(by[pirondini["uri"]], "it:person:senato:36417")

    def test_gruppo_con_parentesi_dentro(self):
        # 10ª Commissione, sedute 280 e 40; 3ª Commissione, seduta 76
        self.assertEqual(_gruppo("Il senatore GUIDI ( Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP ) considera apprezzabili le puntualizzazioni"),
                         "Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP")
        self.assertEqual(_gruppo("Interviene brevemente il senatore GUIDI ( Cd'I-NM (UDC-CI-NcI-IaC)-MAIE ), il quale sostiene"),
                         "Cd'I-NM (UDC-CI-NcI-IaC)-MAIE")
        self.assertEqual(_gruppo("Il senatore SPAGNOLLI ( Aut (SVP-PATT, Cb) ), relatore, dà conto del disegno di legge, d'iniziativa governativa"), "Aut (SVP-PATT, Cb)")
        self.assertEqual(_gruppo("La senatrice CAMUSSO (PD-IDP) rileva preliminarmente"), "PD-IDP")

    def test_niente_gruppo_se_non_è_una_sigla(self):
        for t in ("Il presidente ZAFFINI avverte che la documentazione acquisita nell'ambito dell'esame dell'atto comunitario n. COM(2025) 102 definitivo",
                  "la proposta di nomina del professor Blangiardo a Presidente dell'ISTAT (Atto n. 4), dal momento che",
                  "il disegno di legge delega per la determinazione dei LEP (A.S. 1623 ), elaborato in ottemperanza",
                  "il Comitato per la determinazione dei LEP (CLEP), che quindi svolge un ruolo consultivo",
                  "grazie all'installazione di pannelli fotovoltaici, secondo i canoni nZEB ( Nearly Zero Energy Building ). Inoltre",
                  "Il PRESIDENTE ricorda che il capo IV (articoli da 12 a 17) del disegno di legge n. 1484"):
            self.assertIsNone(_gruppo(t), t)

    def test_controlli_e_carico(self):
        self.assertEqual(_regole(self.righe), [])
        self.assertIn("it:senato:19:comm:7acommissionepermanente", script_commissione(self.righe))


if __name__ == "__main__":
    unittest.main()
