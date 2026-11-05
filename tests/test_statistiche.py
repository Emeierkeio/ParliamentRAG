"""Statistiche di visita (api/statistiche.py): cosa si salva di una visita, senza database."""

import datetime as dt
import unittest
from unittest import mock

from api import statistiche as S


class TestStatistiche(unittest.TestCase):
    def test_percorso_senza_id_delle_condivise(self):
        self.assertEqual(S.percorso("/#/c/y-CW7dTYFmtcwrtP"), "/#/c/…")
        self.assertEqual(S.percorso("/?lang=it#/strumenti/sedute"), "/")
        self.assertEqual(S.percorso("/#/strumenti/fonte?u=x&t=y"), "/#/strumenti/fonte")

    def test_provenienza_solo_esterna(self):
        self.assertEqual(S.provenienza("https://www.google.com/search?q=x"), "google.com")
        self.assertIsNone(S.provenienza("https://www.parliamentrag.it/#/"))
        self.assertIsNone(S.provenienza(""))

    def test_dispositivo_e_browser(self):
        self.assertEqual((S.dispositivo(390), S.dispositivo(900), S.dispositivo(1440), S.dispositivo(None)),
                         ("telefono", "tablet", "computer", None))
        self.assertEqual(S.browser("Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15"), "Safari")
        self.assertEqual(S.browser("Mozilla/5.0 Chrome/130.0 Safari/537.36 Edg/130.0"), "Edge")

    def test_visitatore_cambia_col_giorno(self):
        with mock.patch.object(S.agente, "_sale", lambda: b"chiave"):
            a = S._visitatore("1.2.3.4", "ua", dt.date(2026, 11, 4))
            self.assertEqual(a, S._visitatore("1.2.3.4", "ua", dt.date(2026, 11, 4)))
            self.assertNotEqual(a, S._visitatore("1.2.3.4", "ua", dt.date(2026, 11, 5)))
            self.assertNotIn("1.2.3.4", a)

    def test_senza_login_configurato_il_pannello_non_esiste(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        req = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)})
        with mock.patch.object(S.accesso, "env", lambda nome, pred=None: ""):
            with self.assertRaises(HTTPException) as e:
                S._login(req)
            self.assertEqual(e.exception.status_code, 404)

    def test_accesso_col_cookie_firmato(self):
        import time
        from fastapi import HTTPException
        from starlette.requests import Request
        A = S.accesso
        cred = {"STATISTICHE_UTENTE": "u", "STATISTICHE_PASSWORD": "p"}
        req = lambda cookie: Request({"type": "http", "headers": [(b"cookie", cookie.encode())], "client": ("127.0.0.1", 1),  # noqa: E731
                                      "path": "/sistema", "query_string": b"", "scheme": "http", "server": ("x", 80)})
        with mock.patch.object(A, "env", lambda nome, pred=None: cred.get(nome, pred)):
            scad = int(time.time()) + 60
            self.assertTrue(A.dentro(req(f"pannello={scad}.{A._firma(scad)}")))
            self.assertFalse(A.dentro(req(f"pannello={scad}.firma-sbagliata")))
            self.assertFalse(A.dentro(req(f"pannello={scad - 120}.{A._firma(scad - 120)}")))      # scaduto
            with self.assertRaises(HTTPException) as e:
                A.richiedi(req(""), pagina=True)
            self.assertEqual((e.exception.status_code, e.exception.headers["Location"]), (303, "/accedi?dopo=/sistema"))

    def test_periodo(self):
        oggi = dt.date.today()
        self.assertEqual(S.periodo(7), (oggi - dt.timedelta(days=6), oggi))
        self.assertEqual(S.periodo(30, oggi, oggi + dt.timedelta(days=5)), (oggi, oggi))       # mai oltre oggi
        self.assertEqual(S.periodo(30, oggi, oggi - dt.timedelta(days=2)), (oggi - dt.timedelta(days=2),) * 2)


if __name__ == "__main__":
    unittest.main()
