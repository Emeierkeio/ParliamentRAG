"""Ricerca degli atti come la fa chi lavora in Parlamento (api/strumenti/atti.py): numeri scritti «AC 1695» o «A.S. 1353»,
titoli senza codice HTML, l'oggetto delle interrogazioni negli elenchi. Le prove sul database si saltano se Postgres non
risponde."""

import re
import unittest

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""

from api.strumenti import atti, ricerca


class TestNumeri(unittest.TestCase):
    def test_numero_con_il_ramo(self):
        self.assertEqual(atti.numero_e_ramo("AC 1695"), ("1695", "camera"))
        self.assertEqual(atti.numero_e_ramo("A.C. 1695"), ("1695", "camera"))
        self.assertEqual(atti.numero_e_ramo("C. 1917-B"), ("1917-B", "camera"))
        self.assertEqual(atti.numero_e_ramo("C.2750"), ("2750", "camera"))
        self.assertEqual(atti.numero_e_ramo("S. 1353"), ("1353", "senato"))
        self.assertEqual(atti.numero_e_ramo("A.S. 1689/I"), ("1689/I", "senato"))
        self.assertEqual(atti.numero_e_ramo("AS 935"), ("935", "senato"))
        self.assertEqual(atti.numero_e_ramo("ddl S. 1353"), ("1353", "senato"))
        self.assertEqual(atti.numero_e_ramo("DDL 1353"), ("1353", None))
        self.assertEqual(atti.numero_e_ramo("pdl n. 1695"), ("1695", None))

    def test_numero_senza_prefisso_resta_com_e(self):
        self.assertEqual(atti.numero_e_ramo("1695"), ("1695", None))
        self.assertEqual(atti.numero_e_ramo("4-09302"), ("4-09302", None))
        self.assertEqual(atti.numero_e_ramo("5/04321"), ("5/04321", None))
        self.assertEqual(atti.numero_e_ramo("3174-bis"), ("3174-bis", None))


class TestTitoli(unittest.TestCase):
    def test_titolo_senza_html(self):
        t = 'S. 1689. - "Bilancio di previsione" <em>(approvato dal Senato)</em> (2750)'
        self.assertEqual(atti.ActBrief(uri="x", chamber="camera", legislature=19, number="2750", kind="bill", title=t).title,
                         'S. 1689. - "Bilancio di previsione" (approvato dal Senato) (2750)')

    def test_oggetto_di_un_interrogazione(self):
        testo = ("Atto Camera Interrogazione a risposta scritta 4-09302 presentato da SOTTANELLI Giulio Cesare testo di Lunedì "
                 "12 ottobre 2026, seduta n. 725 SOTTANELLI . — Al Ministro del lavoro e delle politiche sociali . — Per sapere – "
                 "premesso che: l'INPS ha diffuso una circolare")
        o = atti.oggetto(testo)
        self.assertTrue(o.startswith("Al Ministro del lavoro e delle politiche sociali"))
        self.assertIn("l'INPS ha diffuso una circolare", o)
        senato = ("Atto Senato Interrogazione a risposta scritta 4-03566 presentata da ELENA MURELLI giovedì 19 novembre 2026, "
                  "seduta n.478 MURELLI - Al Ministro della salute - Premesso che: l'articolo 1 della legge")
        self.assertTrue(atti.oggetto(senato).startswith("Al Ministro della salute"))
        mozione = ("Atto Camera Mozione 1-00614 presentato da BAKKALI Ouidad testo di Venerdì 30 ottobre 2026, seduta n. 736 "
                   "La Camera, premesso che: la legge 9 luglio 1990, n. 185")
        self.assertTrue(atti.oggetto(mozione).startswith("La Camera, premesso che: la legge 9 luglio 1990"))
        self.assertIsNone(atti.oggetto(None))


class TestFrasi(unittest.TestCase):
    def test_piu_parole_sono_una_frase(self):
        self.assertEqual(ricerca.parole_esatte("separazione delle carriere"), ('"separazione delle carriere"', None))

    def test_una_parola_intera(self):
        # «premierato» e «premier» hanno la stessa radice: la parola deve esserci (premierato, premierati)
        self.assertEqual(ricerca.parole_esatte("premierato"), ("premierato", r"\mpremierat"))
        self.assertEqual(ricerca.parole_esatte("INPS"), ("INPS", None))           # parola corta: basta la radice

    def test_la_sintassi_esplicita_resta(self):
        for q in ('"frase esatta"', "salario -minimo", "pensioni or previdenza", "(caro affitti)"):
            self.assertEqual(ricerca.parole_esatte(q), (q, None))


@unittest.skipIf(C is None, f"Postgres locale non raggiungibile: {MOTIVO}")
class TestSulDatabase(unittest.TestCase):
    def _testi(self, colpi):
        return [C.execute("SELECT text FROM speech WHERE uri = %s", (h.uri,)).fetchone()["text"].lower() for h in colpi]

    def test_interventi_con_la_frase(self):
        colpi = ricerca.cerca_interventi(C, "separazione delle carriere", chamber="senato", limit=20, frase=True)
        self.assertTrue(colpi)
        # la frase con le forme flesse («separare le carriere» va bene), mai le parole sparse né «carro»
        self.assertTrue(all(re.search(r"separ\w*\s+(?:\w+\s+)?carrier", t) for t in self._testi(colpi)))
        colpi = ricerca.cerca_interventi(C, "premierato", limit=20, frase=True)
        self.assertTrue(colpi)
        self.assertTrue(all("premierat" in t for t in self._testi(colpi)))
        # il totale con le stesse regole
        self.assertLess(ricerca.totale_interventi(C, "premierato", frase=True), ricerca.totale_interventi(C, "premierato"))

    def test_numero_scritto_come_in_aula(self):
        n, xs = atti.cerca_atti(C, number="AC 1695")
        self.assertEqual([(x.chamber, x.number) for x in xs], [("camera", "1695")])
        n, xs = atti.cerca_atti(C, number="S. 1353")
        self.assertEqual([(x.chamber, x.number) for x in xs], [("senato", "1353")])

    def test_elenco_con_l_oggetto(self):
        n, xs = atti.cerca_atti(C, q="INPS", chamber="camera", signer="it:person:camera:306064", kind="written_question")
        x = next(x for x in xs if x.uri == "it:camera:19:aic:4-02224")
        self.assertIn("Al Ministro del lavoro", x.subject)
        self.assertIn("inps", x.excerpt.lower())         # con q, il passaggio dove compare la parola («Inps» nel testo)

    def test_progetti_di_legge_senza_oggetto(self):
        n, xs = atti.cerca_atti(C, number="1695", chamber="camera")
        self.assertIsNone(xs[0].subject)                 # il titolo di un pdl dice già l'argomento


if __name__ == "__main__":
    unittest.main()
