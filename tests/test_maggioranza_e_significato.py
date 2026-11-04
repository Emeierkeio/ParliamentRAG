"""La regola unica della maggioranza (api/fascicolo/maggioranza.py), chi la usa, il link al resoconto del Senato
(sitting.record_url) e lo strumento della chat per significato. Le prove sul database si saltano se Postgres non
risponde; quella per significato usa come testo il vettore di un brano già nel database (niente chiamate al modello)."""

import datetime as dt
import unittest
from unittest import mock

from api import agente, registro
from api.fascicolo import maggioranza as M
from api.strumenti import comune

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""

OGGI = dt.date(2026, 11, 4)


class Regola(unittest.TestCase):
    def setUp(self):
        self.s = M.Schieramenti(
            fiducie={"fdi": [(dt.date(2026, 6, 1), 100, 100)], "pd": [(dt.date(2026, 6, 1), 0, 60)],
                     "nm_c": [(dt.date(2026, 6, 1), 5, 6)], "nm_s": [(dt.date(2026, 6, 1), 1, 6)],
                     "vecchio": [(dt.date(2024, 6, 1), 10, 10)]},
            al_governo={"vecchio"}, nomi={"fdi": "FdI", "pd": "PD", "nm_c": "NM", "nm_s": "NM", "misto": "Misto",
                                          "vecchio": "X", "nuovo": "Y"})

    def test_fiducie_e_riserva(self):
        self.assertEqual(self.s.lato("fdi", OGGI), M.MAGGIORANZA)
        self.assertEqual(self.s.lato("pd", OGGI), M.OPPOSIZIONE)
        self.assertEqual(self.s.lato("vecchio", OGGI), M.MAGGIORANZA)           # niente fiducie nei 12 mesi: la riserva
        self.assertEqual(self.s.lato("vecchio", dt.date(2024, 12, 1)), M.MAGGIORANZA)
        self.assertEqual(self.s.lato("nuovo", OGGI), M.OPPOSIZIONE)
        self.assertEqual(self.s.lato("misto", OGGI), M.MISTO)                   # il Misto senza componente
        self.assertEqual(self.s.lato(None), M.OPPOSIZIONE)

    def test_gruppi_dello_stesso_partito_insieme(self):
        self.assertEqual(self.s.lato(["nm_c", "nm_s"], OGGI), M.OPPOSIZIONE)    # 6 su 12: la metà non basta
        self.assertEqual(self.s.lato(["nm_c", "fdi"], OGGI), M.MAGGIORANZA)
        self.assertEqual(self.s.lato(["nm_c", "misto"], OGGI), M.MAGGIORANZA)   # il Misto non conta

    def test_una_regola_sola(self):
        from api.fascicolo import autorevolezza as A
        self.assertIs(A.lato_alla_data, M.lato_alla_data)
        pr = A.Profili(persone={}, alias={}, gruppi={"fdi": {"name": "FdI"}, "pd": {"name": "PD"}}, organi={},
                       schieramenti=self.s)
        self.assertEqual(pr.lato("fdi", OGGI), M.MAGGIORANZA)
        self.assertEqual(pr.lato("pd", OGGI), M.OPPOSIZIONE)
        self.assertEqual(pr.lato(A.GOVERNO), M.MAGGIORANZA)

    def test_un_prompt_solo_per_i_dibattiti(self):
        from api.fascicolo import recupero_modello
        from api.fascicolo.generazione import debate_relevance
        self.assertIs(debate_relevance.PROMPT, recupero_modello.PROMPT_GIUDIZIO)
        with mock.patch.object(recupero_modello, "giudica_dibattiti", return_value={"t": "T"}) as g:
            self.assertEqual(debate_relevance.judge_debates("q", ["t"]), {"t": "T"})
        g.assert_called_once()


class GovernoNellaVerifica(unittest.TestCase):
    def test_ministro_con_seggio_alla_camera(self):
        """Alla Camera il resoconto non scrive la carica dei ministri parlamentari: senza gruppo dichiarato e con un
        incarico di governo quel giorno parlano per il Governo, come nel recupero."""
        from api.fascicolo import autorevolezza as A, verifica as V
        p = {"mandati": [{"chamber": "camera"}], "governo": [{"start": dt.date(2022, 10, 31), "end": None}]}
        pr = A.Profili(persone={"x": p}, alias={"x": "x"}, gruppi={}, organi={})
        self.assertFalse(V._al_governo_il(pr, "x", OGGI))
        self.assertTrue(V._al_governo_il(pr, "x", OGGI, senza_gruppo=True))
        self.assertFalse(V._al_governo_il(pr, "x", dt.date(2022, 10, 1), senza_gruppo=True))


