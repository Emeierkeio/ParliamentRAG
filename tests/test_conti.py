"""Strumenti di conteggio (api/strumenti/conti.py) sul Postgres locale: le regole senza database, poi i conti su numeri
noti della XIX. Le prove sul database si saltano se Postgres non risponde."""

import datetime as dt
import unittest

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""

from api import agente, registro
from api.strumenti import conti

CAT = {"g:fdi": {"uri": "g:fdi", "chamber": "camera", "kind": "group", "name": "Fratelli d'Italia", "short_name": "FDI", "part_of": None},
       "g:misto": {"uri": "g:misto", "chamber": "camera", "kind": "group", "name": "Misto", "short_name": "MISTO", "part_of": None},
       "g:eu": {"uri": "g:eu", "chamber": "camera", "kind": "misto_component", "name": "+Europa", "short_name": "MISTO-+EU",
                "part_of": "g:misto"},
       "s:fdi": {"uri": "s:fdi", "chamber": "senato", "kind": "group", "name": "Fratelli d'Italia", "short_name": "FdI", "part_of": None}}


class TestRegole(unittest.TestCase):
    def test_gruppi_chiesti_e_misto(self):
        self.assertEqual(conti.gruppi_chiesti(CAT, "fdi"), ["g:fdi", "s:fdi"])
        self.assertEqual(conti.gruppi_chiesti(CAT, "FdI", "senato"), ["s:fdi"])
        self.assertEqual(conti.gruppi_chiesti(CAT, "Misto"), ["g:eu", "g:misto"])            # il Misto con le componenti
        self.assertEqual(conti.etichetta(CAT, "g:eu"), "Misto - +Europa (MISTO-+EU)")
        with self.assertRaises(ValueError):
            conti.gruppi_chiesti(CAT, "inesistente")

    def test_rami_mai_sommati_se_non_chiesto(self):
        self.assertEqual(conti._dimensioni(["anno"], conti.DIM_VOTI, None, False), ["ramo", "anno"])
        self.assertEqual(conti._dimensioni(["anno"], conti.DIM_VOTI, None, True), ["anno"])
        self.assertEqual(conti._dimensioni(["anno"], conti.DIM_VOTI, "camera", False), ["anno"])
        with self.assertRaises(ValueError):
            conti._dimensioni(["colore"], conti.DIM_VOTI, None, False)

    def test_pagina_e_frase(self):
        p = conti._pagina([{"n": i} for i in range(300)], 500, 0)
        self.assertEqual((len(p["rows"]), p["rows_total"]), (conti.RIGHE_MAX, 300))         # tetto alle righe
        self.assertIn("offset=200", p["more"])
        self.assertEqual(conti._regex_parole("povertà  assoluta"), r"\mpovertà\s+assoluta\M")
        self.assertEqual(conti._regex_parole("l'Italia (oggi)"), r"\ml['’]Italia\s+\(oggi\)\M")

    def test_prompt_ed_etichette(self):
        self.assertIn("strumenti di conteggio, mai la stima", agente.PROMPT)
        self.assertIn("elenco parziale", agente.PROMPT.replace("è parziale", "elenco parziale"))
        self.assertIn("salute", agente.PROMPT)
        for s in registro.STRUMENTI:
            self.assertIn(s.nome, agente.ETICHETTE)


@unittest.skipIf(C is None, f"Postgres non raggiungibile: {MOTIVO}")
class TestConti(unittest.TestCase):
    def test_tempo_massimo(self):
        with self.assertRaises(conti.ConteggioTroppoLungo):
            with conti.tempo_massimo(C, 1):
                C.execute("SELECT pg_sleep(2)")
        self.assertEqual(C.execute("SELECT 1 AS x").fetchone()["x"], 1)                      # la connessione resta buona

    def test_votazioni_divise_per_ramo(self):
        r = conti.conta_votazioni(C, final=True, secret=False)
        self.assertEqual({x["ramo"] for x in r["rows"]}, {"camera", "senato"})
        self.assertIn("counted", r)
        self.assertEqual(r["total"], sum(x["votazioni"] for x in r["rows"]))

    def test_voto_gruppi(self):
        r = conti.voto_gruppi(C, "camera", final=True, groups=["Lega", "FdI"])
        self.assertEqual(len(r["groups"]), 2)
        self.assertTrue(all(0.5 <= g["cohesion"] <= 1 for g in r["groups"]))
        self.assertIn("different_positions", r)
        self.assertEqual(r["different_positions"]["total"], len(r["different_positions"]["rows"]))

    def test_leggi_una_volta_sola(self):
        r = conti.conta_atti(C, laws=True, group_by=["iniziativa"])
        per = {x["iniziativa"]: x["leggi"] for x in r["rows"]}
        self.assertGreater(per["governo"], per["parlamentare"])
        tutti = conti.conta_atti(C, became_law=True)
        self.assertLess(r["total"], tutti["total"])                                           # gli atti dei due rami contano una volta

    def test_iniziativa_e_frase(self):
        self.assertGreater(conti.conta_atti(C, chamber="senato", initiative="Regione Toscana")["total"], 0)
        r = conti.conta_interventi(C, phrase="povertà assoluta", start=dt.date(2026, 1, 1), group_by=["gruppo"])
        self.assertTrue(all(x["occorrenze"] >= x["interventi"] for x in r["rows"]))
        self.assertTrue(all(x["ramo"] in ("camera", "senato") for x in r["rows"]))

    def test_cambi_gruppo(self):
        r = conti.cambi_gruppo(C, limit=5)
        self.assertEqual(set(r["by_chamber"]), {"camera", "senato"})
        self.assertTrue(all(x["from"] != x["to"] for x in r["rows"]))

    def test_registro_dice_se_l_elenco_e_parziale(self):
        r = registro.esegui(C, "cerca_atti", {"initiative": "Regione Toscana", "limit": 3})
        self.assertGreater(r["total"], 3)
        self.assertIn("offset=3", r["more"])
        d = registro.esegui(C, "cerca_interventi", {"q": "levano in piedi", "captions": True, "start": "2026-02-03", "end": "2026-02-03"})
        self.assertTrue(any("si levano in piedi" in h["snippet"] for h in d["items"]))


if __name__ == "__main__":
    unittest.main()
