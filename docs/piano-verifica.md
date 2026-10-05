# Piano: verificare le tre garanzie

> Stato: proposta del 6 ottobre 2026. Nessun codice scritto.

## Obiettivo

ParliamentRAG promette tre cose su ogni risposta che parla del Parlamento:

1. **Tutti i gruppi.** Nessun gruppo omesso in silenzio.
2. **Voci autorevoli.** Per ogni gruppo parla chi conosce il tema, secondo criteri dichiarati.
3. **Citazioni esatte.** Ogni citazione è testo detto in Aula, attribuito alla persona giusta, con il link al
   resoconto.

Oggi le promesse le mantiene il codice di Fascicoli, e chi legge deve fidarsi. Questo piano costruisce un
**verificatore** pubblico: prende una risposta, la confronta con i dati aperti e scrive un rapporto. Chiunque
lo fa girare ottiene lo stesso rapporto. Il verificatore controlla qualsiasi sistema che produca il formato
descritto qui sotto: Fascicoli, Stenografo, un assistente collegato al nostro server MCP, un sistema di altri.

Il verificatore e la pipeline dei dati sono la parte aperta di ParliamentRAG. Fascicoli, Stenografo e Scranno
restano fuori da questo repository.

## Cosa esiste già

| Pezzo | Dove | Cosa fa | Limite per la verifica |
|---|---|---|---|
| Controllo delle citazioni | `fascicoli/backend/app/services/generation/surgeon.py` | Accetta una citazione solo se compare alla lettera nel passaggio; corregge la maiuscola iniziale; scarta le citazioni di terzi dentro un intervento (`_is_nested_quote`) | Lavora sul testo dei chunk, che è preprocessato. Quando fallisce non scarta: sostituisce con frasi estratte |
| Registro delle citazioni | `.../generation/citation_registry.py` | Segue ogni citazione dalla prova al testo finale | Pensato per la pipeline, non per una risposta esterna |
| Copertura dei gruppi | `pipeline.py` (`_inject_missing_party_paragraphs`), `evaluation.py` (`ALL_PARTIES = 10`) | Aggiunge i gruppi mancanti, misura la copertura | Elenco dei gruppi fisso in `default.yaml`, non ricavato dal grafo alla data |
| Autorevolezza | `backend/app/services/authority/` (`scorer.py`, `components.py`), pesi in `backend/config/default.yaml` | Sei componenti tra 0 e 1, pesati, per domanda | Richiede gli embedding di passaggi, atti, professioni e studi, che oggi non pubblichiamo |
| Dataset tabellare | Hugging Face `emeierkeio/parliamentrag-camera-leg19` | `speeches` con testo integrale e `speaker_id`, `memberships` con date, `persons`, `organizations` (componenti del Misto incluse) | Niente chunk, niente embedding |
| Grafo in RDF | Zenodo, DOI 10.5281/zenodo.21560331 | Lo stesso grafo, con gli URI ufficiali | Niente embedding |
| Pipeline dei dati | `parliamentrag-iswc/build`, copia in `fascicoli/build` | Costruisce il grafo da dati.camera.it | Vive in due repository |

## Principi

- **Deterministico.** Stessa risposta, stessa versione dei dati, stesso rapporto. Il verificatore non chiama
  modelli linguistici.
- **Offline.** Gira sui dati pubblicati (parquet di Hugging Face o dump Zenodo), senza il nostro backend.
- **Versionato.** Ogni rapporto riporta la versione dei dati, la versione del verificatore e, per
  l'autorevolezza, la versione dei pesi.
- **Un rapporto, non un voto.** Le citazioni hanno un esito netto: esatta o no. Per gruppi e autorevolezza
  il rapporto mostra i fatti (quali gruppi mancano, che posizione ha il deputato citato) e lascia a chi legge
  il giudizio.
- **Nessun privilegio per i nostri sistemi.** Fascicoli passa dallo stesso controllo di un sistema esterno.

## Il formato della risposta verificabile

