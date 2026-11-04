"""Agente della chat: un modello OpenAI (API Responses) che sceglie da sé gli strumenti del registro e risponde solo con
quei dati. Chiamate a OpenAI con la libreria standard. Gli eventi escono in NDJSON: status, tool, dati, delta,
suggestions, done, error.

Limiti fuori dal modello: passi massimi per domanda, domande nell'ora in corso per IP (contate per impronta, mai per IP), tetto di spesa giornaliero (token
contati dalle risposte di OpenAI). Stanno nello schema `sito` di Postgres, così un rilascio non li azzera; senza
SITO_PG_PASSWORD (sviluppo) in `dati/api/spesa.sqlite`. I link della risposta che non compaiono nei dati letti
si tolgono; una risposta con citazioni passa sempre da `verifica_citazioni`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

from pipeline.ambiente import QUI, env

from . import registro
from .db import connessione, connessione_sito

log = logging.getLogger("parliamentrag.agente")

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
- Per un tema o «cosa si è detto su…», e quando le parole esatte non trovano abbastanza, cerca per significato; per una frase o una parola precisa cerca negli interventi per parole.
- Per numeri, conteggi, classifiche, percentuali e matrici usa gli strumenti di conteggio, mai la stima né un campione. Dai il numero con quello che dice il campo counted (che cosa si è contato, periodo, regole) e Camera e Senato separati, salvo che la domanda chieda il totale.
- Un elenco con il campo more, o con total maggiore degli elementi ricevuti, è parziale: leggi le pagine successive (offset) o usa un conteggio prima di concludere. Da un elenco parziale non si ricavano «mai», «nessuno», «tutti» né totali; se non hai letto tutto, dì quanti ne hai controllati su quanti.
- Le didascalie del resoconto (applausi, proteste, commenti, chi «si leva in piedi») stanno nelle reactions degli interventi della seduta e si cercano negli interventi con captions: riportale come sono scritte.

Regole
- I fatti vengono dai dati, mai dalla memoria. Sono fatti: votazioni e numeri, atti e iter, composizione, schede. Le affermazioni dette negli interventi non sono fatti: attribuiscile sempre («secondo X (gruppo), in Aula il <data>, …»).
- Le parole dei parlamentari solo tra «…», copiate esattamente da un intervento, con nome e gruppo vicino. Mai citare tra «…» un intervento di tipo summary: è il riassunto del funzionario. Se citi, chiama verifica_citazioni sulla risposta prima di chiuderla e togli le citazioni non verificate.
- Gruppo Misto: indica la componente, non «Misto».
- Niente fatti personali, familiari o di salute di parlamentari o dei loro familiari (malattie, disabilità, figli, lutti, fede, orientamento), anche se li hanno raccontati in un intervento: non riferirli e non usarli per scegliere o elencare persone. Se la domanda li chiede, rifiuta quella parte in una frase e offri quello che è pubblico: interventi, firme e voti sul tema.
- Se il dato non c'è, dillo in una frase e indica la fonte ufficiale. I dati si aggiornano ogni notte: per oggi o gli ultimi giorni dì fino a quando arrivano.
- Ogni fatto con la sua fonte: per ogni votazione, atto, seduta, intervento o scheda che usi metti il link ufficiale che trovi nei dati (source_url, card_url, url), come link Markdown [testo](url) vicino al fatto. Link solo a indirizzi presenti nei dati letti.
- Fiducia: alla Camera una questione di fiducia su un testo con più articoli dà una votazione per articolo; le questioni poste si contano per atto e data, non per votazione. Le mozioni di sfiducia a un ministro non sono questioni di fiducia.
- Rispondi in {lingua}; le citazioni restano in italiano. Risposta diretta in alto, poi i dettagli. Frasi semplici, niente titoli. Non nominare gli strumenti.
- Alla fine, su una riga a parte, scrivi SEGUITI: e tre domande successive utili separate da « | »."""


ULTIMO_PASSO = ("Non puoi più consultare i dati. Rispondi ora con quello che hai già letto, senza inventare niente: "
                "dì cosa hai trovato e cosa manca, e dove guardare nelle fonti ufficiali.")

