# Guida per chi sviluppa

Comandi, struttura del codice e regole della pipeline. La presentazione del progetto sta nel [README](../README.md).

## Capire il codice

La mappa del codice sta in `graphify-out/` (fuori da git) e si rifà da sola a ogni commit, checkout e merge (hook di graphify).

- `graphify-out/graph.html`: la mappa interattiva, da aprire nel browser; i colori sono le aree del codice.
- `graphify-out/GRAPH_REPORT.md`: le funzioni più collegate, le aree, i cicli di import.
- `graphify query "chi scrive in Postgres?"`: domande sul codice dal terminale; `graphify path "scarica" "carica"` mostra il percorso fra due punti.

Per la sicurezza la mappa serve a vedere chi tocca cosa: quali funzioni leggono segreti (`ambiente.py`), chi scrive nel database (`carica/`), chi chiama siti esterni (`fonti/`).

## API

```
.venv/bin/pip install -r requirements-api.txt     # versioni fissate
.venv/bin/uvicorn api.main:app --port 8790       # documentazione su http://localhost:8790/v1/docs
```

Legge Postgres con l'utente `lettura` (`schema/lettura.sql`): sola lettura, 8 secondi al massimo per query, 20 connessioni. La password sta in `.env` (`API_PG_PASSWORD`). Per crearlo o cambiarla:
`{ printf '\\set password %s\n' "$(grep '^API_PG_PASSWORD=' .env | cut -d= -f2-)"; cat schema/lettura.sql; } | docker compose exec -T testi psql -U parliamentrag -d parliamentrag -v ON_ERROR_STOP=1`.

La chat scrive ogni domanda in `registro.chat` (`schema/registro.sql`), per trovare gli errori: domanda, risposta, strumenti, tempi e costo, senza IP. Lo schema è a parte: `lettura` non lo vede, l'utente `registro` può solo inserire. Si crea come `lettura`, con `REGISTRO_PG_PASSWORD` in `.env` e `schema/registro.sql`. Senza la password la chat funziona e non scrive il registro.

```
api/strumenti/   funzioni tipizzate su Postgres: persone, sedute, voti, atti ed emendamenti, ricerca negli interventi
api/modelli.py   formati delle risposte (Pydantic)
api/main.py      rotte HTTP sotto /v1, limite di 120 richieste al minuto per IP
```

Le rotte, l'agente e il server MCP (più avanti) usano gli stessi strumenti. Nessuna rotta accetta query libere. Una persona con due schede (i senatori, con l'id della Camera e quello del Senato) è una persona sola: interventi, voti e firme contano tutte e due le schede.

## Pipeline notturna

```
.venv/bin/python -m pipeline giro            # un giro completo
.venv/bin/python -m pipeline riprendi [id]   # riprende un giro dai passi non riusciti
.venv/bin/python -m pipeline passo <nome>    # solo alcuni passi
.venv/bin/python -m pipeline stato [id]      # esito di ogni passo
.venv/bin/python -m unittest discover -s tests -t .
```

