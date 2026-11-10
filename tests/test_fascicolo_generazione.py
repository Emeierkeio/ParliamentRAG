"""Generazione del fascicolo e flusso SSE (api/fascicolo/generazione, api/fascicolo/servizio.py) con il modello finto:
nessuna chiamata a OpenAI, nessun database. Recupero e autorevolezza sono finti con l'interfaccia dei loro moduli."""

import datetime as dt
import hashlib
import json
import logging
import re
import sys
import types
import unittest
from unittest import mock

import api.fascicolo
from api.fascicolo import modello, servizio
from api.fascicolo.generazione import gruppi
from api.fascicolo.generazione.pipeline import GenerationPipeline
from api.fascicolo.generazione.verbatim import is_verbatim

def setUpModule():
    logging.disable(logging.WARNING)                 # i passi avvisano a ogni citazione scartata: qui è voluto


def tearDownModule():
    logging.disable(logging.NOTSET)


GRUPPI = [gruppi.Gruppo("Fratelli d'Italia", "maggioranza", frozenset({"camera", "senato"})),
          gruppi.Gruppo("Partito Democratico - Italia Democratica e Progressista", "opposizione", frozenset({"camera", "senato"})),
          gruppi.Gruppo("Misto", "misto", frozenset({"camera", "senato"})),
          gruppi.Gruppo("+Europa - Stati Uniti d'Europa", "misto", frozenset({"camera"}), True)]

TESTI = {
    "it:camera:19:sed1:a": ("Il salario minimo legale è una misura di civiltà che il nostro Paese aspetta da troppo tempo. "
                            "Noi chiediamo di approvarlo subito, per i lavoratori poveri che oggi guadagnano meno di nove euro."),
    "it:camera:19:sed1:b": ("La contrattazione collettiva resta lo strumento migliore per tutelare i salari dei lavoratori italiani. "
                            "Un salario minimo per legge rischia di abbassare le retribuzioni invece di alzarle."),
    "it:camera:19:sed1:c": ("Sul salario minimo la nostra componente ha presentato una proposta che fissa la soglia a nove euro lordi. "
                            "È una scelta europea, già fatta da ventidue Paesi dell'Unione con buoni risultati."),
    "it:camera:19:sed1:d": ("Il Governo ha scelto di rafforzare la contrattazione collettiva con la delega approvata dal Parlamento. "
                            "Abbiamo detto con chiarezza che la strada del salario minimo legale non è la nostra."),
}
PERSONE = {"it:camera:19:sed1:a": ("it:person:camera:1", "Anna Rossi", "Partito Democratico - Italia Democratica e Progressista", None, False),
           "it:camera:19:sed1:b": ("it:person:camera:2", "Bruno Bianchi", "Fratelli d'Italia", None, False),
           "it:camera:19:sed1:c": ("it:person:camera:3", "Carla Verdi", "Misto", "+Europa - Stati Uniti d'Europa", False),
           "it:camera:19:sed1:d": ("it:person:camera:4", "Dario Neri", None, None, True)}


def brani():
    out = []
    for i, (uri, testo) in enumerate(TESTI.items()):
        persona, nome, gruppo, componente, governo = PERSONE[uri]
        partito = "Governo" if governo else (componente or gruppo)
        out.append({"chunk_id": f"{uri}#0", "speech_uri": uri, "ord": 0, "start_char": 0, "end_char": len(testo),
                    "text": testo, "speech_text": testo, "kind": "verbatim",
                    "speaker": {"uri": persona, "nome": nome, "gruppo": gruppo or "", "sigla": None, "componente": componente,
                                "ruolo": "governo" if governo else "deputato", "carica": "Ministro del lavoro" if governo else None},
                    "partito": partito, "partito_data": partito, "lato": "governo" if governo else "", "governo": governo,
                    "chamber": "camera", "date": "2025-03-0%d" % (i + 1), "sitting": "it:camera:19:sed1", "sitting_number": 1,
                    "debate": "Proposta di legge sul salario minimo", "url": f"https://www.camera.it/x#{i}",
                    "similarita": 0.8, "canali": ["denso"]})
    return out


