# Produzione su Railway

Il servizio pubblico gira su Railway in due servizi dello stesso progetto:

- **web**: l'immagine del `Dockerfile` (`uvicorn api.main:app`), che serve il sito (`sito/`), le API sotto `/v1`, il server MCP su `/mcp` e la chat. Configurazione in `railway.toml`.
- **db**: Postgres 16 con pgvector, con un volume per i dati.

La pipeline notturna resta sulla VPS: scarica dalle fonti, trasforma e carica nel Postgres di Railway. L'immagine web non contiene la pipeline, Playwright né le sue dipendenze: solo `requirements-api.txt`, `api/`, `sito/`, `schema/` e `pipeline/ambiente.py`.

Comandi e struttura del codice stanno nella [guida per chi sviluppa](sviluppo.md).

## Immagine web

```
docker build -t parliamentrag-web .
docker run --rm --env-file prova.env -p 8795:8795 parliamentrag-web     # prova.env: variabili qui sotto, PORT=8795
```

- Python 3.13 slim, utente `web` (uid 10001) senza privilegi, circa 190 MB.
- Avvio: `uvicorn api.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`. Railway assegna `PORT`. Senza `--forwarded-allow-ips` uvicorn ignora le intestazioni del proxy e i reindirizzamenti del sito uscirebbero in http.
- Un solo processo: il limite di richieste per IP vive in memoria, per processo. Con più repliche il limite vale per replica.
- Railway controlla `/v1/salute` a ogni rilascio (`healthcheckPath`): la versione nuova prende il traffico solo se risponde 200, cioè se raggiunge il database. L'`HEALTHCHECK` del Dockerfile serve a `docker run`.
- `.env` resta fuori dall'immagine (`.dockerignore`): in produzione i valori arrivano dalle variabili del servizio.

## Variabili d'ambiente del servizio web

Tutte quelle che il codice di `api/` legge con `env(...)`. I segreti si scrivono solo nel pannello delle variabili di Railway.

| Variabile | Obbligatoria | A cosa serve | Valore in produzione |
|---|---|---|---|
| `API_PG_HOST` | sì | host di Postgres per tutti e tre gli utenti | `${{db.RAILWAY_PRIVATE_DOMAIN}}` (rete privata) |
| `PG_PORTA` | sì | porta di Postgres; il predefinito 5440 vale solo in locale | `5432` |
| `API_PG_UTENTE` | no | utente di sola lettura | `lettura` (predefinito) |
| `API_PG_PASSWORD` | sì | password di `lettura` (`schema/lettura.sql`) | segreto |
| `REGISTRO_PG_PASSWORD` | no | password di `registro`: senza, la chat risponde e non scrive `registro.chat` | segreto |
| `SITO_PG_PASSWORD` | no | password di `sito`: senza, niente conversazioni condivise né cache delle traduzioni | segreto |
| `OPENAI_API_KEY` | sì per la chat | chat, traduzioni in inglese, vettore della domanda nella ricerca | segreto |
| `BREVO_API_KEY` | no | invio delle segnalazioni di errore; senza, le segnalazioni non partono | segreto |
| `API_PROXY` | sì | `1`: l'IP per i limiti si legge da `X-Forwarded-For`, che dietro Railway scrive il proxy | `1` |
| `LIMITE_SALE` | sì | chiave dell'impronta degli IP per il limite della chat; senza, ne nasce una casuale a ogni avvio e un rilascio azzera i conteggi | 64 caratteri esadecimali casuali, segreto |
| `AGENTE_DOMANDE_ORA` | no | domande alla chat per IP nell'ora | `10` (predefinito) |
| `AGENTE_DOLLARI_GIORNO` | no | tetto di spesa giornaliero di chat e traduzioni, in dollari | `10` (predefinito) |
| `AGENTE_MODELLO` | no | modello della chat | predefinito nel codice |
| `TRADUZIONI_MODELLO` | no | modello delle traduzioni | predefinito nel codice |
| `MCP_STRUMENTI_INTERNI` | no | `1` espone su `/mcp` anche gli strumenti interni | `0` (predefinito) |
| `CARTELLA_DATI` | no | cartella dei dati del servizio (foto dei senatori in `foto/senatori`) | `dati` (predefinito) |
| `PORT` | no | la assegna Railway | non impostarla |

Il nome del database è fisso nel codice: `parliamentrag`.

## Foto dei senatori

