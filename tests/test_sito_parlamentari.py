"""Schede di deputati e senatori per il sito, sul Postgres locale (utente `lettura`). Si saltano se il database non
risponde. La parte senza database (sigle, estratti, rotte) gira sempre."""

import unittest

from api import sito_parlamentari as S

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""

CHIAVI = {"id", "name", "firstName", "lastName", "photo", "group", "mistoComponent", "groupHistory", "mistoComponents",
          "committees", "governmentOffices", "institutionalRole", "profession", "education", "mandateStart", "cameraUrl",
          "counts", "votes", "recentSpeeches", "dataAsOf"}


class TestFormato(unittest.TestCase):
    def test_sigle(self):
        self.assertEqual(S.sigla("Lega - Salvini Premier"), "Lega")
        self.assertEqual(S.sigla("MoVimento 5 Stelle"), "M5S")
        self.assertEqual(S.sigla("Civici d'Italia-UDC-Noi Moderati (Noi con l'Italia, Coraggio Italia, Italia al Centro)-MAIE-Centro Popolare"), "Civici")
        self.assertEqual(S.sigla("Misto"), "Misto")

    def test_commissione_permanente_con_competenza(self):
        self.assertEqual(S.nome_organo("V Commissione", "camera"), "V Commissione (Bilancio, Tesoro e Programmazione)")
        self.assertEqual(S.nome_organo("V Commissione", "senato"), "V Commissione")

    def test_estratto_senza_saluti(self):
        t = "Grazie, Presidente. " + "parola " * 80
        e = S.estratto(t)
        self.assertTrue(e.startswith("Parola"))
        self.assertTrue(e.endswith("…"))
        self.assertLessEqual(len(e), S.ESTRATTO)

    def test_titolo_senza_orari(self):
        self.assertEqual(S.titolo_pulito("Seguito della discussione (A.C. 2124-A) (ore 13,31). (ore 13,31)"),
                         "Seguito della discussione (A.C. 2124-A)")

    def test_voti_senato_assenti_dalle_votazioni_tenute(self):
        v = S.voti_senato({"favor": 60, "against": 20, "abstain": 0, "absent": 0, "total": 80}, 100)
        self.assertEqual((v["total"], v["absent"], v["participationPct"]), (100, 20, 80.0))

    def test_rotte(self):
        percorsi = {r.path for r in S.router.routes}
        for p in ("/dati/schede/indice.json", "/dati/schede/{pid}.json", "/dati/senatori.json", "/dati/senatori/{did}.json",
                  "/dati/senato/seats.json", "/dati/foto/senatori/{did}.jpg", "/dati/anagrafica/{pid}.json", "/dati/aic"):
            self.assertIn(p, percorsi)


@unittest.skipIf(C is None, f"Postgres non raggiungibile: {MOTIVO}")
class TestSchede(unittest.TestCase):
    def test_deputato_nel_misto_per_componente(self):
        d = S.scheda(C, "camera", "307143")                # Ziello: dalla Lega al Misto, componente Futuro Nazionale
        self.assertLessEqual(CHIAVI, set(d))
        self.assertEqual(d["group"]["acronym"], "Misto")
        self.assertEqual(d["mistoComponent"]["short"], "FNV")
        self.assertEqual([g["acronym"] for g in d["groupHistory"]], ["Misto", "Lega"])
        self.assertTrue(d["recentSpeeches"] and d["recentSpeeches"][0]["url"].startswith("https://www.camera.it/leg19/410?idSeduta="))
        self.assertGreater(d["votes"]["total"], 0)

    def test_senatore(self):
        d = S.scheda(C, "senato", "28924")
        self.assertEqual(d["group"]["acronym"], "PD")
        self.assertIn("senatoUrl", d)
        self.assertEqual(d["recentSpeeches"], [])
        self.assertGreater(d["votes"]["total"], d["votes"]["absent"])

    def test_scheda_che_non_esiste(self):
        self.assertIsNone(S.scheda(C, "camera", "1"))

    def test_elenco_senatori(self):
        e = S.elenco_senatori(C)
        self.assertGreater(len(e["deputies"]), 190)
        self.assertTrue(all(x["group"] != "?" for x in e["deputies"]))

    def test_anagrafica_e_atto(self):
        a = S.anagrafica(C, "307143")
        self.assertEqual(a["nascita"], "19920411")
        self.assertEqual(a["tipo"], "maggioritario")
        x = S.atto_aic(C, "4/06717")
        self.assertEqual(x["concluso"], "0")
        self.assertTrue(x["testo"] and x["autore"].startswith("GRIMALDI MARCO"))