def finto_chat(modello_, messaggi, ip=None, json_schema=None, massimo=None, timeout=180, **altro):
    """Il modello finto: risponde a ogni prompt della generazione nella forma che si aspetta."""
    sistema = messaggi[0]["content"] if messaggi[0]["role"] == "system" else ""
    utente = messaggi[-1]["content"]
    if json_schema:                                           # l'analista
        return json.dumps({"claims": [], "query_type": "policy", "requires_government_view": True})
    if "<DIBATTITI>" in utente:
        return json.dumps({"giudizi": {"1": "T"}})
    if "selezionatore di citazioni" in sistema and "CANDIDATI" in utente:
        return json.dumps({"selected": 1, "stance": "critical", "confidence": 0.9})
    if "selezionatore di citazioni" in sistema:
        return "NONE"
    if "scrivi SOLO\nl'introduzione" in sistema or "Scrivi le 2 frasi" in utente:
        return "Si discute del salario minimo legale. Sono stati analizzati 4 interventi di 4 deputati."
    m = re.search(r"«(.+?)» \[CIT:(b\d+)\]", utente)          # chi scrive la sezione: la citazione obbligatoria
    if m:
        oratore = re.search(r"Oratore: (.+)", utente).group(1).strip()
        return (f"Il gruppo interviene sul tema. **{oratore.split()[-1]}** afferma che «{m.group(1)}» [CIT:{m.group(2)}]. "
                "La posizione resta coerente con le altre evidenze.")
    return "Testo."


def finto_post(url, corpo, timeout=120):
    if url == modello.VETTORI:                                # vettori finti: testi uguali coseno 1, diversi coseno 0
        def vettore(t):
            v = [0.0] * 64
            v[int(hashlib.md5(t.encode()).hexdigest(), 16) % 64] = 1.0
            return v
        return {"data": [{"index": i, "embedding": vettore(t)} for i, t in enumerate(corpo["input"])], "usage": {"total_tokens": 1}}
    raise AssertionError("chiamata inattesa al modello")


class Connessione:
    """Una connessione finta: risponde alle poche query del servizio."""
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, par=None):
        r = mock.MagicMock()
        if "FROM speech" in sql:
            righe = [{"uri": u, "text": TESTI[u]} for u in par[0]]
        elif "FROM person" in sql:
            righe = [{"uri": u, "given_name": "", "family_name": "", "photo": None, "profession": None, "education": None,
                      "camera_id": u.rsplit(":", 1)[1], "commissione": None} for u in par[0]]
        else:
            righe = []
        r.fetchall.return_value = righe
        r.__iter__ = lambda s: iter(righe)
        return r


def moduli_finti(punteggi=None):
    recupero = types.ModuleType("api.fascicolo.recupero")
    recupero.risolvi_ambito = lambda domanda, ambito=None: types.SimpleNamespace(rami=["camera", "senato"], da=None, a=None)
    recupero.recupera = lambda c, domanda, ambito, ip=None: {"evidenze": brani()}
    aut = types.ModuleType("api.fascicolo.autorevolezza")
    aut.punteggi = lambda c, domanda, ambito=None, persone=None, pesi=None, ip=None: punteggi if punteggi is not None else [
        {"uri": "it:person:camera:1", "punteggio": 0.7, "componenti": {"interventions": 0.9, "committee": 0.5}},
        {"uri": "it:person:camera:2", "punteggio": 0.6},
        {"uri": "it:person:camera:3", "punteggio": 0.4}]
    return {"api.fascicolo.recupero": recupero, "api.fascicolo.autorevolezza": aut}


class ConModelloFinto(unittest.TestCase):
    def setUp(self):
        gruppi.imposta(GRUPPI)
        self.addCleanup(gruppi.imposta, [])
        self.finti = {}
        for nome, p in (("chat", mock.patch.object(modello, "chat", side_effect=finto_chat)),
                        ("post", mock.patch.object(modello, "_post", side_effect=finto_post)),
                        ("conta", mock.patch.object(modello.agente, "_conta")),
                        ("limiti", mock.patch.object(servizio.agente, "controlla_limiti", return_value=None)),
                        ("salva", mock.patch.object(servizio.conversazioni, "salva")),
                        ("db", mock.patch.object(servizio, "connessione", Connessione)),
                        ("voti", mock.patch.object(servizio, "compute_group_votes", return_value={}))):
            self.finti[nome] = p.start()
            self.addCleanup(p.stop)

    def eventi(self, domanda="Qual è la posizione dei gruppi parlamentari sul tema: salario minimo?", lingua="it", **kw):
        finti = moduli_finti(**kw)
        # `from . import recupero` legge prima l'attributo del pacchetto: se il modulo vero è già importato, vince lui
        with mock.patch.dict(sys.modules, finti), mock.patch.multiple(
                api.fascicolo, create=True, **{k.rsplit(".", 1)[1]: m for k, m in finti.items()}):
            righe = list(servizio.stream(domanda, None, lingua, "1.2.3.4"))
        return [json.loads(r[5:]) for r in righe if r.startswith("data:")]


