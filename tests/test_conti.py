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
from api.strumenti import atti, conti

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

    def test_confronti_regole(self):
        self.assertEqual(conti._pos((3, 1, 0)), "favor")
        self.assertEqual(conti._pos((2, 2, 0)), "tie")
        self.assertIsNone(conti._pos((0, 0, 0)))
        cat = CAT | {"g:lega": {"uri": "g:lega", "chamber": "camera", "kind": "group", "name": "Lega - Partito Sardo d'Azione",
                                "short_name": "LEGA", "part_of": None},
                     "g:az": {"uri": "g:az", "chamber": "camera", "kind": "misto_component", "name": "Azione", "short_name": "AZ",
                              "part_of": "g:misto"}}
        self.assertEqual(conti._un_gruppo(cat, "AZ", "camera"), ["g:az"])
        self.assertEqual(conti._un_gruppo(cat, "azione", "camera"), ["g:az"])                  # il nome esatto vince
        self.assertEqual(conti._un_gruppo(cat, "Misto", "camera"), ["g:az", "g:eu", "g:misto"])   # il Misto con le componenti
        with self.assertRaises(ValueError):                                                     # «Azione» è anche nella Lega
            conti._un_gruppo(cat, "azion", "camera")
        with self.assertRaises(ValueError):
            conti.confronta_voti(None, "camera", "classifica")

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

    def test_confronta_voti(self):
        # numeri del database al 5/11/2026, controllati a mano il 26/11 (righe 706 e 755 del registro della chat)
        r = conti.confronta_voti(C, "camera", "persone", persons=["it:person:camera:306064", "it:person:camera:300447"],
                                 end=dt.date(2026, 11, 5))
        self.assertEqual(r["same"], sum(n for k, n in r["pairs"].items() if k.split("/")[0] == k.split("/")[1]))
        self.assertEqual(r["different_votes"]["total"], r["votes_both"] - r["same"])
        r = conti.confronta_voti(C, "camera", "dissensi", final=True, start=dt.date(2022, 12, 30), end=dt.date(2022, 12, 30))
        fassino = [x for x in r["cases"]["rows"] if any("Fassino" in y["persona"] for y in x["chi"])]
        self.assertEqual(len(fassino), 1)                       # unico sì del PD sul DDL 705 (DL 162/2022)
        self.assertEqual(fassino[0]["group_position"], "against")
        self.assertFalse(any(x["gruppo"] == "Misto (MISTO)" for x in r["cases"]["rows"]))
        r = conti.confronta_voti(C, "camera", "segreti", start=dt.date(2026, 7, 14), end=dt.date(2026, 7, 14))
        em = [x for x in r["rows"] if x["number"] == 12][0]      # em. 1.1077 alla legge elettorale, 187-188
        self.assertEqual((em["favor"], em["against"]), (187, 188))
        self.assertEqual(em["majority_short_if_for"], em["majority_voters"] - 187)
        r = conti.confronta_voti(C, "camera", "maggioranza", group="AZ-PER-RE", final=True)
        self.assertGreater(r["votes"], 0)
        self.assertEqual(r["different_votes"]["total"], r["votes"] - r["same"])

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

    def test_atti_per_parole_del_testo(self):
        # il titolo di un'interrogazione è solo l'intestazione («INTERROGAZIONE A RISPOSTA SCRITTA 4/02224 presentata da…»):
        # l'argomento (qui l'INPS) sta nel testo, e la ricerca per parole deve trovarlo
        n, xs = atti.cerca_atti(C, q="INPS", chamber="camera", signer="it:person:camera:306064", limit=100)
        self.assertIn("it:camera:19:aic:4-02224", [x.uri for x in xs])
        # prima gli atti con le parole nel titolo, poi quelli con le parole solo nel testo
        n, xs = atti.cerca_atti(C, q="salario minimo", chamber="camera", limit=5)
        self.assertTrue(all("salario minimo" in (x.title or "").lower() for x in xs))
        # anche il conteggio: «quante interrogazioni ha presentato Sottanelli sull'INPS»
        self.assertGreater(conti.conta_atti(C, q="INPS", signer="it:person:camera:306064")["total"], 0)


if __name__ == "__main__":
    unittest.main()
