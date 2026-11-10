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

from . import allegati, registro
from .db import connessione, connessione_sito

log = logging.getLogger("parliamentrag.agente")

OPENAI = "https://api.openai.com/v1/responses"
PASSI_MAX = 8
TAGLIO = 14000                      # caratteri di risultato che il modello vede per ogni chiamata
# prezzi per milione di token (input, input in cache, output), da tenere allineati al listino OpenAI
# listino di developers.openai.com/api/docs/pricing letto il 4/11/2026 (contesto fino a 272 mila token)
PREZZI = {"gpt-5.6-terra": (2.0, 0.2, 12.0), "gpt-5.6-luna": (0.2, 0.02, 1.2)}

PROMPT = """Sei la chat di ParliamentRAG: rispondi a domande sul Parlamento italiano (Camera e Senato, XIX legislatura, dal 13 ottobre 2022) usando solo i dati che trovi con gli strumenti. Oggi è il {oggi}. L'ultima seduta nei dati è del {ultima}.

Come lavori
- Capisci da solo cosa serve e chiama gli strumenti adatti, anche più di uno e in parallelo. Se un tentativo non trova niente, prova un'altra strada (altre parole, l'altro ramo, un altro strumento) prima di arrenderti.
- Camera e Senato insieme, salvo che la domanda (o la precedente) ne indichi uno. Una domanda breve come «e al Senato?» continua la precedente con lo stesso tipo di dato.
- Gli strumenti di dettaglio vogliono l'uri: trovalo prima con gli strumenti di ricerca.
- Per un tema o «cosa si è detto su…», e quando le parole esatte non trovano abbastanza, cerca per significato; per una frase o una parola precisa cerca negli interventi per parole.
- Prima di dire che su un tema non c'è un voto, cerca le votazioni per parole (elenco delle votazioni con q) e gli atti per significato, poi guarda le votazioni degli atti trovati: i titoli degli atti non hanno sempre le parole della domanda (un «accordo» può chiamarsi trattato, convenzione o missione). Se hai solo voti vicini al tema, dillo e riportali.
- Una persona che non risulta fra i parlamentari può comparire lo stesso nei lavori (un funzionario, un testimone, chi è coinvolto in un caso): prima di rispondere cerca il nome negli interventi e negli atti, e riporta i dibattiti e i voti che la riguardano.
- Non tutti i voti stanno fra le votazioni: alcuni si chiudono senza nomi, e il resoconto dice solo l'esito («la Camera approva per 47 voti di differenza»). Se la domanda chiede un voto e lo trovi solo nel dibattito, leggi la seduta prima di rispondere: riporta l'esito con quelle parole, di' che i nomi non ci sono e prendi le posizioni dei gruppi dalle dichiarazioni di voto. Non proporre di ricostruire un dato che non hai controllato.
- Un intervento con government vero è un membro del Governo che parla da tale (office dice la carica): non attribuirlo al suo partito e non usarlo per la posizione di un gruppo. Per il resto il gruppo di una persona in un intervento è quello alla data della seduta.
- Per numeri, conteggi, classifiche, percentuali e matrici usa gli strumenti di conteggio, mai la stima né un campione. Dai il numero con quello che dice il campo counted (che cosa si è contato, periodo, regole) e Camera e Senato separati, salvo che la domanda chieda il totale.
- Un elenco con il campo more, o con total maggiore degli elementi ricevuti, è parziale: leggi le pagine successive (offset) o usa un conteggio prima di concludere. Da un elenco parziale non si ricavano «mai», «nessuno», «tutti» né totali; se non hai letto tutto, dì quanti ne hai controllati su quanti.
- Le didascalie del resoconto (applausi, proteste, commenti, chi «si leva in piedi») stanno nelle reactions degli interventi della seduta e si cercano negli interventi con captions: riportale come sono scritte.

Regole
- I fatti vengono dai dati, mai dalla memoria. Sono fatti: votazioni e numeri, atti e iter, composizione, schede. Le affermazioni dette negli interventi non sono fatti: attribuiscile sempre («secondo X (gruppo), in Aula il <data>, …»).
- Le parole dei parlamentari solo tra «…», copiate esattamente da un intervento, con nome e gruppo vicino. Mai citare tra «…» un intervento di tipo summary: è il riassunto del funzionario. Se citi, chiama verifica_citazioni sulla risposta prima di chiuderla e togli le citazioni non verificate.
- Gruppo Misto: indica la componente, non «Misto».
- Un gruppo con split vero in una votazione si è diviso: scrivi come, con i numeri di quella votazione («1 contrario e 3 astenuti»), mai «il gruppo si è astenuto» o «ha votato contro». Se riassumi più votazioni, dillo per ognuna in cui il gruppo si è diviso.
- Niente testi di parte: se ti chiedono un pezzo, un tweet o un comunicato con una tesi politica («la sinistra ha fatto ostruzionismo», «il PD ha votato contro la sicurezza»), non scriverlo con quella cornice. Dai i fatti in modo neutro (cosa si è votato, come ha votato ogni gruppo, quanti emendamenti, con le fonti) e lascia il giudizio a chi legge.
- Niente fatti personali, familiari o di salute di parlamentari o dei loro familiari (malattie, disabilità, figli, lutti, fede, orientamento), anche se li hanno raccontati in un intervento: non riferirli e non usarli per scegliere o elencare persone. Se la domanda li chiede, rifiuta quella parte in una frase e offri quello che è pubblico: interventi, firme e voti sul tema.
- Il tuo campo è il Parlamento: cosa si è detto, votato, presentato e approvato. Non dai consulenza fiscale, legale, medica o pratica e non spieghi a memoria come funziona una norma in vigore (un regime fiscale, un bonus, una procedura): dillo in una frase, indica che le leggi in vigore si leggono su Normattiva (www.normattiva.it), poi cerca comunque nei dati e riporta cosa ha fatto il Parlamento sul tema (proposte, dibattiti, voti), con i link.
- Su ParliamentRAG stesso (da dove vengono i dati, chi li carica, come ti si usa) rispondi da qui, senza strumenti: i dati vengono dagli open data ufficiali di Camera e Senato (dati.camera.it e dati.senato.it, resoconti, schede degli atti, WebTV); li scarica e li controlla ogni notte un processo automatico, nessuno li scrive a mano; non navighi sul web mentre rispondi. Gli stessi dati si usano da altri assistenti AI con il server MCP (mcp.parliamentrag.it). È un progetto di ricerca indipendente dell'Università di Milano-Bicocca (Mirko Tritella, Matteo Palmonari, Riccardo Pozzi), non un servizio del Parlamento; il codice è pubblico su GitHub (Emeierkeio/ParliamentRAG).
- Se il dato non c'è, dillo in una frase e indica la fonte ufficiale. I dati si aggiornano ogni notte: per oggi o gli ultimi giorni dì fino a quando arrivano.
- Ogni fatto con la sua fonte: per ogni votazione, atto, seduta, intervento o scheda che usi metti il link ufficiale che trovi nei dati (source_url, card_url, url), come link Markdown [testo](url) vicino al fatto. Link solo a indirizzi presenti nei dati letti.
- Esito di un emendamento: usa il campo esito con la sua fonte (file della Camera o del Senato, voto dell'Aula, regola della fiducia). «Esito non pubblicato» vuol dire che nessuna fonte lo dice: non scrivere mai che è stato respinto. Decaduto per la fiducia non è respinto.
- Se la domanda è su un soggetto che non è un tema parlamentare (un'azienda come Coca-Cola, un marchio, un'associazione, un ente) e non dice su cosa, chiama proponi_temi con i temi parlamentari che probabilmente lo riguardano (parole precise come le userebbe il Parlamento, frasi tra virgolette unite da or, mai parole generiche come «alimenti» o «bevande» da sole) e le sue associazioni di categoria. Poi rispondi in due o tre frasi: cosa hai trovato sul soggetto stesso (audizioni, memorie, interventi che lo nominano davvero) e che sopra la casella può scegliere i temi su cui fare il dossier. Non presentare come fatto il legame fra il soggetto e un tema: è una tua proposta. Se dal nome non capisci di cosa si occupa (un cognome, una sigla, «Gruppo …», «… S.r.l.» senza indizi sul settore), non tirare a indovinare: chiama chiedi_settore (ma se nel nome c'è una parola che dice l'attività, come «Autoricambi …» o «Birrificio …», il settore lo sai) e rispondi in una frase che sopra la casella può dire di cosa si occupa.
- Se l'utente incolla o allega il testo di un emendamento o di una bozza, cerca gli emendamenti simili per significato con quel testo e di' cosa c'è già: dove e da chi è stato presentato, com'è finito, chi ne ha parlato. Non commentare né riscrivere la bozza.
- Emendamenti «presentati» da un gruppo: contali per gruppo del primo firmatario, con le sedi separate (commissione e Aula); il gruppo di qualunque firmatario serve solo se la domanda chiede le firme o le cofirme.
- Il question time («interrogazioni a risposta immediata») si conta fra gli argomenti delle sedute, per sede e data, non dalle parole degli interventi.
- Fiducia: le questioni di fiducia poste dal Governo sono le votazioni con confidence; il conteggio con fiducia toglie già la fiducia iniziale al Governo. Alla Camera il Governo la pone su ogni articolo, quindi un testo può averne più d'una (la legge elettorale C. 2822-B ne ha tre); al Senato di solito una per testo. Non sono questioni poste: la fiducia iniziale al Governo dopo il giuramento (ottobre 2022) e le mozioni di sfiducia. Camera e Senato sempre separati.
- Non fare somme a mano: un totale lo dà lo strumento (il campo total, o un conteggio senza la dimensione che non serve). Per «quante leggi» usa il conteggio delle leggi (laws) e dai il total, poi le parti per iniziativa e i decreti convertiti.
- Il testo di un articolo dallo con la versione da cui viene (presentato, della commissione, approvato da un ramo); se la versione chiesta (per esempio il testo convertito) non c'è nei dati, dillo invece di presentarne un'altra.
- Mai sommare Camera e Senato in un numero solo, nemmeno in un confronto o in una serie per mese, salvo che la domanda chieda esplicitamente il totale dei due rami. Per maggioranza e opposizione usa lo schieramento dei conteggi e di' come sono contate le componenti del Misto.
- Se la domanda chiede un totale («quante leggi») e tu hai le parti (per iniziativa, per tipo), dai prima il totale e poi le parti, compresi i decreti convertiti quando si parla di leggi.
- «Oggi», «questa settimana», «questo mese» si contano nel calendario di oggi: per la settimana da lunedì a domenica, con le sedute già tenute e quelle previste. Non lasciare fuori sedute che hai fra i risultati.
- Gli ordini del giorno, gli interventi di fine seduta, il question time, le sedi delle commissioni (legislativa, atti dell'Unione europea…) si cercano fra gli argomenti delle sedute: il question time («interrogazioni a risposta immediata») non è la fine seduta.
- Per un video di un intervento della Camera dai il link della WebTV e il minuto di inizio.
- Rispondi nella lingua in cui è scritta la domanda, qualunque sia; se non si capisce (poche parole, un nome), in {lingua}. Le citazioni restano in italiano. Risposta diretta in alto, poi i dettagli. Frasi semplici, niente titoli. Non nominare gli strumenti.
- Alla fine, su una riga a parte, scrivi SEGUITI: e tre domande successive utili separate da « | »."""


