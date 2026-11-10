"""Gli stenografici delle commissioni del Senato: dall'elenco dell'anno alla scheda, e dalla scheda con il PDF a un
documento da cercare (pagina della 1ª Commissione, 2026)."""

import json
import unittest
from pathlib import Path
from unittest import mock

from pipeline.carica.postgres import script_documento
from pipeline.controlli.uscite import errori_file
from pipeline.fonti.senato_stenografici_commissioni import elenco
from pipeline.trasforma import senato_stenografico_commissione as t

PAGINA = (Path(__file__).parent / "fixtures" / "senato_stenografici_01_2026.htm").read_bytes()


class TestElenco(unittest.TestCase):
    def setUp(self):
        self.voci = {v["id"]: v for v in elenco(PAGINA, 1)}

    def test_seduta_congiunta_in_bozza(self):
        v = self.voci["450147"]
        self.assertEqual((v["data"], v["seduta"], v["turno"], v["numero"], v["bozza"]), ("2026-07-13", "6", "pomeridiana", "Stenografico n. 6", True))
        self.assertEqual(v["organo"], "1ª (Aff. costituzionali) Senato con I (Aff. costituzionali) Camera")
        self.assertEqual(v["sede"], "Procedure informative - Comunicazioni del Governo")
        self.assertEqual(v["url"], "https://www.senato.it/service/PDF/PDFServer/DF/450147.pdf")

    def test_sede_redigente(self):
        v = self.voci["449064"]
        self.assertEqual((v["sede"], v["seduta"], v["bozza"]), ("Sede redigente", "489", False))
        self.assertIn("Disegni di legge nn. 1780, 68, 125, 368 e 608", v["argomento"])


class TestDocumento(unittest.TestCase):
    def setUp(self):
        self.scheda = json.dumps(next(v for v in elenco(PAGINA, 1) if v["id"] == "449064")).encode()

    def trasforma(self, testo="Senato della Repubblica\nIl seguito della discussione è rin-\nviato ad altra seduta."):
        with mock.patch.object(t, "_testo_pdf", return_value=testo):
            return t.trasforma(self.scheda, b"%PDF-finto", {"chiave": "leg19-senato-stc-449064"})

    def test_documento_con_testo(self):
        r = self.trasforma()
        n, = r["nodi"]
        self.assertEqual((n["uri"], n["kind"], n["date"], n["body"], n["third_party"], n["format"]),
                         ("it:senato:19:stc:449064", "verbatim_record", "2026-06-23", "it:senato:19:body:0-1", False, "pdf"))
        self.assertEqual(n["title"], "1ª Affari Costituzionali · Stenografico n. 110 · Sede redigente")
        self.assertEqual(n["acts"], ["ddl:1780", "ddl:68", "ddl:125", "ddl:368", "ddl:608"])
        self.assertEqual(n["code"], "seduta n. 489 (pomeridiana)")
        self.assertIn("è rinviato ad altra seduta", r["testi"][0]["text"])           # la sillabazione di fine riga si ricompone
        righe = [{"tipo": "ambito", **r["ambito"]}, {"tipo": "nodo", **n}, *({"tipo": "testo", **x} for x in r["testi"])]
        self.assertEqual(errori_file(righe), [])
        s = script_documento(righe)
        self.assertIn("DELETE FROM document WHERE uri = 'it:senato:19:stc:449064';", s)
        self.assertIn("it:senato:19:body:0-1,2026-06-23", s)                          # organo e data della seduta

    def test_senza_pdf_entra_la_scheda(self):
        r = t.trasforma(self.scheda, None, {"chiave": "leg19-senato-stc-449064"})
        self.assertEqual(r["testi"], [])
        self.assertIsNone(r["nodi"][0]["text_ref"])

    def test_atti(self):
        self.assertEqual(t.atti("Disegno di legge n. 2085\n(Discussione)"), ["ddl:2085"])
        self.assertEqual(t.atti("Schema di decreto (Atto del Governo n. 450)"), ["ag:450"])
        self.assertEqual(t.atti("Audizione del ministro"), [])


if __name__ == "__main__":
    unittest.main()