Un sistema che vuole farsi verificare produce un JSON con la domanda, il periodo considerato e le
affermazioni. Bozza dello schema (`schema/risposta-verificabile.v1.json`):

```json
{
  "schema": "https://w3id.org/parliamentrag/verifica/v1",
  "sistema": { "nome": "Fascicoli", "versione": "2026-10-06" },
  "domanda": "Cosa pensano i gruppi del salario minimo?",
  "periodo": { "dal": "2022-10-13", "al": "2026-10-05" },
  "gruppi_dichiarati_assenti": [
    { "gruppo": "https://dati.camera.it/ocd/gruppoParlamentare.rdf/gp…", "motivo": "nessun intervento" }
  ],
  "affermazioni": [
    {
      "gruppo": "https://dati.camera.it/ocd/gruppoParlamentare.rdf/gp…",
      "deputato": "https://dati.camera.it/ocd/persona.rdf/p…",
      "intervento": "leg19_sed0123_…",
      "citazione": "il salario minimo non è una misura sufficiente",
      "link": "https://www.camera.it/leg19/410?idSeduta=0123&tipo=stenografico#…"
    }
  ],
  "testo": "Il testo della risposta come lo vede l'utente, facoltativo"
}
```

Scelte da fissare:

- **Identificatori.** Gruppi e deputati con gli URI di dati.camera.it, già presenti nel grafo. Interventi con
  lo `speech_id` del dataset, non con l'ID del chunk, perché il dataset pubblico non contiene i chunk.
- **Componenti del Misto.** Una citazione di un deputato del Misto indica la componente (per esempio
  +Europa), non il Misto in blocco.
- **Il testo libero è facoltativo.** Il verificatore controlla le affermazioni strutturate. Un secondo
  passo, più avanti, può estrarle dal testo con le convenzioni di Fascicoli (`«…»` seguito dal link).

## Controllo 1: citazioni esatte

Il controllo più solido, da fare per primo. Il codice di partenza è il controllo letterale di `surgeon.py`,
estratto in una funzione pura senza dipendenze dal backend.

Per ogni affermazione il verificatore controlla, nell'ordine:

1. **L'intervento esiste** nella versione dei dati.
2. **La citazione compare nel testo dell'intervento.** Prima alla lettera, poi dopo una normalizzazione
   dichiarata e chiusa: spazi multipli, apostrofi e virgolette tipografiche, maiuscola della prima lettera.
   Nient'altro: niente ellissi, niente parole saltate.
3. **La citazione appartiene all'oratore.** Il verificatore rifiuta le parole di terzi riportate
   nell'intervento: riusa le regole di `_is_nested_quote` e di `reported_speech.py`.
4. **L'oratore è il deputato indicato** (`speaker_id` dell'intervento).
5. **Il gruppo è quello giusto alla data dell'intervento**, da `memberships`. Per il Misto, la componente.
6. **Il link porta al resoconto di quella seduta.** Controllo sul formato e sull'ID della seduta, senza
   scaricare la pagina.

Esiti possibili per ogni citazione: `esatta`, `esatta_dopo_normalizzazione`, `non_trovata`,
`parole_di_terzi`, `oratore_errato`, `gruppo_errato`, `link_errato`, `intervento_inesistente`.

Un punto da chiarire subito. Fascicoli verifica sul testo dei chunk, che è preprocessato; il dataset
pubblica il testo integrale degli interventi. Prima di tutto bisogna misurare quante citazioni oggi
accettate da Fascicoli non si trovano nel testo integrale. Se sono poche, il verificatore usa il testo
integrale. Se sono molte, il preprocessamento va reso reversibile o pubblicato.

Più avanti c'è un secondo livello: confronto con il resoconto stenografico ufficiale su camera.it, scaricato
e conservato con data e hash. Fa la differenza tra «esatta rispetto ai nostri dati» ed «esatta rispetto alla
Camera».

## Controllo 2: tutti i gruppi

Il verificatore ricava l'elenco dei gruppi dal grafo, non da una lista scritta a mano: i gruppi con almeno
un membro nel periodo della domanda, da `memberships` e `organizations`. Così tiene conto dei cambi di nome
(Italia Viva → Italia Viva-Casa Riformista) e delle componenti del Misto.

