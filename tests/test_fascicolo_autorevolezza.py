"""Autorevolezza (api/fascicolo/autorevolezza.py): le funzioni della formula, con i pesi e i parametri del backend
precedente, e la classifica del sito sul database. Il test sul database usa come domanda il vettore di un brano già
nel database (niente chiamate al modello) e si salta se Postgres non risponde."""

import datetime as dt
import re
import unittest
from unittest import mock

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""

from api.fascicolo import autorevolezza as A

OGGI = dt.date(2026, 11, 4)


class TestFormula(unittest.TestCase):
    def test_pesi_del_modello(self):
        self.assertEqual(A.PESI, {"profession": 0.15, "education": 0.10, "committee": 0.25, "acts": 0.20,
                                  "interventions": 0.25, "role": 0.05})
        self.assertAlmostEqual(sum(A.PESI.values()), 1.0)
        self.assertEqual((A.EMIVITA_ATTI, A.EMIVITA_INTERVENTI, A.TETTO, A.K_BRANI, A.K_ATTI), (548, 548, 0.8, 2000, 500))

    def test_percentile_come_numpy(self):
        v = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
        self.assertAlmostEqual(A.percentile(v, 50), 3.5)           # numpy.percentile(v, 50)
        self.assertAlmostEqual(A.percentile(v, 95), 7.95)          # numpy.percentile(v, 95)
        self.assertEqual(A.percentile([2.0], 95), 2.0)

    def test_relativo_simile(self):
        r = A.relativo_simile({"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4, "e": 0.5})
        self.assertEqual(r["a"], 0.0)                             # sotto la mediana
        self.assertEqual(r["c"], 0.0)                             # la mediana
        self.assertEqual(r["e"], 1.0)
        self.assertTrue(0 < r["d"] < 1)
        self.assertEqual(A.relativo_simile({"a": 0.2, "b": 0.2}), {"a": 1.0, "b": 1.0})
        self.assertEqual(A.relativo_simile({"a": 0.1, "b": 0.3}, 50, 100)["b"], 1.0)

    def test_relativo_log(self):
        r = A.relativo_log({"a": 4.0, "b": 1.0, "c": 0.0})
        self.assertEqual(r["a"], 1.0)
        self.assertAlmostEqual(r["b"], 0.4307, places=4)          # log(2)/log(5)
        self.assertNotIn("c", r)
        self.assertEqual(A.relativo_log({}), {})

    def test_pesi_tema(self):
        sempre = lambda sid, quando: True                          # noqa: E731
        righe = [{"sid": "a", "item": "i1", "date": OGGI, "score": 0.9},
                 {"sid": "a", "item": "i1", "date": OGGI, "score": 0.5},   # stesso intervento: conta il brano migliore
                 {"sid": "b", "item": "i2", "date": OGGI, "score": 0.5},
                 {"sid": "c", "item": "i3", "date": OGGI + dt.timedelta(days=1), "score": 0.9},   # dopo il riferimento
                 {"sid": "d", "item": "i4", "date": OGGI - dt.timedelta(days=548), "score": 0.9},  # una emivita fa
                 {"sid": "e", "item": "i5", "date": None, "score": 0.9}]
        w = A.pesi_tema(righe, OGGI, 548, sempre, 0.5)
        self.assertAlmostEqual(w["a"], 1.0)
        self.assertAlmostEqual(w["b"], 0.5)                        # il più lontano conta metà del più vicino
        self.assertNotIn("c", w)
        self.assertAlmostEqual(w["d"], 0.5)
        self.assertAlmostEqual(w["e"], 0.5)                        # senza data: SENZA_DATA
        firma = A.pesi_tema(righe[:1], OGGI, 548, sempre, 0.5, lambda r: 0.3)
        self.assertAlmostEqual(firma["a"], 0.3)
        self.assertEqual(A.pesi_tema(righe, OGGI, 548, lambda s, q: s != "a", 0.5).get("a"), None)

    def test_ruolo(self):
        governo = [{"title": "undersecretary", "label": "Sottosegretario", "start": dt.date(2022, 11, 1), "end": None},
                   {"title": "minister", "label": "Ministro", "start": dt.date(2020, 1, 1), "end": dt.date(2021, 1, 1)}]
        self.assertEqual(A.punteggio_ruolo(governo, [], {}, OGGI), (0.7, "Sottosegretario"))    # il ministero è finito
        cariche = [{"title": "chair", "body": "b1", "body_name": "XI COMMISSIONE", "start": dt.date(2022, 11, 1), "end": None}]
        punti, nome = A.punteggio_ruolo([], cariche, {"b1": 1.0}, OGGI)
        self.assertAlmostEqual(punti, 0.91)                        # 0,7 × (1 + 0,3)
        self.assertEqual(nome, "Presidente XI COMMISSIONE")
        self.assertEqual(A.punteggio_ruolo([], [{**cariche[0], "title": "quaestor"}], {}, OGGI), (0.3, None))
        sedi = [{"body": "b1", "start": None, "end": dt.date(2023, 1, 1)}, {"body": "b2", "start": None, "end": None}]
        self.assertEqual(A.punteggio_commissione(sedi, {"b1": 1.0, "b2": 0.4}, OGGI), 0.4)

    def test_pesi_della_richiesta(self):
        self.assertIsNone(A.pesi_richiesta(None))
        self.assertIsNone(A.pesi_richiesta({"profession": -1}))
        self.assertIsNone(A.pesi_richiesta({"profession": 0}))
        self.assertIsNone(A.pesi_richiesta({"profession": "x"}))
        p = A.pesi_richiesta({"interventions": 2, "acts": 2})
        self.assertEqual(p, {"profession": 0.0, "education": 0.0, "committee": 0.0, "acts": 0.5, "interventions": 0.5, "role": 0.0})

    def test_istruzione_non_pubblicata(self):
        p = A.pesi_persona(True, A.PESI)
        self.assertEqual(p["education"], 0.0)
        self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertAlmostEqual(p["committee"], 0.25 / 0.9)
        self.assertIs(A.pesi_persona(False, A.PESI), A.PESI)

    def test_schieramenti(self):
        lati = {"fdi": A.MAGGIORANZA, "pd": A.OPPOSIZIONE, "misto": A.MISTO}
        lato = lambda g, il=None: lati.get(g, A.OPPOSIZIONE)        # noqa: E731
        gruppi = [{"grp": "pd", "start": dt.date(2022, 10, 13), "end": dt.date(2024, 1, 1)},
                  {"grp": "fdi", "start": dt.date(2024, 1, 2), "end": None}]
        self.assertFalse(A.valida(gruppi, lato, "fdi", dt.date(2023, 5, 1)))      # da opposizione a maggioranza: non vale
        self.assertTrue(A.valida(gruppi, lato, "fdi", dt.date(2025, 5, 1)))
        self.assertFalse(A.valida(gruppi, lato, "fdi", None))                     # senza data, ha cambiato: non vale
        self.assertTrue(A.valida([{**gruppi[0], "grp": "misto"}, gruppi[1]], lato, "fdi", dt.date(2023, 5, 1)))
        self.assertTrue(A.valida([], lato, None, dt.date(2023, 5, 1)))

    def test_lato_dalle_fiducie(self):
        fiducie = [(dt.date(2026, 3, 1), 10, 12), (dt.date(2025, 1, 1), 0, 12)]
        self.assertEqual(A.lato_alla_data(fiducie, OGGI, A.OPPOSIZIONE), A.MAGGIORANZA)       # 10 su 12 presenti
        self.assertEqual(A.lato_alla_data(fiducie, dt.date(2025, 6, 1), A.MAGGIORANZA), A.OPPOSIZIONE)
        self.assertEqual(A.lato_alla_data([(dt.date(2026, 3, 1), 6, 12)], OGGI, A.MAGGIORANZA), A.OPPOSIZIONE)  # metà: no
        self.assertEqual(A.lato_alla_data(fiducie, dt.date(2028, 1, 1), A.MISTO), A.MISTO)     # niente fiducie: la riserva
        self.assertEqual(A.lato_alla_data(fiducie, OGGI, A.OPPOSIZIONE, misto=True), A.MISTO)

    def test_organi(self):
        self.assertEqual(A.temi_organo("XI Commissione")[0], "XI COMMISSIONE (LAVORO PUBBLICO E PRIVATO)")
        self.assertIn("salario minimo", A.temi_organo("XI Commissione")[1])
        self.assertEqual(A.temi_organo("I Commissione")[0][:15], "I COMMISSIONE (")      # non «II» né «III»
        self.assertTrue(A.temi_organo("Comitato per la legislazione")[1])
        self.assertTrue(A.temi_organo("Comitato parlamentare di controllo sull'attuazione dell'Accordo di Schengen, di "
                                      "vigilanza sull'attività di Europol, di controllo e vigilanza in materia di "
                                      "immigrazione (Comitato parlamentare Schengen, Europol e immigrazione)")[1])
        self.assertTrue(A.tematico("2ª Commissione permanente (Giustizia)"))
        self.assertTrue(A.tematico("Commissione Parlamentare di Inchiesta sul Femminicidio"))
        self.assertFalse(A.tematico("Giunta per il Regolamento"))
        self.assertFalse(A.tematico("Ufficio di Presidenza"))

    def test_id_del_sito(self):
        self.assertEqual(A.id_sito({"uri": "u", "camera_id": "300469"}, "camera"), "http://dati.camera.it/ocd/persona.rdf/p300469")
        self.assertEqual(A.id_sito({"uri": "u", "camera_id": "1", "senato_id": "36449"}, "senato"), "http://dati.senato.it/senatore/36449")


def vettore_di_prova(c) -> str:
    """Il vettore del titolo di un progetto di legge sul salario minimo: una domanda «salario minimo» senza modello."""
    r = c.execute("""SELECT v.embedding::text AS e FROM passage p JOIN passage_vector v ON v.hash = p.hash JOIN act a ON a.uri = p.uri
                     WHERE p.source = 'act_title' AND a.title ILIKE '%%salario minimo%%' ORDER BY a.date LIMIT 1""").fetchone()
    return r["e"] if r else None


@unittest.skipIf(C is None, f"database non raggiungibile: {MOTIVO}")
class TestMaggioranza(unittest.TestCase):
    """Lo schieramento dai voti di fiducia, nei due rami: Noi Moderati sostiene il governo pur senza ministri."""
    ATTESI = {A.MAGGIORANZA: ("Fratelli d'Italia", "Lega", "Forza Italia", "Noi Moderati"),
              A.OPPOSIZIONE: ("Partito Democratico", "Movimento 5 Stelle", "Alleanza Verdi e Sinistra")}

    def test_camera_e_senato(self):
        pr = A.profili(C)
        for ramo in ("camera", "senato"):
            gruppi = [g for g in pr.gruppi.values() if g["chamber"] == ramo and g["kind"] == "group"]
            for lato, nomi in self.ATTESI.items():
                for nome in nomi:
                    g = next((g for g in gruppi if nome.lower() in g["name"].lower()), None)
                    if g is None and nome == "Alleanza Verdi e Sinistra" and ramo == "senato":   # al Senato è nel Misto
                        g = next(g for g in pr.gruppi.values() if g["chamber"] == ramo and nome in g["name"])
                    with self.subTest(ramo=ramo, gruppo=nome):
                        self.assertIsNotNone(g)
                        self.assertEqual(pr.lato(g["uri"]), lato)
        misto = next(g for g in pr.gruppi.values() if g["chamber"] == "camera" and g["name"] == "Misto")
        self.assertEqual(pr.lato(misto["uri"]), A.MISTO)


@unittest.skipIf(C is None, f"database non raggiungibile: {MOTIVO}")
class TestClassifica(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q = vettore_di_prova(C)
        if cls.q is None:
            raise unittest.SkipTest("nessun vettore di prova")
        with mock.patch.object(A, "vettore", lambda d, ip=None: cls.q), mock.patch.object(A, "_vettori_parole", lambda pr, ip: {}):
            cls.r = A.classifica(C, "salario minimo (prova)", "camera")
            cls.voci = A.punteggi(C, "salario minimo (prova)", A._Ramo(("camera",)))

    def test_forma_della_vecchia_rotta(self):
        self.assertEqual(set(self.r) - {"cached"}, {"topic", "count", "computation_time_ms", "deputies"})
        self.assertEqual(self.r["count"], len(self.r["deputies"]))
        d = self.r["deputies"][0]
        self.assertEqual(set(d), {"id", "first_name", "last_name", "group", "coalition", "authority_score", "score_breakdown",
                                  "photo", "camera_profile_url", "profession", "education", "committee", "committees",
                                  "institutional_role"})
        self.assertEqual(set(d["score_breakdown"]), {"speeches", "acts", "committee", "profession", "education", "role"})
        punti = [x["authority_score"] for x in self.r["deputies"]]
        self.assertEqual(punti, sorted(punti, reverse=True))
        self.assertTrue(all(re.search(r"p(\d+)$", x["id"]) for x in self.r["deputies"]))    # il sito ricava l'id così
        self.assertTrue(all(0 <= v <= A.TETTO for x in self.r["deputies"] for v in x["score_breakdown"].values()))

    def test_misto_per_componente(self):
        gruppi = {x["group"] for x in self.r["deputies"]}
        self.assertIn("Misto", gruppi)                              # chi non è iscritto a una componente
        self.assertTrue(any("Europa" in g for g in gruppi))          # +Europa con il suo nome, non «Misto»
        self.assertIn(self.r["deputies"][0]["coalition"], (A.MAGGIORANZA, A.OPPOSIZIONE, A.MISTO))

    def test_sul_tema_conta(self):
        primi = self.r["deputies"][:20]
        self.assertTrue(any("XI COMMISSIONE" in (x["committee"] or "") for x in primi))
        self.assertTrue(all(x["score_breakdown"]["speeches"] > 0 or x["score_breakdown"]["acts"] > 0 for x in primi[:10]))

    def test_punteggi_e_rango(self):
        per_voce = {}
        for x in self.voci:
            per_voce.setdefault(x["voce"], []).append(x)
        for xs in per_voce.values():
            self.assertEqual([x["rango"] for x in xs], list(range(1, len(xs) + 1)))
            self.assertTrue(all(x["nel_gruppo"] == len(xs) for x in xs))
        x = self.voci[0]
        self.assertEqual(set(x["componenti"]), set(A.COMPONENTI))
        self.assertAlmostEqual(x["punteggio"], sum(A.PESI[k] * v for k, v in x["componenti"].items()), places=6)

    def test_persone_scelte_e_cache(self):
        uno = self.voci[3]
        with mock.patch.object(A, "vettore", lambda d, ip=None: self.q), mock.patch.object(A, "_vettori_parole", lambda pr, ip: {}):
            solo = A.punteggi(C, "salario minimo (prova)", A._Ramo(("camera",)), persone=[uno["uri"], "it:person:camera:0"])
            self.assertTrue(A.classifica(C, "salario minimo (prova)", "camera")["cached"])
        self.assertEqual(solo[0]["punteggio"], uno["punteggio"])
        self.assertFalse(solo[1]["disponibile"])


if __name__ == "__main__":
    unittest.main()
