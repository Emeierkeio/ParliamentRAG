"""Le votazioni della Camera lette dal sito, in attesa degli open data: stesso formato, segnate come provvisorie."""

import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from pipeline.carica.postgres import script_voti
from pipeline.fonti import camera_voti, camera_voti_sito as sito
from pipeline.lago import Lago
from pipeline.trasforma.camera_voti import trasforma

PAGINA = (Path(__file__).parent / "fixtures" / "camera_voti_sito_747_53.html").read_text()
NON_SCHEDA = "<html><body><h1>Risultati della ricerca nelle votazioni elettroniche della XIX Legislatura</h1></body></html>"
P = "http://dati.camera.it/ocd/persona.rdf/p"
D = "http://dati.camera.it/ocd/deputato.rdf/d"
NOMI = [("AMICH", "VINCENZO", 1), ("BONAFE'", "SIMONA", 2), ("CUPERLO", "GIOVANNI", 3), ("D'ALFONSO", "LUCIANO", 4),
        ("DE MARIA", "ANDREA", 5), ("DEL BARBA", "MAURO", 6), ("FORNARO", "FEDERICO", 7), ("GIGLIO VIGNA", "ALESSANDRO", 8),
        ("MAGI", "RICCARDO", 9), ("MULE'", "GIORGIO", 10), ("RAMPELLI", "FABIO", 11), ("SASSO", "ROSSANO", 12),
        ("SCHLEIN", "ELENA ETHEL", 13), ("SOUMAHORO", "ABOUBAKAR", 14), ("STEGER", "DIETER", 15), ("ZARATTI", "FILIBERTO", 16)]
PERSONE = [{"persona": f"{P}{n}", "cognome": c, "nome": nome} for c, nome, n in NOMI]
GRUPPI = {f"{D}{n}_19": {"gruppo": "http://dati.camera.it/ocd/gruppoParlamentare.rdf/gr4136"} for _c, _n, n in NOMI}
GRUPPI[f"{D}15_19"] = {"gruppo": "http://dati.camera.it/ocd/gruppoParlamentare.rdf/gr4131",
                       "componente": "http://dati.camera.it/ocd/componenteGruppoMisto.rdf/cgm4137"}


class TestScheda(unittest.TestCase):
    def setUp(self):
        self.s = sito.leggi_scheda(PAGINA)

    def test_intestazione_e_conti(self):
        s = self.s
        self.assertEqual((s["numero"], s["seduta"], s["data"], s["finale"], s["segreta"]), (53, 747, "20261117", True, False))
        self.assertEqual(s["descrizione"], "PDL 2830 E ABB - VOTO FINALE")
        self.assertEqual(s["presidente"], "RAMPELLI FABIO")
        self.assertEqual((s["conti"]["favorevoli"], s["conti"]["contrari"], s["conti"]["astenuti"]), (147, 93, 5))
        self.assertIs(s["approvato"], True)
        self.assertEqual(len(s["voti"]), 16)
        self.assertIn(("CUPERLO GIANNI", "PD-IDP", "Contrario"), s["voti"])

    def test_una_pagina_che_non_e_una_scheda(self):
        self.assertIsNone(sito.leggi_scheda(NON_SCHEDA))

    def test_la_seduta_finisce_alla_prima_scheda_che_manca(self):
        pagine = {1: PAGINA.replace("n.53", "n.1"), 2: PAGINA.replace("n.53", "n.2")}
        schede = sito.schede_seduta(19, 747, pausa=0, pagina=lambda leg, seduta, numero: pagine.get(numero, NON_SCHEDA))
        self.assertEqual([s["numero"] for s in schede], [1, 2])


class TestNomi(unittest.TestCase):
    def test_nome_d_uso_e_apostrofi(self):
        r = sito.riconosci({"CUPERLO GIANNI", "MULE' GIORGIO", "SCHLEIN ELLY", "DE MARIA ANDREA"}, PERSONE)
        self.assertEqual(r, {"CUPERLO GIANNI": f"{P}3", "MULE' GIORGIO": f"{P}10", "SCHLEIN ELLY": f"{P}13", "DE MARIA ANDREA": f"{P}5"})

    def test_cognome_di_due_persone_non_si_sceglie_a_caso(self):
        due = PERSONE + [{"persona": f"{P}99", "cognome": "CUPERLO", "nome": "MARIO"}]
        self.assertNotIn("CUPERLO GIANNI", sito.riconosci({"CUPERLO GIANNI"}, due))
        # se uno solo dei due è in carica, è lui
        self.assertEqual(sito.riconosci({"CUPERLO GIANNI"}, due, in_carica={f"{P}3"}), {"CUPERLO GIANNI": f"{P}3"})

    def test_tipo_dalla_descrizione(self):
        self.assertEqual(sito.tipo_e_titolo("ODG 9/2830 E ABB/4", False, 19),
                         {"tipo": "Ordine del Giorno", "titolo": "Votazione Ordine del giorno 9/2830 E ABB/4 ",
                          "aic": "http://dati.camera.it/ocd/aic.rdf/aic9_02830_004_19"})
        self.assertEqual(sito.tipo_e_titolo("ARTICOLO 2", False, 19)["tipo"], "Articolo")
        self.assertEqual(sito.tipo_e_titolo("PDL 2830 E ABB - EM 1.1002", False, 19)["tipo"], "Altre")
        self.assertEqual(sito.tipo_e_titolo("PDL 2830 E ABB - VOTO FINALE", True, 19)["tipo"], "Finale atto Camera")


