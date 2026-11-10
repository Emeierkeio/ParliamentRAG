"""Convocazioni delle commissioni permanenti: dalle pagine della Camera (V Commissione, 10/11/2026) e del Senato
(1ª Commissione, settimana dal 9 al 15 novembre 2026) alle voci con ora, sede, argomenti e atti."""

import datetime as dt
import unittest
from pathlib import Path

from pipeline.carica.postgres import script_convocazioni
from pipeline.controlli.uscite import _regole
from pipeline.fonti.camera_convocazioni import giorni, giorno_mostrato
from pipeline.trasforma.convocazioni import ora, settimana, trasforma_camera, trasforma_senato

QUI = Path(__file__).parent / "fixtures"
CAMERA = (QUI / "camera_convocazioni_3505.htm").read_bytes()
SENATO = (QUI / "senato_convocazioni_01.htm").read_bytes()


def righe(r: dict) -> list[dict]:
    return [{"tipo": "ambito", **r["ambito"]}, *({"tipo": "nodo", **n} for n in r["nodi"])]


class TestCamera(unittest.TestCase):
    def setUp(self):
        self.r = trasforma_camera(CAMERA, {"chiave": "leg19-conv-3505-20261110", "url": "https://www.camera.it/leg19/1099?shadow_organo_parlamentare=3505"})
        self.nodi = self.r["nodi"]

    def test_pagina(self):
        self.assertEqual(giorno_mostrato(CAMERA), dt.date(2026, 11, 10))
        self.assertEqual([g.day for g in giorni(CAMERA)], [3, 4, 9, 10, 11, 12])

    def test_blocchi(self):
        riunite, consultiva, governo = self.nodi                              # l'avviso in fondo non è una convocazione
        self.assertEqual((riunite["start_time"], riunite["seat"], riunite["place"], riunite["date"]),
                         ("08:30", "Commissioni riunite", "Sala del Mappamondo", "2026-11-10"))
        self.assertEqual(riunite["body"], "it:camera:19:body:o19_3505")
        self.assertEqual(riunite["body_name"], "V Commissione (Bilancio, tesoro e programmazione)")
        self.assertIn("Ore 12: CGIL, CISL e UIL", riunite["text"].split("\n"))
        self.assertEqual((consultiva["start_time"], consultiva["acts"]), ("13:40", ["ac:3119"]))
        self.assertEqual((governo["start_time"], governo["when"], governo["seat"], governo["acts"]),
                         (None, "Al termine", "Atti del Governo", ["ag:446", "ag:450"]))
        self.assertEqual(governo["uri"], "it:camera:19:conv:3505:2026-11-10:03")
        self.assertFalse(any(n["cancelled"] for n in self.nodi))

    def test_ora(self):
        self.assertEqual([ora(x) for x in ("Ore 8.30", "ore 14", "12:00", "Al termine", "")], ["08:30", "14:00", "12:00", None, None])

    def test_controlli_e_script(self):
        self.assertEqual(_regole(righe(self.r)), [])
        s = script_convocazioni(righe(self.r))
        self.assertIn("DELETE FROM convocation WHERE source_key = 'leg19-conv-3505-20261110';", s)
        self.assertIn('"{""ag:446"",""ag:450""}"', s)
        # una pagina senza convocazioni toglie quelle di prima e non carica niente
        vuoto = script_convocazioni([{"tipo": "ambito", **self.r["ambito"]}])
        self.assertIn("DELETE FROM convocation WHERE source_key", vuoto)
        self.assertNotIn("COPY", vuoto)


class TestSenato(unittest.TestCase):
    def setUp(self):
        self.r = trasforma_senato(SENATO, {"chiave": "leg19-senato-conv-01"})
        self.nodi = self.r["nodi"]

    def test_settimana(self):
        self.assertEqual(settimana("Settimana dal 9 al 15 novembre 2026"), (dt.date(2026, 11, 9), dt.date(2026, 11, 15)))
        self.assertEqual(settimana("Settimana dal 30 novembre al 6 dicembre 2026"), (dt.date(2026, 11, 30), dt.date(2026, 12, 6)))
        self.assertEqual(settimana("Settimana dal 28 dicembre al 3 gennaio 2027"), (dt.date(2026, 12, 28), dt.date(2027, 1, 3)))
        self.assertEqual(self.r["ambito"]["source_key"], "leg19-senato-conv-01-20261109")     # la settimana resta nella chiave

    def test_sedute_del_giorno(self):
        self.assertEqual(len(self.nodi), 12)
        self.assertEqual(sorted({n["date"] for n in self.nodi}), ["2026-11-10", "2026-11-11", "2026-11-12"])
        prima = self.nodi[0]
        self.assertEqual((prima["start_time"], prima["seat"], prima["number"], prima["place"], prima["acts"]),
                         ("12:00", "Ufficio di Presidenza Integrato", "197", "AULA 1ª COMMISSIONE", ["ddl:550"]))
        self.assertEqual(prima["body"], "it:senato:19:body:0-1")
        self.assertTrue(prima["body_name"].startswith("1ª Commissione (Affari costituzionali"))
        self.assertTrue(all(n["start_time"] for n in self.nodi))

    def test_sede_e_relatori_nel_testo(self):
        plenaria = next(n for n in self.nodi if n["number"] == "552")
        self.assertEqual(plenaria["seat"], "Plenaria; Sede redigente*")
        self.assertIn("ddl 88 (Promozione equilibrio tra i sessi)", plenaria["text"])
        self.assertIn("ddl:88", plenaria["acts"])

    def test_atti_del_governo_e_nomine_dai_link(self):
        from pipeline.trasforma.convocazioni import atti_senato
        cella = ('<a href="http://www.senato.it/leg/19/BGT/Schede/docnonleg/54887.htm">450</a> '
                 '<a href="http://www.senato.it/leg/19/BGT/Schede/docnonleg/54892.htm">Nomina n. 147</a> '
                 '<a href="http://www.senato.it/leg/19/BGT/Schede/docnonleg/54257.htm">COM(2026) 311 definitivo</a> '
                 '<a href="http://www.senato.it/leg/19/BGT/Schede/Ddliter/56628.htm">550</a>')
        self.assertEqual(atti_senato(cella), ["ddl:550", "ag:450", "nomina:147"])

    def test_sconvocata(self):
        sconvocate = [n for n in self.nodi if n["cancelled"]]
        self.assertEqual(len(sconvocate), 2)
        self.assertEqual(_regole(righe(self.r)), [])


if __name__ == "__main__":
    unittest.main()
