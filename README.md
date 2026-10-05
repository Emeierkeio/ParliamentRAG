# ParliamentRAG, centro di ricerca

Il sito di [www.parliamentrag.it](https://www.parliamentrag.it). Presenta il centro di ricerca dell'Università di Milano-Bicocca che studia come leggere i lavori parlamentari con l'intelligenza artificiale senza perdere le fonti: i sistemi, le pubblicazioni, il metodo e i dati aperti.

## Le pagine

| Percorso | Contenuto |
|---|---|
| `/` | Il progetto in tre punti: il grafo della Camera, il retrieval che pesa l'autorevolezza, dati e codice aperti |
| `/sistemi` | Fascicoli, Stenografo, Scranno |
| `/pubblicazioni` | I paper di ISWC 2026, con il link alla demo |
| `/method` | Come funziona il sistema |
| `/data` | Il grafo della Camera, XIX legislatura, e i dump RDF |
| `/aggiornamenti` | Le novità del progetto |
| `/sviluppatori` | Il server MCP, le API HTTP su richiesta, i dump e i dataset |
| `/iswc` | Il questionario della demo a ISWC 2026, raggiunto con il QR al banchetto |
| `/privacy`, `/termini` | Informativa e condizioni d'uso |

Le vecchie pagine operative (chat, temi, timeline, parlamentari, gruppi, classifica, compasso, ricerca) rimandano a [Fascicoli](https://www.fascicoli.it), in `next.config.ts`.

## Come è fatto

Next.js senza backend. Le parti dinamiche sono due route:

- `/api/newsletter/subscribe`: iscrizione con doppio consenso su Brevo. Il sito non salva l'indirizzo, lo passa a Brevo.
- `/api/feedback/booth`: salva le risposte al questionario `/iswc` in Postgres.

I numeri del grafo, la data dell'ultimo aggiornamento e gli esempi di `/data` stanno in `src/data/`. Li rigeneri dal sistema ParliamentRAG prima di pubblicare:

```bash
node scripts/snapshot-data.mjs
```

I dump RDF si scaricano da Zenodo ([DOI 10.5281/zenodo.21560331](https://doi.org/10.5281/zenodo.21560331)).

## Avvio in locale

```bash
npm install
cp .env.example .env.local
npm run dev
```

Le variabili sono in `.env.example`. Senza le chiavi Brevo il modulo della newsletter non compare. Senza `DATABASE_URL` il questionario risponde 503.

## Pubblicazione

Railway, progetto «ParliamentRAG centro», servizio `sito` e database `Postgres`, entrambi in Europa (Paesi Bassi). Ogni push su `main` pubblica il sito. Il server Next standalone ha bisogno di `HOSTNAME=0.0.0.0`.

## La famiglia ParliamentRAG

- [Fascicoli](https://www.fascicoli.it): un tema, tutti i gruppi. Dossier con le posizioni dei gruppi, le voci autorevoli e i voti.
- [Stenografo](https://www.stenografo.it): risposte puntuali sui fatti della Camera, ogni frase con la fonte ufficiale.
- [Scranno](https://www.scranno.it): l'Aula di Montecitorio da esplorare, posto per posto.

Il sistema presentato a ISWC 2026 sta nel repository [Emeierkeio/ParliamentRAG](https://github.com/Emeierkeio/ParliamentRAG), tag `iswc2026-demo`. La demo risponde su [truthful-amazement-production.up.railway.app](https://truthful-amazement-production.up.railway.app).

Dati: Camera dei Deputati, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.it). Progetto indipendente: non è affiliato alla Camera dei Deputati.
