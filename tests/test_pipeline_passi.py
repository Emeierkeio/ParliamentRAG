"""Trasformazioni del giro: un grezzo che non si trasforma non ferma gli altri e si riprova al giro dopo; una sola
versione per chiave; registro dei passi coerente."""

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.lago import Lago
from pipeline.orchestra import Contesto, ordina
from pipeline.passi import PASSI, DaRifare, Trasforma

ROTTI: set = set()


def trasforma_finta(corpo: bytes, info: dict) -> dict:
    if info["chiave"] in ROTTI:
        raise ValueError("grezzo illeggibile")
    return {"ambito": {"kind": "prova", "testo": corpo.decode()}, "nodi": [], "archi": [], "testi": []}


class TestTrasforma(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cartella = Path(self.tmp.name)
        self.ctx = Contesto("g", self.cartella, {}, {})
        self.lago = Lago(self.cartella)
        ROTTI.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def uscita(self, k: str) -> dict:
        return json.loads((self.cartella / "uscite" / "v3" / "f" / f"{k}.jsonl").read_text().splitlines()[0])

    def test_un_grezzo_rotto_non_ferma_gli_altri_e_si_riprova(self):
        for k in ("a", "b", "c"):
            self.lago.salva("f", k, k.encode())
        ROTTI.add("b")
        t = Trasforma("f", trasforma_finta)
        r = t(self.ctx)
        self.assertEqual(r["trasformati"], 2)
        self.assertIn("avviso", r)
        self.assertEqual(DaRifare(self.cartella, "f").chiavi, {"b"})
        self.assertTrue((self.cartella / "uscite" / ".f.ultimo").exists())     # il segno va avanti per gli altri
        ROTTI.clear()
        r = t(self.ctx)                                     # al giro dopo: solo il grezzo rimasto indietro
        self.assertEqual(r["trasformati"], 1)
        self.assertNotIn("avviso", r)
        self.assertEqual(self.uscita("b")["testo"], "b")
        self.assertEqual(DaRifare(self.cartella, "f").chiavi, set())

    def test_tutti_rotti_il_passo_fallisce_ma_non_li_perde(self):
        self.lago.salva("f", "a", b"a")
        ROTTI.add("a")
        with self.assertRaises(RuntimeError):
            Trasforma("f", trasforma_finta)(self.ctx)
        self.assertEqual(DaRifare(self.cartella, "f").chiavi, {"a"})

    def test_una_versione_per_chiave_la_piu_recente(self):
        self.lago.salva("f", "a", b"vecchia")
        self.lago.salva("f", "a", b"nuova")
        r = Trasforma("f", trasforma_finta)(self.ctx)
        self.assertEqual(r["trasformati"], 1)
        self.assertEqual(self.uscita("a")["testo"], "nuova")


class TestRegistroPassi(unittest.TestCase):
    def test_ordine_e_dipendenze(self):
        nomi = [p.nome for p in ordina(PASSI)]
        per = {p.nome: p for p in PASSI}
        trasforma = [n for n in nomi if n.startswith("trasforma_")]
        self.assertTrue(all(nomi.index(t) < nomi.index("controlla_uscite") for t in trasforma))
        self.assertEqual(per["controlla_uscite"].dopo, [])               # una trasformazione fallita non ferma i controlli
        self.assertEqual(set(per["controlla_uscite"].dopo_comunque), set(trasforma))
        self.assertEqual(per["carica_postgres"].dopo, ["controlla_uscite"])
        self.assertNotIn("scarica_senato_esiti", per["trasforma_senato_emendamenti"].dopo)
        self.assertEqual(per["scarica_senato_misto"].timeout_minuti, 10)

    def test_siti_e_tempo(self):
        per = {p.nome: p for p in PASSI}
        self.assertTrue(all(p.sito == "camera" for n, p in per.items() if n.startswith("scarica_camera_")))
        self.assertEqual(per["scarica_senato_aic"].sito, "camera")
        self.assertEqual(per["scarica_senato_osr"].sito, "")
        self.assertFalse(per["carica_postgres"].limite_giro)
        self.assertFalse(per["trasforma_camera_voti"].limite_giro)
        self.assertTrue(per["scarica_camera_voti"].limite_giro)
        self.assertTrue(per["carica_postgres"].usa_db and per["scarica_senato_foto"].usa_db)


if __name__ == "__main__":
    unittest.main()
