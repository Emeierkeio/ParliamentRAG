# Ecosistema ParliamentRAG, nuova versione

Versione locale e statica del nuovo ecosistema: il sito di ParliamentRAG e i tre
sistemi (Stenografo, Fascicoli, Scranno) su un solo design system, «Resoconto».

## Avvio

```sh
cd ecosistema
python3 serve.py
```

Poi apri http://localhost:4873/ (porta a `parliamentrag/index.html`).

`serve.py` serve i file statici e inoltra le richieste `GET /api/*` al backend di
ParliamentRAG. Il backend non accetta chiamate da altri domini (CORS): la pagina chiama
`/api` sullo stesso indirizzo e il server locale le gira al backend. Le risposte restano
in memoria per 10 minuti. Scranno usa `/api` per le sedute e le votazioni.

Variabili d'ambiente:

- `BACKEND`: indirizzo del backend (predefinito
  `https://thesis-parliamentrag-production.up.railway.app`), per esempio
  `BACKEND=http://localhost:8000 python3 serve.py` con il backend in locale.
- `PORT`: porta del server locale (predefinita 4873).

Con `python3 -m http.server` le pagine si aprono lo stesso, ma `/api` non esiste:
Scranno mostra allora la fiducia del 7/10/2026 salvata in `aula.js`.

## Struttura

```
ecosistema/
  DESIGN.md              regole del design system
  shared/
    famiglia.css         token e componenti comuni
    famiglia.js          testata, piede, tema, comparse
    data/dati.js         numeri del grafo + tema «Salario minimo» (citazioni verificate)
    data/aula.js         seggi reali dell'Aula + fiducia del 7/10/2026 (voto di riserva)
  parliamentrag/         il progetto di ricerca: home, metodo, verifica, dati,
                         ricerca, sviluppatori, aggiornamenti, privacy, termini
  stenografo/            domande puntuali, risposte con la fonte accanto a ogni frase
  fascicoli/             un tema, tutti i gruppi
  scranno/               l'Aula seggio per seggio, con le votazioni da /api
  serve.py               server locale: file statici + /api inoltrato al backend
```

## Dati

Nessun dato inventato. Le fonti sono:

- `dati.js`: numeri del grafo al 12/10/2026 (`centro/src/data/site-data.json`);
  11 citazioni sul salario minimo, una per gruppo più il Governo, prese dal grafo con
  il server MCP e confrontate parola per parola con i resoconti su camera.it il
  13/10/2026; voto per gruppo sull'emendamento 1.1000 Conte (seduta 209).
- `aula.js`: posti e deputati da `scranno/public/data` (camera.it, 30/9/2026);
  voti individuali della fiducia `camera_leg19_sed722_v034` dal server MCP, usati da
  Scranno quando `/api` non risponde.
- Scranno, modalità Voti: sedute e votazioni da `/api/timeline` (le stesse del sito di
  ParliamentRAG). Un link diretto a una votazione è `scranno/index.html#voto=<id>`, per
  esempio `#voto=camera_leg19_sed722_v034`.

Le risposte di Stenografo e il fascicolo sono esempi statici, costruiti solo con
questi dati. In locale l'iscrizione agli aggiornamenti non parte.

## Numeri e data del grafo: una sola fonte

Tutte le pagine leggono numeri e data del grafo da `window.DATI.stats`. Con `serve.py`
il file `shared/data/dati.js` viene servito con i valori letti in quel momento da
`/api/data/stats`, lo stesso grafo che usa Fascicoli; il file su disco resta come riserva.
Nessuna pagina scrive a mano un numero o una data del grafo.

Scranno ha in più i dettagli di ogni deputato (`scranno/deputati.js`), estratti dal grafo
con lo script di Scranno. Per riallinearli alla stessa data:

```sh
scripts/aggiorna_scranno.sh   # serve il tunnel SSH verso Neo4j (make tunnel in ricerca/)
```
