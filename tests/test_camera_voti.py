"""I voti OCD di una seduta diventano votazioni e voti dei singoli, e i conti tornano (seduta 8, 2 votazioni)."""

import gzip
import json
import unittest
from collections import Counter
from pathlib import Path

from pipeline.carica.postgres import script_voti
from tests import db_locale
from pipeline.controlli.uscite import _regole_voti, avvisi_voti
from pipeline.trasforma.camera_voti import aic_dalla_descrizione, atti_dalla_descrizione, esito, trasforma, uri_votazione

SCHEMA = (Path(__file__).parent.parent / "schema" / "v3.sql").read_text()

CORPO = (Path(__file__).parent / "fixtures" / "camera_voti_leg19_sed0008.json.gz").read_bytes()


class TestVoti(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-voti-sed0008"})
        self.voti = [a for a in self.r["archi"] if a["type"] == "VOTED"]

    def test_struttura(self):
        self.assertEqual(len(self.r["nodi"]), 2)
        self.assertEqual(len(self.voti), 798)
        self.assertTrue(all(a["from"].startswith("it:person:camera:") for a in self.voti))
        self.assertEqual(self.r["ambito"]["sitting"], "it:camera:19:sed0008")

    def test_totali_tornano(self):
        self.assertEqual(_regole_voti(self.r["nodi"], self.r["archi"]), [])

    def test_totali_sbagliati_sono_un_avviso(self):
        nodi = [dict(n) for n in self.r["nodi"]]
        nodi[0]["favor"] += 1
        self.assertEqual(_regole_voti(nodi, self.r["archi"]), [])
        self.assertEqual(len(avvisi_voti(nodi, self.r["archi"])), 1)
        self.assertTrue(all(n["ballots_match"] for n in self.r["nodi"]))

    def test_gruppo_al_voto(self):
        self.assertTrue(all(a["group"] and a["group"].startswith("it:camera:19:group:") for a in self.voti))

    def test_esiti(self):
        self.assertEqual(esito("Non ha votato", "In missione"), "mission")
        self.assertEqual(esito("Non ha votato", "Presidente di turno"), "chair")
        self.assertEqual(esito("Non ha votato", "Non ha partecipato"), "absent")
        self.assertEqual(esito("Favorevole", "Presidente di turno"), "favor")
        self.assertEqual(uri_votazione("http://dati.camera.it/ocd/votazione.rdf/vs19_722_001", 19), "it:camera:19:sed0722:v001")
        self.assertGreater(Counter(a["result"] for a in self.voti)["mission"], 0)

    def test_caricamento(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]]
        s = script_voti(righe)
        self.assertIn("DELETE FROM vote WHERE sitting = 'it:camera:19:sed0008' AND source = 'ocd';", s)
        self.assertTrue(s.rstrip().endswith("COMMIT;"))



class TestAttoDallaDescrizione(unittest.TestCase):
    """Votazioni senza l'atto in dati.camera.it: il riferimento si ricava dalla descrizione, o dalla seduta."""

    def test_progetti_di_legge(self):
        self.assertEqual(atti_dalla_descrizione("PDL 2822-A E ABB - EM 1.1", 19), ["ac19_2822"])
        self.assertEqual(atti_dalla_descrizione("DDL.n. 2920-A", 19), ["ac19_2920"])
        self.assertEqual(atti_dalla_descrizione("Votazione Fiducia A.C. 3053", 19), ["ac19_3053"])
        self.assertEqual(atti_dalla_descrizione("EM 1.2", 19), [])

    def test_mozioni_e_risoluzioni(self):
        self.assertEqual(aic_dalla_descrizione("MOZ 1-346 CPV 16 DISP", 19), ["aic1_00346_19"])
        self.assertEqual(aic_dalla_descrizione("R6-280,284DISP AFRICA7 BURKINA-FASO", 19), ["aic6_00280_19", "aic6_00284_19"])
        self.assertEqual(aic_dalla_descrizione("RIS 280,281,282 D MIS SCH 10 EUNAVFOR", 19), ["aic6_00280_19", "aic6_00281_19", "aic6_00282_19"])
        self.assertEqual(aic_dalla_descrizione("RIS 6-266", 19), ["aic6_00266_19"])
        for t in ("EM 1.2", "ARTICOLO 3", "DOC IV-TER, N 22-A", None):
            self.assertEqual(aic_dalla_descrizione(t, 19), [])

    def test_mozione_diventa_arco(self):
        corpo = gzip.compress(json.dumps({"seduta": "http://dati.camera.it/ocd/seduta.rdf/s19_377", "voti": [], "votazioni": [
            {"votazione": "http://dati.camera.it/ocd/votazione.rdf/vs19_377_140", "data": "20241105", "tipo": "Altre",
             "descrizione": "MOZ 1-346 CPV 16 DISP"}]}).encode())
        r = trasforma(corpo, {"chiave": "leg19-voti-sed0377"})
        self.assertEqual([a["to_ref"] for a in r["archi"] if a["type"] == "ON"], ["aic1_00346_19"])
        s = script_voti([{"tipo": "ambito", **r["ambito"]}] + [{"tipo": "nodo", **n} for n in r["nodi"]] + [{"tipo": "arco", **a} for a in r["archi"]])
        self.assertIn("'it:camera:19:aic:' || replace(regexp_replace(v.act_ref, '^aic|_19$', '', 'g'), '_', '-')", s)

    def test_seguito_nello_schema(self):
        # emendamenti dal fascicolo della seduta, poi il blocco aperto dalla votazione che nomina l'atto
        f = SCHEMA[SCHEMA.index("CREATE OR REPLACE FUNCTION lega_voti_seguito"):]
        f = f[:f.index("$$;")]
        self.assertIn("e.venue = 'assembly' AND e.sitting_number = v.sed", f)
        self.assertIn("HAVING count(DISTINCT e.act) = 1", f)
        self.assertIn("y.act = p.atto", f)                 # l'atto è fra i punti all'ordine del giorno della seduta
        self.assertIn("b.atto IS DISTINCT FROM p.atto", f)  # nessuna votazione del blocco legata ad altro
        self.assertIn("lega_voti_seguito(l)", (Path(__file__).parent.parent / "pipeline" / "carica" / "postgres.py").read_text())



