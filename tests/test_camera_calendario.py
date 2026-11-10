"""Il calendario dei lavori dell'Assemblea della Camera: dalle righe della tabella alle voci giorno per giorno."""

import datetime as dt
import unittest
from pathlib import Path

from pipeline.carica.postgres import script_calendario
from pipeline.controlli import uscite
from pipeline.fonti.camera_calendario import vigente
from pipeline.trasforma.camera_calendario import date_di, trasforma

GREZZO = (Path(__file__).parent / "fixtures" / "camera_calendario_vigente.htm").read_bytes()


class TestCalendario(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(GREZZO, {"chiave": "leg19-calendario-vigente"})
        self.per_giorno = {}
        for n in self.r["nodi"]:
            self.per_giorno.setdefault(n["date"], []).append(n)

    def test_giorno_con_orario_e_atto(self):
        voci = self.per_giorno["2026-11-11"]
        dl = next(v for v in voci if v["when"] == "Mercoledì 11 novembre (ore 12)")
        self.assertTrue(dl["title"].startswith("Discussione sulle linee generali del disegno di legge n. 3121"))
        self.assertEqual(dl["acts"], ["ac:3121"])
        self.assertEqual(dl["calendar"], "Calendario n. 44")

    def test_riga_senza_colonna_dei_giorni(self):
        comune = self.per_giorno["2026-11-11"][0]
        self.assertIsNone(comune["when"])
        self.assertIn("Parlamento in seduta comune", comune["title"])

    def test_riga_per_piu_giorni(self):
        # «Mercoledì 11 (…) e giovedì 12 novembre (… eventualmente venerdì 13 novembre)»: la voce vale per i tre giorni
        for giorno in ("2026-11-11", "2026-11-12", "2026-11-13"):
            self.assertTrue(any("n. 3121" in v["title"] and v["title"].startswith("Seguito") for v in self.per_giorno[giorno]), giorno)

    def test_ordine_e_uri(self):
        for giorno, voci in self.per_giorno.items():
            self.assertEqual([v["order"] for v in voci], list(range(1, len(voci) + 1)))
            self.assertTrue(all(v["uri"].startswith(f"it:camera:19:calendario:{giorno.replace('-', '')}:") for v in voci))

    def test_date(self):
        self.assertEqual(date_di("Lunedì 30 novembre e martedì 1° dicembre (ore 10)", 2026, 11), [dt.date(2026, 11, 30), dt.date(2026, 12, 1)])
        self.assertEqual(date_di("Giovedì 7 gennaio", 2026, 12), [dt.date(2027, 1, 7)])        # il calendario di dicembre arriva a gennaio
        self.assertEqual(date_di("Mozioni in materia di lavoro", 2026, 11), [])

    def test_controlli_e_script(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]]
        self.assertEqual(uscite._regole(righe), [])
        script = script_calendario(righe)
        self.assertIn("DELETE FROM calendar_item WHERE chamber = 'camera' AND source = 'camera_calendario';", script)
        self.assertEqual(script.count("it:camera:19:calendario:"), len(self.r["nodi"]))
        self.assertEqual(script_calendario(righe[:1]), "")                                      # niente voci: non si cancella quello di prima

    def test_calendario_vigente_nella_pagina(self):
        pagina = b'<select id="selectedDoc"><option selected="selected" value="lavori.vigente.20261109">Aggiornamento</option><option value="lavori.vigente.20261028">x</option></select>'
        self.assertEqual(vigente(pagina), "lavori.vigente.20261109")
        self.assertIsNone(vigente(b"<html></html>"))


if __name__ == "__main__":
    unittest.main()
