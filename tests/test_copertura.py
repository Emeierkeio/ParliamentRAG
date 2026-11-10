"""La copertura del dominio parlamentare (copertura.toml): l'elenco resta allineato alle fonti e la percentuale torna."""

import tomllib
import unittest
from pathlib import Path

from api.copertura import FILE, VALE, calcola, query, stati

RADICE = Path(__file__).parent.parent
ELENCO = tomllib.loads(FILE.read_text(encoding="utf-8"))
VOCI = ELENCO["voce"]


class TestElenco(unittest.TestCase):
    def test_ogni_fonte_della_pipeline_sta_in_una_voce(self):
        # chi aggiunge una fonte a pipeline.toml deve dire qui che cosa copre: così il pannello non resta indietro
        fonti = set(tomllib.loads((RADICE / "pipeline.toml").read_text(encoding="utf-8"))["fonti"])
        dette = {f for v in VOCI for f in v.get("fonti", [])}
        self.assertEqual(fonti - dette, set())

    def test_voci_complete(self):
        nomi = [v["nome"] for v in VOCI]
        self.assertEqual(len(nomi), len(set(nomi)))
        for v in VOCI:
            s = stati(v)
            self.assertTrue(s, v["nome"])
            self.assertFalse("parlamento" in s and len(s) > 1, v["nome"])          # o i due rami o la voce comune
            self.assertTrue(set(s.values()) <= set(VALE) | {"non_c_e"}, v["nome"])
            self.assertIn(v["peso"], (1, 2, 3), v["nome"])
            for ramo, stato in s.items():                                             # chi manca o è parziale dice perché
                if stato in ("manca", "parziale"):
                    self.assertTrue(v.get(f"perche_{ramo}") or v.get("perche"), f"{v['nome']} ({ramo}) senza motivo")
                if stato == "fatto":
                    self.assertTrue(v.get("fonti"), f"{v['nome']} fatto senza fonti")

    def test_query_solo_di_lettura(self):
        for v in VOCI:
            for ramo in stati(v):
                q = query(v, ramo)
                if q:
                    self.assertTrue(q.startswith("SELECT count(*) FROM "), q)
                    self.assertNotIn(";", q)
                    self.assertNotIn("{ramo}", q)


class TestCalcolo(unittest.TestCase):
    def test_percentuale_pesata(self):
        voci = [{"area": "A", "nome": "uno", "peso": 3, "camera": "fatto", "senato": "manca", "perche_senato": "x"},
                {"area": "A", "nome": "due", "peso": 1, "camera": "parziale", "senato": "non_c_e", "perche": "y"},
                {"area": "B", "nome": "tre", "peso": 2, "parlamento": "fatto"}]
        r = calcola(voci, {"uno|camera": 0, "tre|parlamento": 12})
        self.assertEqual(r["percento"], round(100 * (3 + 0.5 + 2) / (3 + 3 + 1 + 2), 1))    # il ramo che non lo pubblica non conta
        self.assertEqual(r["rami"], {"camera": 87.5, "senato": 0.0, "parlamento": 100.0})
        self.assertEqual(r["aree"], {"A": 50.0, "B": 100.0})
        self.assertEqual(r["conti"], {"fatto": 2, "parziale": 1, "manca": 1})
        uno, due, tre = r["voci"]
        self.assertTrue(uno["rami"]["camera"]["vuoto"])                                      # dato per fatto, zero righe
        self.assertEqual(uno["rami"]["senato"]["perche"], "x")
        self.assertIsNone(uno["rami"]["camera"]["perche"])
        self.assertEqual(due["rami"]["camera"]["perche"], "y")
        self.assertFalse(tre["rami"]["parlamento"]["vuoto"])

    def test_elenco_vero(self):
        r = calcola(VOCI)
        self.assertTrue(0 < r["percento"] < 100)
        self.assertEqual(set(r["rami"]), {"camera", "senato", "parlamento"})


if __name__ == "__main__":
    unittest.main()
