"""Strumenti dell'API sul Postgres locale (utente `lettura`). Si saltano se il database non risponde."""

import datetime as dt
import unittest

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""

from api.strumenti import atti, conti, documenti, persone, ricerca, sedute, voti


@unittest.skipIf(C is None, f"Postgres non raggiungibile: {MOTIVO}")
class TestApi(unittest.TestCase):
    def test_sola_lettura(self):
        import psycopg
        with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
            C.execute("CREATE TABLE prova (a int)")

    def test_documenti_depositati_su_un_atto(self):
        # contributi scritti (legati all'atto) e memorie delle audizioni (legate dall'audizione dello stesso giorno)
        n, righe = documenti.documenti(C, act="it:camera:19:ac:3120", limit=50)
        self.assertGreaterEqual(n, 40)
        self.assertEqual({r["kind"] for r in righe}, {"written_contribution", "memorandum"})
        self.assertTrue(all(" " not in r["url"] for r in righe))                 # link interi anche in Markdown
        ania = documenti.documenti(C, act="ac:3120", author="ANIA")[1][0]
        testo = documenti.documento(C, ania["uri"])
        self.assertEqual(len(testo["text"]), documenti.PAGINA)
        self.assertIn("offset=11000", testo["more"])
        self.assertIsNone(documenti.documento(C, "it:camera:19:doc:inesistente"))

    def test_assenze_del_senato_ricavate(self):
        # il Senato non pubblica gli assenti: in carica senza scheda; chi presiedeva la seduta è chair, non assente
        r = conti.presenze(C, "senato", start=dt.date(2026, 2, 25), end=dt.date(2026, 2, 25), order_by="absent", limit=250)
        righe = {x["persona"]: x for x in r["rows"]}
        self.assertTrue(all(x["ballots"] + x["absent"] + x["chair"] <= r["votes_in_set"] for x in r["rows"]))
        self.assertGreater(sum(x["absent"] for x in r["rows"]), 0)
        self.assertEqual(righe["Renzo Piano"]["absent"], r["votes_in_set"])          # senatore a vita, in carica, nessuna scheda
        self.assertIn("ricavati", r["counted"])
        self.assertNotIn("ricavati", conti.presenze(C, "camera", start=dt.date(2026, 2, 11), end=dt.date(2026, 2, 11), limit=1)["counted"])

    def test_senatore_una_persona_due_schede(self):
        renzi = persone.cerca_persone(C, q="renzi", chamber="senato")[0]
        self.assertEqual(renzi.name, "Matteo Renzi")
        scheda = persone.scheda_persona(C, renzi.uri)
        self.assertTrue(any(u.startswith("it:person:camera:") for u in scheda.same_as))
        self.assertGreater(scheda.counts.speeches, 0)

    def test_misto_per_componente(self):
        k = persone.composizione(C, "camera")
        misto = next(g for g in k.groups if g.group.short_name == "MISTO")
        self.assertTrue(misto.components)
        self.assertLessEqual(sum(x.members for x in misto.components), misto.members)
        self.assertEqual(sum(g.members for g in k.groups) + k.not_in_group, k.members)

    def test_voti_per_parole_anche_dal_testo_dell_atto(self):
        # alla Camera la descrizione di una mozione ha solo i firmatari: il tema sta nel testo dell'atto
        n, vs = voti.elenco_votazioni(C, chamber="camera", kind="motion", q="Israele", limit=100)
        self.assertGreater(n, 0)
        self.assertIn("it:camera:19:sed0483:v005", [v.uri for v in vs])

    def test_voto_tutti_i_gruppi_hanno_nome(self):
        _, vs = voti.elenco_votazioni(C, chamber="camera", final=True, limit=1)
        v = voti.votazione(C, vs[0].uri)
        self.assertTrue(all(g.group is not None for g in v.groups))
        self.assertEqual(sum(g.favor for g in v.groups), v.favor)

    def test_seduta_e_atti(self):
        # la più recente può essere la seduta prevista dall'ordine del giorno, che non ha ancora interventi
        _, ss = sedute.elenco_sedute(C, chamber="senato", body="aula", limit=5)
        s = sedute.seduta(C, next(x for x in ss if x.status == "held").uri)
        self.assertTrue(any(i.speeches for i in s.items))
        a = atti.atto(C, "it:senato:19:ddl:1695")
        self.assertEqual({v.kind for v in a.versions}, {"presented", "committee", "message"})
        n, es = atti.emendamenti(C, a.uri, limit=5)
        self.assertEqual(n, a.amendments.total)

    def test_ricerca_interventi(self):
        hs = ricerca.cerca_interventi(C, '"salario minimo"', limit=3)
        self.assertTrue(hs and all("[[" in h.snippet for h in hs))


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(C is None, f"Postgres non raggiungibile: {MOTIVO}")
class TestAgenteEMcp(unittest.TestCase):
    """L'agente con un modello finto: niente chiamate a OpenAI, niente spesa."""

    def test_ciclo_agente(self):
        import sqlite3
        from unittest import mock
        from api import agente
        risposte = iter([
            {"output": [{"type": "function_call", "name": "cerca_persone", "call_id": "c1", "arguments": '{"q": "renzi", "chamber": "senato"}'}],
             "usage": {"input_tokens": 1000, "output_tokens": 100}},
            {"output": [{"type": "message", "content": [{"type": "output_text",
              "text": "Matteo Renzi è senatore ([scheda](https://inventato.example/x)) e ha detto «questa frase non esiste da nessuna parte».\nSEGUITI: a | b | c"}]}],
             "usage": {"input_tokens": 2000, "output_tokens": 200}}])
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.execute("CREATE TABLE domande (impronta TEXT NOT NULL, ts REAL NOT NULL)")
        db.execute("CREATE TABLE spesa (giorno TEXT PRIMARY KEY, dollari REAL NOT NULL)")
        import contextlib
        with mock.patch.object(agente, "chiama_openai", lambda *a, **k: next(risposte)), mock.patch.object(agente, "_registro_spesa", lambda: db), \
             mock.patch.object(agente, "connessione_sito", lambda: contextlib.nullcontext(None)), \
             mock.patch.object(agente, "env", lambda n, d=None: {"OPENAI_API_KEY": "finta"}.get(n, d)):
            eventi = list(agente.rispondi("chi è renzi?", [], "it", "1.2.3.4"))
        tipi = [e["type"] for e in eventi]
        self.assertEqual(tipi[-1], "done")
        testo = next(e["text"] for e in eventi if e["type"] == "delta")
        self.assertNotIn("inventato.example", testo)                       # link non visto nei dati: tolto
        verifica = next(e["result"] for e in eventi if e["type"] == "dati" and e["name"] == "verifica_citazioni")
        self.assertEqual(verifica["verified"], 0)
        self.assertEqual(next(e["questions"] for e in eventi if e["type"] == "suggestions"), ["a", "b", "c"])
        self.assertEqual(db.execute("SELECT count(*) FROM domande").fetchone()[0], 1)

    def test_mcp(self):
        from unittest import mock
        from api import mcp
        # gli strumenti italiani stanno in tools/list solo con MCP_STRUMENTI_INTERNI=1 (test_mcp_pubblico.py per gli altri)
        mock.patch.object(mcp, "env", lambda n, d=None: "1" if n == "MCP_STRUMENTI_INTERNI" else d).start()
        self.addCleanup(mock.patch.stopall)
        lista = mcp.gestisci(C, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        nomi = {t["name"] for t in lista["result"]["tools"]}
        self.assertIn("verifica_citazioni", nomi)
        r = mcp.gestisci(C, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "composizione", "arguments": {"chamber": "senato"}}})
        self.assertEqual(r["result"]["structuredContent"]["result"]["chamber"], "senato")
        r = mcp.gestisci(C, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "composizione", "arguments": {"chamber": "x"}}})
        self.assertTrue(r["result"]["isError"])
        self.assertIsNone(mcp.gestisci(C, {"jsonrpc": "2.0", "method": "notifications/initialized"}))