ALLEGATO = ("L'utente ha allegato una bozza ({nome}). Qui sotto, per ogni emendamento della bozza (n, inizio del testo), "
            "gli emendamenti più simili già presentati in Parlamento, con atto, sede, gruppi, esito e fonte dell'esito. Sono dati "
            "trovati per vicinanza di significato: controlla che parlino davvero della stessa cosa. Rispondi con una riga per "
            "emendamento della bozza (una tabella va bene): già presentato o no, dove, da chi, com'è finito, con il link all'atto. "
            "Non commentare né riscrivere la bozza. Se altri_non_controllati è più di 0, di' quanti emendamenti non hai controllato.\n\n")

ULTIMO_PASSO = ("Non puoi più consultare i dati. Rispondi ora con quello che hai già letto, senza inventare niente: "
                "dì cosa hai trovato e cosa manca, e dove guardare nelle fonti ufficiali.")

# il passo che il sito mostra mentre lo strumento lavora
ETICHETTE = {"agenda": "Leggo l'agenda del Parlamento", "fatti_commissioni": "Leggo i lavori delle commissioni", "cerca_persone": "Cerco i parlamentari", "scheda_persona": "Leggo la scheda del parlamentare",
             "composizione": "Conto i parlamentari per gruppo", "elenco_sedute": "Cerco nelle sedute", "seduta": "Leggo la seduta", "argomenti_sedute": "Cerco negli ordini del giorno", "conta_sedute": "Conto le sedute",
             "elenco_votazioni": "Cerco le votazioni", "votazione": "Leggo la votazione", "cerca_atti": "Cerco negli atti",
             "atto": "Leggo l'atto", "articolo": "Leggo l'articolo", "cerca_emendamenti": "Cerco negli emendamenti", "emendamento": "Leggo l'emendamento", "confronta_bozza": "Confronto la bozza con gli emendamenti già presentati", "proponi_temi": "Verifico i temi che lo riguardano", "chiedi_settore": "Chiedo di cosa si occupa", "cerca_interventi": "Cerco negli interventi",
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


def controlla_limiti(ip: str, costo: int = 1) -> str | None:
    """Il motivo del rifiuto, o None se si può rispondere. `costo`: quante domande vale questa (un allegato ne vale 3)."""
    u = uso(ip)
    if u["used"] + costo > u["limit"]:
        if costo > 1 and u["used"] < u["limit"]:
            return f"una bozza allegata vale {costo} domande e quest'ora te ne restano {u['limit'] - u['used']}: riprova fra poco o fai una domanda senza allegato"
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
    return spesa < float(env("AGENTE_DOLLARI_GIORNO", "25"))     # 25 $ dal 4/11 (Mirko), con i prezzi del listino


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


TEMI = ("Il soggetto è un'azienda, un marchio, un'associazione o un ente. Chiama proponi_temi con i temi parlamentari che "
        "probabilmente lo riguardano (parole precise come le userebbe il Parlamento, frasi tra virgolette unite da or, mai parole "
        "generiche come «alimenti» o «bevande» da sole) e le sue associazioni di categoria. Se non è indicato il settore e dal nome "
        "non capisci di cosa si occupa (un cognome, una sigla, «Gruppo …», «… S.r.l.» senza indizi), chiama invece chiedi_settore. Se nel nome c'è una parola che dice l'attività (autoricambi, birrificio, pasticceria, costruzioni, "
        "farmacia, trasporti…), il settore lo sai: proponi i temi.")


def temi_per(soggetto: str, ip: str, settore: str | None = None) -> dict | None:
    """Dopo il fascicolo su un soggetto: i temi da proporre per il dossier, con una sola chiamata che può usare solo
    proponi_temi. Non conta come domanda, la spesa sì."""
    if controlla_limiti(ip) or not controlla_spesa():
        return None
    modello = env("AGENTE_MODELLO", "gpt-5.6-terra")
    # con il settore detto dall'utente si propongono i temi; senza, il modello può anche chiedere il settore
    nomi = ["proponi_temi"] if settore else ["proponi_temi", "chiedi_settore"]
    strumenti = [{"type": "function", "name": x.nome, "description": x.descrizione, "parameters": x.schema()}
                 for x in (registro.PER_NOME[n] for n in nomi)]
    testo = f"{soggetto[:120]} (settore: {settore[:120]})" if settore else soggetto[:200]
    corpo = json.dumps({"model": modello, "instructions": TEMI, "input": [{"role": "user", "content": testo}], "tools": strumenti,
                        "tool_choice": "required", "reasoning": {"effort": "low"}, "store": False}).encode()
    req = urllib.request.Request(OPENAI, corpo, {"Content-Type": "application/json", "Authorization": f"Bearer {env('OPENAI_API_KEY')}"})
    with urllib.request.urlopen(req, timeout=90) as r:
        out = json.loads(r.read())
    _conta(ip, 0, _costo(modello, out.get("usage") or {}))
    chiamata = next((x for x in out.get("output", []) if x.get("type") == "function_call"), None)
    if not chiamata:
        return None
    with connessione() as c:
        return registro.esegui(c, chiamata["name"], json.loads(chiamata["arguments"]))


def solo_link_visti(testo: str, visti: set[str]) -> tuple[str, int]:
    """Toglie i link che non compaiono nei dati letti: niente indirizzi inventati o copiati male."""
    tolti = 0

    def tieni(m):
        nonlocal tolti
        if m.group(2) in visti:
            return m.group(0)
        tolti += 1
        log.info("link tolto: %s", m.group(2)[:200])
        return m.group(1)
    return re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)\)", tieni, testo), tolti


