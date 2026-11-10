"""Atti del Governo e nomine sottoposti a parere: dalla pagina della Camera e dagli open data del Senato agli atti
con le assegnazioni, i termini e i pareri (campione vero del 10/11/2026)."""

import json
import unittest
from pathlib import Path

from pipeline.carica.postgres import script_atti_governo
from pipeline.controlli.uscite import _regole_atti_governo
from pipeline.fonti.camera_atti_governo import conta
from pipeline.trasforma.atti_governo import giorno, trasforma_camera, trasforma_senato, uri_atto

QUI = Path(__file__).parent / "fixtures"
PAGINA = (QUI / "camera_atti_governo.htm").read_bytes()
SENATO = json.loads((QUI / "senato_atti_governo.json").read_text(encoding="utf-8"))


class TestCamera(unittest.TestCase):
    def setUp(self):
        self.r = trasforma_camera(PAGINA, {"chiave": "leg19-atti-governo", "impronta": "x"})
        self.nodi = {n["uri"]: n for n in self.r["nodi"]}
        self.archi = self.r["archi"]

    def di(self, uri):
        return [a for a in self.archi if a["from"] == uri]

    def test_tutti_gli_atti_della_pagina(self):
        self.assertEqual(conta(PAGINA), 6)
        self.assertEqual(len(self.nodi), 6)
        self.assertEqual(sum(n["kind"] == "appointment" for n in self.nodi.values()), 2)

    def test_atto_con_termine_e_rilievi(self):
        a = self.nodi["it:camera:19:ag:455"]
        self.assertEqual((a["number"], a["kind"], a["status"], a["date"]), ("455", "government_act", "In corso di esame", "2026-11-03"))
        self.assertFalse(a["title"].endswith("(455)"))                      # il numero ripetuto in coda non resta nel titolo
        primaria, rilievi = self.di(a["uri"])
        self.assertEqual((primaria["to"], primaria["seat"], primaria["date"], primaria["deadline"], primaria["basis"]),
                         ("it:camera:19:body:o19_3504", "opinion", "2026-11-03", "2026-12-13", "ex art.143,co. 4"))
        self.assertEqual((rilievi["to"], rilievi["seat"], rilievi["deadline"]), ("it:camera:19:body:o19_3505", "remarks", "2026-11-23"))

    def test_riunite_parere_e_profili_ue(self):
        a = self.di("it:camera:19:ag:446")
        riunite = next(x for x in a if x["title"].startswith("Commissioni riunite"))
        self.assertEqual(riunite["to"], riunite["title"])                   # le riunite non sono un organo dell'anagrafica
        bilancio = next(x for x in a if x["title"] == "V Bilancio e Tesoro")
        self.assertEqual((bilancio["opinion"], bilancio["opinion_date"]), ("favorevole con condizione", "2026-11-10"))
        # nella pagina la XIV è scritta in due modi: si lega per il numero romano
        ue = next(x for x in a if x["seat"] == "eu_compatibility")
        self.assertEqual(ue["to"], "it:camera:19:body:o19_3514")
        self.assertEqual(self.nodi["it:camera:19:ag:446"]["kind_raw"], "schema di decreto legislativo")
        self.assertEqual(self.nodi["it:camera:19:ag:446"]["status_date"], "2026-11-10")

    def test_stralcio(self):
        self.assertEqual(self.nodi["it:camera:19:ag:137-bis"]["number"], "137-bis")

    def test_nomina(self):
        n = self.nodi["it:camera:19:nomina:89"]                              # nella pagina è «nomina_089»
        self.assertEqual((n["number"], n["kind"], n["description"]), ("89", "appointment", "Ministro per lo Sport e i giovani"))
        a, = self.di(n["uri"])
        self.assertEqual((a["deadline"], a["opinion"], a["opinion_date"]), ("2025-06-26", "favorevole", "2025-07-02"))
        self.assertTrue(a["basis"].startswith("nel caso di cui al quinto periodo"))

    def test_date(self):
        self.assertEqual(giorno("(assegnato il 3 novembre 2026"), "2026-11-03")
        self.assertEqual(giorno(" con termine al 1° luglio 2025"), "2025-07-01")
        self.assertIsNone(giorno("senza data"))
        self.assertEqual(uri_atto("senato", 19, "nomina", "007"), "it:senato:19:nomina:7")

    def test_controlli(self):
        ambito = self.r["ambito"]
        # sei atti sono pochi per la regola dei cinquanta: è l'unico errore
        self.assertEqual(len(_regole_atti_governo(self.r["nodi"], self.archi, ambito)), 1)
        molti = [{**n, "uri": f"{n['uri']}-{i}"} for i in range(10) for n in self.r["nodi"]]
        archi = [{**a, "from": f"{a['from']}-{i}"} for i in range(10) for a in self.archi]
        self.assertEqual(_regole_atti_governo(molti, archi, ambito), [])
        self.assertTrue(_regole_atti_governo(molti, [], ambito))            # alla Camera senza assegnazioni la pagina è cambiata
        self.assertTrue(_regole_atti_governo([{**n, "status": None} for n in molti], archi, ambito))

    def test_script(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}, *({"tipo": "nodo", **n} for n in self.r["nodi"]),
                 *({"tipo": "arco", **a} for a in self.archi)]
        s = script_atti_governo(righe)
        self.assertIn("DELETE FROM act WHERE chamber = 'camera' AND legislature = 19 AND kind IN ('government_act', 'appointment');", s)
        self.assertIn("deadline, basis, opinion, opinion_date", s)
        self.assertIn("it:camera:19:ag:455,it:camera:19:body:o19_3504,opinion,2026-11-03", s)
        self.assertNotIn("kind = 'bill'", s)                                  # non tocca i progetti di legge


class TestSenato(unittest.TestCase):
    def setUp(self):
        self.r = trasforma_senato(SENATO, 19, {"chiave": "leg19-atti-governo", "impronta": "x"})
        self.nodi = {n["uri"]: n for n in self.r["nodi"]}

    def test_atto_e_nomina(self):
        a = self.nodi["it:senato:19:ag:453"]
        self.assertEqual((a["kind"], a["status"], a["date"], a["description"]),
                         ("government_act", "da assegnare", "2026-10-30", "Ministro della difesa (Gov. Meloni-I)"))
        n = self.nodi["it:senato:19:nomina:148"]
        self.assertEqual(n["kind"], "appointment")
        self.assertIn("CONSOB", n["title"])
        self.assertEqual(a["card_url"], "https://www.senato.it/leg/19/BGT/Schede/docnonleg/55029.htm")
        self.assertEqual(self.r["ambito"]["chamber"], "senato")
        self.assertEqual(self.r["archi"], [])

    def test_un_record_per_numero(self):
        doppio = {"atti": SENATO["atti"] + [{**SENATO["atti"][0], "url": "http://www.senato.it/service/PDF/PDFServer/BGT/1.pdf"}], "nomine": []}
        nodi = trasforma_senato(doppio, 19)["nodi"]
        self.assertEqual(len(nodi), len({x["numero"] for x in SENATO["atti"]}))
        self.assertIn("http://www.senato.it/service/PDF/PDFServer/BGT/1.pdf", [u for n in nodi for u in n["text_urls"]])


if __name__ == "__main__":
    unittest.main()
