"""I voti OSR di una seduta del Senato diventano votazioni e voti dei singoli, e i conti tornano (seduta 469, 28/10/2026)."""

import unittest
from collections import Counter
from pathlib import Path

from pipeline.carica.postgres import script_voti
from pipeline.controlli.uscite import _regole_voti, avvisi_voti
from pipeline.trasforma.senato_voti import _tipo, trasforma

CORPO = (Path(__file__).parent / "fixtures" / "senato_voti_sed0469.json.gz").read_bytes()


class TestSenatoVoti(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-senato-voti-sed0469"})

    def test_votazioni(self):
        self.assertEqual(len(self.r["nodi"]), 6)
        self.assertTrue(all(n["uri"].startswith("it:senato:19:sed0469:v") for n in self.r["nodi"]))
        self.assertEqual(_regole_voti(self.r["nodi"], self.r["archi"]), [])
        self.assertEqual(avvisi_voti(self.r["nodi"], self.r["archi"]), [])

    def test_voti(self):
        esiti = Counter(a["result"] for a in self.r["archi"])
        self.assertTrue({"favor", "against"} <= set(esiti))
        self.assertTrue(all(a["from"].startswith("it:person:senato:") for a in self.r["archi"]))

    def test_caricamento_e_tipi(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]]
        s = script_voti(righe)
        self.assertIn("source = 'osr'", s)
        self.assertIn("group_at(b.person, x.date)", s)  # il gruppo del senatore dall'anagrafica alla data
        self.assertEqual((_tipo("Votazione finale"), _tipo("Questione di fiducia"), _tipo("Mozione di sfiducia individuale")),
                         ("final", "confidence", "motion"))


if __name__ == "__main__":
    unittest.main()


class TestRichiesteRaggruppate(unittest.TestCase):
    """Lo scarico raggruppa le votazioni di più sedute: al massimo BLOCCO per richiesta, i tratti restano per seduta."""

    def test_gruppi(self):
        from pipeline.fonti.senato_voti import gruppi
        numeri = [("a", n) for n in range(1, 30)] + [("b", n) for n in range(1, 30)]
        g = gruppi(numeri, 45)
        self.assertEqual(g, [[("a", 1, 29), ("b", 1, 16)], [("b", 17, 29)]])
        g = gruppi([(s, 1) for s in "abcdefgh"], 45, 6)
        self.assertEqual([len(x) for x in g], [6, 2])

    def test_url_sotto_il_limite(self):
        from pipeline.fonti import senato_voti as sv
        uri = "http://dati.senato.it/sedutaassemblea/239080"
        self.assertEqual(sv.corto(uri), "sa:239080")
        self.assertEqual(sv.corto("a"), "<a>")
        sedute = " || ".join(f"?seduta = {sv.corto(uri)}" for _ in range(sv.SEDUTE_PER_RICHIESTA))
        self.assertLessEqual(sv.lunghezza_url(sv.VOTAZIONI.replace("{SEDUTE}", sedute)), sv.LIMITE_URL)
        tratti = " UNION ".join(sv.TRATTO.replace("{S}", sv.corto(uri)).replace("{DA}", "1000").replace("{A}", "1044") for _ in range(sv.TRATTI_PER_RICHIESTA))
        self.assertLessEqual(sv.lunghezza_url(sv.VOTI.replace("{TRATTI}", tratti)), sv.LIMITE_URL)

    def test_lotto(self):
        from pipeline.fonti import senato_voti as sv
        chieste = []

        def chiedi(q):
            chieste.append(q)
            if "osr:Votazione" in q:
                return [{"seduta": "a", "votazione": "va1", "numero": "1"}, {"seduta": "b", "votazione": "vb1", "numero": "1"}]
            return [{"v": "vb1", "n": "1", "p": "osr:favorevole", "senatore": "s2"}, {"v": "va1", "n": "1", "p": "osr:contrario", "senatore": "s1"}]
        r = sv._lotto([{"seduta": "a"}, {"seduta": "b"}, {"seduta": "c"}], chiedi)
        self.assertEqual(len(chieste), 2)
        self.assertNotIn("VALUES", chieste[0] + chieste[1])
        self.assertIn("<a>", chieste[1])  # uri non del Senato: resta intero
        self.assertEqual(r["a"][1][0]["senatore"], "s1")
        self.assertEqual(r["b"][0], [{"votazione": "vb1", "numero": "1"}])
        self.assertEqual(r["c"], ([], []))
