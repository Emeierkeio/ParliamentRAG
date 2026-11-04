"""Recupero delle evidenze del fascicolo: funzioni pure, e alcune prove sul database locale (saltate se non c'è)."""

import datetime as dt
import unittest

from api.fascicolo import recupero_commissioni as comm
from api.fascicolo.recupero import Ambito, risolvi_ambito, statistiche
from api.fascicolo.recupero_canali import _modello_re, _titolo, parole_chiave, similarita, url_intervento
from api.fascicolo.recupero_fusione import deduplica, fondi, scegli
from api.fascicolo.recupero_gruppi import chiave, componente_senato, partito


def brano(cid, persona, part, sim, governo=False):
    return {"chunk_id": cid, "speaker": {"uri": persona, "nome": persona}, "partito": part, "similarita": sim,
            "governo": governo, "canali": ["denso"]}


class Ambiti(unittest.TestCase):
    def test_predefinito_e_ordine(self):
        self.assertEqual(Ambito().rami, ["camera", "senato"])
        self.assertEqual(Ambito(rami=["senato", "camera"]).rami, ["camera", "senato"])

    def test_errori(self):
        with self.assertRaises(ValueError):
            Ambito(rami=["regione"])
        with self.assertRaises(ValueError):
            Ambito(da=dt.date(2025, 1, 2), a=dt.date(2025, 1, 1))

    def test_ramo_nominato(self):
        self.assertEqual(risolvi_ambito("interrogazioni del M5S al Senato sulla sanità").rami, ["senato"])
        self.assertEqual(risolvi_ambito("cosa hanno detto i deputati sul salario minimo").rami, ["camera"])
        # «camera di commercio» non è la Camera; un ramo scelto vince sulla domanda
        self.assertEqual(risolvi_ambito("la camera di commercio e le imprese").rami, ["camera", "senato"])
        self.assertEqual(risolvi_ambito("al Senato", Ambito(rami=["camera"])).rami, ["camera"])

    def test_anno(self):
        a = risolvi_ambito("interventi sulla povertà assoluta nel 2026")
        self.assertEqual((a.da, a.a), (dt.date(2026, 1, 1), dt.date(2026, 12, 31)))
        self.assertEqual(risolvi_ambito("dal 2024 a oggi").da, dt.date(2024, 1, 1))
        fisso = Ambito(da=dt.date(2023, 5, 1))
        self.assertEqual(risolvi_ambito("nel 2026", fisso).da, dt.date(2023, 5, 1))


class Gruppi(unittest.TestCase):
    def test_partito_fra_i_rami(self):
        self.assertEqual(partito("Lega Salvini Premier - Partito Sardo d'Azione"), "Lega - Salvini Premier")
        self.assertEqual(partito("MoVimento 5 Stelle"), "Movimento 5 Stelle")
        self.assertEqual(partito("Noi Moderati - MAIE"), "Noi Moderati - MAIE - Centro Popolare")
        self.assertEqual(partito("+Europa - Stati Uniti d'Europa"), "+Europa - Stati Uniti d'Europa")
        self.assertEqual(chiave("Lega - Salvini  Premier"), chiave("LEGA-SALVINI PREMIER"))

    def test_componente_del_misto_al_senato(self):
        self.assertEqual(componente_senato("Misto-AVS"), ("AVS", "Alleanza Verdi e Sinistra"))
        self.assertEqual(componente_senato("Misto-PRC-SE-OS"), ("PRC-SE-OS", "Misto - PRC-SE-OS"))
        self.assertEqual(componente_senato("Misto"), (None, None))
        self.assertEqual(componente_senato(None), (None, None))


