"""Agente della chat: un modello OpenAI (API Responses) che sceglie da sé gli strumenti del registro e risponde solo con
quei dati. Chiamate a OpenAI con la libreria standard. Gli eventi escono in NDJSON: status, tool, dati, delta,
suggestions, done, error.

Limiti fuori dal modello: passi massimi per domanda, domande per IP al giorno, tetto di spesa giornaliero (token
contati dalle risposte di OpenAI, in `dati/api/spesa.sqlite`). I link della risposta che non compaiono nei dati letti
si tolgono; una risposta con citazioni passa sempre da `verifica_citazioni`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

from pipeline.ambiente import QUI, env

from . import registro
from .db import connessione

OPENAI = "https://api.openai.com/v1/responses"
PASSI_MAX = 8
TAGLIO = 14000                      # caratteri di risultato che il modello vede per ogni chiamata
# prezzi per milione di token (input, input in cache, output), da tenere allineati al listino OpenAI
PREZZI = {"gpt-5.6-terra": (1.25, 0.125, 10.0)}

PROMPT = """Sei la chat di ParliamentRAG: rispondi a domande sul Parlamento italiano (Camera e Senato, XIX legislatura, dal 13 ottobre 2022) usando solo i dati che trovi con gli strumenti. Oggi è il {oggi}. L'ultima seduta nei dati è del {ultima}.

Come lavori
- Capisci da solo cosa serve e chiama gli strumenti adatti, anche più di uno e in parallelo. Se un tentativo non trova niente, prova un'altra strada (altre parole, l'altro ramo, un altro strumento) prima di arrenderti.
- Camera e Senato insieme, salvo che la domanda (o la precedente) ne indichi uno. Una domanda breve come «e al Senato?» continua la precedente con lo stesso tipo di dato.
- Gli strumenti di dettaglio vogliono l'uri: trovalo prima con gli strumenti di ricerca.

