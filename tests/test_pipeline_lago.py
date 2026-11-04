"""Lago dei grezzi: versioni, ritorno a una versione già vista, calo delle righe nelle fonti a query."""

import json
import tempfile
import time
import unittest
from pathlib import Path

from pipeline.lago import Lago, controlla_calo


class TestLago(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lago = Lago(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_stessa_versione_non_si_riscrive(self):
        a = self.lago.salva("f", "k", b"A")
        prima = self.lago.ultimo("f", "k")["scaricato"]
        b = self.lago.salva("f", "k", b"A")
        self.assertTrue(a["nuovo"])
        self.assertFalse(b["nuovo"])
        self.assertEqual(self.lago.ultimo("f", "k")["scaricato"], prima)   # niente ritrasformazioni a ogni giro

    def test_a_b_a_l_ultima_vista_vince(self):
        self.lago.salva("f", "k", b"A")
        self.lago.salva("f", "k", b"B")
        self.assertEqual(self.lago.leggi(self.lago.ultimo("f", "k")["file"]), b"B")
        da = time.time()
        r = self.lago.salva("f", "k", b"A")
        self.assertTrue(r["nuovo"])
        self.assertEqual(self.lago.leggi(self.lago.ultimo("f", "k")["file"]), b"A")
        self.assertEqual([g["chiave"] for g in self.lago.nuovi_dal("f", da)], ["k"])

    def test_ultimi_dal_una_versione_per_chiave(self):
        self.lago.salva("f", "k", b"1")
        self.lago.salva("f", "k", b"2")
        self.lago.salva("f", "j", b"x")
        u = self.lago.ultimi_dal("f", 0)
        self.assertEqual([g["chiave"] for g in u], ["j", "k"])
        self.assertEqual(self.lago.leggi(u[1]["file"]), b"2")

    def test_calo_oltre_il_cinque_per_cento(self):
        self.lago.salva("f", "leg19-persone", json.dumps([{"x": i} for i in range(100)]).encode())
        controlla_calo(self.lago, "f", "leg19-persone", 96)           # 4% in meno: passa
        controlla_calo(self.lago, "f", "leg19-nuova", 1)              # niente versione prima: passa
        with self.assertRaises(RuntimeError):
            controlla_calo(self.lago, "f", "leg19-persone", 94)
        controlla_calo(self.lago, "f", "leg19-persone", 50, massimo=0.6)


if __name__ == "__main__":
    unittest.main()
