"""Verifica delle tre garanzie (api/fascicolo/verifica.py): voci, nomi, ambito, posizioni e rapporto senza database;
poi una risposta con citazioni vere e una con un gruppo mancante sul database, con il vettore di un brano già nel
database come domanda (niente chiamate al modello). I test sul database si saltano se Postgres non risponde."""

import unittest
from unittest import mock

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""

from api import pubblico
from api.fascicolo import autorevolezza as A
from api.fascicolo import verifica as V
from tests.test_fascicolo_autorevolezza import vettore_di_prova


def P(uri, given, family, gruppo=None, componente=None, governo=False, ramo="camera"):
    return V.Persona(uri, given, family, gruppo, componente, governo, ramo)


class TestVoci(unittest.TestCase):
    def test_voce_del_gruppo(self):
        self.assertEqual(V.voce_del_gruppo("Fratelli d'Italia", None, False).key, "FdI")
        self.assertEqual(V.voce_del_gruppo("Lega Salvini Premier - Partito Sardo d'Azione", None, False).key, "Lega")
        self.assertEqual(V.voce_del_gruppo("Misto", "+Europa - Stati Uniti d'Europa", False).key, "+Europa")
        self.assertEqual(V.voce_del_gruppo("Misto", "Alleanza Verdi e Sinistra", False).key, "AVS")   # componente col nome di un gruppo
        self.assertEqual(V.voce_del_gruppo("Civici d'Italia-UDC-Noi Moderati (Noi con l'Italia)", None, False).key, "NM")
        self.assertEqual(V.voce_del_gruppo("Misto", None, False).key, "Misto NI")          # nel Misto senza componente
        self.assertEqual(V.voce_del_gruppo("Fratelli d'Italia", None, True).key, "Governo")

    def test_nominata_come(self):
        lega = next(v for v in V.VOCI if v.key == "Lega")
        azione = next(v for v in V.VOCI if v.key == "Azione")
        self.assertIsNone(V.nominata_come("Il decreto lega la proposta al bilancio.", lega))
        self.assertEqual(V.nominata_come("Per la Lega il testo va bene.", lega), "Lega")
        self.assertIsNone(V.nominata_come("Serve un'azione del governo.", azione))
        self.assertEqual(V.nominata_come("I Fratelli d’Italia votano a favore.", V.VOCI[0]), "Fratelli d'Italia")

    def test_etichette_e_nomi(self):
        self.assertEqual(V.etichetta_gruppo("MISTO", None), V.MISTO_SENZA_COMPONENTE)
        self.assertEqual(V.etichetta_gruppo(None, "SUD CHIAMA NORD"), "Sud Chiama Nord")
        self.assertEqual(V.nome_camera("URZI'"), "URZÌ")
        testo = "Come ha detto Scotto, «un testo da citare qui»."
        k = testo.index("«")
        self.assertTrue(V.nominato_vicino(testo, k, k + 24, "Scotto"))
        self.assertFalse(V.nominato_vicino(testo, k, k + 24, "Rossi"))
        self.assertEqual(V.ruolo_nel_dibattito("Sottosegretario di Stato per l'economia", False), "governo")
        self.assertEqual(V.ruolo_nel_dibattito("relatrice", False), "relatore")
        self.assertIsNone(V.ruolo_nel_dibattito("PRESIDENTE", False))

    def test_ambito(self):
        self.assertEqual(V.rami_attesi(["camera", "senato"], "Cosa ha detto il Senato sul ddl?", "", []), (["senato"], "question"))
        self.assertEqual(V.rami_attesi(["camera", "senato"], "camera di commercio e imprese", "", []), (["camera", "senato"], "both"))
        self.assertEqual(V.rami_attesi(["camera", "senato"], "salario minimo", "vedi www.camera.it/leg19", []), (["camera"], "answer"))
        self.assertEqual(V.rami_attesi(["camera"], "senatori", "", []), (["camera"], "request"))
        self.assertEqual(V.tema_dalla_risposta("Il tema è chiaro. Lui disse «una cosa». Poi altro.", 20), "Il tema è chiaro.")


