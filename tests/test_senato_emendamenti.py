"""Gli emendamenti del Senato dai bulk data in Akoma Ntoso diventano gli stessi record della Camera (ddl 1110 e 1101)."""

import gzip
import json
import unittest
from pathlib import Path

from pipeline.controlli.uscite import _regole
from pipeline.trasforma.senato_emendamenti import trasforma

F = Path(__file__).parent / "fixtures"


def _corpo(*nomi):
    return gzip.compress(json.dumps({n: (F / n).read_text() for n in nomi}).encode())


class TestSenatoEmendamenti(unittest.TestCase):
    def test_aula(self):
        r = trasforma(_corpo("senato_emendamento_1110_A_35.3.akn.xml"), {"chiave": "leg19-senato-eme-1110-A"})
        n = r["nodi"][0]
        self.assertEqual((n["uri"], n["act"], n["venue"], n["presented"]),
                         ("it:senato:19:ddl:1110:eme:a:35.3", "it:senato:19:ddl:1110", "assembly", "2024-04-23"))
        self.assertEqual([a["from"] for a in r["archi"]][:2], ["it:person:senato:32608", "it:person:senato:32691"])
        self.assertTrue(r["testi"][0]["text"].startswith("Dopo il comma 1"))

    def test_nuovo_testo(self):
        """Gli emendamenti al nuovo testo della commissione restano distinti da quelli al testo presentato."""
        r = trasforma(_corpo("senato_emendamento_1101NT_C_4.1.akn.xml"), {"chiave": "leg19-senato-eme-1101_NT-C"})
        self.assertEqual(r["nodi"][0]["uri"], "it:senato:19:ddl:1101:eme:c:nt:4.1")
        righe = [{"tipo": "ambito", **r["ambito"]}] + [{"tipo": "nodo", **x} for x in r["nodi"]] + \
                [{"tipo": "arco", **x} for x in r["archi"]] + [{"tipo": "testo", **x} for x in r["testi"]]
        self.assertEqual(_regole(righe), [])


if __name__ == "__main__":
    unittest.main()
