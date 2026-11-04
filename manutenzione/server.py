"""Pagina di manutenzione: risponde 503 con Retry-After su ogni percorso.

Solo libreria standard. La porta arriva da $PORT (Railway la assegna), in locale 8080.
/salute e /v1/salute rispondono 200: servono al controllo di Railway a ogni rilascio,
che altrimenti non metterebbe mai in linea il servizio.
"""

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGINA = (Path(__file__).resolve().parent / "index.html").read_bytes()
SALUTE = {"/salute", "/v1/salute"}


class Manutenzione(BaseHTTPRequestHandler):
    def version_string(self) -> str:
        return "manutenzione"

    def _rispondi(self, corpo: bool) -> None:
        percorso = self.path.split("?", 1)[0]
        # il controllo di Railway usa il percorso impostato nel servizio (spesso «/»): si riconosce dallo User-Agent
        if percorso in SALUTE or self.headers.get("User-Agent", "").startswith("RailwayHealthCheck"):
            stato, dati, tipo = 200, b"ok\n", "text/plain; charset=utf-8"
        else:
            stato, dati, tipo = 503, PAGINA, "text/html; charset=utf-8"
        self.send_response(stato)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dati)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex")
        if stato == 503:
            self.send_header("Retry-After", "3600")
        self.end_headers()
        if corpo:
            self.wfile.write(dati)

    def do_GET(self) -> None:
        self._rispondi(True)

    def do_HEAD(self) -> None:
        self._rispondi(False)

    # ogni altro metodo riceve la stessa pagina
    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_GET

    def log_message(self, formato: str, *args) -> None:
        # niente IP nei log: solo metodo, percorso e stato
        print(f"{self.command} {self.path.split('?', 1)[0]} {args[1] if len(args) > 1 else ''}", flush=True)


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", "8080"))
    print(f"manutenzione in ascolto sulla porta {porta}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", porta), Manutenzione).serve_forever()