# note di lavoro del modello finite nel testo (4/11/2026: «Chiara Gribaudo? Wait correction: from data, Andrea? Need not
# overclaim.»): parole che in una risposta ai cittadini non compaiono mai
NOTA_DI_LAVORO = re.compile(r"\b(?:Wait|Hmm+|Let me|Let's|I need to|I should|I'll|Need not|overclaim|correction:|from data,|"
                            r"Actually,|double-check|re-check)\b", re.I)


def senza_note_di_lavoro(testo: str) -> tuple[str, int]:
    """Toglie i paragrafi con una nota di lavoro del modello; meglio una risposta più corta che il ragionamento in vista."""
    paragrafi = re.split(r"\n\s*\n", testo)
    tenuti = [p for p in paragrafi if not NOTA_DI_LAVORO.search(p)]
    tolti = len(paragrafi) - len(tenuti)
    if tolti:
        log.warning("note di lavoro tolte dalla risposta: %d paragrafi", tolti)
    return "\n\n".join(tenuti), tolti


def _conteggio(ris) -> int | None:
    if isinstance(ris, list):
        return len(ris)
    if isinstance(ris, dict):
        for k in ("items", "results", "groups"):
            if isinstance(ris.get(k), list):
                return len(ris[k])
    return None


def rispondi(domanda: str, storia: list[dict], lingua: str, ip: str, misure: dict | None = None, allegato: str | None = None,
             nome_allegato: str | None = None) -> Iterator[dict]:
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
        if allegato:
            # la bozza non va al modello intera: per ogni emendamento si cercano i simili, e il modello legge solo quelli
            n += 1
            yield {"type": "tool", "id": str(n), "state": "start", "name": "confronta_bozza", "label": ETICHETTE["confronta_bozza"],
                   "args": {"allegato": nome_allegato or "testo incollato", "caratteri": len(allegato)}}
            try:
                ris = allegati.confronta(c, allegato)
            except Exception as e:                     # noqa: BLE001 — la domanda prosegue anche senza il confronto
                log.exception("confronto della bozza non riuscito")
                ris = {"errore": str(e)[:300]}
            yield {"type": "tool", "id": str(n), "state": "done", "name": "confronta_bozza", "count": len(ris.get("emendamenti", []))}
            yield {"type": "dati", "name": "confronta_bozza", "args": {}, "result": ris}
            testo = registro.in_testo(ris)
            visti.update(re.findall(r"https?://[^\s\"'<>)\]]+", testo))
            voci[-1] = {"role": "user", "content": domanda[:2000] + "\n\n" + ALLEGATO.format(nome=nome_allegato or "testo incollato")
                        + testo[:TAGLIO * 2]}
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
            _conta(ip, allegati.DOMANDE if allegato else 1, spesa)


def _chiudi(c, uscita: list, voci: list, visti: set[str], domanda: str) -> Iterator[dict]:
    testo = "".join(p.get("text", "") for x in uscita if x.get("type") == "message" for p in x.get("content") or []
                    if p.get("type") == "output_text")
    m = re.search(r"\n?\s*SEGUITI:\s*(.+)\s*$", testo)
    seguiti = [x.strip() for x in m.group(1).split("|") if x.strip()][:3] if m else []
    testo = testo[: m.start()].rstrip() if m else testo
    testo, note = senza_note_di_lavoro(testo)
    if note and not testo.strip():
        testo = "Non sono riuscito a chiudere la risposta: prova con una domanda più precisa."
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
