# Produzione sulla VPS

Tutto il servizio gira sulla VPS Hetzner (CPX32, Helsinki: 4 vCPU, 8 GB di RAM, 160 GB di disco), in tre contenitori dello stesso progetto Compose, dalla cartella del repo (`/opt/piattaforma`):

- **testi**: Postgres 16 con pgvector (`docker-compose.yml`), lo stesso database del giro notturno, porta solo su 127.0.0.1;
- **web**: l'immagine del `Dockerfile` (`uvicorn api.main:app`): sito (`sito/`), API `/v1`, server MCP `/mcp`, chat, fascicolo, autorevolezza e verifica;
- **caddy**: HTTPS con Let's Encrypt davanti a web (`deploy/vps/Caddyfile`), porte 80 e 443.

Web e Caddy stanno in `docker-compose.vps.yml`, che si usa insieme al file di base:

```
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
```

Il giro notturno gira sulla stessa macchina e scrive nel database in locale (senza `PGHOST`), come sul Mac. Scelta del 4/11/2026. Comandi e struttura del codice stanno nella [guida per chi sviluppa](sviluppo.md).

## Memoria

Con Neo4j spento la VPS ha circa 7 GB liberi. Il fascicolo e l'autorevolezza cercano negli indici HNSW dei soli interventi (`speech_vector_hnsw`, 1 GB) e degli atti (`act_vector_hnsw`, 250 MB), che devono stare in memoria; l'indice di tutti i brani (`passage_vector_hnsw`, 3,1 GB) lo usa solo la ricerca per significato della chat e può stare nella cache del sistema. In `.env`:

```
PG_SHARED_BUFFERS=2GB
PG_CACHE=5GB
PG_SHM=2g
```

