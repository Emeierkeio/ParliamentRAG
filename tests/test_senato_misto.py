"""Le componenti del Misto del Senato dalla composizione storica di senato.it (pagina del 3/11/2026)."""

import re
import unittest
from pathlib import Path

from pipeline.trasforma import senato_misto

PAGINA = (Path(__file__).parent / "fixtures" / "senato_misto_storica.html").read_text(encoding="utf-8")
MISTO = "it:senato:19:group:9"


class TestSenatoMisto(unittest.TestCase):
    def setUp(self):
        persone = {f"it:person:senato:{d}" for d in re.findall(r"scheda-attivita\?did=(\d+)", PAGINA)}
        self.nodi, self.archi = senato_misto.trasforma(PAGINA, 19, MISTO, persone, "https://www.senato.it/x")
        self.adesioni = {(a["from"].rsplit(":", 1)[-1], a["to"].rsplit(":", 1)[-1]): a for a in self.archi if a["type"] == "MEMBER_OF"}

    def test_date_italiane(self):
        self.assertEqual(senato_misto.data_it("Entra nel gruppo il 1º marzo 2024"), "2024-03-01")
        self.assertIsNone(senato_misto.data_it("in corso"))

    def test_nome_di_oggi_e_alias(self):
        az = next(n for n in self.nodi if n["uri"].endswith("misto-az"))
        self.assertEqual((az["name"], az["short_name"], az["start"]), ("Azione-Renew Europe", "Az-RE", "2023-11-09"))
        self.assertIn("Az", az["aliases"])
        avs = next(n for n in self.nodi if n["uri"].endswith("misto-avs"))
        self.assertEqual(avs["name"], "Alleanza Verdi e Sinistra")
        self.assertTrue(all(a["to"] == MISTO for a in self.archi if a["type"] == "PART_OF"))
        self.assertEqual(len(self.nodi), 5)

    def test_adesioni_datate(self):
        calenda = self.adesioni[("30110", "misto-az")]                       # entra nel gruppo con la componente
        self.assertEqual((calenda["start"], calenda["end"]), ("2023-11-09", None))
        gelmini = self.adesioni[("22966", "misto-az")]                       # esce dalla componente prima che dal gruppo
        self.assertEqual(gelmini["end"], "2024-09-17")
        nave = self.adesioni[("36410", "misto-a-psi")]                       # entra nel gruppo l'8, componente dal 9
        self.assertEqual(nave["start"], "2026-10-09")

    def test_una_adesione_per_carica(self):
        magni = [k for k in self.adesioni if k[0] == "36437"]                # tesoriere e membro: una adesione sola
        self.assertEqual(magni, [("36437", "misto-avs")])

    def test_senatori_a_vita_senza_componente(self):
        self.assertNotIn("28543", {k[0] for k in self.adesioni})              # Monti

    def test_componente_lasciata_e_annotazione(self):
        """Dall'11/11/2026 chi cambia componente ha due voci: «AVS fino all'8 ottobre 2026» e, in un
        <span class="annotazione">, «A-PSI dal 9 ottobre 2026»."""
        riga = ('<tr><td><a href="/x/scheda-attivita?did=36410">NAVE Luigi</a>'
                "<span>AVS fino    all'8 ottobre 2026</span>"
                '<span class="annotazione"><br/>A-PSI dal 9 ottobre 2026</span></td>'
                "<td><span>Entra nel gruppo l'8 ottobre 2026<br></span></td></tr>")
        voci = [(r["sigla"], r["dal"], r["al"]) for r in senato_misto.righe(riga)]
        self.assertEqual(voci, [("AVS", None, "2026-10-08"), ("A-PSI", "2026-10-09", None)])

    def test_sigla_sconosciuta(self):
        rotta = PAGINA.replace("<span>\n                  AVS", "<span>\n                  XYZ", 1)
        with self.assertRaises(ValueError):
            senato_misto.trasforma(rotta, 19, MISTO, {"it:person:senato:22918"}, "x")


if __name__ == "__main__":
    unittest.main()