class TestFlusso(ConModelloFinto):
    def test_eventi_che_legge_il_sito(self):
        ev = self.eventi()
        tipi = [e["type"] for e in ev]
        for t in ("progress", "experts", "topic_stats", "citation_details", "chunk", "complete"):
            self.assertIn(t, tipi)
        self.assertEqual([e["step"] for e in ev if e["type"] == "progress"], [1, 2, 3, 4, 5])
        self.assertIn("Trovate 4 evidenze", [e["message"] for e in ev if e["type"] == "progress"])
        self.assertLess(tipi.index("citation_details"), tipi.index("chunk"))

    def test_citazioni_verificate_con_link_e_testo(self):
        ev = self.eventi()
        testo = "".join(e["data"] for e in ev if e["type"] == "chunk")
        dettagli = next(e for e in ev if e["type"] == "citation_details")["citations"]
        link = re.findall(r"\[«([^»]+)»\]\((b\d+)\)", testo)
        self.assertTrue(link)
        self.assertEqual({i for _, i in link}, {d["chunk_id"] for d in dettagli})
        for q, i in link:
            d = next(x for x in dettagli if x["chunk_id"] == i)
            self.assertTrue(d["verified"])
            self.assertTrue(d["url"].startswith("https://www.camera.it/"))
            self.assertTrue(is_verbatim(q, TESTI[d["intervention_id"]]))

    def test_una_voce_per_gruppo_e_misto_per_componente(self):
        ev = self.eventi()
        esperti = [e for e in ev if e["type"] == "experts"][-1]["data"]
        gruppi_ = [x["group"] for x in esperti]
        self.assertEqual(len(gruppi_), len(set(gruppi_)))
        self.assertIn("+Europa - Stati Uniti d'Europa", gruppi_)
        self.assertNotIn("Misto", gruppi_)
        self.assertNotIn("Governo", gruppi_)
        pd = next(x for x in esperti if x["group"].startswith("Partito Democratico"))
        self.assertEqual(pd["id"], "http://dati.camera.it/ocd/persona.rdf/p1")
        self.assertEqual(pd["score_breakdown"]["speeches"], 0.9)
        testo = "".join(e["data"] for e in ev if e["type"] == "chunk")
        self.assertIn("## Gruppo Misto", testo)
        self.assertIn("Per +Europa - Stati Uniti d'Europa,", testo)

    def test_conta_la_domanda_e_scrive_il_registro(self):
        self.eventi()
        self.finti["conta"].assert_any_call("1.2.3.4", 1, 0)
        riga = self.finti["salva"].call_args[0][0]
        self.assertIsNone(riga["errore"])
        self.assertIn("«", riga["risposta"])
        self.assertEqual(riga["modello"], "fascicolo")

    def test_limite_raggiunto(self):
        with mock.patch.object(servizio.agente, "controlla_limiti", return_value="hai usato tutte le 10 domande"):
            ev = self.eventi()
        self.assertEqual(ev, [{"type": "error", "code": "rate_limited", "message": "hai usato tutte le 10 domande"}])

    def test_senza_autorevolezza_va_avanti_senza_filtro(self):
        ev = self.eventi(punteggi=[])
        self.assertTrue(any(e["type"] == "citation_details" and e["citations"] for e in ev))

    def test_errore_del_modello(self):
        with mock.patch.object(servizio, "GenerationPipeline", side_effect=modello.ModelloNonDisponibile("tetto di spesa di oggi raggiunto")):
            ev = self.eventi()
        self.assertEqual(ev[-1]["type"], "error")
        self.assertEqual(ev[-1]["code"], "quota_exhausted")