@unittest.skipUnless(db_locale(), "serve il Postgres locale")
class TestSeguitoNelDatabase(unittest.TestCase):
    """lega_voti_seguito su una seduta finta della legislatura 99, in una transazione annullata."""

    def test_legami(self):
        from pipeline.carica.postgres import psql
        voti = [(1, "DDL 10-A - EM 1.1"), (2, "EM 1.2"), (3, "ARTICOLO 1"), (4, "DOC IV-TER, N 2"), (5, "EM 7.7"), (6, "ARTICOLO 7"),
                (7, "PDL 10-A - EM 3.1"), (8, "EM 2.1"), (9, "EM 3.2")]
        sql = ["BEGIN;",
               "INSERT INTO act (uri, chamber, legislature, number, kind, source) VALUES "
               "('it:camera:99:ac:10', 'camera', 99, '10', 'bill', 'prova'), ('it:camera:99:ac:20', 'camera', 99, '20', 'bill', 'prova');",
               "INSERT INTO sitting (uri, chamber, body, number, date, source) VALUES ('it:camera:99:sed0005', 'camera', 'it:camera:99:aula', 5, '2099-01-01', 'prova');",
               "INSERT INTO agenda_item (uri, sitting, ord) VALUES ('it:camera:99:sed0005:tit1', 'it:camera:99:sed0005', 1);",
               "INSERT INTO agenda_item_act (item, act_ref, act) VALUES ('it:camera:99:sed0005:tit1', 'pdl:10-A', 'it:camera:99:ac:10');",
               # 7.7 e 2.1 stanno nel fascicolo di un altro atto della seduta
               "INSERT INTO amendment (uri, act, number, venue, sitting_number, hash, source_key) VALUES "
               "('e1', 'it:camera:99:ac:20', '7.7', 'assembly', 5, 'h', 'prova'), ('e2', 'it:camera:99:ac:20', '2.1', 'assembly', 5, 'h', 'prova');"]
        for n, d in voti:
            sql.append(f"INSERT INTO vote (uri, sitting, chamber, legislature, number, date, description, kind, source) VALUES "
                       f"('it:camera:99:sed0005:v{n:03d}', 'it:camera:99:sed0005', 'camera', 99, {n}, '2099-01-01', '{d}', 'other', 'prova');")
        sql += ["INSERT INTO vote_act VALUES ('it:camera:99:sed0005:v001', 'ac99_10', 'it:camera:99:ac:10'), "
                "('it:camera:99:sed0005:v007', 'ac99_10', 'it:camera:99:ac:10');",
                "SELECT lega_voti_seguito(99);",
                "SELECT string_agg(right(x.vote, 4) || '=' || x.act, ' ' ORDER BY x.vote) FROM vote_act x WHERE x.vote LIKE 'it:camera:99:%';",
                "ROLLBACK;"]
        out = psql("\n".join(sql) + "\n")
        riga = next(r for r in out.splitlines() if "v001=" in r).strip()
        # v002 e v003 seguono l'apertura; v005 e v008 dal fascicolo; il DOC e il blocco che apre (v006) restano senza;
        # il blocco di v007 ha una votazione legata a un altro atto (v008), quindi v009 non eredita
        self.assertEqual(riga, "v001=it:camera:99:ac:10 v002=it:camera:99:ac:10 v003=it:camera:99:ac:10 "
                               "v005=it:camera:99:ac:20 v007=it:camera:99:ac:10 v008=it:camera:99:ac:20")


if __name__ == "__main__":
    unittest.main()