senato.it serve le foto dietro il WAF, quindi la pipeline le scarica (passo `senato_foto`, con il browser senza interfaccia) e le scrive nella tabella `person_photo` di Postgres (jpeg in `bytea`, 212 foto, circa 8 MB), tenendo una copia in `dati/foto/senatori/`. La rotta `/dati/foto/senatori/{id}.jpg` legge la tabella, poi il file, e solo se mancano tutti e due rimanda a senato.it. Le foto arrivano in produzione con `pg_dump` e poi con il giro notturno, come gli altri dati: il servizio web non ha bisogno di volumi.

## Database su Railway

### Dimensioni misurate (4/11/2026, Postgres locale)

| Cosa | Spazio |
|---|---|
| `pg_database_size('parliamentrag')` | 11,3 GB (12.145.892.375 byte), senza l'indice HNSW |
| `passage_vector` (1.185.472 vettori `halfvec(1024)`) | 3,5 GB, di cui 179 MB di chiave primaria |
| `ballot` | 2,2 GB, di cui 809 MB di chiave primaria |
| `speech` | 965 MB |
| `passage` | 549 MB |
| `document` | 368 MB |
| `amendment_signer`, `amendment` | 291 MB, 279 MB |
| `act` | 229 MB |
| `passage_vector_hnsw` | in costruzione (fase «loading tuples», 80%); stima 2,5-3 GB |

Totale atteso con l'indice: circa 14-15 GB. Con la crescita della legislatura conviene un volume da 25 GB. Il `pg_dump -Fc` non contiene gli indici ma scrive i vettori come testo: stima 4-6 GB, da misurare al primo dump.

### Creare il servizio

1. Nel progetto Railway, nuovo servizio da immagine Docker `pgvector/pgvector:pg16` (la stessa del `docker-compose.yml`, pgvector 0.8), oppure il modello pgvector di Railway, purché dia Postgres 16.
2. Volume montato su `/var/lib/postgresql/data`, 25 GB. Il piano Hobby arriva a 5 GB di volume: serve il piano Pro.
3. Variabili del servizio db: `POSTGRES_DB=parliamentrag`, `POSTGRES_USER=parliamentrag` (gli script `schema/*.sql` danno i permessi a partire da questo proprietario), `POSTGRES_PASSWORD` segreta, `PGDATA=/var/lib/postgresql/data/pgdata` (il volume contiene già `lost+found`).
4. TCP Proxy pubblico acceso sulla porta 5432: serve al ripristino e al giro notturno della VPS. Il servizio web usa la rete privata.
5. TLS: l'immagine `pgvector/pgvector` non lo attiva. Prima di aprire il proxy pubblico va attivato (certificato nel volume e `ssl=on`), oppure si usa un'immagine Railway con TLS e pgvector, se il modello lo offre. Dalla VPS ci si collega con `PGSSLMODE=require`. Va verificato prima del primo ripristino.
6. Memoria: per la ricerca semantica l'indice HNSW (circa 3 GB) dovrebbe stare in memoria. Impostazioni consigliate per un contenitore da 4 GB: `shared_buffers=1GB`, `effective_cache_size=3GB`, `maintenance_work_mem=2GB` solo durante la costruzione dell'indice.

### Copiare il database locale

Dal Mac, a indice HNSW finito. Le password restano in variabili d'ambiente, mai negli argomenti.

```
# 1. dump dal contenitore locale (formato custom, compresso)
docker compose exec -T testi pg_dump -U parliamentrag -d parliamentrag -Fc > dati/parliamentrag.dump
ls -lh dati/parliamentrag.dump

# 2. ripristino verso Railway, senza permessi (gli utenti li creano gli script al passo 3);
#    PGOPTIONS dà memoria alla costruzione dell'indice HNSW, che pg_restore rifà da zero
export PGHOST=<host del TCP proxy> PGPORT=<porta del proxy> PGUSER=parliamentrag PGDATABASE=parliamentrag PGSSLMODE=require
read -s PGPASSWORD; export PGPASSWORD
PGOPTIONS='-c maintenance_work_mem=2GB -c max_parallel_maintenance_workers=0' \
  pg_restore --no-privileges --no-owner --role=parliamentrag -d parliamentrag --jobs=4 dati/parliamentrag.dump
```

`pg_restore` crea anche l'estensione `vector`. I client `pg_dump`/`pg_restore` vanno usati alla versione 16 (quelli del contenitore locale, oppure `postgresql@16` sul Mac). L'indice HNSW si ricostruisce sul server: in locale, con 2 GB di `maintenance_work_mem` e senza processi paralleli, ci sono volute circa due ore e mezza; su un contenitore più piccolo può volerci di più. Il dump del 4/11 è già pronto: `dati/dump/parliamentrag-2026-11-04.dump` (5,9 GB, impronta SHA-256 in `.sha256` accanto; lo schema si ripristina senza errori, provato in un database temporaneo).