class Canali(unittest.TestCase):
    def test_parole_chiave(self):
        p = parole_chiave("Qual è la posizione dei gruppi parlamentari sul tema: salario minimo?")
        self.assertEqual(p, ["salario", "minimo", "salario minimo"])

    def test_espressione_della_parola(self):
        self.assertEqual(_modello_re("c++"), r"\mc\+\+\M")

    def test_similarita_e_url(self):
        self.assertAlmostEqual(similarita(0.0), 1.0)
        self.assertAlmostEqual(similarita(1.0), 0.5)
        self.assertEqual(url_intervento("it:camera:19:sed0594:tit00060.sub00040.int00020"),
                         "https://www.camera.it/leg19/410?idSeduta=0594&tipo=stenografico#sed0594.stenografico.tit00060.sub00040.int00020")
        self.assertIsNone(url_intervento("it:senato:19:sed0194:int00233"))
        # il Senato non ha ancore: la pagina della seduta, se c'è (sitting.record_url)
        pagina = "https://www.senato.it/show-doc?leg=19&tipodoc=Resaula&id=1"
        self.assertEqual(url_intervento("it:senato:19:sed0194:int00233", pagina), pagina)
        self.assertIsNone(url_intervento("it:senato:19:sed0194:int00233", ""))
        self.assertIsNone(url_intervento("it:camera:19:stc:84:audiz2:audizione:20251014:0021:x"))

    def test_titolo_senza_orari(self):
        self.assertEqual(_titolo("Seguito della discussione (A.C. 2416-A) (ore 12,27). (ore 12,27) (ore 12,27)"),
                         "Seguito della discussione (A.C. 2416-A)")
        self.assertIsNone(_titolo(None))


class Fusione(unittest.TestCase):
    def test_deduplica_tiene_il_migliore_e_i_canali(self):
        d = [brano("a", "p1", "X", 0.7), brano("a", "p1", "X", 0.8)]
        g = [dict(brano("a", "p1", "X", 0.5), canali=["grafo"]), dict(brano("b", "p2", "Y", 0.6), canali=["grafo"])]
        out = {r["chunk_id"]: r for r in deduplica(d, g)}
        self.assertEqual(out["a"]["similarita"], 0.8)
        self.assertEqual(out["a"]["canali"], ["denso", "grafo"])
        self.assertEqual(out["b"]["canali"], ["grafo"])

    def test_tetto_per_persona(self):
        cand = [brano(f"c{i}", "p1", "X", 0.9) for i in range(30)] + [brano(f"d{i}", f"q{i}", "Y", 0.6) for i in range(30)]
        out = fondi(cand, [], 20, ["X", "Y"])
        self.assertEqual(sum(r["speaker"]["uri"] == "p1" for r in out), 2)       # quanti/10

    def test_minimo_per_partito(self):
        # 40 brani forti di X, 5 deboli di Z: Z sale a 5 togliendo i peggiori di X, senza superare quanti
        cand = [brano(f"x{i}", f"px{i}", "X", 0.95) for i in range(40)] + [brano(f"z{i}", f"pz{i}", "Z", 0.2) for i in range(5)]
        for r in cand:
            r["score"] = r["similarita"]
        out = scegli(cand, 30, ["X", "Z"])
        self.assertLessEqual(len(out), 30)
        self.assertEqual(sum(r["partito"] == "Z" for r in out), 5)


class Commissioni(unittest.TestCase):
    def test_parole(self):
        out = comm.per_parole("le carceri e la magistratura", rami=("camera", "senato"))
        self.assertEqual(out[0]["nome"], "II COMMISSIONE (GIUSTIZIA)")
        self.assertEqual(out[1], {**out[0], "nome": "2ª Commissione permanente (Giustizia)", "chamber": "senato"})
        # «NATO» dentro «Senato» non vale
        self.assertFalse([x for x in comm.per_parole("il premierato al Senato") if x["nome"].startswith("III ")])

    def test_classifica_dai_progetti(self):
        progetti = [{"number": "1", "cos": 0.6, "commissioni": ["XII Commissione"]},
                    {"number": "2", "cos": 0.58, "commissioni": ["XII Commissione"]},
                    {"number": "3", "cos": 0.4, "commissioni": ["I Commissione"]}]          # oltre il margine
        out = comm.classifica(progetti, "camera")
        self.assertEqual([x["nome"] for x in out], ["XII COMMISSIONE (AFFARI SOCIALI)"])
        self.assertEqual(out[0]["bills"], ["1", "2"])
        sparsi = [{"number": str(i), "cos": 0.5, "commissioni": [n]} for i, n in
                  enumerate(["I Commissione", "II Commissione", "III Commissione"])]
        self.assertEqual(comm.classifica(sparsi, "camera"), [])                     # nessuna ha il 40%


