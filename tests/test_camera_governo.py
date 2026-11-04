"""Governi e incarichi di governo (campione del 30/10/2026: Meloni, Draghi, Salvini, Bernini)."""

import json
import unittest
from pathlib import Path

from pipeline.carica.postgres import psql, script_governo
from pipeline.controlli.uscite import _regole_governo
from pipeline.trasforma.camera_governo import trasforma
from tests import db_locale

GREZZI = json.loads((Path(__file__).parent / "fixtures" / "camera_governo_campione.json").read_text(encoding="utf-8"))


class TestGoverno(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(GREZZI, 19)
        self.nodi = {n["uri"]: n for n in self.r["nodi"]}
        self.chi = {n["family_name"]: n["uri"] for n in self.r["nodi"] if n["label"] == "Person"}

    def incarichi(self, cognome):
        return [a for a in self.r["archi"] if a["from"] == self.chi[cognome]]

    def test_un_solo_presidente_oggi(self):
        self.assertEqual(_regole_governo(self.r["nodi"], self.r["archi"]), [])

    def test_draghi_chiuso_con_il_governo(self):
        pm = next(a for a in self.incarichi("Draghi") if a["title"] == "prime_minister")
        self.assertEqual((pm["end"], pm["end_reason"]), ("2022-10-21", "fine del governo"))

    def test_salvini_due_incarichi(self):
        titoli = {a["title"] for a in self.incarichi("Salvini") if not a["end"]}
        self.assertEqual(titoli, {"minister", "deputy_prime_minister"})
        ministero = next(a["to"] for a in self.incarichi("Salvini") if a["title"] == "minister" and not a["end"])
        self.assertIn("Infrastrutture", self.nodi[ministero]["name"])

    def test_caricamento(self):
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]]
        s = script_governo(righe)
        self.assertIn("coalesce(person.given_name, EXCLUDED.given_name)", s)  # non sovrascrive l'anagrafica della Camera
        self.assertTrue(s.rstrip().endswith("COMMIT;"))



@unittest.skipUnless(db_locale(), "serve il Postgres locale")
class TestNomeDelloStub(unittest.TestCase):
    """Un ministro non parlamentare che parla al Senato ha un id di senato.it senza anagrafica: lega_governo lo lega
    alla scheda del governo e gli dà nome e cognome. Transazione annullata, legislatura finta."""

    def test_nome_dalla_carica(self):
        out = psql("\n".join([
            "BEGIN;",
            "INSERT INTO person (uri, stub, given_name, family_name, sort_name) VALUES "
            "('it:person:camera:prova1', false, 'Marina Elvira', 'Calderone', 'Calderone Marina Elvira');",
            "INSERT INTO person (uri) VALUES ('it:person:senato:prova1'), ('it:person:senato:prova2');",
            "INSERT INTO office (person, target, title, start_date) VALUES ('it:person:camera:prova1', 'it:gov:prova', 'minister', '2099-01-01');",
            "INSERT INTO sitting (uri, chamber, body, number, date, source) VALUES ('it:prova:sed1', 'senato', 'aula', 1, '2099-02-01', 'prova');",
            "INSERT INTO agenda_item (uri, sitting, ord) VALUES ('it:prova:sed1:t1', 'it:prova:sed1', 1);",
            "INSERT INTO speech (uri, item, ord, person, speaker_label, as_office, kind, hash, text) VALUES "
            "('it:prova:sed1:t1:p1', 'it:prova:sed1:t1', 1, 'it:person:senato:prova1', 'CALDERONE, ministro del lavoro e delle politiche sociali', 'ministro', 'speech', 'h', 't'), "
            "('it:prova:sed1:t1:p2', 'it:prova:sed1:t1', 2, 'it:person:senato:prova2', 'ROSSI, sottosegretario di Stato', 'sottosegretario', 'speech', 'h', 't');",
            "SELECT lega_governo('it:prova:');",
            "SELECT 'nomi:' || string_agg(uri || '=' || coalesce(given_name || ' ' || family_name, '-') || '/' || stub, ' ' ORDER BY uri) "
            "FROM person WHERE uri LIKE 'it:person:senato:prova%';",
            "ROLLBACK;"]) + "\n")
        riga = next(r.strip() for r in out.splitlines() if "nomi:" in r)
        # Rossi non ha una carica di governo alla data: resta senza nome
        self.assertEqual(riga, "nomi:it:person:senato:prova1=Marina Elvira Calderone/true it:person:senato:prova2=-/true")


if __name__ == "__main__":
    unittest.main()
