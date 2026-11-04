"""Emendamenti del sito: lettura dei testi, ancoraggi, sigle; sul Postgres locale elenco e leggi (si saltano se il
database non risponde)."""

import json
import time
import unittest

from api import sito_emendamenti as S

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""


class TestTesti(unittest.TestCase):
    def test_articolo_della_camera(self):
        a = S.articolo("270-", "Articolo 3.\n\n(Modifiche\n\nall'articolo 94)\n\n1. Al codice:\n\na) la lettera;\n\n"
                               "b) l'altra.\n\n2. Dopo il comma:\n\n«1. Nuovo comma.»")
        self.assertEqual(a["num"], "3")                  # il numero nel testo vince sulla colonna
        self.assertEqual(a["heading"], "Modifiche all'articolo 94")
        self.assertEqual([c["num"] for c in a["commi"]], ["1", "2"])
        self.assertEqual([b["kind"] for b in a["commi"][0]["blocks"]], ["p", "point", "point"])
        self.assertEqual(a["commi"][0]["blocks"][1]["label"], "a)")

    def test_articolo_del_senato(self):
        a = S.articolo(None, "2\n\n(Agricoltore custode)\n\n1\n\nSono riconosciuti:\n\na\n\ndella manutenzione;\n\n2\n\nAltro.")
        self.assertEqual((a["num"], a["heading"]), ("2", "Agricoltore custode"))
        self.assertEqual([c["num"] for c in a["commi"]], ["1", "2"])
        self.assertEqual(a["commi"][0]["blocks"][1], {"kind": "point", "label": "a)", "text": "della manutenzione;", "depth": 0})

    def test_numeri_tra_virgolette_non_sono_commi(self):
        a = S.articolo("1", "Art. 1.\n\n1. Dopo il comma 2 è inserito il seguente:\n\n«2-bis. Testo\n\n3. ancora citato»\n\n2. Vero.")
        self.assertEqual([c["num"] for c in a["commi"]], ["1", "2"])

    def test_decreto(self):
        arts = [{"num": "1", "commi": []}, {"num": "1", "commi": [1]}, {"num": "2", "commi": [1]}]
        self.assertEqual(len(S.articoli_decreto(arts)), 2)

    def test_ancora_ed_esito(self):
        self.assertEqual(S.ancora("Al comma 2, lettera b), sostituire"), ("2", "b"))
        self.assertEqual(S.ancora("Sopprimerlo."), (None, None))
        self.assertEqual(S.esito("Inammissibile"), "inammissibile")
        self.assertEqual(S.esito("irricevibile"), "altro")

    def test_identici_senza_punteggiatura(self):
        self.assertEqual(S.impronta("dal 1° gennaio 2040."), S.impronta("dal 1 gennaio 2040 ."))

    def test_sigle_misto_per_componente(self):
        self.assertEqual(S.sigla("Futuro Nazionale Vannacci - Free"), "FNV")
        self.assertEqual(S.sigla("Civici d'Italia-UDC-Noi Moderati"), "NM")
        self.assertEqual(S.sigla("Misto"), "Misto")

    def test_stato_della_camera(self):
        self.assertEqual(S.stato("camera", "Approvato definitivamente dal Senato. Legge"), "appr. definit. Legge")
        self.assertEqual(S.stato("camera", "In corso di esame in Commissione"), "esame in comm.")

    def test_titolo_breve(self):
        t = "S. 1689. - \"Conversione in legge del decreto-legge 11 aprile 2025, n. 48, recante disposizioni urgenti\" <em>(approvato dal Senato)</em> (2750)"
        self.assertEqual(S.titolo_breve(t), "Disposizioni urgenti (decreto-legge 48/2025)")


@unittest.skipIf(C is None, f"Postgres non raggiungibile: {MOTIVO}")
class TestDati(unittest.TestCase):
    def test_elenco_veloce_e_completo(self):
        S._memo.clear()
        t = time.monotonic()
        xs = json.loads(S.elenco(C).body)
        self.assertLess(time.monotonic() - t, 5)           # a freddo; il servizio lo prepara all'avvio
        self.assertGreater(len(xs), 500)
        per = {x["slug"]: x for x in xs}
        self.assertIn("legge-elettorale", per)
        self.assertEqual(per["54468"]["numbers"], ["C. 2355", "S. 1509"])
        self.assertEqual(per["54468"]["stato"], "appr. definit. Legge")

    def test_letture_legate(self):
        self.assertEqual(json.loads(S.elenco(C).body)[0]["slug"], "54965")   # la legge di bilancio 2026, la più emendata
        L = S.legge(C, "50878")
        self.assertEqual(L["bill"]["numbers"], ["S. 17", "C. 1304", "S. 17-B"])
        self.assertTrue(any(a["vote"] for a in L["amendments"]))            # voti dell'Aula della Camera
        self.assertTrue(all(a["stage"] in {s["id"] for s in L["stages"]} for a in L["amendments"]))

    def test_legge_elettorale(self):
        L = json.loads(S.legge_elettorale(C).body)
        self.assertEqual(L["bill"]["slug"], "legge-elettorale")
        self.assertIn("S. 1971", L["bill"]["numbers"])


if __name__ == "__main__":
    unittest.main()