Dopo il ripristino, una volta: `psql -c "ANALYZE"` (circa due minuti), perché il dump non porta le statistiche del planner e senza di esse le query sui voti (`ballot`) scelgono piani lenti.

### Creare gli utenti `lettura`, `registro`, `sito`

Dopo il ripristino, con le stesse variabili `PG*` del passo 2. Le tre password sono quelle che poi vanno nel servizio web.

```
for f in lettura:API_PG_PASSWORD registro:REGISTRO_PG_PASSWORD sito:SITO_PG_PASSWORD; do
  read -s -p "${f#*:}: " P; echo
  { printf '\\set password %s\n' "$P"; cat "schema/${f%%:*}.sql"; } | psql -v ON_ERROR_STOP=1
done
```

Gli script si possono rilanciare: creano l'utente se manca, aggiornano la password e rifanno i permessi. `lettura.sql` va rilanciato anche dopo una tabella nuova creata da un utente diverso da `parliamentrag`.

## Domini

Il DNS sta su Cloudflare; gli apex rimandano già a www con un 301.

1. Nel servizio web, Settings → Networking → Custom Domain: aggiungi `www.parliamentrag.it` e `mcp.parliamentrag.it`. Railway dà per ciascuno un CNAME (`….up.railway.app`) e un record TXT di verifica.
2. Su Cloudflare: i due CNAME e i TXT. Con il proxy arancione acceso, SSL/TLS in modalità «Full (strict)», così Railway può emettere il certificato.
3. Lo stesso servizio risponde su entrambi i nomi: il sito su `/`, i client MCP su `https://mcp.parliamentrag.it/mcp`, l'icona su `/icon.png`.
4. Prova: `curl https://www.parliamentrag.it/v1/salute` e un `initialize` su `https://mcp.parliamentrag.it/mcp`.

## Giro notturno verso Railway

La pipeline scrive in Postgres con `psql`, e un solo punto costruisce il comando: `comando_psql()` in `pipeline/carica/postgres.py`, usato dal caricamento, dallo schema, dalle foto dei senatori e da `pipeline/vettori.py` (lettura in CSV con `leggi_csv()`, brani, vettori, indice).

- Senza `PGHOST` nell'ambiente (o in `.env`): il Postgres locale, con `docker compose exec -T testi psql -U parliamentrag -d parliamentrag`, come prima.
- Con `PGHOST`: il Postgres remoto. Si usa il `psql` del sistema se c'è (sulla VPS: `apt install postgresql-client-16`), altrimenti `docker run --rm -i -e PGHOST -e PGPORT -e PGUSER -e PGPASSWORD -e PGSSLMODE pgvector/pgvector:pg16 psql`, che dà il client 16 senza installare niente. `-e NOME` senza valore passa la variabile senza scriverla negli argomenti: le password non compaiono mai in `ps` né nei log. Con `docker run`, `PGHOST` deve essere un nome raggiungibile dal contenitore (il TCP proxy di Railway lo è; `localhost` no).

Sulla VPS, in `.env`: `PGHOST` e `PGPORT` del TCP proxy, `PGUSER=parliamentrag`, `PGPASSWORD`, `PGSSLMODE=require`. Il traffico in entrata su Railway non si paga. Il giro può continuare a caricare anche nel Postgres della VPS, come copia di lavoro e di riserva: basta lanciarlo senza `PGHOST`.

All'inizio di ogni giro una prova (`SELECT 1`) controlla che il database risponda, e un'altra che sul disco dei dati ci siano almeno `spazio_minimo_gb` liberi: se una fallisce il giro si chiude subito come «bloccato», senza scaricare niente.

### Caricamento

- Il caricamento tiene un registro file per file (`caricamento.sqlite` nella cartella dei dati, separato per destinazione: «locale» o `host:porta`): percorso, impronta, data. Salta i file già caricati e invariati, e dopo un'interruzione riprende dal primo che manca. Per ricaricare tutto in un database nuovo basta un `PGHOST` diverso; per ricaricare tutto nello stesso, si cancellano le sue righe da `caricamento.sqlite`.
- Ordine: anagrafica, poi governo e corrispondenze, poi atti e sindacato ispettivo, poi il resto.
- Un file che non passa i controlli o non si carica va in quarantena (nel registro, con il motivo) e gli altri vanno avanti; il riepilogo del passo e la mail di fine giro lo dicono. A ogni giro i file in quarantena si ricontrollano e si riprovano.
- Il caricamento ha un suo tempo (`[carica] tempo_minuti` in `pipeline.toml`, 150): finito quello si ferma fra un file e l'altro, e il giro dopo riprende. Non dipende dal tempo del giro: parte anche se i download lo hanno finito.
- `schema/v3.sql` si applica solo se è cambiato dall'ultima volta in quella destinazione, con `SET lock_timeout = '5s'`: se una tabella è occupata (un indice in costruzione) lo schema aspetta il giro dopo e il caricamento va avanti.

