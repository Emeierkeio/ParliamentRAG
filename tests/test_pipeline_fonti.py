"""Connettori: percorsi di pipeline.toml dalla radice del repo, ripiego del Misto del Senato, resoconti AKN del bulk."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.ambiente import QUI, percorso
from pipeline.fonti import senato_akn, senato_browser, senato_misto
from pipeline.lago import Lago
from pipeline.orchestra import Contesto

PAGINA_MISTO = b"<html>Componenti partitiche</html>"


class SessioneBloccata:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        raise senato_browser.Bloccato("HTTP 403")

    def __exit__(self, *a):
        pass


def akn(numero: int, testo: str) -> bytes:
    return f'<an:FRBRnumber value="{numero}"/>{testo}'.encode()


class TestFonti(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cartella = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_percorsi_dalla_radice_del_repo(self):
        self.assertEqual(percorso("dati/import/x.csv"), QUI / "dati" / "import" / "x.csv")
        self.assertEqual(percorso("/tmp/x"), Path("/tmp/x"))
        self.assertEqual(percorso("~/x"), Path.home() / "x")

    def test_misto_il_file_salvato_a_mano_solo_se_il_lago_e_vuoto(self):
        f = self.cartella / "misto.html"
        f.write_bytes(PAGINA_MISTO)
        ctx = Contesto("g", self.cartella, {"fonti": {"senato_misto": {"legislatura": 19, "did": 9, "file_import": str(f)}}}, {})
        with mock.patch.object(senato_browser, "Sessione", SessioneBloccata):
            self.assertEqual(senato_misto.scarica(ctx)["importati"], 1)    # lago vuoto: vale il file
            f.write_bytes(PAGINA_MISTO + b"vecchia")
            self.assertEqual(senato_misto.scarica(ctx)["importati"], 0)    # c'è già una pagina nel lago: resta quella
        self.assertEqual(Lago(self.cartella).leggi(Lago(self.cartella).ultimo("senato_misto", "leg19-senato-misto")["file"]), PAGINA_MISTO)

    def test_resaula_vince_il_file_piu_recente(self):
        radice = self.cartella / "Leg19"
        for atto, nome, testo in (("Atto1", "01000001-ra.akn.xml", "vecchio"), ("Atto2", "01000009-ra.akn.xml", "nuovo"),
                                  ("Atto3", "01000005-ra.akn.xml", "medio")):
            (radice / atto / "resaula").mkdir(parents=True)
            (radice / atto / "resaula" / nome).write_bytes(akn(390, testo))
        self.assertEqual(senato_akn.sedute_resaula(radice)[390].name, "01000009-ra.akn.xml")


if __name__ == "__main__":
    unittest.main()