class TestPersoneNominate(unittest.TestCase):
    PERSONE = [P("a", "Arturo", "Scotto", "Partito Democratico - Italia Democratica e Progressista"),
               P("b", "Mario", "Rossi", "Fratelli d'Italia"), P("c", "Anna", "Rossi", "Movimento 5 Stelle"),
               P("d", "Matteo", "Salvini", "Lega - Salvini Premier", governo=True),
               P("e", "Riccardo", "Magi", "Misto", "+Europa - Stati Uniti d'Europa")]

    def nomi(self, testo):
        return {x["person_id"]: x for x in V.persone_nominate(testo, self.PERSONE)}

    def test_nome_cognome_e_omonimi(self):
        n = self.nomi("Arturo Scotto e Rossi (M5S) ne hanno parlato; anche Magi.")
        self.assertEqual(set(n), {"a", "c", "e"})
        self.assertEqual(n["a"]["matched_by"], "full_name")
        self.assertEqual(n["c"]["matched_by"], "surname_and_group")
        self.assertEqual(n["e"]["group"], "+Europa (Misto)")                   # la componente, non il Misto
        self.assertEqual(self.nomi("Ne ha parlato Rossi."), {})                 # due Rossi: non si sa chi

    def test_maschere_e_gruppo_sbagliato(self):
        self.assertEqual(self.nomi("Il gruppo Lega - Salvini Premier vota contro."), {})
        self.assertEqual(self.nomi("Lui disse: «come ricordava Scotto ieri»."), {})
        self.assertEqual(self.nomi("lo scotto da pagare"), {})                   # minuscolo: non è un nome
        n = self.nomi("Arturo Scotto (FdI) ha detto.")
        self.assertTrue(n["a"]["group_mismatch"])
        self.assertFalse(self.nomi("Matteo Salvini (Governo) ha risposto.")["d"]["group_mismatch"])

    def test_cognome_che_fa_da_nome_o_da_nome_comune(self):
        persone = self.PERSONE + [P("g", "Stefano", "Graziano", "Partito Democratico - Italia Democratica e Progressista"),
                                  P("h", "Graziano", "Delrio", "Partito Democratico - Italia Democratica e Progressista", ramo="senato"),
                                  P("p", "Renzo", "Piano", None, ramo="senato"), P("r", "Raffaele", "Bruno", "Movimento 5 Stelle")]
        nomi = lambda t: set(x["person_id"] for x in V.persone_nominate(t, persone))
        self.assertEqual(nomi("Al Senato, **Graziano Delrio** dichiara."), {"h"})           # nome di battesimo, non Stefano Graziano
        self.assertEqual(nomi("Bruno Tabacci afferma che la legge è sbagliata."), set())    # non Raffaele Bruno
        self.assertEqual(nomi("gli obiettivi del Piano nazionale e completare il Piano"), set())
        self.assertEqual(nomi("Per il M5S ha parlato Bruno, poi Graziano (PD-IDP)."), {"r", "g"})   # il cognome da solo conta ancora
        self.assertEqual(nomi("Lo ha detto Piano."), {"p"})


class TestRapporto(unittest.TestCase):
    VOCI = [v for v in V.VOCI if v.key in ("FdI", "PD", "SCN", "Governo")]

    def citata(self, pid, nome, voce, attribuita=True, stato="exact"):
        return {"text": "…", "start": 0, "end": 1, "status": stato, "attributed": attribuita,
                "speech": {"person_id": pid, "uri": pid, "name": nome, "group": voce, "voice": voce, "speaking_role": None}}

    def test_posizioni_fra_chi_ha_parlato(self):
        classifica = [{"uri": u, "punteggio": s} for u, s in (("a", .9), ("b", .8), ("c", .7), ("d", .6))]
        voce_di = {"a": "PD", "b": "PD", "c": "PD", "d": "FdI"}
        t = V.posizioni(classifica, voce_di, {"b": None, "c": None, "d": "PD"})
        self.assertEqual((t["b"]["rank"], t["c"]["rank"], t["d"]["rank"]), (1, 2, 3))   # d ha parlato per il PD allora
        self.assertNotIn("a", t)
        self.assertEqual(V.posizioni(classifica, voce_di, None)["a"]["pool_size"], 3)

    def test_rapporto(self):
        citate = [self.citata("a", "Arturo Scotto", "PD"), self.citata("x", "Ignoto", "FdI", attribuita=False)]
        classifica = [{"uri": "a", "punteggio": .9}, {"uri": "x", "punteggio": .5}]
        r = V.rapporto("Il PD e il Governo.", citate, [], self.VOCI, classifica, "tema", "question", [],
                       {"a": "PD", "x": "FdI"}, ["camera"], {"a": None, "x": None}, "request")
        stati = {g["key"]: g["status"] for g in r["groups"]["items"]}
        self.assertEqual(stati, {"FdI": "missing", "PD": "quoted", "SCN": "silent", "Governo": "named"})
        self.assertEqual(r["summary"], {"groups": "fail", "authority": "pass", "quotes": "fail"})   # x non è nominata
        self.assertEqual((r["groups"]["named"], r["groups"]["total"], r["groups"]["silent"]), (2, 4, 1))
        self.assertEqual(r["scope"], "Camera dei deputati, XIX legislatura")
        voce = r["authority"]["voices"][0]
        self.assertEqual((voce["rank"], voce["pool_size"], voce["authoritative"], voce["pool"]), (1, 1, True, "speakers_on_topic"))

    def test_fuori_tema_e_senza_classifica(self):
        nominata = {"person_id": "z", "uri": "z", "name": "Zeta", "group": "PD", "voice": "PD", "in_government": False, "group_mismatch": False}
        r = V.rapporto("Zeta", [], [], self.VOCI, [{"uri": "z", "punteggio": .1}], "t", "question", [nominata], {"z": "PD"},
                       ["camera"], {}, None)
        self.assertEqual(r["authority"]["voices"][0]["on_topic"], False)
        self.assertEqual(r["summary"]["authority"], "fail")
        r = V.rapporto("Zeta", [], [], self.VOCI, None, "t", "question", [nominata], {"z": "PD"}, ["camera"], None)
        self.assertEqual((r["summary"]["authority"], r["authority"]["available"]), ("na", False))
        self.assertNotIn("silent", {g["status"] for g in r["groups"]["items"]})       # senza chi ha parlato, niente mute