Per ogni gruppo il rapporto dice una di quattro cose:

- `citato`: almeno una citazione esatta di un suo membro.
- `assente_confermato`: la risposta dichiara il gruppo assente e il controllo non trova interventi sul tema.
- `assente_contestato`: la risposta dichiara il gruppo assente, ma il controllo trova interventi sul tema.
- `omesso`: il gruppo non compare né tra i citati né tra i dichiarati assenti. È il caso che la garanzia
  vieta.

Il punto debole è «interventi sul tema», che non è un fatto lessicale. Propongo due livelli, entrambi
riportati nel rapporto:

- **Lessicale, deterministico.** Ricerca full-text (BM25) sugli interventi del gruppo nel periodo, con i
  termini della domanda e i concetti EuroVoc collegati. Il rapporto elenca i primi interventi trovati, così
  chi legge giudica da sé.
- **Semantico, con versione fissata.** Stessa ricerca con gli embedding pubblicati (vedi controllo 3) e una
  soglia di similarità dichiarata. È deterministico solo a parità di modello, embedding e soglia: il rapporto
  li riporta.

## Controllo 3: voci autorevoli

Il verificatore ricalcola l'autorevolezza del deputato citato con lo stesso codice di
`backend/app/services/authority/` e i pesi di `default.yaml`, e scrive la sua posizione nel gruppo:
«3° su 41 per questa domanda», con i sei punteggi. Non decide se 3° basta.

Il ricalcolo ha bisogno di dati che oggi non pubblichiamo: embedding dei passaggi (circa 178.000), degli
atti, delle professioni e dei titoli di studio, e l'embedding della domanda. Tre strade:

| Strada | Come | Pro | Contro |
|---|---|---|---|
| A. Pubblicare gli embedding | File parquet versionato su Hugging Face e Zenodo, float16 (circa 0,5 GB per i passaggi) | Ricalcolo completamente offline | La domanda va comunque trasformata in embedding: serve una chiave OpenAI, oppure la risposta include il vettore |
| B. Endpoint pubblico | `GET /authority?domanda=…&deputato=…` restituisce componenti e posizione | Semplice per chi verifica | Chi verifica si fida del nostro server: non è indipendente |
| C. Modello aperto | Ricalcolare tutto con un modello di embedding aperto | Nessuna chiave, nessuna dipendenza | Punteggi diversi da quelli di Fascicoli: va validato contro l'attuale |

Propongo A come riferimento e B come scorciatoia, segnata nel rapporto come «calcolato dal server di
ParliamentRAG». C diventa un esperimento per l'articolo su rivista.

## Il rapporto

JSON per le macchine, Markdown per le persone. Esempio:

```
Verifica ParliamentRAG v0.1 · dati 2026-10-05 · pesi authority 2026-08

Citazioni   11 su 12 esatte
  ✗ #7  non_trovata: «…» non compare nell'intervento leg19_sed0412_…
Gruppi      9 citati, 1 assente confermato, 0 omessi
Autorevolezza (posizione nel gruppo)
  FdI       <deputato> 1° su 118
  PD        <deputato> 2° su 69
  …
```

## Interfacce

1. **Libreria Python** `parliamentrag-verifica`: `verifica(risposta, dati) -> Rapporto`.
2. **Riga di comando:** `parliamentrag-verifica risposta.json --dati ./camera-leg19`. Al primo avvio scarica
   la versione dei dati indicata.
3. **Pagina `/verifica` sul sito del centro.** Incolli il JSON e leggi il rapporto. Il primo controllo può
   girare nel browser (con Pyodide o un port in TypeScript); gli altri due chiamano una route.
4. **Nei nostri sistemi.** Fascicoli produce il JSON accanto a ogni dossier e mostra il rapporto. È la prova
   pubblica che i nostri sistemi passano dallo stesso controllo.

## Struttura del repository