# il passo che il sito mostra mentre lo strumento lavora
ETICHETTE = {"cerca_persone": "Cerco i parlamentari", "scheda_persona": "Leggo la scheda del parlamentare",
             "composizione": "Conto i parlamentari per gruppo", "elenco_sedute": "Cerco nelle sedute", "seduta": "Leggo la seduta",
             "elenco_votazioni": "Cerco le votazioni", "votazione": "Leggo la votazione", "cerca_atti": "Cerco negli atti",
             "atto": "Leggo l'atto", "articolo": "Leggo l'articolo", "emendamenti": "Leggo gli emendamenti", "cerca_interventi": "Cerco negli interventi",
             "cerca_per_significato": "Cerco per significato", "verifica_citazioni": "Controllo le citazioni",
             "organo": "Leggo le cariche dell'organo", "conta_votazioni": "Conto le votazioni", "voto_gruppi": "Conto i voti dei gruppi",
             "presenze": "Conto presenze e assenze", "conta_interventi": "Conto gli interventi", "conta_reazioni": "Conto le reazioni in Aula",
             "conta_atti": "Conto gli atti", "conta_emendamenti": "Conto gli emendamenti", "cambi_gruppo": "Conto i cambi di gruppo"}

_blocco = threading.Lock()


ORA = 3600
_SALE = None


def _sale() -> bytes:
    """Chiave dell'impronta degli IP: da LIMITE_SALE, o casuale per processo (un riavvio azzera i limiti)."""
    global _SALE
    if _SALE is None:
        _SALE = env("LIMITE_SALE", secrets.token_hex(32)).encode()
    return _SALE


def _impronta(ip: str) -> str:
    return hmac.new(_sale(), ip.encode(), hashlib.sha256).hexdigest()[:32]


def _registro_spesa() -> sqlite3.Connection:
    """Domande dell'ora in corso per impronta dell'IP (mai l'IP) e spesa del giorno."""
    f = QUI / "dati" / "api" / "spesa.sqlite"
    f.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(f, check_same_thread=False)
    db.execute("DROP TABLE IF EXISTS uso")          # la prima versione teneva l'IP per giorno, senza scadenza
    db.execute("CREATE TABLE IF NOT EXISTS domande (impronta TEXT NOT NULL, ts REAL NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS domande_impronta ON domande (impronta, ts)")
    db.execute("CREATE TABLE IF NOT EXISTS spesa (giorno TEXT PRIMARY KEY, dollari REAL NOT NULL)")
    return db


def _oggi() -> str:
    return dt.date.today().isoformat()


def uso(ip: str) -> dict:
    """Domande usate nell'ora in corso (il conteggio riparte allo scoccare dell'ora), limite e secondi alla ripartenza."""
    limite, ora = int(env("AGENTE_DOMANDE_ORA", "10")), time.time()
    inizio = ora - ora % ORA
    with connessione_sito() as c:
        if c:
            c.execute("DELETE FROM sito.domanda WHERE ts < to_timestamp(%s)", (inizio,))
            n = c.execute("SELECT count(*) AS n FROM sito.domanda WHERE impronta = %s", (_impronta(ip),)).fetchone()["n"]
        else:
            with _blocco, _registro_spesa() as db:
                db.execute("DELETE FROM domande WHERE ts < ?", (inizio,))
                n = db.execute("SELECT count(*) FROM domande WHERE impronta = ?", (_impronta(ip),)).fetchone()[0]
    return {"used": n, "limit": limite, "resets_in": round(inizio + ORA - ora)}


