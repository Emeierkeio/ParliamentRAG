"""I termini per gli emendamenti dai sommari: frasi vere dei Bollettini e dei sommari del Senato, casi della misura del 9/11/2026."""

import unittest

from pipeline.termini import concorda, impronta, richiesta
from pipeline.trasforma.termini_emendamenti import estrai


def leggi(testo: str, data: str, ramo: str = "camera") -> list[dict]:
    return estrai({"speech": "it:camera:19:bol:p1", "kind": "summary", "chamber": ramo, "date": data, "body_name": "X",
                   "acts": [{"ref": "ac:3120", "act": "it:camera:19:ac:3120"}], "text": testo})


def unico(testo: str, data: str) -> dict:
    r = leggi(testo, data)
    assert len(r) == 1, r
    return r[0]


class TestRegole(unittest.TestCase):
    def test_concorrenza(self):
        e = unico("Nessuno chiedendo di intervenire, dichiara concluso l'esame preliminare del provvedimento e ricorda che il termine "
                  "per la presentazione delle proposte emendative è fissato alle ore 12 di lunedì 9 novembre.", "2026-11-04")
        self.assertEqual((e["esito"], e["scadenza"], e["ora"], e["evento"], e["tipo"]), ("estratto", "2026-11-09", "12:00", "fissato", "emendamenti"))

    def test_domani_e_subemendamenti(self):
        e = unico("Evidenzia che il termine per la presentazione di subemendamenti all'emendamento della relatrice è fissato alle ore 14 "
                  "di domani, mercoledì 4 giugno.", "2025-06-03")
        self.assertEqual((e["scadenza"], e["ora"], e["tipo"]), ("2025-06-04", "14:00", "subemendamenti"))

    def test_proroga_salta_la_data_vecchia(self):
        e = unico("Il PRESIDENTE, valutate le richieste provenienti anche da altri Gruppi parlamentari, propone di posticipare il termine "
                  "per la presentazione di eventuali ordini del giorno ed emendamenti al disegno di legge n. 808, già fissato per martedì "
                  "21 novembre alle ore 18, a lunedì 27 novembre alle ore 15. La Commissione conviene.", "2023-11-15")
        self.assertEqual((e["evento"], e["scadenza"], e["ora"]), ("prorogato", "2023-11-27", "15:00"))

    def test_richiesta_non_e_decisione(self):
        e = unico("Il senatore MARTELLA ( PD-IDP ) chiede di posticipare il termine per la presentazione degli emendamenti alle ore 14 "
                  "di lunedì 9 dicembre.", "2024-12-05")
        self.assertEqual((e["esito"], e["motivo"]), ("scartato", "richiesta o proposta, non decisione"))

    def test_refuso_della_fonte(self):
        e = unico("Marco OSNATO, presidente, ricorda che mercoledì 9 maggio è scaduto il termine per la presentazione di emendamenti.",
                  "2024-05-21")
        self.assertEqual(e["esito"], "scartato")
        self.assertIn("giorno della settimana incoerente", e["motivo"])

    def test_al_termine_vuol_dire_alla_fine(self):
        self.assertEqual(leggi("Nella giornata di domani, martedì 6 dicembre, al termine delle votazioni pomeridiane dell'Assemblea, "
                               "avranno luogo le votazioni sugli emendamenti.", "2022-12-05"), [])

    def test_anno_dopo(self):
        e = unico("Il termine per la presentazione di proposte emendative è fissato alle ore 12 di giovedì 8 gennaio.", "2025-12-16")
        self.assertEqual(e["scadenza"], "2026-01-08")

    def test_scaduto_con_conto(self):
        e = unico("Il PRESIDENTE comunica che, alla scadenza del termine fissato alle ore 17 di ieri, sono stati presentati 378 emendamenti "
                  "e 31 ordini del giorno pubblicati in allegato.", "2026-02-25")
        self.assertEqual((e["evento"], e["scadenza"], e["ora"], e["presentati"]), ("scaduto", "2026-02-24", "17:00", 378))

    def test_annunciato(self):
        e = unico("Avverte che il termine per la presentazione delle proposte emendative sarà fissato nella riunione dell'Ufficio di "
                  "Presidenza, integrato dai rappresentanti dei gruppi, già convocata per la giornata di domani.", "2025-11-25")
        self.assertEqual((e["evento"], e["esito"]), ("annunciato", "senza data"))

    def test_solo_sommari(self):
        r = estrai({"speech": "s", "kind": "verbatim", "chamber": "camera", "date": "2026-11-03", "acts": [],
                    "text": "il termine degli emendamenti scadrà alle ore 12 di lunedì prossimo."})
        self.assertEqual(r, [])


class TestSecondaLettura(unittest.TestCase):
    C = {"hash": "h", "scadenza": "2026-11-09", "ora": None, "frase": "è fissato alle ore 12 di lunedì 9 novembre", "date": "2026-11-04",
         "body_name": "X Commissione", "item_title": "C. 3120", "paragrafo": "…"}

    def test_coincide_e_prende_l_ora_scritta(self):
        self.assertEqual(concorda(self.C, {"decided": True, "date": "2026-11-09", "time": "12:00", "event": "fixed"}), (True, "12:00"))

    def test_data_diversa(self):
        self.assertEqual(concorda(self.C, {"decided": True, "date": "2026-11-10", "time": None, "event": "fixed"}), (False, None))

    def test_non_deciso(self):
        self.assertEqual(concorda(self.C, {"decided": False, "date": "2026-11-09", "time": None, "event": "other"}), (False, None))

    def test_ora_non_scritta_nella_frase(self):
        self.assertEqual(concorda(self.C, {"decided": True, "date": "2026-11-09", "time": "18:00", "event": "fixed"}), (True, None))

    def test_ore_diverse(self):
        c = {**self.C, "ora": "12:00"}
        self.assertEqual(concorda(c, {"decided": True, "date": "2026-11-09", "time": "10:00", "event": "fixed"}), (False, None))

    def test_richiesta_senza_la_proposta_delle_regole(self):
        r = richiesta(self.C)
        testo = r["body"]["messages"][1]["content"]
        self.assertIn("Seduta di mercoledì 2026-11-04", testo)
        self.assertNotIn("2026-11-09", testo)            # il modello non vede la data delle regole
        self.assertEqual((r["custom_id"], r["url"]), ("h", "/v1/chat/completions"))

    def test_impronta_stabile(self):
        self.assertEqual(impronta("a", "b"), impronta("a", "b"))
        self.assertEqual(len(impronta("a", "b")), 16)


if __name__ == "__main__":
    unittest.main()