class TestFormato(unittest.TestCase):
    def setUp(self):
        self.d = sito.in_formato_ocd([sito.leggi_scheda(PAGINA)], 19, PERSONE, GRUPPI)

    def test_stesso_formato_degli_open_data(self):
        v = self.d["votazioni"][0]
        self.assertEqual(self.d["seduta"], "http://dati.camera.it/ocd/seduta.rdf/s19_747")
        self.assertEqual(self.d["fonte"], "sito")
        self.assertEqual((v["votazione"], v["numero"], v["tipo"], v["finale"], v["approvato"], v["favorevoli"]),
                         ("http://dati.camera.it/ocd/votazione.rdf/vs19_747_053", "747053", "Finale atto Camera", "1", "1", "147"))
        self.assertEqual(v["presidente"], f"{D}11_19")
        self.assertIn("RifVotazione=747_53", v["scheda"])

    def test_la_trasformazione_la_segna_provvisoria(self):
        r = trasforma(camera_voti._comprimi(self.d), {"chiave": "leg19-voti-sed0747"})
        nodo = r["nodi"][0]
        self.assertEqual((nodo["uri"], nodo["source"], nodo["final"], nodo["kind"]), ("it:camera:19:sed0747:v053", "camera_sito", True, "final"))
        self.assertEqual(nodo["acts"], ["ac19_2830"])
        per = {a["from"]: a for a in r["archi"] if a["type"] == "VOTED"}
        self.assertEqual(per["it:person:camera:3"]["result"], "against")            # Cuperlo
        self.assertEqual(per["it:person:camera:4"]["result"], "absent")             # D'Alfonso, non ha partecipato
        self.assertEqual(per["it:person:camera:10"]["result"], "mission")
        self.assertEqual(per["it:person:camera:11"]["result"], "chair")
        self.assertEqual(per["it:person:camera:15"]["group"], "it:camera:19:group:cgm4137")   # la componente del Misto, non il Misto

    def test_l_atto_vale_per_tutta_la_serie(self):
        # la scheda nomina l'atto solo nella prima votazione; mozioni e risoluzioni chiudono la serie
        base = sito.leggi_scheda(PAGINA)
        serie = [{**base, "numero": n, "finale": False, "descrizione": d} for n, d in
                 enumerate(["DDL 3133-A - EM 1.1", "EM 1.2", "ODG 9/3133-A/4", "MOZ 1-346", "EM 2.1", "PDL 2822-B - ART 1"], start=1)]
        d = sito.in_formato_ocd(serie, 19, PERSONE, GRUPPI)
        self.assertEqual([v.get("atto", "").rsplit("/", 1)[-1] for v in d["votazioni"]],
                         ["ac19_3133", "ac19_3133", "", "", "", "ac19_2822-B"])
        self.assertTrue(d["votazioni"][2]["aic"].endswith("aic9_03133_004_19"))

    def test_un_nome_non_riconosciuto_ferma_la_seduta(self):
        with self.assertRaises(RuntimeError):
            sito.in_formato_ocd([sito.leggi_scheda(PAGINA)], 19, PERSONE[:-1], GRUPPI)

    def test_open_data_e_sito_si_sostituiscono(self):
        r = trasforma(camera_voti._comprimi(self.d), {"chiave": "leg19-voti-sed0747"})
        righe = [{"tipo": "ambito", **r["ambito"]}] + [{"tipo": "nodo", **n} for n in r["nodi"]] + [{"tipo": "arco", **a} for a in r["archi"]]
        self.assertIn("DELETE FROM vote WHERE sitting = 'it:camera:19:sed0747' AND source IN ('camera_sito', 'ocd');", script_voti(righe))


class TestGiro(unittest.TestCase):
    """Nel passo dei voti: si prova sul sito solo ciò che gli open data non hanno, e la provvisoria si riscrive."""

    def test_solo_le_sedute_che_mancano(self):
        with tempfile.TemporaryDirectory() as tmp:
            import json
            lago = Lago(Path(tmp))
            lago.salva("camera_ocd", "leg19-persone", json.dumps(PERSONE).encode(), "", "json")
            vera = {"seduta": "http://dati.camera.it/ocd/seduta.rdf/s19_746", "votazioni": [],
                    "voti": [{"votazione": "v", "deputato": d, "tipo": "Favorevole", **g} for d, g in GRUPPI.items()]}
            lago.salva(camera_voti.NOME, "leg19-voti-sed0746", camera_voti._comprimi(vera), "", "json.gz")
            chieste = []

            def schede(leg, seduta, pausa=0, **_):
                chieste.append(seduta)
                return [sito.leggi_scheda(PAGINA)] if seduta == 747 else []
            ctx = types.SimpleNamespace(log=lambda *_: None)
            indice = [{"seduta": "http://dati.camera.it/ocd/seduta.rdf/s19_746"}]
            cfg = {"sito_sedute_avanti": 2, "sito_sedute_indietro": 1, "sito_pausa_secondi": 0}
            with mock.patch.object(sito, "schede_seduta", schede):
                r = camera_voti._dal_sito(ctx, lago, 19, indice, cfg)
                self.assertEqual((r, chieste), ({"dal_sito": 1}, [745, 747, 748]))
                salvata = camera_voti.leggi(lago.leggi(lago.ultimo(camera_voti.NOME, "leg19-voti-sed0747")["file"]))
                self.assertEqual((salvata["fonte"], len(salvata["voti"])), ("sito", 16))
                # quando la seduta arriva negli open data non si chiede più al sito
                chieste.clear()
                camera_voti._dal_sito(ctx, lago, 19, indice + [{"seduta": "http://dati.camera.it/ocd/seduta.rdf/s19_747"}], cfg)
                self.assertEqual(chieste, [748, 749])
                # spento da configurazione
                self.assertEqual(camera_voti._dal_sito(ctx, lago, 19, indice, {"sito_sedute_avanti": 0}), {})


if __name__ == "__main__":
    unittest.main()