def controlla_limiti(ip: str) -> str | None:
    """Il motivo del rifiuto, o None se si può rispondere."""
    u = uso(ip)
    if u["used"] >= u["limit"]:
        minuti = max(1, -(-u["resets_in"] // 60))
        return f"hai usato tutte le {u['limit']} domande di quest'ora: il conteggio riparte fra {minuti} minuti"
    if not controlla_spesa():
        return "la chat ha raggiunto il tetto di spesa di oggi: riprova domani"
    return None


def controlla_spesa() -> bool:
    """Vero se la spesa di oggi (chat, fascicoli e traduzioni) è sotto il tetto giornaliero."""
    with connessione_sito() as c:
        if c:
            spesa = float(c.execute("SELECT coalesce(sum(dollari), 0) AS d FROM sito.spesa WHERE giorno = current_date").fetchone()["d"])
        else:
            with _blocco, _registro_spesa() as db:
                riga = db.execute("SELECT dollari FROM spesa WHERE giorno = ?", (_oggi(),)).fetchone()
            spesa = riga[0] if riga else 0.0
    return spesa < float(env("AGENTE_DOLLARI_GIORNO", "10"))


def _conta(ip: str, domande: int, dollari: float) -> None:
    with connessione_sito() as c:
        if c:
            if domande:
                c.cursor().executemany("INSERT INTO sito.domanda (impronta) VALUES (%s)", [(_impronta(ip),)] * domande)
            if dollari:
                c.execute("INSERT INTO sito.spesa (dollari) VALUES (%s)", (dollari,))
            return
    with _blocco, _registro_spesa() as db:
        if domande:
            db.executemany("INSERT INTO domande VALUES (?, ?)", [(_impronta(ip), time.time())] * domande)
        db.execute("""INSERT INTO spesa VALUES (?, ?) ON CONFLICT (giorno) DO UPDATE SET dollari = dollari + excluded.dollari""",
                   (_oggi(), dollari))


def _costo(modello: str, uso: dict) -> float:
    pin, pcache, pout = PREZZI.get(modello, (2.0, 0.2, 15.0))     # modello senza prezzo: stima per eccesso
    cache = (uso.get("input_tokens_details") or {}).get("cached_tokens", 0)
    return ((uso.get("input_tokens", 0) - cache) * pin + cache * pcache + uso.get("output_tokens", 0) * pout) / 1e6


def schemi() -> list[dict]:
    return [{"type": "function", "name": s.nome, "description": s.descrizione, "parameters": s.schema()} for s in registro.STRUMENTI]


def chiama_openai(modello: str, istruzioni: str, voci: list, chiave: str, strumenti: bool = True) -> dict:
    # store falso: niente resta sui server di OpenAI; il ragionamento torna cifrato e si ripassa al passo dopo.
    # strumenti falso: l'ultimo passo, il modello deve rispondere con quello che ha letto
    corpo = json.dumps({"model": modello, "instructions": istruzioni, "input": voci, "tools": schemi(),
                        "tool_choice": "auto" if strumenti else "none",
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


def rispondi(domanda: str, storia: list[dict], lingua: str, ip: str, misure: dict | None = None) -> Iterator[dict]:
    """Generatore di eventi per una domanda. Ogni strumento usa una connessione di sola lettura. In `misure` lascia
    modello e spesa, per il registro delle chat."""
    misure = {} if misure is None else misure
    modello = env("AGENTE_MODELLO", "gpt-5.6-terra")
    misure["modello"] = modello
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
            for passo in range(PASSI_MAX):
                ultimo = passo == PASSI_MAX - 1
                if ultimo:
                    # niente più strumenti: una risposta con quello che si è trovato è meglio di nessuna risposta
                    voci.append({"role": "user", "content": ULTIMO_PASSO})
                try:
                    r = chiama_openai(modello, istruzioni, voci, chiave, strumenti=not ultimo)
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
                    yield {"type": "tool", "id": str(n), "state": "start", "name": x["name"], "label": ETICHETTE.get(x["name"], x["name"]),
                           "args": argomenti}
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
            misure["dollari"] = spesa
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
        try:
            ris = registro.esegui(c, "verifica_citazioni", {"text": testo})
            yield {"type": "dati", "name": "verifica_citazioni", "args": {}, "result": ris}
        except Exception:                            # noqa: BLE001 — la risposta arriva anche se il controllo non riesce
            log.exception("controllo delle citazioni non riuscito")
            yield {"type": "status", "text": "citazioni non controllate"}
    yield {"type": "delta", "text": testo}
    if seguiti:
        yield {"type": "suggestions", "questions": seguiti}
    yield {"type": "done"}
