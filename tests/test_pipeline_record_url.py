"""Indirizzo del resoconto ufficiale delle sedute d'Aula del Senato (sitting.record_url), dal grezzo al caricamento."""

import unittest
from pathlib import Path

from pipeline.carica.postgres import COLONNE, righe_tabelle
from pipeline.trasforma.senato_resoconto import indirizzo_resoconto, trasforma

CORPO = (Path(__file__).parent / "fixtures" / "senato_resoconto_0300.akn").read_bytes()
BULK = "https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData.git#Leg19/Atto00058684/resaula/01526543-ra.akn.xml"
SHOW = "https://www.senato.it/show-doc?leg=19&tipodoc=Resaula&id={}"


class TestRecordUrl(unittest.TestCase):
    def test_dall_url_del_grezzo(self):
        self.assertEqual(indirizzo_resoconto(BULK, 19, 469), SHOW.format(1526543))
        pagina = SHOW.format(1425984) + "&part=doc_dc"
        self.assertEqual(indirizzo_resoconto(pagina, 19, 212), pagina)                  # importata come HTML: già show-doc
        self.assertIsNone(indirizzo_resoconto("http://dati.senato.it/osr/RESAULA/2025-05-07/300", 19, 300))
        self.assertEqual(indirizzo_resoconto("http://dati.senato.it/osr/RESAULA/2025-05-07/300", 19, 300, {300: 1450001}),
                         SHOW.format(1450001))                                         # dal file del bulk con lo stesso numero

    def test_nella_seduta_e_nella_tabella(self):
        r = trasforma(CORPO, {"chiave": "leg19-senato-sed0300", "url": BULK})
        seduta = next(n for n in r["nodi"] if n["label"] == "Sitting")
        self.assertEqual(seduta["record_url"], SHOW.format(1526543))
        righe = [{"tipo": "nodo", **n} for n in r["nodi"]] + [{"tipo": "arco", **a} for a in r["archi"]] + [{"tipo": "testo", **t} for t in r["testi"]]
        riga = righe_tabelle(righe)["sitting"][0]
        self.assertEqual(riga[COLONNE["sitting"].index("record_url")], SHOW.format(1526543))


if __name__ == "__main__":
    unittest.main()