class TestParti(unittest.TestCase):
    def test_id_del_sito(self):
        self.assertEqual(servizio.id_sito("it:person:camera:307134"), "http://dati.camera.it/ocd/persona.rdf/p307134")
        self.assertEqual(servizio.id_sito("it:person:senato:17542"), "http://dati.senato.it/senatore/17542")

    def test_verifica_toglie_le_citazioni_che_non_tornano(self):
        ev, per_id = servizio.evidenze(brani())
        vera = "Noi chiediamo di approvarlo subito"
        testo = f"**Rossi** dice «{vera}» e [«parole mai dette»](b2). Vedi [«{vera}»](b1) e [«x»](b99)."
        testo = testo.replace(f"«{vera}» e", f"[«{vera}»](b1) e", 1)
        out, buoni, tolte = servizio.verifica_citazioni(Connessione(), testo, per_id)
        self.assertEqual(buoni, {"b1"})
        self.assertEqual(tolte, 2)
        self.assertNotIn("mai dette", out)
        self.assertIn(f"[«{vera}»](b1)", out)

    def test_evidenze_nel_formato_della_generazione(self):
        gruppi.imposta(GRUPPI)
        self.addCleanup(gruppi.imposta, [])
        ev, _ = servizio.evidenze(brani())
        self.assertEqual([e["evidence_id"] for e in ev], ["b1", "b2", "b3", "b4"])
        self.assertEqual(ev[2]["party"], "+Europa - Stati Uniti d'Europa")
        self.assertEqual(ev[2]["misto_component"], "+Europa - Stati Uniti d'Europa")
        self.assertEqual(ev[3]["speaker_role"], "GovernmentMember")
        self.assertEqual(ev[1]["coalition"], "maggioranza")
        self.assertEqual(ev[0]["date"], dt.date(2025, 3, 1))

    def test_classifica_nel_gruppo(self):
        ev = [{"speaker_id": f"p{i}", "party": "A", "speaker_role": "Deputy"} for i in range(7)]
        posti = servizio.classifica_per_gruppo(ev, {f"p{i}": {"score": i / 10} for i in range(7)})
        self.assertEqual(posti["p6"]["rank"], 1)
        self.assertEqual(posti["p0"]["rank"], 7)
        self.assertEqual(posti["p0"]["pool_size"], 7)

    def test_traduzione_non_tocca_le_citazioni(self):
        from api.fascicolo.generazione import traduzione
        testo = "Per X, **Rossi** dice [«noi chiediamo»](b1)."
        with mock.patch.object(traduzione, "chat", return_value="For X, **Rossi** says __CIT_1__."):
            self.assertEqual(traduzione.traduci(testo, "en"), "For X, **Rossi** says [«noi chiediamo»](b1).")
        with mock.patch.object(traduzione, "chat", return_value="For X, **Rossi** says."):
            self.assertEqual(traduzione.traduci(testo, "en"), testo)


class TestRotta(unittest.TestCase):
    def test_rotta_in_sse_con_lingua_e_pesi(self):
        from api import sito
        req = types.SimpleNamespace(headers={"accept-language": "en-GB"})
        # chi chiama e il conteggio delle visite vogliono una richiesta vera (indirizzo, cookie): qui si prova solo il
        # passaggio di lingua e pesi. Dal 10/11/2026 la rotta riconosce chi chiama con `chi`, non più con `ip`.
        with mock.patch.object(sito, "chi", return_value="1.2.3.4"), mock.patch.object(sito.statistiche, "registra"), \
                mock.patch.object(servizio, "stream", return_value=iter(["data: {}\n\n"])) as s:
            r = sito.fascicolo(req, sito.Fascicolo(query="salario minimo", authority_weights={"committee": 40, "interventions": 60}))
        self.assertEqual(r.media_type, "text/event-stream")
        s.assert_called_once_with("salario minimo", {"committee": 40.0, "interventions": 60.0}, "en", "1.2.3.4")


class TestGenerazione(ConModelloFinto):
    def test_pipeline_cita_solo_brani_verbatim(self):
        ev, per_id = servizio.evidenze(brani())
        for e in ev:
            e["debate_relevance"] = "T"
        r = GenerationPipeline().generate(query="salario minimo", evidence_list=ev, parties=gruppi.nomi(["camera"]),
                                          scope=(("camera", 19),))
        self.assertFalse(r["metadata"]["citation_integrity"]["verbatim"]["failed"])
        self.assertNotIn("[CIT:", r["text"])
        self.assertIn("## Posizione del Governo", r["text"])
        self.assertIn("## Posizioni della Maggioranza", r["text"])
        self.assertEqual(r["topic_statistics"]["intervention_count"], 4)


if __name__ == "__main__":
    unittest.main()