`pg_prewarm` (già nell'immagine) con `autoprewarm` ricarica dopo ogni riavvio le pagine che erano in memoria. Dopo il primo ripristino: `SELECT pg_prewarm('speech_vector_hnsw'), pg_prewarm('act_vector_hnsw');`. Il contenitore web ha un tetto di 1 GB. `stop_grace_period` di 120 s: con meno, Docker ferma Postgres prima che chiuda e al riavvio parte il ripristino automatico.

## Statistiche di visita

Le conta il servizio stesso (`api/statistiche.py`, tabella `sito.visita` in `schema/sito.sql`): la pagina manda a `/api/visita` percorso, provenienza, larghezza della finestra e lingua, solo su www.parliamentrag.it (in locale con `?stat=1`); domande alla chat e fascicoli li conta il servizio. Niente cookie né IP: il visitatore è un'impronta di IP, browser e giorno con `LIMITE_SALE`. Paese e regione vengono dall'IP con il file DB-IP «IP to City Lite» (CC BY 4.0) in `dati/geo/`, montato in sola lettura nel container web: lo scarica `deploy/vps/geoip.sh` una volta al mese, chiamato da `pipeline/notte.sh`; senza il file paese e regione restano vuoti. Gli attivi ora vengono da `/api/presenza`, che ogni pagina in primo piano chiama una volta al minuto: restano in memoria per due minuti. Il pannello è `https://www.parliamentrag.it/statistiche`, dietro login, e mostra anche da quale pagina partono le domande, le pagine di uscita e gli strumenti usati dalla chat (vista `registro.uso_strumenti`, senza domande né risposte). Dopo il ripristino va rilanciato `schema/sito.sql` (crea la tabella, la vista e i permessi), dopo `schema/registro.sql`.

## Concorrenza

Un processo uvicorn; ogni risposta della chat occupa un thread per la sua durata (40 al massimo, il predefinito di Starlette) e una connessione a Postgres (100 al massimo). Prova del 4/11: 10 domande insieme, tutte servite, in 6-29 s, con 10 connessioni aperte. I fascicoli girano al più 3 alla volta (`FASCICOLI_INSIEME`); il quarto aspetta il suo turno con l'evento `waiting`. I limiti per visitatore: 10 domande l'ora (`AGENTE_DOMANDE_ORA`) e 120 richieste al minuto alle API; il tetto di spesa giornaliero (`AGENTE_DOLLARI_GIORNO`, 25 $) ferma chat e fascicolo per tutti quando è raggiunto.

## Variabili d'ambiente del servizio web

Tutte quelle che il codice di `api/` legge con `env(...)`. I segreti stanno in `.env.web` sulla VPS (chmod 600), mai nel repo.

| Variabile | Obbligatoria | A cosa serve | Valore in produzione |
|---|---|---|---|
| `API_PG_HOST` | sì | host di Postgres per tutti e tre gli utenti | `testi` (lo mette `docker-compose.vps.yml`) |
| `PG_PORTA` | sì | porta di Postgres; il predefinito 5440 vale solo dal Mac | `5432` (lo mette `docker-compose.vps.yml`) |
| `API_PG_UTENTE` | no | utente di sola lettura | `lettura` (predefinito) |
| `API_PG_PASSWORD` | sì | password di `lettura` (`schema/lettura.sql`) | segreto |
| `REGISTRO_PG_PASSWORD` | no | password di `registro`: senza, la chat risponde e non scrive `registro.chat` | segreto |
| `SITO_PG_PASSWORD` | no | password di `sito`: senza, niente conversazioni condivise né cache delle traduzioni | segreto |
| `OPENAI_API_KEY` | sì per la chat | chat, traduzioni in inglese, vettore della domanda nella ricerca | segreto |
| `BREVO_API_KEY` | no | invio delle segnalazioni di errore; senza, le segnalazioni non partono | segreto |
| `API_PROXY` | sì | `1`: l'IP per i limiti si legge da `X-Forwarded-For`, che scrive Caddy | `1` (lo mette `docker-compose.vps.yml`) |
| `LIMITE_SALE` | sì | chiave dell'impronta degli IP per il limite della chat; senza, ne nasce una casuale a ogni avvio e un rilascio azzera i conteggi | 64 caratteri esadecimali casuali, segreto |
| `AGENTE_DOMANDE_ORA` | no | domande alla chat per IP nell'ora | `10` (predefinito) |
| `AGENTE_DOLLARI_GIORNO` | no | tetto di spesa giornaliero di chat, fascicoli e traduzioni, in dollari | `25` (predefinito) |
| `AGENTE_MODELLO` | no | modello della chat | predefinito nel codice |
| `TRADUZIONI_MODELLO` | no | modello delle traduzioni | predefinito nel codice |
| `MCP_STRUMENTI_INTERNI` | no | `1` espone su `/mcp` anche gli strumenti interni | `0` (predefinito) |
| `CARTELLA_DATI` | no | cartella dei dati del servizio (foto dei senatori in `foto/senatori`) | `dati` (predefinito) |
| `PORT` | no | porta di uvicorn nel contenitore | `8000` (lo mette `docker-compose.vps.yml`) |

Il nome del database è fisso nel codice: `parliamentrag`.

`.env.web` sulla VPS: `API_PG_PASSWORD`, `REGISTRO_PG_PASSWORD`, `SITO_PG_PASSWORD`, `OPENAI_API_KEY`, `BREVO_API_KEY`, `LIMITE_SALE`, `STATISTICHE_UTENTE` e `STATISTICHE_PASSWORD` (login del pannello `/statistiche`; senza, il pannello non esiste). Le altre del servizio le mette `docker-compose.vps.yml`.

## Foto dei senatori

senato.it serve le foto dietro il WAF, quindi la pipeline le scarica (passo `senato_foto`, con il browser senza interfaccia) e le scrive nella tabella `person_photo` di Postgres (jpeg in `bytea`, 212 foto, circa 8 MB), tenendo una copia in `dati/foto/senatori/`. La rotta `/dati/foto/senatori/{id}.jpg` legge la tabella, poi il file, e solo se mancano tutti e due rimanda a senato.it. Le foto arrivano in produzione con `pg_dump` e poi con il giro notturno, come gli altri dati: il servizio web non ha bisogno di volumi.

## Primo avvio

### Copiare il database

Dal Mac, con un dump fatto dopo l'ultimo caricamento (`docker compose exec -T testi pg_dump -U parliamentrag -d parliamentrag -Fc > dati/dump/parliamentrag-AAAA-MM-GG.dump`, impronta con `shasum -a 256`):

```
scp dati/dump/parliamentrag-AAAA-MM-GG.dump* root@89.167.54.206:/opt/piattaforma/dati/dump/
```

Sulla VPS, con Neo4j spento (`docs/vps/neo4j.sh spegni`) perché la ricostruzione degli indici HNSW è il momento di picco della memoria:

```
cd /opt/piattaforma
shasum -a 256 -c dati/dump/parliamentrag-AAAA-MM-GG.dump.sha256
docker compose up -d testi
docker compose exec -T -e PGOPTIONS='-c maintenance_work_mem=2GB -c max_parallel_maintenance_workers=0' testi \
  pg_restore -U parliamentrag -d parliamentrag --no-privileges --no-owner --role=parliamentrag < dati/dump/parliamentrag-AAAA-MM-GG.dump
docker compose exec -T testi psql -U parliamentrag -d parliamentrag -c ANALYZE
```

`pg_restore` crea l'estensione `vector` e ricostruisce i tre indici HNSW. Il modo veloce, usato il 4/11/2026 (20 minuti in tutto invece di 3-4 ore), con il sito spento:

1. dati in parallelo: `docker cp` del dump nel contenitore, poi `pg_restore --section=pre-data` e `pg_restore --section=data -j 3`;
2. Postgres con `PG_SHARED_BUFFERS=1GB` e `PG_SHM=5g` in `.env` (`docker compose up -d testi`), perché la costruzione in parallelo di un indice HNSW tiene il grafo nella memoria condivisa;
3. `pg_restore --section=post-data` con `PGOPTIONS='-c maintenance_work_mem=4GB -c max_parallel_maintenance_workers=3'`: tutti gli indici e le chiavi in 11 minuti, l'indice di tutti i brani (3 GB) compreso;
4. di nuovo `PG_SHARED_BUFFERS=2GB` e `PG_SHM=2g`, e riavvio di testi.

Con `maintenance_work_mem` più piccolo dell'indice la costruzione esce dalla memoria e richiede ore. `ANALYZE` (circa due minuti) serve perché il dump non porta le statistiche del planner: senza, le query sui voti scelgono piani lenti. Dopo il ripristino: `TRUNCATE sito.spesa, sito.domanda, sito.visita`, perché il dump porta la spesa e i contatori delle prove in locale.

### Creare gli utenti `lettura`, `registro`, `sito`

Dopo il ripristino, dentro il contenitore. Le tre password sono quelle che poi vanno nel servizio web.

```
for f in lettura:API_PG_PASSWORD registro:REGISTRO_PG_PASSWORD sito:SITO_PG_PASSWORD; do
  read -s -p "${f#*:}: " P; echo
  { printf '\\set password %s\n' "$P"; cat "schema/${f%%:*}.sql"; } | docker compose exec -T testi psql -U parliamentrag -d parliamentrag -v ON_ERROR_STOP=1
done
```

Gli script si possono rilanciare: creano l'utente se manca, aggiornano la password e rifanno i permessi. `lettura.sql` va rilanciato anche dopo una tabella nuova creata da un utente diverso da `parliamentrag`.

### Avviare web e Caddy

```
ufw allow 443/tcp && ufw allow 443/udp            # la 80 è già aperta
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build web caddy
curl -s http://127.0.0.1:80 -H 'Host: www.parliamentrag.it' -o /dev/null -w '%{http_code}\n'   # 308 verso https
```

Caddy prende la porta 80: il rinnovo di certbot in modalità standalone per db.parliamentrag.it non funziona più. Finché Neo4j resta spento non serve; se si riaccende per tornare indietro, il certificato attuale vale ancora fino alla sua scadenza.

## Domini

Il DNS sta su Cloudflare, i record www sempre «DNS only» (Caddy deve vedere l'IP vero del visitatore e rispondere alla prova di Let's Encrypt):

1. `www.parliamentrag.it` e `mcp.parliamentrag.it`: record A verso 89.167.54.206 al posto dei CNAME verso Railway. L'apex `parliamentrag.it` A verso la stessa VPS (Caddy rimanda a www).
2. Caddy chiede i certificati al primo accesso: `docker compose -f docker-compose.yml -f docker-compose.vps.yml logs caddy`.
3. Prova: `curl https://www.parliamentrag.it/v1/salute` e un `initialize` su `https://mcp.parliamentrag.it/mcp`.

Per tornare indietro: i record di prima (CNAME verso Railway, con il sito vecchio ancora acceso) e `docs/vps/neo4j.sh accendi`.

## Aggiornare il codice

```
deploy/vps/aggiorna.sh
```

`git pull --ff-only`, nuova immagine web, riavvio di web e Caddy (il database no), controllo di `/v1/salute`. Se il servizio non risponde lo script esce con 1 e dice a quale commit tornare. Non c'è più il «push su main = deploy»: l'aggiornamento parte solo dalla VPS.

## Giro notturno

La pipeline scrive in Postgres con `psql`, e un solo punto costruisce il comando: `comando_psql()` in `pipeline/carica/postgres.py`. Sulla VPS non serve `PGHOST`: il giro usa `docker compose exec -T testi psql`, come sul Mac. `PGHOST` resta per caricare in un Postgres remoto.

All'inizio di ogni giro una prova (`SELECT 1`) controlla che il database risponda, e un'altra che sul disco dei dati ci siano almeno `spazio_minimo_gb` liberi: se una fallisce il giro si chiude subito come «bloccato», senza scaricare niente. Il passo `controlla_indice` copia in `speech_vector` e `act_vector` i vettori dei brani nuovi e controlla che i tre indici HNSW siano validi.

### Caricamento

- Il caricamento tiene un registro file per file (`caricamento.sqlite` nella cartella dei dati, separato per destinazione: «locale» o `host:porta`): percorso, impronta, data. Salta i file già caricati e invariati, e dopo un'interruzione riprende dal primo che manca. Per ricaricare tutto in un database nuovo basta un `PGHOST` diverso; per ricaricare tutto nello stesso, si cancellano le sue righe da `caricamento.sqlite`.
- Ordine: anagrafica, poi governo e corrispondenze, poi atti e sindacato ispettivo, poi il resto.
- Un file che non passa i controlli o non si carica va in quarantena (nel registro, con il motivo) e gli altri vanno avanti; il riepilogo del passo e la mail di fine giro lo dicono. A ogni giro i file in quarantena si ricontrollano e si riprovano.
- Il caricamento ha un suo tempo (`[carica] tempo_minuti` in `pipeline.toml`, 150): finito quello si ferma fra un file e l'altro, e il giro dopo riprende. Non dipende dal tempo del giro: parte anche se i download lo hanno finito.
- `schema/v3.sql` si applica solo se è cambiato dall'ultima volta in quella destinazione, con `SET lock_timeout = '5s'`: se una tabella è occupata (un indice in costruzione) lo schema aspetta il giro dopo e il caricamento va avanti.

Da sapere:

- l'indice HNSW si costruisce una volta sola (`CREATE INDEX IF NOT EXISTS`); i vettori nuovi entrano nell'indice al caricamento. Il passo `controlla_indice` avvisa se manca o non è valido;
- `indice()` imposta `maintenance_work_mem = '2GB'`: con Neo4j spento la VPS ha la memoria per farlo, solo se un indice va rifatto;
- `invia_vettori` non spende più di `[vettori] dollari_per_notte` (5 $) in 24 ore, stimati dai caratteri dei brani.

Playwright e Chromium per senato.it: `.venv/bin/playwright install --with-deps chromium` (una volta, come root).

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
30 1 * * *  root  /opt/piattaforma/pipeline/notte.sh
# controllo esterno: esce con 1 se nelle ultime 26 ore non c'è un giro completo riuscito
0 9 * * *   root  cd /opt/piattaforma && .venv/bin/python -m pipeline salute || <avviso>
# fotografia della VPS per il pannello /sistema: giri, quarantena, disco, memoria, container, backup
*/10 * * * * root  cd /opt/piattaforma && .venv/bin/python -m pipeline sistema > /dev/null
```

Il pannello del responsabile è `https://www.parliamentrag.it/sistema`, con lo stesso login delle statistiche: stato del giro notturno e dei passi, freschezza dei dati per ramo, righe e peso del database, errori e tempi della chat, costi OpenAI, disco, memoria, container e backup, con gli avvisi calcolati in cima. Il container web non vede la VPS: `python -m pipeline sistema` (cron ogni 10 minuti) scrive `dati/sistema/stato.json`, montato in sola lettura nel container; chat e costi vengono dalle viste `registro.uso_chat` e `registro.spesa_vettori` di `schema/sito.sql`.

`python -m pipeline salute` serve a un controllo esterno (un altro cron, un servizio di monitoraggio): dice se c'è un giro completo riuscito nelle ultime 26 ore.

Il processo di ogni passo ha un gruppo di processi suo: alla scadenza si fermano anche `psql`, `git` e Chromium lanciati dal passo. Un giro fermato con SIGTERM (spegnimento della VPS, `kill`) si chiude come «interrotto» e si riprende con `python -m pipeline riprendi`.

Il cron vecchio (`/etc/cron.d/parliamentrag-nightly`, `make update-data`) lo sospende `docs/vps/neo4j.sh spegni`.

## Backup

`/opt/parliamentrag-backup/backup.sh` (00:45 UTC, restic su Storage Box) oggi salva il Postgres dell'archivio e Neo4j. Va aggiunto il dump del database `parliamentrag` del contenitore `testi` (`pg_dump -Fc`, circa 6 GB, una copia per notte, le ultime due), e con Neo4j spento la sua parte va saltata (riga in `docs/vps/README.md`).

## Costo

Nessun costo in più per l'hosting: la VPS c'è già (35,49 € al mese più IVA). A parte OpenAI per chat, fascicoli e traduzioni, con il tetto giornaliero `AGENTE_DOLLARI_GIORNO`, e gli embedding dei brani nuovi della notte (`[vettori] dollari_per_notte`, 5 $ al massimo).
