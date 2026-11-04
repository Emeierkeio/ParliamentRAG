"""Avviso a fine giro: se l'esito non è ok (o ci sono avvisi, come file in quarantena), una mail a
segnalazioni@parliamentrag.it via Brevo con i passi falliti e la coda del log. La chiave sta in BREVO_API_KEY
(ambiente o .env) e non si stampa; senza chiave l'avviso si scrive solo nel log.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from .ambiente import env
from .orchestra import Stato

BREVO = "https://api.brevo.com/v3/smtp/email"
MITTENTE = {"name": "ParliamentRAG", "email": "news@parliamentrag.it"}
DESTINATARIO = "segnalazioni@parliamentrag.it"
RIFIUTATO = 3


def riepilogo(stato: Stato, giro: str) -> tuple[str, list[str], list[str]]:
    """Esito del giro, righe dei passi non riusciti, avvisi dei passi riusciti."""
    info = stato.giro_info(giro) or {}
    falliti, avvisi = [], []
    for nome, esito, t, _ini, _fine, riep, err in stato.passi_del_giro(giro):
        if esito not in ("ok", "in_corso"):
            falliti.append(f"- {nome}: {esito} (tentativo {t}) {(err or '').strip().splitlines()[-1][:400] if err else ''}")
        elif esito == "in_corso":
            falliti.append(f"- {nome}: rimasto in corso (il giro si è fermato qui)")
        try:
            a = json.loads(riep or "{}").get("avviso")
        except (ValueError, AttributeError):
            a = None
        avvisi += [f"- {nome}: {x[:600]}" for x in ([a] if isinstance(a, str) else a or [])]
    return info.get("esito") or "sconosciuto", falliti, avvisi


def testo_mail(giro: str, esito: str, falliti: list[str], avvisi: list[str], coda_log: str) -> tuple[str, str]:
    oggetto = f"Giro notturno {giro}: {esito}" + (f", {len(falliti)} passi non riusciti" if falliti else "") + \
              (f", {len(avvisi)} avvisi" if avvisi else "")
    parti = [f"Giro {giro}, esito: {esito}."]
    if falliti:
        parti += ["", "Passi non riusciti:", *falliti]
    if avvisi:
        parti += ["", "Avvisi:", *avvisi]
    if coda_log:
        parti += ["", "Fine del log:", coda_log]
    parti += ["", "Dettagli: python -m pipeline stato " + giro]
    return oggetto, "\n".join(parti)


def invia_mail(oggetto: str, testo: str, apri=urllib.request.urlopen) -> bool:
    chiave = env("BREVO_API_KEY", "")
    if not chiave:
        print("BREVO_API_KEY assente: la mail non parte", flush=True)
        return False
    corpo = {"sender": MITTENTE, "to": [{"email": DESTINATARIO}], "subject": oggetto[:200], "textContent": testo[:50_000]}
    r = urllib.request.Request(BREVO, json.dumps(corpo).encode(), {"api-key": chiave, "Content-Type": "application/json", "accept": "application/json"})
    try:
        with apri(r, timeout=30) as risposta:
            risposta.read()
        return True
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"mail non inviata: {e}", flush=True)
        return False


def avvisa(cartella: Path, dal: float, uscita: int, log: str = "", invia=invia_mail) -> int:
    """Guarda i giri partiti da `dal` (l'ora di avvio di notte.sh) e manda la mail se serve. Restituisce 0."""
    if uscita == RIFIUTATO:
        print("giro rifiutato (ce n'era già uno recente): nessuna mail", flush=True)
        return 0
    coda = ""
    if log and Path(log).is_file():
        coda = "\n".join(Path(log).read_text(errors="replace").splitlines()[-40:])
    stato = Stato(cartella / "stato.sqlite")
    giri = stato.giri_dal(dal)
    if not giri:
        oggetto, testo = testo_mail("(non partito)", f"uscita {uscita}", [], [], coda)
        invia(oggetto, testo)
        return 0
    g = giri[-1]
    esito, falliti, avvisi = riepilogo(stato, g)
    if esito == "ok" and not falliti and not avvisi and uscita == 0:
        print(f"giro {g} ok: nessuna mail", flush=True)
        return 0
    oggetto, testo = testo_mail(g, esito, falliti, avvisi, coda if esito != "ok" else "")
    invia(oggetto, testo)
    return 0
