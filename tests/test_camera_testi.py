"""Il testo stampato di un progetto di legge diventa testo, articoli e norme citate (C. 3148, ottobre 2026)."""

import unittest
from pathlib import Path

from pipeline.carica.postgres import script_testo_atto
from pipeline.trasforma.camera_testi import trasforma

CORPO = (Path(__file__).parent / "fixtures" / "testo_ac3148.htm").read_bytes()


class TestTesti(unittest.TestCase):
    def test_testo(self):
        r = trasforma(CORPO, {"chiave": "leg19-testo-leg.19.pdl.camera.3148.19PDL0218420"})
        n = r["nodi"][0]
        self.assertTrue(r["testi"][0]["text"].startswith("DISEGNO DI LEGGE"))
        self.assertEqual(n["articles"][0]["number"], "1")
        self.assertIn({"urn": "urn:nir:stato:decreto.legge:2026-09-10;157", "label": "decreto-legge 10 settembre 2026, n. 157"}, n["citations"])
        righe = [{"tipo": "ambito", **r["ambito"]}, {"tipo": "nodo", **n}, {"tipo": "testo", **r["testi"][0]}]
        self.assertIn("DELETE FROM act_text WHERE code = 'leg.19.pdl.camera.3148.19PDL0218420';", script_testo_atto(righe))

    def test_testo_a_fronte(self):
        """Stampato «A» (C. 2822-A): gli articoli sono quelli della commissione, a destra; «Identico» vale il testo a sinistra."""
        riga = lambda sx, dx: f'<tr><td valign="top" width="50%">{sx}</td><td valign="top" width="50%">{dx}</td></tr>'
        corpo = ("<html><body><table>" + riga("<p>Testo del proponente</p>", "<p>Testo della commissione</p>")
                 + riga('<p class="articolo" title="art.1">Art. 1.</p>', '<p class="articolo" title="art.1">Art. 1.</p>')
                 + riga("<p>1. Comma presentato.</p>", "<p>1. Comma riscritto.</p>")
                 + riga("<p>2. Comma rimasto.</p>", "<p>2. Identico.</p>")
                 + riga('<p class="articolo" title="art.2">Art. 2.</p>', '<p class="articolo" title="art.2">Art. 2.</p>')
                 + riga("<p>1. Ultimo.</p>", "<p>Identico.</p>") + "</table></body></html>").encode()
        arts = trasforma(corpo, {"chiave": "leg19-testo-leg.19.pdl.camera.2822_A.19PDL0199150"})["nodi"][0]["articles"]
        self.assertEqual([a["number"] for a in arts], ["1", "2"])
        self.assertIn("Comma riscritto", arts[0]["text"])
        self.assertIn("Comma rimasto", arts[0]["text"])
        self.assertNotIn("Identico", arts[0]["text"] + arts[1]["text"])

    def test_senza_articoli(self):
        """Stampato con solo frontespizio e pareri (C. 2935-A, relazione orale): testo senza menu né piè di pagina."""
        corpo = (Path(__file__).parent / "fixtures" / "camera_testo_2935A_senza_articoli.htm").read_bytes()
        r = trasforma(corpo, {"chiave": "leg19-testo-leg.19.pdl.camera.2935_A.19PDL0196510"})
        t = r["testi"][0]["text"]
        self.assertTrue(t.startswith("FRONTESPIZIO"))
        self.assertIn("N. 2935-A", t)
        self.assertNotIn("Cookie", t)
        self.assertEqual(r["nodi"][0]["articles"], [])


if __name__ == "__main__":
    unittest.main()
