"""Quali progetti di legge si richiedono ogni notte: quelli con il file, quelli il cui iter è cambiato, quelli in esame."""

import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from pipeline.fonti import camera_emendamenti as fonte
from pipeline.lago import Lago


class TestCandidati(unittest.TestCase):
    def giro(self, tmp, stati, risposte):
        chiesti = []

        def get(url, dal, tentativi=3):
            n = url.rsplit(".ac.", 1)[1].removesuffix(".xml")
            chiesti.append(n)
            return risposte.get(n, (404, None))
        ctx = types.SimpleNamespace(cartella=Path(tmp), log=lambda *_: None,
                                    config={"fonti": {fonte.NOME: {"legislatura": 19, "pausa_secondi": 0}}})
        with mock.patch.object(fonte, "stati_iter", lambda lago, leg: stati), mock.patch.object(fonte, "_get_se_cambiato", get):
            return fonte.scarica(ctx), chiesti

    def test_un_atto_in_esame_si_riprova_anche_se_lo_stato_non_cambia(self):
        stati = {"3133": "In corso di esame in Commissione", "3152": "Assegnato", "2830": "In discussione"}
        with tempfile.TemporaryDirectory() as tmp:
            _, chiesti = self.giro(tmp, stati, {})
            self.assertEqual(sorted(chiesti), ["2830", "3133", "3152"])          # primo giro: tutti, e nessuno ha il file
            # secondo giro, stati uguali: l'assegnato non si richiede, quelli in esame sì; il file del 3133 ora c'è
            r, chiesti = self.giro(tmp, stati, {"3133": (200, b"<proposteEmendativeAC/>")})
            self.assertEqual(sorted(chiesti), ["2830", "3133"])
            self.assertEqual(r["nuovi"], 1)
            lago = Lago(Path(tmp))
            self.assertIsNotNone(lago.ultimo(fonte.NOME, "leg19-eme-ac3133"))
            assenti = json.loads(lago.leggi(lago.ultimo(fonte.NOME, "leg19-eme-assenti")["file"]))
            self.assertEqual(assenti, {"2830": "In discussione", "3152": "Assegnato"})


if __name__ == "__main__":
    unittest.main()