Prima volta: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`. Le dipendenze sono `pypdf`, per il testo dei PDF, e `cryptography` (con `cffi` e `pycparser`) per i PDF cifrati, tutte con la versione fissata; il resto è libreria standard.

### Come è fatta

```
fonti/       un connettore per fonte: scarica nel lago, con i suoi limiti di velocità
lago.py      grezzi salvati una volta sola, con fonte, chiave, impronta, url, data
trasforma/   dal grezzo ai record dello schema v3 (nodi, archi, testi), funzioni pure
controlli/   regole prima del caricamento: se una fallisce, il giro non pubblica
carica/      Postgres: schema/v3.sql, una transazione per seduta
orchestra.py passi con dipendenze, tempo massimo, tentativi, ripresa, stato in SQLite
passi.py     il registro dei passi
pipeline.toml configurazione, una sezione per fonte
```

Regole:
- un passo che fallisce ferma solo i passi che ne dipendono;
- ogni passo gira in un processo a parte con un tempo massimo; il giro ha un tempo massimo;
- un solo giro alla volta (lucchetto con pid, che scade se il processo è morto);
- i grezzi non si cambiano: ogni passo si rifà dai grezzi;
- niente segreti negli argomenti dei comandi: solo variabili d'ambiente o `.env`.

### Aggiungere una fonte

1. `fonti/<nome>.py` con `scarica(ctx)`, che salva nel `Lago`.
2. `trasforma/<nome>.py` con `trasforma(grezzo, info) -> {"nodi", "archi", "testi"}`, con un test su un file d'esempio in `tests/fixtures/`.
3. Due `Passo` in `passi.py` e una sezione in `pipeline.toml`.

### Fonti caricate

Database unico: Postgres con pgvector (`docker compose up -d`), deciso il 30/10; il grafo si pubblica in RDF con R2RML e SPARQL.

Fatto, tutto per la Camera XIX:
- resoconti stenografici dell'Assemblea, con le didascalie come `reaction`;
- anagrafica da dati.camera.it: persone, mandati, gruppi e componenti del Misto, organi, appartenenze e cariche, tutte datate (`group_at(persona, data)`);
- governi e ministeri (anche il governo Draghi, ancora in carica all'inizio della XIX), con gli incarichi datati di presidente, vicepresidenti, ministri, viceministri e sottosegretari;
- progetti di legge: iter, versioni del testo, firmatari (anche i ministri), assegnazioni, relatori legati alla persona, abbinamenti, trasmissioni al Senato, legge che ne è nata;
- Bollettino delle commissioni (resoconto sommario): sedute per sede con chi presiede, orari e governo presente; argomenti con l'atto e la fase dell'esame; paragrafi del sommario marcati `summary` (non citabili tra virgolette), con persona, gruppo e ruolo; allegati come `document`. Le commissioni si legano all'anagrafica (le riunite restano col codice del Bollettino);
- stenografici delle commissioni (audizioni formali, indagini conoscitive, altre sedute): interventi parola per parola marcati `verbatim`, di deputati o di auditi con nome e qualifica; chi parla senza link alla scheda si lega al deputato in carica con lo stesso nome, se è uno solo;
- sindacato ispettivo e indirizzo (circa 31 mila atti): interrogazioni scritte, orali e in commissione, interpellanze, mozioni, risoluzioni, ordini del giorno, con il testo, firmatari, ministero destinatario, temi EuroVoc e stato; si legano ai voti (ordini del giorno votati) e agli argomenti del Bollettino. Nel lago per mese di presentazione: ogni notte si riscaricano solo i mesi cambiati;
- WebTV: per ogni seduta d'Aula il video e, per ogni intervento, i secondi di inizio e fine legati all'intervento del resoconto (attraverso l'ancora dello stenografico). Elenco dal servizio dell'archivio, una pagina ogni 10 secondi come chiede il sito, 100 sedute per notte; i video non si scaricano;
- ordine del giorno dell'Assemblea: sedute previste (`status = planned`) con argomenti, orari, atti e relatori; il resoconto, quando arriva, sostituisce la seduta prevista e mai il contrario. Gli argomenti di ordine del giorno, Bollettino e stenografici si legano agli atti (`lega_argomenti`);
- documenti acquisiti dalle commissioni permanenti (circa 4 mila memorie e contributi scritti): chi li ha mandati, per quale audizione o atto, quando, e il testo (PDF, DOCX, PPTX). Sono scritti di terzi (`third_party`): nel sito solo estratti con il link. 300 file per notte;
- dossier dei Servizi di documentazione (circa 3.600, da temi.camera.it, CC BY-SA 4.0): data, servizio, codice, atto a cui si riferiscono e testo integrale dalla versione HTML. 300 per notte;
- votazioni elettroniche e voto di ogni deputato, con il gruppo attribuito dalla Camera in quel voto; un controllo blocca il giro se i voti dei singoli non tornano con i totali;
- emendamenti (dagli XML di documenti.camera.it, riscaricati solo se cambiati) e testi degli atti, articolo per articolo.

Senato XIX, con gli stessi record della Camera:
- anagrafica da dati.senato.it: senatori eletti, a vita e di diritto, gruppi col nome in vigore e i precedenti come alias, commissioni col nome alla data; ogni senatore che è stato deputato o membro del governo si lega alla sua scheda della Camera (`person_same_as`);
- disegni di legge con firmatari (senatori e deputati) e votazioni elettroniche con il voto di ogni senatore; il gruppo nel voto si ricava dall'anagrafica alla data. Al massimo 60 sedute di voti per notte, con 5 secondi fra le richieste: senato.it blocca l'IP dopo circa 400 richieste ravvicinate;
- sindacato ispettivo del Senato (da dati.camera.it);
- resoconti stenografici dell'Assemblea in Akoma Ntoso: interventi singoli anche dentro gli scambi, con la persona, la carica e il presidente di turno; i membri del governo che non sono senatori si legano alla scheda del governo (`lega_governo`); didascalie come `reaction`; sezioni legate ai ddl;
- dai bulk data ufficiali del Senato su GitHub (SenatoDellaRepubblica/AkomaNtosoBulkData, CC BY 4.0, aggiornati ogni giorno): resoconti d'Aula, resoconti sommari delle commissioni (marcati `summary`, come il Bollettino della Camera), testi dei ddl (presentato, testo della commissione, messaggio alla Camera) con gli articoli, ed emendamenti d'Aula e di commissione con testo, firmatari e data di presentazione (i bulk data non danno l'esito). Clone git parziale in `dati/cache/senato_akn`: ogni notte git scarica solo i file nuovi. Su GitHub non c'è il WAF di senato.it; le sedute più recenti del bulk restano qualche giorno indietro.


### Note su dati.camera.it

- Al massimo 10 mila righe per risposta; con OFFSET su query ordinate e pesanti risponde 500. Le query grandi si paginano per chiave (`sparql.per_chiave`) o si spezzano (i voti, a blocchi di 20 votazioni) e si controlla il totale con un COUNT.
- Le triple sono ripetute su più grafi: conteggi sempre con `COUNT(DISTINCT …)`.
- I nodi anonimi (firmatari del governo) si leggono solo nella stessa query che li raggiunge.
