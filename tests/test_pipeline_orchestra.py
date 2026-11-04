"""Orchestratore: dipendenze, blocco della Camera, tempo del giro, prove iniziali, lucchetto, scadenza e interruzione."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from pipeline.orchestra import Lucchetto, Passo, Stato, giro, ordina

QUI = Path(__file__).resolve().parent.parent


# i passi girano in un processo a parte: funzioni a livello di modulo, che si possono copiare
def ok(ctx):
    return {"fatto": True}


def fallisce(ctx):
    raise RuntimeError("guasto")


def camera_503(ctx):
    raise RuntimeError("urllib.error.HTTPError: HTTP Error 503: Service Unavailable")


def con_avviso(ctx):
    return {"trasformati": 3, "avviso": "1 grezzo non trasformato"}


def lancia_figlio_e_dorme(ctx):
    p = subprocess.Popen(["sleep", "60"])
    (ctx.cartella / "nipote.pid").write_text(str(p.pid))
    time.sleep(60)


def dorme(ctx):
    (ctx.cartella / "partito").write_text("1")
    time.sleep(60)


def _vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # un processo finito ma non ancora raccolto (zombie) conta come morto
    r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return bool(r.stdout.strip()) and not r.stdout.strip().startswith("Z")


class TestOrchestra(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cartella = Path(self.tmp.name)
        self.config = {"giro": {"timeout_minuti": 60}}

    def tearDown(self):
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        self.tmp.cleanup()

    def test_fallito_ferma_solo_chi_dipende(self):
        passi = [Passo("a", fallisce), Passo("b", ok, dopo=["a"]), Passo("c", ok, dopo_comunque=["a"]), Passo("d", ok)]
        r = giro(passi, self.config, self.cartella)
        self.assertEqual(r["passi"], {"a": "errore", "b": "saltato", "c": "ok", "d": "ok"})
        self.assertEqual(r["esito"], "parziale")

    def test_dopo_comunque_ordina(self):
        passi = [Passo("carica", ok, dopo_comunque=["t1", "t2"]), Passo("t1", ok), Passo("t2", ok)]
        self.assertEqual([p.nome for p in ordina(passi)], ["t1", "t2", "carica"])
        with self.assertRaises(ValueError):
            ordina([Passo("x", ok, dopo_comunque=["manca"])])

    def test_blocco_della_camera_salta_gli_altri_passi_della_camera(self):
        passi = [Passo("scarica_camera_a", camera_503, sito="camera", tentativi=3), Passo("scarica_camera_b", ok, sito="camera"),
                 Passo("scarica_senato", ok)]
        inizio = time.time()
        r = giro(passi, self.config, self.cartella)
        self.assertLess(time.time() - inizio, 30)          # niente secondo tentativo contro un sito che blocca
        self.assertEqual(r["passi"], {"scarica_camera_a": "errore", "scarica_camera_b": "saltato", "scarica_senato": "ok"})
        errore = dict((n, e) for n, _, _, _, _, _, e in Stato(self.cartella / "stato.sqlite").passi_del_giro(r["giro"]))["scarica_camera_b"]
        self.assertIn("503", errore)

    def test_tempo_del_giro_finito_non_salta_il_caricamento(self):
        passi = [Passo("scarica_x", ok), Passo("carica", ok, dopo_comunque=["scarica_x"], limite_giro=False)]
        r = giro(passi, {"giro": {"timeout_minuti": -1}}, self.cartella)
        self.assertEqual(r["passi"], {"scarica_x": "saltato", "carica": "ok"})

    def test_prova_iniziale_ferma_il_giro(self):
        def database():
            raise RuntimeError("il database non risponde")
        r = giro([Passo("a", ok)], self.config, self.cartella, prove=[("prova_database", database)])
        self.assertEqual(r["esito"], "bloccato")
        self.assertNotIn("a", r["passi"])
        self.assertEqual(Stato(self.cartella / "stato.sqlite").giro_info(r["giro"])["esito"], "bloccato")

    def test_avvisi_nel_risultato(self):
        r = giro([Passo("t", con_avviso)], self.config, self.cartella)
        self.assertEqual(r["esito"], "ok")
        self.assertEqual(r["avvisi"], ["t: 1 grezzo non trasformato"])

    def test_scadenza_ferma_anche_i_figli(self):
        r = giro([Passo("lungo", lancia_figlio_e_dorme, timeout_minuti=0.05)], self.config, self.cartella)
        self.assertEqual(r["passi"]["lungo"], "timeout")
        pid = int((self.cartella / "nipote.pid").read_text())
        for _ in range(20):
            if not _vivo(pid):
                break
            time.sleep(0.2)
        self.assertFalse(_vivo(pid), "il processo lanciato dal passo è ancora vivo")

    def test_tipo_e_ultimo_riuscito(self):
        r = giro([Passo("a", ok)], self.config, self.cartella, tipo="passo")
        st = Stato(self.cartella / "stato.sqlite")
        self.assertEqual(st.giro_info(r["giro"])["tipo"], "passo")
        self.assertIsNone(st.ultimo_riuscito())            # un giro di soli passi non conta come giro completo
        r = giro([Passo("a", ok)], self.config, self.cartella)
        self.assertEqual(st.ultimo_riuscito()["id"], r["giro"])

    def test_sigterm_chiude_il_giro_come_interrotto(self):
        codice = ("import sys; from pathlib import Path; from pipeline.orchestra import Passo, giro; "
                  "from tests.test_pipeline_orchestra import dorme; "
                  f"giro([Passo('lungo', dorme)], {{'giro': {{'timeout_minuti': 60}}}}, Path({str(self.cartella)!r}))")
        p = subprocess.Popen([sys.executable, "-c", codice], cwd=QUI)
        for _ in range(100):
            if (self.cartella / "partito").exists():
                break
            time.sleep(0.1)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(30), 128 + signal.SIGTERM)
        st = Stato(self.cartella / "stato.sqlite")
        g = st.ultimo_giro()
        self.assertEqual(st.giro_info(g)["esito"], "interrotto")
        self.assertEqual(st.passi_del_giro(g)[0][1], "interrotto")
        self.assertFalse((self.cartella / "giro.lock").exists())


class TestLucchetto(unittest.TestCase):
    def test_un_giro_alla_volta_e_lucchetto_scaduto(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "giro.lock"
            with Lucchetto(f):
                with self.assertRaises(RuntimeError):
                    Lucchetto(f).__enter__()
            self.assertFalse(f.exists())
            p = subprocess.Popen(["true"])
            p.wait()
            f.write_text(str(p.pid))                       # pid di un processo che non c'è più
            with Lucchetto(f):
                self.assertEqual(f.read_text(), str(os.getpid()))


if __name__ == "__main__":
    unittest.main()