```
ParliamentRAG/
├── verifica/              libreria e riga di comando (Python)
│   ├── citazioni.py
│   ├── gruppi.py
│   ├── autorevolezza.py
│   └── rapporto.py
├── schema/                risposta-verificabile.v1.json, rapporto.v1.json
├── dati/                  pipeline dei dati, spostata da parliamentrag-iswc/build
├── tests/fixtures/        risposte vere e casi costruiti, con il rapporto atteso
└── src/                   il sito, come oggi
```

Il sito resta dov'è. Il repository diventa il posto dove stanno dati, schema e verificatore.

## Fasi

| Fase | Contenuto | Fatto quando | Stima |
|---|---|---|---|
| 0 | Schema v1 del formato e del rapporto; 20 risposte vere di Fascicoli convertite a mano | Lo schema valida le 20 risposte | 2 giorni |
| 1 | Controllo delle citazioni sul dataset Hugging Face; misura della differenza tra chunk e testo integrale | Le 20 risposte passano, 30 casi costruiti falliscono con l'esito giusto | 4 giorni |
| 2 | Riga di comando, rapporto Markdown, pagina `/verifica` solo per le citazioni | Chiunque verifica una risposta dal sito | 3 giorni |
| 3 | Controllo dei gruppi, livello lessicale | I cambi di nome e le componenti del Misto sono coperti dai test | 4 giorni |
| 4 | Embedding pubblicati (strada A) e livello semantico dei gruppi | Embedding su Hugging Face con versione; rapporti identici su due macchine | 4 giorni |
| 5 | Autorevolezza ricalcolata | Posizioni uguali a quelle di Fascicoli sulle 20 risposte | 5 giorni |
| 6 | Fascicoli esporta il JSON per ogni dossier | Ogni dossier ha il suo rapporto | 3 giorni |
| 7 | Spostamento della pipeline dei dati in `dati/` | `make update-data` gira da qui; Fascicoli la usa da qui | 3 giorni |

Le fasi 0–2 si possono chiudere prima di ISWC (25–29 ottobre): a Bari si può mostrare la verifica delle
citazioni dal vivo, anche su una risposta di ChatGPT con il nostro MCP.

## Banco di prova per la rivista

Con il verificatore, le tre garanzie diventano misure confrontabili tra sistemi diversi:

- un set pubblico di 50 domande, con periodo e gruppi attesi;
- risposte di Fascicoli, di LLM generici senza strumenti e di LLM generici con il nostro MCP;
- per ciascuno: quota di citazioni esatte, gruppi omessi, posizione media delle voci citate.

È il contributo per l'estensione su rivista dell'articolo In-Use: un metodo che chiunque può applicare a
qualunque sistema, non solo al nostro.

## Decisioni da prendere

1. **Licenza del verificatore.** Apache 2.0 come il codice di ricerca, oppure EUPL.
2. **Lingua dello schema.** Nomi dei campi in italiano (come sopra) o in inglese, più adatto a sistemi
   esterni e alla rivista.
3. **Pubblicare gli embedding.** Sono derivati da un modello OpenAI: va controllato che i termini d'uso ne
   permettano la ridistribuzione.
4. **Normalizzazione delle citazioni.** L'elenco chiuso proposto nel controllo 1 va approvato e poi
   congelato in v1.
5. **Elenco dei gruppi in Fascicoli.** Se il verificatore ricava i gruppi dal grafo, anche Fascicoli
   dovrebbe smettere di usare la lista fissa di `default.yaml`, altrimenti i due possono divergere.

## Rischi

- **Chunk e testo integrale divergono.** Se la differenza è grande, la fase 1 si allunga. La misura va fatta
  il primo giorno.
- **«Sul tema» resta un giudizio.** Il controllo dei gruppi lo rende trasparente, non oggettivo. Il rapporto
  deve dirlo.
- **Versioni dei dati.** Una risposta di agosto verificata sui dati di ottobre può dare esiti diversi (cambi
  di gruppo, interventi corretti). Il formato deve indicare la versione dei dati usata da chi ha risposto.
