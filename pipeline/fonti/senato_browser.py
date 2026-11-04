"""Pagine di senato.it dietro il WAF di AWS, che risponde 202 con una pagina di verifica in JavaScript finché il browser
non ha il cookie `aws-waf-token`. Si apre una volta la pagina con Chromium senza interfaccia (Playwright), la verifica
si risolve da sola, e le richieste successive passano con gli stessi cookie, senza aprire altre pagine.

senato.it blocca l'IP dopo circa 400 richieste ravvicinate, a qualunque ritmo (memoria dei giri di ottobre): ogni
sessione ha un tetto suo e una pausa fra l'una e l'altra, e tutte le sessioni dello stesso giro contano le richieste
in un file comune (`senato_richieste.json` nella cartella dei dati) con un tetto per giro
(`[senato] massimo_richieste_giro` di pipeline.toml): i passi girano in processi diversi e da soli non si vedono.

Un 404 (o un altro 4xx che non sia 403 o 429) vuol dire che quella pagina non c'è: `NonTrovato`, che chi chiama salta.
Solo 403, 429 e 5xx (e la rete) sono un blocco: `Bloccato`, e la sessione si ferma.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

BASE = "https://www.senato.it/"
UA = "Mozilla/5.0 (compatible; ParliamentRAG/1.0; +https://www.parliamentrag.it)"


class Bloccato(RuntimeError):
    """senato.it non ha servito la pagina neanche dopo la verifica: si riprova al giro dopo."""


class NonTrovato(RuntimeError):
    """La pagina non c'è (404 o un altro 4xx che non sia un blocco): si salta, le altre vanno avanti."""


BLOCCHI = {403, 429}
SALTA_RISORSE = {"image", "stylesheet", "font", "media"}    # la verifica del WAF chiede solo HTML e JavaScript


class Contatore:
    """Le richieste a senato.it di un giro, in un file comune a tutti i passi del giro."""

    def __init__(self, ctx):
        self.file = Path(ctx.cartella) / "senato_richieste.json"
        self.giro = ctx.giro
        self.tetto = int(ctx.config.get("senato", {}).get("massimo_richieste_giro", 350))

    def fatte(self) -> int:
        try:
            d = json.loads(self.file.read_text())
        except (OSError, ValueError):
            return 0
        return int(d.get("fatte", 0)) if d.get("giro") == self.giro else 0

    def conta(self) -> None:
        n = self.fatte()
        if n >= self.tetto:
            raise Bloccato(f"tetto di {self.tetto} richieste a senato.it per giro raggiunto")
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"giro": self.giro, "fatte": n + 1}))
        tmp.replace(self.file)


class Sessione:
    def __init__(self, pausa: float = 2.0, massimo: int = 300, ctx=None):
        self.pausa, self.massimo, self.fatte = pausa, massimo, 0
        self.contatore = Contatore(ctx) if ctx is not None else None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._p = sync_playwright().start()
        self._b = self._p.chromium.launch(headless=True)
        self._c = self._b.new_context(locale="it-IT", user_agent=UA)
        self._c.route("**/*", lambda r: r.abort() if r.request.resource_type in SALTA_RISORSE else r.continue_())
        try:
            self._verifica()
        except BaseException:
            self.__exit__()                          # la verifica non passa: il browser non resta aperto
            raise
        return self

    def __exit__(self, *_):
        self._b.close()
        self._p.stop()

    def _verifica(self) -> None:
        if self.contatore:
            self.contatore.conta()
        pagina = self._c.new_page()
        try:
            pagina.goto(BASE, wait_until="domcontentloaded", timeout=60_000)
            # la pagina di verifica si ricarica da sola nella pagina vera, che ha il menu del sito
            pagina.wait_for_function("() => !!document.querySelector('a[href*=\"composizione\"]')", timeout=45_000)
        except Exception as e:
            raise Bloccato(f"senato.it non supera la verifica: {e}") from e
        finally:
            pagina.close()

    def scarica(self, url: str) -> bytes:
        """Il contenuto di un indirizzo di senato.it; un 202 vuol dire verifica scaduta: si rifà una volta."""
        if self.fatte >= self.massimo:
            raise Bloccato(f"tetto di {self.massimo} richieste per giro raggiunto")
        from playwright.sync_api import Error as ErrorePlaywright
        for tentativo in (1, 2):
            time.sleep(self.pausa * tentativo)
            if self.contatore:
                self.contatore.conta()
            self.fatte += 1
            try:
                r = self._c.request.get(url, timeout=60_000)
            except ErrorePlaywright as e:              # rete: connessione chiusa, tempo scaduto, cambio di IP
                if tentativo == 1:
                    continue
                raise Bloccato(f"{url}: {str(e).splitlines()[0][:200]}") from e
            if r.status == 200:
                return r.body()
            if r.status == 202 and tentativo == 1:
                self._verifica()
                continue
            if 400 <= r.status < 500 and r.status not in BLOCCHI:
                raise NonTrovato(f"{url}: HTTP {r.status}")
            raise Bloccato(f"{url}: HTTP {r.status}")
        raise Bloccato(url)
