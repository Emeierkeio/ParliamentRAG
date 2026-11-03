"""Il connettore dei resoconti della Camera riempie i buchi sotto l'ultima seduta nel lago."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pipeline.fonti import camera_resoconti as fonte
from pipeline.lago import Lago


class TestBuchi(unittest.TestCase):
    def test_riempie_i_buchi_e_va_avanti(self):
        with tempfile.TemporaryDirectory() as d:
            cartella = Path(d)
            lago = Lago(cartella)
            for n in (1, 2, 9, 10):                       # 3-8 mancano, come dopo uno scarico a mano fuori ordine
                lago.salva(fonte.NOME, fonte.chiave(n, 19), f"seduta {n}".encode() * 20, "", "xml")
            pubblicate = set(range(1, 12))                # alla fonte ci sono le sedute 1-11
            chiesti = []

            def finto(url, tentativi):
                n = int(url.split("=")[1])
                chiesti.append(n)
                return f"seduta {n}".encode() * 20 if n in pubblicate else None

            cfg = {"fonti": {fonte.NOME: {"legislatura": 19, "url": "x?n={num}", "pausa_secondi": 0, "ricontrolla": 2, "massimo_per_giro": 100}}}
            ctx = SimpleNamespace(config=cfg, cartella=cartella, log=lambda *_: None)
            with mock.patch.object(fonte, "_scarica", finto):
                esito = fonte.scarica(ctx)
            presenti = sorted(int(k[-4:]) for k in Lago(cartella).chiavi(fonte.NOME))
            self.assertEqual(presenti, list(range(1, 12)))
            self.assertEqual(esito["buchi"], 6)
            self.assertEqual(esito["ultima"], 11)
            self.assertEqual(chiesti, [3, 4, 5, 6, 7, 8, 9, 10, 11, 12])

    def test_i_buchi_contano_nel_massimo(self):
        with tempfile.TemporaryDirectory() as d:
            cartella = Path(d)
            lago = Lago(cartella)
            lago.salva(fonte.NOME, fonte.chiave(20, 19), b"x" * 200, "", "xml")
            cfg = {"fonti": {fonte.NOME: {"legislatura": 19, "url": "x?n={num}", "pausa_secondi": 0, "ricontrolla": 1, "massimo_per_giro": 5}}}
            ctx = SimpleNamespace(config=cfg, cartella=cartella, log=lambda *_: None)
            with mock.patch.object(fonte, "_scarica", lambda url, t: b"y" * 200):
                esito = fonte.scarica(ctx)
            self.assertEqual(esito["buchi"], 5)
            self.assertEqual(sorted(int(k[-4:]) for k in Lago(cartella).chiavi(fonte.NOME)), [1, 2, 3, 4, 5, 20])


if __name__ == "__main__":
    unittest.main()
