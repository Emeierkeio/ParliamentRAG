"""Server locale dell'ecosistema: pagine statiche + /api inoltrato al backend.

Il backend non accetta richieste da altri domini (CORS), quindi il browser
chiama /api sullo stesso indirizzo delle pagine e questo server le inoltra.
In produzione lo stesso ruolo lo fa una route del sito o la configurazione CORS.

    python3 serve.py            # http://localhost:4873
    BACKEND=https://... python3 serve.py
"""

import http.server
import json
import os
import socketserver
import time
import urllib.error
import urllib.request

PORTA = int(os.environ.get("PORT", "4873"))
BACKEND = os.environ.get("BACKEND", "https://thesis-parliamentrag-production.up.railway.app").rstrip("/")
RADICE = os.path.dirname(os.path.abspath(__file__))

# Le votazioni passate non cambiano: una cache in memoria evita di rifare le stesse chiamate.
CACHE: dict[str, tuple[float, int, bytes]] = {}
DURATA_CACHE = 600


class Gestore(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=RADICE, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.inoltra()
        if self.path.split("?")[0] == "/shared/data/dati.js":
            return self.dati_vivi()
        return super().do_GET()

    def dati_vivi(self):
        """dati.js con i numeri del grafo letti adesso dal backend (lo stesso grafo di Fascicoli).

        Tutte le pagine leggono numeri e data da qui, quindi sono sempre allineate.
        Se il backend non risponde resta il file statico. `triples` viene dall'export RDF
        e il backend lo restituisce vuoto: in quel caso si tiene quello del file.
        """
        with open(os.path.join(RADICE, "shared", "data", "dati.js"), encoding="utf-8") as f:
            testo = f.read()
        dati = json.loads(testo[len("window.DATI="):].rstrip().rstrip(";"))
        try:
            adesso = time.time()
            voce = CACHE.get("/api/data/stats")
            if voce and adesso - voce[0] < DURATA_CACHE:
                vivi = json.loads(voce[2])
            else:
                with urllib.request.urlopen(BACKEND + "/api/data/stats", timeout=20) as r:
                    corpo = r.read()
                CACHE["/api/data/stats"] = (adesso, 200, corpo)
                vivi = json.loads(corpo)
            for k, v in vivi.items():
                if v is not None:
                    dati["stats"][k] = v
        except Exception:
            pass
        corpo = ("window.DATI=" + json.dumps(dati, ensure_ascii=False) + ";").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def inoltra(self):
        adesso = time.time()
        voce = CACHE.get(self.path)
        if voce and adesso - voce[0] < DURATA_CACHE:
            return self.rispondi(voce[1], voce[2])
        richiesta = urllib.request.Request(BACKEND + self.path, headers={"Accept-Language": "it", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(richiesta, timeout=60) as r:
                corpo = r.read()
                CACHE[self.path] = (adesso, r.status, corpo)
                self.rispondi(r.status, corpo)
        except urllib.error.HTTPError as e:
            self.rispondi(e.code, e.read() or b'{"detail":"errore del backend"}')
        except Exception:
            self.rispondi(502, b'{"detail":"backend non raggiungibile"}')

    def rispondi(self, stato, corpo):
        self.send_response(stato)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args):
        if self.path.startswith("/api/"):
            super().log_message(formato, *args)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"Ecosistema su http://localhost:{PORTA}  ·  /api → {BACKEND}")
    Server(("", PORTA), Gestore).serve_forever()
