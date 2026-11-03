"""Server MCP compatibile con la produzione (mcp.parliamentrag.it): id vecchi ↔ uri v3, protocollo, HTTP, e il contratto
degli otto strumenti pubblici contro le forme delle risposte vere della produzione (fixtures/mcp_produzione_forme.json,
ricavate dalle risposte salvate il 2/11/2026 e, per le liste vuote nei campioni, dal sorgente di ricerca/mcp/server.py).
I test che leggono il database si saltano se Postgres non risponde."""

import asyncio
import json
import unittest
from pathlib import Path
from unittest import mock

try:
    from api.db import connessione
    C = connessione()
except Exception as e:                                   # database spento o .env senza API_PG_PASSWORD
    C, MOTIVO = None, str(e)[:80]
else:
    MOTIVO = ""

from api import mcp, pubblico
from api.pubblico import id_vecchio, uri_v3

FORME = json.loads((Path(__file__).parent / "fixtures" / "mcp_produzione_forme.json").read_text())


def _env(**valori):
    return mock.patch.object(mcp, "env", lambda n, d=None: valori.get(n, d))


class TestIdentificativi(unittest.TestCase):
    COPPIE = [("it:camera:19:sed0736", "leg19_sed736"), ("it:senato:19:sed0469", "sen_leg19_sed469"),
              ("it:camera:19:sed0734:v001", "camera_leg19_sed734_v001"), ("it:senato:19:sed0469:v006", "senato_leg19_sed469_v006"),
              ("it:camera:19:sed0034:v002", "camera_leg19_sed034_v002"), ("it:senato:19:sed0017:v001", "senato_leg19_sed017_v001"),
              ("it:camera:19:sed0736:tit00010", "leg19_sed736_tit00010"), ("it:senato:19:sed0469:d-d1e36", "sen_leg19_sed469_d-d1e36"),
              ("it:camera:19:sed0008:odg00010", "leg19_sed8_odg00010")]

    def test_andata_e_ritorno(self):
        for uri, vecchio in self.COPPIE:
            self.assertEqual(id_vecchio(uri), vecchio)
            self.assertEqual(uri_v3(vecchio), uri)
            self.assertEqual(uri_v3(uri), uri)                         # un uri v3 passa com'è

    def test_formati_tollerati(self):
        self.assertEqual(uri_v3(" camera_leg19_sed1_v1 "), "it:camera:19:sed0001:v001")
        self.assertEqual(uri_v3("leg19_sed0736"), "it:camera:19:sed0736")
        self.assertEqual(uri_v3("sen_leg19_sed470_3_02491____criticit__carcere"), "it:senato:19:sed0470:3_02491____criticit__carcere")

    def test_sconosciuti(self):
        for x in ("", "abc", "senato_leg19_sed1", "it:person:camera:1"):
            self.assertIsNone(uri_v3(x))
        self.assertEqual(id_vecchio("it:person:camera:1"), "it:person:camera:1")

    def test_url_intervento(self):
        self.assertEqual(pubblico.url_intervento("it:camera:19:sed0734:tit00020.sub00040.int00020"),
                         "https://www.camera.it/leg19/410?idSeduta=0734&tipo=stenografico#sed0734.stenografico.tit00020.sub00040.int00020")
        self.assertIsNone(pubblico.url_intervento("it:senato:19:sed0469:int00121"))