Regole
- I fatti vengono dai dati, mai dalla memoria. Sono fatti: votazioni e numeri, atti e iter, composizione, schede. Le affermazioni dette negli interventi non sono fatti: attribuiscile sempre («secondo X (gruppo), in Aula il <data>, …»).
- Le parole dei parlamentari solo tra «…», copiate esattamente da un intervento, con nome e gruppo vicino. Mai citare tra «…» un intervento di tipo summary: è il riassunto del funzionario. Se citi, chiama verifica_citazioni sulla risposta prima di chiuderla e togli le citazioni non verificate.
- Gruppo Misto: indica la componente, non «Misto».
- Se il dato non c'è, dillo in una frase e indica la fonte ufficiale. I dati si aggiornano ogni notte: per oggi o gli ultimi giorni dì fino a quando arrivano.
- Link solo a indirizzi presenti nei dati letti, come link Markdown [testo](url).
- Rispondi in {lingua}; le citazioni restano in italiano. Risposta diretta in alto, poi i dettagli. Frasi semplici, niente titoli. Non nominare gli strumenti.
- Alla fine, su una riga a parte, scrivi SEGUITI: e tre domande successive utili separate da « | »."""


_blocco = threading.Lock()


def _registro_spesa() -> sqlite3.Connection:
    f = QUI / "dati" / "api" / "spesa.sqlite"
    f.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(f, check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS uso (giorno TEXT, ip TEXT, domande INTEGER, dollari REAL, PRIMARY KEY (giorno, ip))")
    return db


def _oggi() -> str:
    return dt.date.today().isoformat()


def controlla_limiti(ip: str) -> str | None:
    """Il motivo del rifiuto, o None se si può rispondere."""
    per_ip, tetto = int(env("AGENTE_DOMANDE_IP_GIORNO", "30")), float(env("AGENTE_DOLLARI_GIORNO", "10"))
    with _blocco, _registro_spesa() as db:
        mie = db.execute("SELECT coalesce(sum(domande), 0) FROM uso WHERE giorno = ? AND ip = ?", (_oggi(), ip)).fetchone()[0]
        tutti = db.execute("SELECT coalesce(sum(dollari), 0) FROM uso WHERE giorno = ?", (_oggi(),)).fetchone()[0]
    if mie >= per_ip:
        return f"hai fatto {mie} domande oggi: il limite è {per_ip} al giorno"
    if tutti >= tetto:
        return "la chat ha raggiunto il tetto di spesa di oggi: riprova domani"
    return None


def _conta(ip: str, domande: int, dollari: float) -> None:
    with _blocco, _registro_spesa() as db:
        db.execute("""INSERT INTO uso VALUES (?, ?, ?, ?) ON CONFLICT (giorno, ip)
                      DO UPDATE SET domande = domande + excluded.domande, dollari = dollari + excluded.dollari""", (_oggi(), ip, domande, dollari))


def _costo(modello: str, uso: dict) -> float:
    pin, pcache, pout = PREZZI.get(modello, (2.0, 0.2, 15.0))     # modello senza prezzo: stima per eccesso
    cache = (uso.get("input_tokens_details") or {}).get("cached_tokens", 0)
    return ((uso.get("input_tokens", 0) - cache) * pin + cache * pcache + uso.get("output_tokens", 0) * pout) / 1e6


def schemi() -> list[dict]:
    return [{"type": "function", "name": s.nome, "description": s.descrizione, "parameters": s.schema()} for s in registro.STRUMENTI]


def chiama_openai(modello: str, istruzioni: str, voci: list, chiave: str) -> dict:
    # store falso: niente resta sui server di OpenAI; il ragionamento torna cifrato e si ripassa al passo dopo
    corpo = json.dumps({"model": modello, "instructions": istruzioni, "input": voci, "tools": schemi(), "tool_choice": "auto",
                        "parallel_tool_calls": True, "reasoning": {"effort": "low"}, "store": False,
                        "include": ["reasoning.encrypted_content"]}).encode()
    req = urllib.request.Request(OPENAI, corpo, {"Content-Type": "application/json", "Authorization": f"Bearer {chiave}"})
    for tentativo in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as e:
            if tentativo == 2 or isinstance(e, urllib.error.HTTPError) and e.code < 500:
                raise
    raise RuntimeError("non raggiungibile")


def solo_link_visti(testo: str, visti: set[str]) -> tuple[str, int]:
    """Toglie i link che non compaiono nei dati letti: niente indirizzi inventati o copiati male."""
    tolti = 0

    def tieni(m):
        nonlocal tolti
        if m.group(2) in visti:
            return m.group(0)
        tolti += 1
        return m.group(1)
    return re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)\)", tieni, testo), tolti


def _conteggio(ris) -> int | None:
    if isinstance(ris, list):
        return len(ris)
    if isinstance(ris, dict):
        for k in ("items", "results", "groups"):
            if isinstance(ris.get(k), list):
                return len(ris[k])
    return None


def rispondi(domanda: str, storia: list[dict], lingua: str, ip: str) -> Iterator[dict]:
    """Generatore di eventi per una domanda. Ogni strumento usa una connessione di sola lettura."""
    modello = env("AGENTE_MODELLO", "gpt-5.6-terra")
    try:
        chiave = env("OPENAI_API_KEY")
    except KeyError:
        yield {"type": "error", "text": "chat non disponibile: manca la chiave del modello"}
        return
    voci = [{"role": m["role"], "content": str(m["content"])[:4000]} for m in storia[-8:]
            if m.get("role") in ("user", "assistant") and m.get("content")]
    voci.append({"role": "user", "content": domanda[:2000]})
    spesa, n, visti = 0.0, 0, set()
    with connessione() as c:
        ultima = c.execute("SELECT max(date) AS d FROM sitting WHERE status = 'held'").fetchone()["d"]
        istruzioni = PROMPT.format(oggi=dt.date.today().strftime("%d/%m/%Y"), ultima=ultima.strftime("%d/%m/%Y") if ultima else "?",
                                   lingua="inglese" if lingua == "en" else "italiano")
        yield {"type": "status", "text": "Leggo la domanda" if lingua != "en" else "Reading the question"}
        try:
            for _ in range(PASSI_MAX):
                try:
                    r = chiama_openai(modello, istruzioni, voci, chiave)
                except urllib.error.HTTPError as e:
                    yield {"type": "error", "text": f"il modello non risponde ({e.code})"}
                    return
                except (urllib.error.URLError, TimeoutError, RuntimeError):
                    yield {"type": "error", "text": "il modello non risponde"}
                    return
                spesa += _costo(modello, r.get("usage") or {})
                uscita = r.get("output") or []
                voci.extend(uscita)
                chiamate = [x for x in uscita if x.get("type") == "function_call"]
                if not chiamate:
                    yield from _chiudi(c, uscita, voci, visti, domanda)
                    return
                for x in chiamate:
                    n += 1
                    try:
                        argomenti = json.loads(x.get("arguments") or "{}")
                    except ValueError:
                        argomenti = {}
                    yield {"type": "tool", "id": str(n), "state": "start", "name": x["name"], "args": argomenti}
                    try:
                        ris = registro.esegui(c, x["name"], argomenti)
                    except Exception as e:             # l'errore torna al modello, che può riprovare in un altro modo
                        ris = {"errore": str(e)[:300]}
                    yield {"type": "tool", "id": str(n), "state": "done", "name": x["name"], "count": _conteggio(ris)}
                    yield {"type": "dati", "name": x["name"], "args": argomenti, "result": ris}
                    testo = registro.in_testo(ris)
                    visti.update(re.findall(r"https?://[^\s\"'<>)\]]+", testo))
                    voci.append({"type": "function_call_output", "call_id": x["call_id"],
                                 "output": testo[:TAGLIO] + ("…[troncato]" if len(testo) > TAGLIO else "")})
            yield {"type": "delta", "text": "Non sono riuscito a chiudere la risposta: prova con una domanda più precisa."}
            yield {"type": "done"}
        finally:
            _conta(ip, 1, spesa)


def _chiudi(c, uscita: list, voci: list, visti: set[str], domanda: str) -> Iterator[dict]:
    testo = "".join(p.get("text", "") for x in uscita if x.get("type") == "message" for p in x.get("content") or []
                    if p.get("type") == "output_text")
    m = re.search(r"\n?\s*SEGUITI:\s*(.+)\s*$", testo)
    seguiti = [x.strip() for x in m.group(1).split("|") if x.strip()][:3] if m else []
    testo = testo[: m.start()].rstrip() if m else testo
    testo, tolti = solo_link_visti(testo, visti)
    if tolti:
        yield {"type": "status", "text": f"{tolti} link non verificati tolti"}
    # una risposta con citazioni passa sempre dal controllo, anche se il modello non l'ha chiesto
    if "«" in testo:
        ris = registro.esegui(c, "verifica_citazioni", {"text": testo})
        yield {"type": "dati", "name": "verifica_citazioni", "args": {}, "result": ris}
    yield {"type": "delta", "text": testo}
    if seguiti:
        yield {"type": "suggestions", "questions": seguiti}
    yield {"type": "done"}