RISPOSTA_CITAZIONI = ("Sul salario minimo alla Camera, Arturo Scotto (PD) ha detto: «se 22 Paesi su 27 hanno il salario minimo "
                      "legale, non è perché sono impazziti». Lorenzo Malagola (FdI) ha risposto che «il salario giusto è "
                      "pienamente alternativo al salario minimo professato dalla sinistra». Secondo Tucci «il salario "
                      "minimo è una misura che abbiamo sempre sostenuto con forza».")
RISPOSTA_GRUPPI = ("Sul salario minimo sono intervenuti FdI, PD, M5S, Forza Italia, AVS, Azione, Italia Viva, Noi Moderati, "
                   "+Europa, Futuro Nazionale, le Minoranze linguistiche, Sud chiama Nord e il Governo.")


@unittest.skipIf(C is None, f"database non raggiungibile: {MOTIVO}")
class TestSulDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q = vettore_di_prova(C)
        if cls.q is None:
            raise unittest.SkipTest("nessun vettore di prova")

    def verifica(self, risposta, domanda="salario minimo (prova)", rami=("camera",)):
        with mock.patch.object(A, "vettore", lambda d, ip=None: self.q), mock.patch.object(A, "_vettori_parole", lambda pr, ip: {}):
            return V.verifica(C, risposta, domanda, list(rami))

    def test_citazioni_vere(self):
        r = self.verifica(RISPOSTA_CITAZIONI)
        stati = [q["status"] for q in r["quotes"]["items"]]
        self.assertEqual(stati, ["exact", "exact", "not_found"])
        self.assertEqual(r["summary"]["quotes"], "fail")
        scotto = r["quotes"]["items"][0]["speech"]
        self.assertEqual((scotto["name"], scotto["voice"], scotto["chamber"]), ("Arturo Scotto", "PD", "camera"))
        self.assertTrue(r["quotes"]["items"][0]["attributed"])
        gruppi = {g["key"]: g["status"] for g in r["groups"]["items"]}
        self.assertEqual((gruppi["PD"], gruppi["FdI"], gruppi["M5S"], gruppi["Lega"]), ("quoted", "quoted", "named", "missing"))
        self.assertTrue(r["authority"]["available"])
        voci = {v["name"]: v for v in r["authority"]["voices"]}
        self.assertEqual(set(voci), {"Arturo Scotto", "Lorenzo Malagola", "Riccardo Tucci"})
        self.assertEqual(voci["Riccardo Tucci"]["source"], "named")
        self.assertTrue(all(v.get("rank") and v["pool"] == "speakers_on_topic" for v in voci.values()))

    def test_gruppo_mancante(self):
        r = self.verifica(RISPOSTA_GRUPPI)
        # i non iscritti del Misto mancano o sono muti secondo chi ha parlato del tema del vettore di prova
        mancanti = [g["key"] for g in r["groups"]["items"] if g["status"] == "missing" and g["key"] != "Misto NI"]
        self.assertEqual(mancanti, ["Lega"])
        self.assertEqual(r["summary"]["groups"], "fail")
        self.assertEqual(r["summary"]["authority"], "na")                      # nessuna persona citata o nominata
        self.assertTrue(all(g["key"] != "Misto" for g in r["groups"]["items"]))  # il Misto non è una voce: le componenti sì

    def test_verify_answer_collegata(self):
        with mock.patch.object(A, "vettore", lambda d, ip=None: self.q), mock.patch.object(A, "_vettori_parole", lambda pr, ip: {}):
            r = pubblico.verify_answer(C, pubblico.VerifyAnswer(answer=RISPOSTA_GRUPPI, question="salario minimo (prova)",
                                                                chamber="camera"))
        self.assertTrue(r["verdict"][0].startswith("❌ All groups:"))
        self.assertIn("missing: Lega", r["verdict"][0])
        self.assertEqual([g for g in r["groups"]["missing"] if g != "Misto, non iscritti"], ["Lega - Salvini Premier"])
        self.assertTrue(r["authority"]["available"])


if __name__ == "__main__":
    unittest.main()