class Link(unittest.TestCase):
    def test_senato_dalla_seduta(self):
        pagina = "https://www.senato.it/show-doc?leg=19&tipodoc=Resaula&id=1"
        self.assertEqual(comune.url_intervento("it:senato:19:sed0469:int00121", pagina), pagina)
        self.assertIsNone(comune.url_intervento("it:senato:19:sed0469:int00121"))
        self.assertTrue(comune.url_intervento("it:camera:19:sed0734:tit00020.sub00040.int00020", pagina).startswith(
            "https://www.camera.it/leg19/410?idSeduta=0734"))

    def test_senza_colonna(self):
        c = mock.MagicMock()
        with mock.patch.object(comune, "ha_colonna", return_value=False):
            self.assertEqual(comune.url_sedute(c, ["it:senato:19:sed0469"]), {})
            self.assertEqual(comune.url_interventi(c, ["it:senato:19:sed0469:int00121"]),
                             {"it:senato:19:sed0469:int00121": None})
        c.execute.assert_not_called()


class Strumento(unittest.TestCase):
    def test_nel_registro_e_nel_prompt(self):
        self.assertIn("cerca_per_significato", registro.PER_NOME)
        self.assertEqual(agente.ETICHETTE["cerca_per_significato"], "Cerco per significato")
        self.assertIn("cerca per significato", agente.PROMPT)
        schema = registro.PER_NOME["cerca_per_significato"].schema()
        self.assertEqual(set(schema["properties"]), {"testo", "fonti", "ramo", "da", "a", "quanti"})
        with self.assertRaises(Exception):
            registro.esegui(None, "cerca_per_significato", {"testo": "sanità", "fonti": ["giornali"]})


class Contesto(unittest.TestCase):
    def test_fascicolo_in_un_contesto(self):
        """StreamingResponse fa ogni next() in una copia nuova del contesto: le variabili messe al primo passo devono
        restare ai passi dopo e il reset non deve fallire."""
        import contextvars
        from api.fascicolo import servizio
        v = contextvars.ContextVar("v", default=None)

        def gen():
            t = v.set("rami")
            try:
                yield "a"
                yield v.get()
            finally:
                v.reset(t)
        g = servizio.in_un_contesto(gen())
        passi = [contextvars.copy_context().run(next, g) for _ in range(2)]
        self.assertEqual(passi, ["a", "rami"])
        with self.assertRaises(StopIteration):
            contextvars.copy_context().run(next, g)


@unittest.skipIf(C is None, f"database non raggiungibile: {MOTIVO}")
class SulDatabase(unittest.TestCase):
    def test_partiti_attesi_dalla_regola(self):
        from api.fascicolo.recupero_gruppi import partiti_attesi
        p = partiti_attesi(C, ["camera", "senato"])
        self.assertEqual(p["Noi Moderati - MAIE - Centro Popolare"]["schieramento"], M.MAGGIORANZA)
        self.assertEqual(p["Alleanza Verdi e Sinistra"]["lato"], M.OPPOSIZIONE)     # al Senato è una componente
        self.assertEqual(p["Misto"]["schieramento"], M.MISTO)
        self.assertIn(p["+Europa - Stati Uniti d'Europa"]["schieramento"], (M.MAGGIORANZA, M.OPPOSIZIONE))

    def test_colonna_record_url(self):
        c = comune.ha_colonna(C, "sitting", "record_url")
        link = comune.url_interventi(C, ["it:senato:19:sed0469:int00121"])
        if not c:
            self.assertEqual(link, {"it:senato:19:sed0469:int00121": None})
        else:
            self.assertIn("it:senato:19:sed0469:int00121", link)       # vuota finché le sedute non si ritrasformano

    def test_cerca_per_significato(self):
        r = C.execute("""SELECT v.embedding::text AS e FROM passage p JOIN passage_vector v ON v.hash = p.hash
                         WHERE p.source = 'speech' AND p.uri = 'it:camera:19:sed0594:tit00060.sub00040.int00020'
                           AND p.ord = 2""").fetchone()
        if r is None:
            self.skipTest("brano senza vettore")
        vettore = [float(x) for x in r["e"].strip("[]").split(",")]
        from api.fascicolo import modello
        with mock.patch.object(modello, "vettori", return_value=[vettore]):
            out = registro.esegui(C, "cerca_per_significato", {"testo": "difesa", "ramo": "camera", "quanti": 3})
            altri = registro.esegui(C, "cerca_per_significato", {"testo": "difesa", "fonti": ["atti", "emendamenti"],
                                                                  "quanti": 3, "da": "2024-01-01"})
        primo = out["risultati"][0]
        self.assertEqual(primo["uri"], "it:camera:19:sed0594:tit00060.sub00040.int00020")
        self.assertEqual(primo["chi"], "Guido Crosetto")
        self.assertEqual(primo["gruppo"], "Governo")
        self.assertTrue(primo["url"].startswith("https://www.camera.it/leg19/410?idSeduta=0594"))
        self.assertTrue(all(x["ramo"] == "camera" for x in out["risultati"]))
        self.assertLessEqual(len(altri["risultati"]), 3)
        self.assertTrue(all(x["data"] is None or x["data"] >= "2024-01-01" for x in altri["risultati"]))


if __name__ == "__main__":
    unittest.main()
