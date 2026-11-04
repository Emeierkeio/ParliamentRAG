"""Controlli prima del caricamento: solo i file nuovi, quarantena invece di fermare il giro, soglia dei voti."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.carica import postgres
from pipeline.carica.registro import Registro
from pipeline.controlli import uscite
from pipeline.orchestra import Contesto


def scrivi(f: Path, righe: list[dict]) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(json.dumps(r) for r in righe) + "\n")


def dossier(uri, titolo="Titolo"):
    return [{"tipo": "ambito", "kind": "dossier"}, {"tipo": "nodo", "label": "Document", "uri": uri, "title": titolo, "date": "2024-01-01"}]


def voti(seduta, favorevoli_pubblicati):
    v = f"it:camera:19:sed{seduta:04d}:v001"
    return [{"tipo": "ambito", "kind": "voti", "chamber": "camera", "legislature": 19, "sitting": f"it:camera:19:sed{seduta:04d}"},
            {"tipo": "nodo", "label": "Vote", "uri": v, "date": "2024-01-01", "favor": favorevoli_pubblicati, "against": 0, "abstain": 0},
            {"tipo": "arco", "type": "VOTED", "from": "it:person:camera:1", "to": v, "result": "favor"}]


class TestControlli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cartella = Path(self.tmp.name)
        self.v3 = self.cartella / "uscite" / "v3"
        self.ctx = Contesto("g1", self.cartella, {}, {})
        self.dest = mock.patch.object(postgres, "destinazione", lambda: "locale")
        self.dest.start()

    def tearDown(self):
        self.dest.stop()
        self.tmp.cleanup()

    def test_quarantena_invece_di_fermare(self):
        scrivi(self.v3 / "camera_dossier" / "buono.jsonl", dossier("a"))
        scrivi(self.v3 / "camera_dossier" / "rotto.jsonl", dossier("b", titolo=None))
        (self.v3 / "camera_dossier" / "illeggibile.jsonl").write_text("{non è json\n")
        r = uscite.controlla(self.ctx)
        self.assertEqual((r["file_controllati"], r["in_quarantena"]), (3, 2))
        self.assertIn("rotto.jsonl", r["avviso"])
        reg = Registro(self.cartella, "locale")
        self.assertEqual(sorted(q["percorso"] for q in reg.quarantena()), ["camera_dossier/illeggibile.jsonl", "camera_dossier/rotto.jsonl"])

    def test_solo_i_file_non_ancora_caricati(self):
        f = self.v3 / "camera_dossier" / "buono.jsonl"
        scrivi(f, dossier("a"))
        reg = Registro(self.cartella, "locale")
        reg.caricato(f, reg.da_caricare(f))
        self.assertEqual(uscite.controlla(self.ctx)["file_controllati"], 0)

    def test_troppi_voti_che_non_tornano_vanno_tutti_in_quarantena(self):
        for s in range(1, 4):
            scrivi(self.v3 / "camera_voti" / f"leg19-voti-sed{s:04d}.jsonl", voti(s, 1 if s == 1 else 5))
        r = uscite.controlla(self.ctx)
        self.assertEqual(r["in_quarantena"], 3)
        self.assertEqual(len(Registro(self.cartella, "locale").quarantena()), 3)


if __name__ == "__main__":
    unittest.main()
