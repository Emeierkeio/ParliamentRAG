"""Bozze allegate alla chat: testo da .docx e divisione in emendamenti (api/allegati.py)."""

import base64
import io
import unittest
import zipfile

from api import allegati

BOZZA = """Emendamenti al ddl concorrenza

1.1
Al comma 1, sostituire le parole: «trenta giorni» con le seguenti: «sessanta giorni».

1.2
Dopo il comma 2, aggiungere il seguente:
«2-bis. Le disposizioni non si applicano alle imprese con meno di dieci dipendenti.»

Art. 3
Sopprimerlo.

Dopo l'articolo 4, inserire il seguente:
«Art. 4-bis. (Sugar tax) 1. L'imposta si applica dal 1° gennaio 2028.»
"""


def _docx(righe: list[str]) -> str:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    corpo = "".join(f'<w:p><w:r><w:t xml:space="preserve">{r}</w:t></w:r></w:p>' for r in righe)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document xmlns:w="{w}"><w:body>{corpo}</w:body></w:document>')
    return base64.b64encode(buf.getvalue()).decode()


class TestAllegati(unittest.TestCase):
    def test_divide_per_numero_e_formula(self):
        pezzi = allegati.dividi(BOZZA)
        self.assertEqual(len(pezzi), 4)
        self.assertTrue(pezzi[0].startswith("1.1\nAl comma 1"))
        self.assertEqual(pezzi[2], "Art. 3\nSopprimerlo.")
        self.assertTrue(pezzi[3].startswith("Dopo l'articolo 4"))

    def test_un_pezzo_solo_senza_divisioni(self):
        self.assertEqual(len(allegati.dividi("Al comma 1, sostituire le parole «x» con «y».")), 1)

    def test_docx(self):
        t = allegati.testo_da_file("bozza.docx", _docx(["1.1", "Al comma 1, sopprimere la lettera b) del testo vigente."]))
        self.assertIn("sopprimere la lettera b)", t)

    def test_formati_non_letti(self):
        with self.assertRaises(allegati.AllegatoNonLeggibile):
            allegati.testo_da_file("bozza.txt", base64.b64encode(b"testo semplice di una bozza qualsiasi").decode())


if __name__ == "__main__":
    unittest.main()
