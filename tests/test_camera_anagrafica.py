"""L'anagrafica OCD della Camera diventa persone e relazioni datate (campione vero del 30/10/2026: Fontana, Bignami, Magi)."""

import json
import unittest
from collections import Counter
from pathlib import Path

from pipeline.carica.postgres import righe_anagrafica, script_anagrafica
from pipeline.controlli.uscite import _regole_anagrafica
from pipeline.trasforma.camera_anagrafica import data, id_persona, leggibile, senza_parentesi, trasforma

GREZZI = json.loads((Path(__file__).parent / "fixtures" / "camera_ocd_leg19_campione.json").read_text(encoding="utf-8"))


def in_corso(a, giorno="2026-10-30"):
    return a["start"] <= giorno and (not a.get("end") or a["end"] >= giorno)


class TestAnagrafica(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(GREZZI, 19)
        self.nodi = {n["uri"]: n for n in self.r["nodi"]}
        self.chi = {n["family_name"]: n["uri"] for n in self.r["nodi"] if n["label"] == "Person"}

    def test_persone(self):
        f = self.nodi[self.chi["Fontana"]]
        self.assertEqual((f["given_name"], f["gender"]), ("Lorenzo", "M"))
        self.assertRegex(f["birth_date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_presidente_della_camera(self):
        cariche = [a for a in self.r["archi"] if a["type"] == "OFFICE" and a["from"] == self.chi["Fontana"] and in_corso(a)]
        self.assertTrue(any(a["title"] == "chair" and self.nodi[a["to"]]["name"] == "Ufficio di Presidenza" for a in cariche))

    def test_capogruppo(self):
        cariche = [a for a in self.r["archi"] if a["type"] == "OFFICE" and a["from"] == self.chi["Bignami"] and in_corso(a)]
        self.assertTrue(any(a["title"] == "leader" and self.nodi[a["to"]]["short_name"] == "FDI" for a in cariche))

    def test_misto_per_componente(self):
        oggi = [self.nodi[a["to"]] for a in self.r["archi"] if a["type"] == "MEMBER_OF" and a["from"] == self.chi["Magi"] and in_corso(a)]
        self.assertEqual(Counter(g["kind"] for g in oggi), {"group": 1, "misto_component": 1})
        comp = next(g for g in oggi if g["kind"] == "misto_component")
        self.assertTrue(comp["name"].startswith("+Europa"))
        parte = {a["from"]: a["to"] for a in self.r["archi"] if a["type"] == "PART_OF"}
        self.assertEqual(self.nodi[parte[comp["uri"]]]["name"], "Misto")

    def test_controlli_passano(self):
        archi = self.r["archi"]
        errori = _regole_anagrafica(self.r["nodi"], archi, {"chamber": "campione"})
        self.assertEqual([e for e in errori if "seggi" not in e], [])

    def test_caricamento(self):
        righe = [{"tipo": "ambito", "chamber": "camera", "legislature": 19, "kind": "anagrafica"}]
        righe += [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]]
        t = righe_anagrafica(righe)
        self.assertEqual(len(t["person"]), 3)
        self.assertEqual(len(t["mandate"]), 3)
        s = script_anagrafica(righe)
        self.assertTrue(s.startswith("BEGIN;") and s.rstrip().endswith("COMMIT;"))
        self.assertIn("DELETE FROM grp WHERE chamber = 'camera' AND legislature = 19;", s)

    def test_funzioni(self):
        self.assertEqual(data("20221013"), "2022-10-13")
        self.assertIsNone(data(""))
        self.assertEqual(id_persona("http://dati.camera.it/ocd/deputato.rdf/d308421_19"), "it:person:camera:308421")
        self.assertEqual(senza_parentesi("ALLEANZA VERDI E SINISTRA (AVS) (27.10.2022"), "ALLEANZA VERDI E SINISTRA")
        self.assertEqual(leggibile("+EUROPA - STATI UNITI D'EUROPA"), "+Europa - Stati Uniti d'Europa")


if __name__ == "__main__":
    unittest.main()