class TestProtocollo(unittest.TestCase):
    """Senza database: solo tools/call lo apre."""

    def r(self, metodo, params=None, ident=1):
        return mcp.gestisci(None, {"jsonrpc": "2.0", "id": ident, "method": metodo, **({"params": params} if params is not None else {})})

    def test_initialize_e_versioni(self):
        for chiesta, attesa in (("2025-06-18", "2025-06-18"), ("2025-03-26", "2025-03-26"), ("2024-11-05", "2024-11-05"),
                                ("2099-01-01", "2025-06-18"), (None, "2025-06-18")):
            res = self.r("initialize", {"protocolVersion": chiesta, "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})["result"]
            self.assertEqual(res["protocolVersion"], attesa)
        self.assertEqual(res["serverInfo"]["name"], "ParliamentRAG")
        self.assertEqual(res["serverInfo"]["websiteUrl"], "https://www.parliamentrag.it")
        self.assertEqual(res["serverInfo"]["icons"][0]["src"], "https://mcp.parliamentrag.it/icon.png")
        self.assertEqual({k: v.get("listChanged") for k, v in res["capabilities"].items() if k != "experimental"},
                         {"tools": False, "resources": False, "prompts": False})
        self.assertIn("verify_answer", res["instructions"])
        self.assertNotIn("MCP Apps", res["instructions"])                # v3 non ha viste né immagini

    def test_metodi_semplici(self):
        self.assertEqual(self.r("ping")["result"], {})
        self.assertEqual(self.r("resources/list")["result"], {"resources": []})
        self.assertEqual(self.r("prompts/list")["result"], {"prompts": []})
        self.assertEqual(self.r("metodo/inventato")["error"]["code"], -32601)

    def test_notifiche_batch_e_messaggi_rotti(self):
        self.assertIsNone(mcp.gestisci(None, {"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(mcp.gestisci(None, {"jsonrpc": "2.0", "id": 5, "result": {}}))          # risposta del client
        self.assertEqual(mcp.gestisci(None, [{"jsonrpc": "2.0", "id": 1, "method": "ping"}])["error"]["code"], -32600)
        self.assertEqual(mcp.gestisci(None, {"id": 1, "method": "ping"})["error"]["code"], -32600)
        self.assertEqual(mcp.gestisci(None, "x")["error"]["code"], -32600)

    def test_elenco_strumenti(self):
        with _env():
            nomi = [t["name"] for t in self.r("tools/list")["result"]["tools"]]
        self.assertEqual(nomi, ["search_parliament", "verify_answer", "list_sessions", "get_session_votes", "get_vote_details",
                                "get_voted_text", "get_debate", "get_vote_hemicycle"])
        with _env(MCP_STRUMENTI_INTERNI="1"):
            nomi = {t["name"] for t in self.r("tools/list")["result"]["tools"]}
        self.assertIn("verifica_citazioni", nomi)
        self.assertIn("get_debate", nomi)

    def test_argomenti_come_in_produzione(self):
        attesi = {"search_parliament": {"query", "doc_type", "group", "start_date", "end_date", "max_results", "chamber"},
                  "verify_answer": {"answer", "question", "chamber"},
                  "list_sessions": {"limit", "before", "search", "from_date", "to_date", "chamber"},
                  "get_session_votes": {"session_id"}, "get_vote_details": {"vote_id", "include_individual_votes", "deputy", "group"},
                  "get_voted_text": {"vote_id"}, "get_debate": {"debate_id"}, "get_vote_hemicycle": {"vote_id", "format"}}
        with _env():
            tools = {t["name"]: t for t in self.r("tools/list")["result"]["tools"]}
        for nome, args in attesi.items():
            self.assertEqual(set(tools[nome]["inputSchema"]["properties"]), args, nome)
            self.assertTrue(tools[nome]["annotations"]["readOnlyHint"])
        self.assertEqual(tools["get_debate"]["inputSchema"]["required"], ["debate_id"])

    def test_strumento_sconosciuto_e_argomenti_sbagliati(self):
        with _env():
            r = self.r("tools/call", {"name": "inventato", "arguments": {}})
            self.assertEqual(r["error"]["code"], -32602)
            r = self.r("tools/call", {"name": "composizione", "arguments": {"chamber": "senato"}})   # interno, nascosto
            self.assertEqual(r["error"]["code"], -32602)
            r = self.r("tools/call", {"name": "get_debate", "arguments": {}})
            self.assertTrue(r["result"]["isError"])
            r = self.r("tools/call", {"name": "get_debate", "arguments": {"debate_id": "x", "altro": 1}})
            self.assertTrue(r["result"]["isError"])
            r = self.r("tools/call", {"name": "get_debate", "arguments": "non un oggetto"})
            self.assertTrue(r["result"]["isError"])


def _http(metodo: str, corpo: bytes = b"", accept: str = "application/json, text/event-stream") -> tuple[int, dict, bytes]:
    """Una richiesta all'app ASGI, senza rete né librerie in più."""
    from api import main
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": metodo, "scheme": "http",
             "path": "/mcp", "raw_path": b"/mcp", "query_string": b"", "root_path": "", "client": ("127.0.0.1", 1),
             "server": ("127.0.0.1", 80), "headers": [(b"content-type", b"application/json"), (b"accept", accept.encode()),
                                                       (b"origin", b"https://claude.ai")]}
    inviati, uscita = [{"type": "http.request", "body": corpo, "more_body": False}], []

    async def ricevi():
        return inviati.pop(0) if inviati else {"type": "http.disconnect"}

    async def manda(m):
        uscita.append(m)
    asyncio.run(main.app(scope, ricevi, manda))
    inizio = next(m for m in uscita if m["type"] == "http.response.start")
    testa = {k.decode().lower(): v.decode() for k, v in inizio["headers"]}
    return inizio["status"], testa, b"".join(m.get("body", b"") for m in uscita if m["type"] == "http.response.body")


class TestHttp(unittest.TestCase):
    INIT = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}).encode()

    def test_sse_e_sessione(self):
        stato, testa, corpo = _http("POST", self.INIT)
        self.assertEqual(stato, 200)
        self.assertTrue(testa["content-type"].startswith("text/event-stream"))
        self.assertTrue(testa.get("mcp-session-id"))
        self.assertEqual(testa["access-control-allow-origin"], "*")
        righe = corpo.decode().split("\n")
        self.assertEqual(righe[0], "event: message")
        self.assertEqual(json.loads(righe[1][len("data: "):])["result"]["protocolVersion"], "2025-03-26")

    def test_json_senza_sse(self):
        stato, testa, corpo = _http("POST", self.INIT, accept="application/json")
        self.assertTrue(testa["content-type"].startswith("application/json"))
        self.assertEqual(json.loads(corpo)["result"]["serverInfo"]["name"], "ParliamentRAG")

    def test_notifica_202_e_metodi_http(self):
        stato, _, corpo = _http("POST", b'{"jsonrpc": "2.0", "method": "notifications/initialized"}')
        self.assertEqual((stato, corpo), (202, b""))
        for m in ("GET", "DELETE"):
            stato, testa, _ = _http(m)
            self.assertEqual((stato, testa.get("allow")), (405, "POST"))
        stato, testa, _ = _http("OPTIONS")
        self.assertEqual(stato, 204)
        self.assertIn("Mcp-Session-Id", testa["access-control-allow-headers"])

    def test_json_rotto_e_batch(self):
        stato, _, corpo = _http("POST", b"{rotto", accept="application/json")
        self.assertEqual((stato, json.loads(corpo)["error"]["code"]), (400, -32700))
        stato, _, corpo = _http("POST", b'[{"jsonrpc": "2.0", "id": 1, "method": "ping"}]', accept="application/json")
        self.assertEqual((stato, json.loads(corpo)["error"]["code"]), (400, -32600))


# ---------- contratto con la produzione ----------

def forma(x, p: str = "", out: dict | None = None) -> dict[str, set[str]]:
    """Percorso → tipi visti (num per int e float), con «[]» per gli elementi delle liste. Come genera_fixture."""
    out = {} if out is None else out
    t = "null" if x is None else {bool: "bool", int: "num", float: "num", str: "str", list: "list", dict: "dict"}[type(x)]
    out.setdefault(p, set()).add(t)
    if isinstance(x, dict):
        for k, v in x.items():
            forma(v, f"{p}.{k}" if p else k, out)
    elif isinstance(x, list):
        for y in x:
            forma(y, p + "[]", out)
    return out


def _genitore(p: str) -> str:
    return p.rsplit(".", 1)[0] if "." in p else ""


@unittest.skipIf(C is None, f"Postgres non raggiungibile: {MOTIVO}")
class TestContratto(unittest.TestCase):
    """Chiamate con gli stessi argomenti dei campioni di produzione; si confrontano chiavi e tipi a ogni livello.
    Regole: (1) ogni chiave v3 esiste in produzione; (2) ogni chiave della produzione c'è anche in v3, quando l'oggetto
    che la contiene c'è ed è un oggetto (per le liste, sull'insieme dei loro elementi); (3) dove entrambi hanno un valore non nullo, il tipo è lo stesso."""
    CHIAMATE = {"list_sessions": {"limit": 1, "chamber": "camera"},
                "get_session_votes": {"session_id": "leg19_sed734"},
                "get_vote_details": {"vote_id": "camera_leg19_sed734_v001", "include_individual_votes": True},
                "get_voted_text": {"vote_id": "camera_leg19_sed734_v001"},
                "get_debate": {"debate_id": "leg19_sed736_tit00040"},
                "get_vote_hemicycle": {"vote_id": "camera_leg19_sed734_v001"},
                "search_parliament": {"query": "tartufo", "max_results": 2}}

    def confronta(self, nome: str, ris: dict):
        prod, v3 = {k: set(v) for k, v in FORME[nome].items()}, forma(ris)
        for p in v3:
            self.assertIn(p, prod, f"{nome}: chiave in più rispetto alla produzione: {p}")
        for p, tipi in prod.items():
            if not p or p.endswith("[]"):
                continue
            g = _genitore(p)
            if g in v3 and "dict" in v3[g]:
                self.assertIn(p, v3, f"{nome}: manca {p}")
            if p in v3:
                a, b = prod[p] - {"null"}, v3[p] - {"null"}
                if a and b:
                    self.assertTrue(a & b, f"{nome}: {p} è {b} in v3, {a} in produzione")

    def test_strumenti_pubblici(self):
        for nome, argomenti in self.CHIAMATE.items():
            with self.subTest(nome):
                self.confronta(nome, pubblico.esegui(C, nome, argomenti))

    def test_verify_answer_con_e_senza_fascicoli(self):
        risposta = "Marianna Ricciardi (M5S) ha detto: «Chiedo di illustrare l'interpellanza»."
        finto = {"scope": "Camera dei deputati, XIX legislatura", "summary": {"groups": "fail", "authority": "pass", "quotes": "pass"},
                 "groups": {"items": [{"key": "M5S", "label": "Movimento 5 Stelle", "status": "quoted"},
                                      {"key": "FdI", "label": "Fratelli d'Italia", "status": "missing"}],
                            "named": 1, "total": 2, "mismatches": []},
                 "authority": {"topic": "farmaci", "available": True, "voices": [
                     {"name": "Marianna Ricciardi", "group": "Movimento 5 Stelle", "role": None, "rank": 2, "pool_size": 7,
                      "group_size": 7, "pool": "speakers_on_topic", "authoritative": True, "source": "quoted"}]},
                 "quotes": {"items": []}}
        with mock.patch.object(pubblico, "_fascicoli", lambda *a: finto):
            r = pubblico.esegui(C, "verify_answer", {"answer": risposta, "question": "farmaci", "chamber": "camera"})
        self.confronta("verify_answer", r)
        self.assertEqual(r["quotes"][0]["status"], "exact")
        self.assertTrue(r["quotes"][0]["speaker_named_nearby"])
        self.assertTrue(r["verdict"][0].startswith("❌ All groups: 1/2"))
        with mock.patch.object(pubblico, "_fascicoli", lambda *a: None):  # verificatore spento: la chiamata riesce lo stesso
            r = pubblico.esegui(C, "verify_answer", {"answer": risposta})
        self.assertEqual(r["outcome"], {"groups": "na", "authority": "na", "quotes": "pass"})
        self.assertFalse(r["authority"]["available"])
        self.assertEqual(len(r["verdict"]), 4)

    def test_casi_del_senato_e_segreti(self):
        r = pubblico.esegui(C, "get_session_votes", {"session_id": "sen_leg19_sed469"})
        self.assertEqual(r["votes"][0]["id"], "senato_leg19_sed469_v001")
        self.assertTrue(r["votes"][0]["description"].startswith("Ddl n. 1804"))
        quorum = next(v for v in r["votes"] if v.get("kind") == "quorum_check")
        self.assertIsNone(quorum["outcome"])
        h = pubblico.esegui(C, "get_vote_hemicycle", {"vote_id": quorum["id"]})
        self.assertEqual((h["available"], h["kind"]), (False, "quorum_check"))
        h = pubblico.esegui(C, "get_vote_hemicycle", {"vote_id": "it:camera:19:sed0345:v001"})         # scrutinio segreto
        self.assertEqual((h["available"], h["secret_vote"]), (False, True))
        d = pubblico.esegui(C, "get_debate", {"debate_id": "sen_leg19_sed469_discussione_dalla_sede_redigente_e_approvazione_del_"
                                                          "disegno_di_legge___1919____pubblicit__sentenze_assoluzione_o_proscioglimento"})
        self.assertEqual(d["id"], "sen_leg19_sed469_d-d1e455")                                     # slug vecchio risolto
        self.assertEqual(d["acts"][0]["number"], "1919")

    def test_coerenza_e_filtri(self):
        r = pubblico.esegui(C, "get_vote_details", {"vote_id": "camera_leg19_sed734_v001", "group": "fratelli"})
        self.assertTrue(r["counts_consistency"]["consistent"])
        self.assertEqual(sum(g["favor"] for g in r["breakdown_by_group"]), r["in_favor"])
        self.assertTrue(r["individual_votes"] and all("Fratelli" in x["party"] for x in r["individual_votes"]))
        self.assertIn("individual_votes_available", pubblico.esegui(C, "get_vote_details", {"vote_id": "camera_leg19_sed734_v001"}))

    def test_non_trovato_come_errore_mcp(self):
        with _env():
            r = mcp.gestisci(C, {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                                 "params": {"name": "get_vote_details", "arguments": {"vote_id": "camera_leg19_sed999_v999"}}})
        self.assertTrue(r["result"]["isError"])
        with _env():
            r = mcp.gestisci(C, {"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                                 "params": {"name": "list_sessions", "arguments": {"limit": 1}}})
        self.assertFalse(r["result"]["isError"])
        self.assertEqual(json.loads(r["result"]["content"][0]["text"]), r["result"]["structuredContent"])


if __name__ == "__main__":
    unittest.main()