class Statistiche(unittest.TestCase):
    def test_conti(self):
        def e(uri, persona, ramo, data, seduta):
            return {"speech_uri": uri, "speaker": {"uri": persona, "nome": persona}, "partito": "X", "lato": "opposizione",
                    "chamber": ramo, "date": data, "debate": "Dibattito", "url": None, "sitting": seduta,
                    "sitting_number": 1}
        s = statistiche([e("s1", "p1", "camera", "2024-01-01", "c1"), e("s1", "p1", "camera", "2024-01-01", "c1"),
                         e("s2", "p2", "senato", "2025-01-01", "s1")])
        self.assertEqual((s["intervention_count"], s["speaker_count"], s["debate_count"]), (2, 2, 1))
        self.assertEqual((s["first_date"], s["last_date"]), ("2024-01-01", "2025-01-01"))
        self.assertEqual(s["by_chamber"]["camera"], {"intervention_count": 1, "speaker_count": 1})
        self.assertEqual(len(s["sessions_detail"]), 2)           # stesso numero, rami diversi: due sedute
        self.assertEqual(statistiche([])["intervention_count"], 0)


def _connessione():
    try:
        from api.db import connessione
        return connessione()
    except Exception:  # noqa: BLE001 - senza database le prove sul database si saltano
        return None


class SulDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = _connessione()
        if cls.c is None:
            raise unittest.SkipTest("database non raggiungibile")

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_partiti_attesi(self):
        from api.fascicolo.recupero_gruppi import partiti_attesi
        p = partiti_attesi(self.c, ["camera", "senato"])
        self.assertEqual(p["Fratelli d'Italia"]["lato"], "maggioranza")
        self.assertEqual(p["Fratelli d'Italia"]["rami"], ["camera", "senato"])
        self.assertEqual(p["Noi Moderati - MAIE - Centro Popolare"]["lato"], "maggioranza")
        self.assertEqual(p["Partito Democratico - Italia Democratica e Progressista"]["lato"], "opposizione")
        self.assertEqual(p["+Europa - Stati Uniti d'Europa"]["lato"], "misto")
        self.assertIn("Misto", p)

    def test_vicini_e_gruppi_alla_data(self):
        from api.fascicolo.recupero_canali import interventi, vicini
        from api.fascicolo.recupero_gruppi import partiti_attesi
        # il vettore di un brano noto, cercato fra i brani dello stesso intervento: il primo è sé stesso
        uri = "it:camera:19:sed0594:tit00060.sub00040.int00020"
        r = self.c.execute("""SELECT v.embedding::text AS e FROM passage p JOIN passage_vector v ON v.hash = p.hash
                              WHERE p.source = 'speech' AND p.uri = %s AND p.ord = 2""", (uri,)).fetchone()
        if r is None:
            self.skipTest("brano senza vettore")
        out = vicini(self.c, r["e"], ["speech"], 3, rami=["camera"], uris=[uri])
        self.assertEqual((out[0]["uri"], out[0]["ord"]), (uri, 2))
        self.assertAlmostEqual(out[0]["similarita"], 1.0, places=3)
        ev = interventi(self.c, out, partiti_attesi(self.c, ["camera"]))
        self.assertEqual(ev[0]["speaker"]["nome"], "Guido Crosetto")
        self.assertTrue(ev[0]["governo"])
        self.assertEqual(ev[0]["lato"], "governo")
        self.assertEqual(ev[0]["text"], ev[0]["speech_text"][ev[0]["start_char"]:ev[0]["end_char"]])
        self.assertTrue(ev[0]["url"].endswith("#sed0594.stenografico.tit00060.sub00040.int00020"))
        with self.assertRaises(ValueError):
            vicini(self.c, r["e"], ["act"], 3, da=dt.date(2025, 1, 1))

    def test_componente_del_misto(self):
        from api.fascicolo.recupero_canali import interventi
        from api.fascicolo.recupero_gruppi import partiti_attesi
        r = self.c.execute("""SELECT s.uri, p.ord, p.start_char, p.end_char FROM speech s JOIN passage p
                                ON p.source = 'speech' AND p.uri = s.uri
                              WHERE s.person = 'it:person:camera:301577' AND s.uri LIKE 'it:camera:19:sed%%' LIMIT 1""").fetchone()
        if r is None:
            self.skipTest("nessun brano")
        ev = interventi(self.c, [{**r, "source": "speech", "similarita": 0.9}], partiti_attesi(self.c, ["camera"]))[0]
        self.assertEqual(ev["speaker"]["gruppo"], "Misto")
        self.assertEqual(ev["speaker"]["componente"], "+Europa - Stati Uniti d'Europa")
        self.assertEqual(ev["partito"], "+Europa - Stati Uniti d'Europa")
        self.assertEqual(ev["lato"], "misto")


if __name__ == "__main__":
    unittest.main()
