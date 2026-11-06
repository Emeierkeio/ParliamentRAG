"""L'elenco cronologico dei resoconti del Senato: numero della seduta e id del resoconto."""

import unittest

from pipeline.fonti.senato_resoconti import leggi_elenco

RIGA = """<tr> <td class="tab1">Giovedì 05 Novembre 2026</td> <td class="tab1" style="font-weight: bold"> {n}</td>
<td class="tab1"> <a href="/show-doc?leg=19&amp;tipodoc=Resaula&amp;id={i}&amp;idoggetto=0" target="_blank"> html </a> </td></tr>"""


class TestElenco(unittest.TestCase):
    def test_numero_e_id(self):
        self.assertEqual(leggi_elenco(RIGA.format(n=473, i=1527338) + RIGA.format(n=472, i=1527087), 19), {473: 1527338, 472: 1527087})

    def test_altra_legislatura_e_pagina_vuota(self):
        self.assertEqual(leggi_elenco(RIGA.format(n=473, i=1527338), 18), {})
        self.assertEqual(leggi_elenco("<html></html>", 19), {})


if __name__ == "__main__":
    unittest.main()