Da sapere:

- l'indice HNSW si costruisce una volta sola (`CREATE INDEX IF NOT EXISTS`); i vettori nuovi entrano nell'indice al caricamento. Il passo `controlla_indice` avvisa se manca o non è valido;
- `indice()` imposta `maintenance_work_mem = '2GB'`: sul database Railway serve memoria per farlo, solo se l'indice va rifatto;
- `invia_vettori` non spende più di `[vettori] dollari_per_notte` (5 $) in 24 ore, stimati dai caratteri dei brani.

## Cron della VPS

Il giro notturno parte da `pipeline/notte.sh`, che:

- tiene un giro alla volta con `flock` (`dati/log/notte.lock`): se il giro di ieri è ancora in corso, quello di oggi non parte;
- scrive un log per giro, `dati/log/giro-AAAAMMGG-HHMMSS.log` (orario UTC), e una riga di inizio e fine in `dati/log/notte.log`; i log più vecchi di 60 giorni si cancellano. `LOG_DIR` cambia la cartella;
- rifiuta un giro completo se uno è riuscito nelle ultime 20 ore (`python -m pipeline giro` esce con 3), così un cron lanciato due volte non ripete le richieste alla Camera e al Senato; `pipeline/notte.sh --forza` lo lancia comunque;
- a fine giro, se l'esito non è ok o ci sono avvisi (file in quarantena, tetti raggiunti), manda una mail a segnalazioni@parliamentrag.it via Brevo (`python -m pipeline avvisa`, mittente news@parliamentrag.it, chiave `BREVO_API_KEY` in `.env`) con i passi non riusciti e la fine del log.

Nel giro, dopo un 403 o un 503 da un sito della Camera (`sito = "camera"` nel passo) i passi successivi della Camera si saltano, con il motivo nello stato: la Camera blocca l'IP e insistere allunga il blocco. Le trasformazioni, i controlli e il caricamento partono anche quando i download hanno finito il tempo del giro.

Orari in UTC, come il cron della VPS. Il giro parte all'01:30 UTC (02:30 in Italia con l'ora solare, 03:30 con l'ora legale):

```
# /etc/cron.d/parliamentrag-pipeline
CRON_TZ=UTC
30 1 * * *  <utente>  <cartella del repo>/pipeline/notte.sh
# controllo esterno: esce con 1 se nelle ultime 26 ore non c'è un giro completo riuscito
0 9 * * *   <utente>  cd <cartella del repo> && .venv/bin/python -m pipeline salute || <avviso>
```

`python -m pipeline salute` serve a un controllo esterno (un altro cron, un servizio di monitoraggio): dice se c'è un giro completo riuscito nelle ultime 26 ore.

Il processo di ogni passo ha un gruppo di processi suo: alla scadenza si fermano anche `psql`, `git` e Chromium lanciati dal passo. Un giro fermato con SIGTERM (spegnimento della VPS, `kill`) si chiude come «interrotto» e si riprende con `python -m pipeline riprendi`.

## Costo stimato

Prezzi dalla pagina ufficiale (docs.railway.com/reference/pricing/plans, letta il 4/11/2026): RAM 10 $ per GB al mese, CPU 20 $ per vCPU al mese, volume 0,15 $ per GB al mese, traffico in uscita 0,05 $ per GB. Railway fattura l'uso misurato al minuto. Il piano Pro costa 20 $ al mese e comprende 20 $ di uso; il piano Hobby non basta perché ferma i volumi a 5 GB.

| Voce | Ipotesi | Al mese |
|---|---|---|
| Volume del database | 25 GB | 3,75 $ |
| RAM del database | 2-4 GB in media | 20-40 $ |
| CPU del database | 0,1-0,2 vCPU in media, più i picchi del giro notturno | 2-4 $ |
| RAM del web | 0,3-0,5 GB | 3-5 $ |
| CPU del web | 0,05-0,1 vCPU | 1-2 $ |
| Traffico in uscita | 10-30 GB | 0,5-1,5 $ |
| **Uso totale** | | **circa 30-55 $** |
| **Fattura (Pro, 20 $ compresi)** | | **circa 30-55 $** |

La voce incerta è la RAM del database: dipende da quanta cache di pagine Railway conta come memoria usata. La cifra vera si legge nel pannello dopo una settimana. Il costo di OpenAI per chat e traduzioni è a parte e ha il suo tetto giornaliero (`AGENTE_DOLLARI_GIORNO`).
