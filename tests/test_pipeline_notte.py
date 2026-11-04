"""Fine del giro notturno: mail se l'esito non è ok, niente mail se tutto è andato bene o il giro è stato rifiutato;
sessione di senato.it (404 si salta, 403/429/5xx fermano, tetto comune ai passi); vettori (riga prima del batch,
tetto di dollari, controllo dell'indice)."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from pipeline import avvisi, vettori
from pipeline.fonti import senato_browser
from pipeline.orchestra import Contesto, Passo, Stato, giro


def ok(ctx):
    return {}


def guasto(ctx):
    raise RuntimeError("HTTP Error 500")


class TestAvvisi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cartella = Path(self.tmp.name)
        self.mail = []

    def tearDown(self):
        self.tmp.cleanup()

    def invia(self, oggetto, testo):
        self.mail.append((oggetto, testo))

    def test_mail_se_non_ok_con_i_passi_falliti(self):
        dal = time.time() - 1
        giro([Passo("a", ok), Passo("b", guasto)], {"giro": {}}, self.cartella)
        log = self.cartella / "giro.log"
        log.write_text("riga uno\nTraceback finale\n")
        avvisi.avvisa(self.cartella, dal, 1, str(log), invia=self.invia)
        self.assertEqual(len(self.mail), 1)
        oggetto, testo = self.mail[0]
        self.assertIn("parziale", oggetto)
        self.assertIn("- b: errore", testo)
        self.assertNotIn("- a:", testo)
        self.assertIn("Traceback finale", testo)

    def test_niente_mail_se_ok_o_rifiutato(self):
        dal = time.time() - 1
        giro([Passo("a", ok)], {"giro": {}}, self.cartella)
        avvisi.avvisa(self.cartella, dal, 0, invia=self.invia)
        avvisi.avvisa(self.cartella, time.time() + 10, avvisi.RIFIUTATO, invia=self.invia)
        self.assertEqual(self.mail, [])

    def test_giro_non_partito(self):
        avvisi.avvisa(self.cartella, time.time() + 10, 1, invia=self.invia)
        self.assertIn("non partito", self.mail[0][0])

    def test_brevo_senza_chiave_non_chiama(self):
        chiamate = []
        with mock.patch.object(avvisi, "env", lambda n, p=None: ""):
            self.assertFalse(avvisi.invia_mail("o", "t", apri=lambda *a, **k: chiamate.append(a)))
        self.assertEqual(chiamate, [])

    def test_brevo_corpo_della_richiesta(self):
        viste = []

        class Risposta:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b"{}"

        def apri(r, timeout):
            viste.append(r)
            return Risposta()
        with mock.patch.object(avvisi, "env", lambda n, p=None: "chiave-finta"):
            self.assertTrue(avvisi.invia_mail("oggetto", "testo", apri=apri))
        r = viste[0]
        corpo = json.loads(r.data)
        self.assertEqual(r.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(r.get_header("Api-key"), "chiave-finta")
        self.assertEqual((corpo["sender"]["email"], corpo["to"][0]["email"]), ("news@parliamentrag.it", "segnalazioni@parliamentrag.it"))


class RispostaFinta:
    def __init__(self, status, corpo=b"ok"):
        self.status, self._corpo = status, corpo

    def body(self):
        return self._corpo


class TestSessioneSenato(unittest.TestCase):
    def sessione(self, stati, ctx=None, massimo=10):
        s = senato_browser.Sessione(pausa=0, massimo=massimo, ctx=ctx)
        risposte = iter(stati)
        s._c = mock.Mock()
        s._c.request.get = lambda url, timeout: RispostaFinta(next(risposte))
        s._verifica = lambda: None
        return s

    def test_404_si_salta_403_429_503_fermano(self):
        self.assertEqual(self.sessione([200]).scarica("u"), b"ok")
        with self.assertRaises(senato_browser.NonTrovato):
            self.sessione([404]).scarica("u")
        for codice in (403, 429, 503):
            with self.assertRaises(senato_browser.Bloccato):
                self.sessione([codice]).scarica("u")

    def test_tetto_comune_ai_passi_dello_stesso_giro(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = Contesto("g1", Path(d), {"senato": {"massimo_richieste_giro": 3}}, {})
            a = self.sessione([200, 200], ctx)
            a.scarica("1"), a.scarica("2")
            b = self.sessione([200, 200], ctx)              # un altro passo, un'altra sessione: lo stesso conto
            b.scarica("3")
            with self.assertRaises(senato_browser.Bloccato):
                b.scarica("4")
            nuovo = Contesto("g2", Path(d), ctx.config, {})   # un giro nuovo riparte da zero
            self.assertEqual(self.sessione([200], nuovo).scarica("5"), b"ok")


class TestVettori(unittest.TestCase):
    def test_riga_prima_del_batch_e_tetto_di_dollari(self):
        ordine = []
        brani = [(vettori.impronta("testo"), "testo")]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(vettori, "_leggi", lambda sql: brani if "speech" in sql else []), \
                mock.patch.object(vettori, "spesa_recente", lambda ore=24: 0.0), \
                mock.patch.object(vettori, "psql", lambda s, timeout=900: ordine.append(("psql", s.split()[0]))), \
                mock.patch.object(vettori.batch, "invia", lambda f, e, descr, meta: ordine.append(("openai", meta["riga"][:9])) or "batch_1"):
            r = vettori.invia(1, Path(d), tetto_dollari=1)
            self.assertEqual(r["batch"], 1)
            self.assertEqual(ordine, [("psql", "COPY"), ("openai", "in_invio-"), ("psql", "UPDATE")])
            ordine.clear()
            r = vettori.invia(1, Path(d), tetto_dollari=0)
            self.assertEqual((r["batch"], ordine), (0, []))
            self.assertIn("tetto", r["avviso"])

    def test_controllo_dell_indice(self):
        with mock.patch.object(vettori, "_leggi", lambda sql: [["t"]]):
            self.assertTrue(vettori.controlla_indice()["validi"])
        with mock.patch.object(vettori, "_leggi", lambda sql: []):
            with self.assertRaises(RuntimeError):
                vettori.controlla_indice()
        with mock.patch.object(vettori, "_leggi", lambda sql: [["f"]]):
            with self.assertRaises(RuntimeError):
                vettori.controlla_indice()


if __name__ == "__main__":
    unittest.main()
