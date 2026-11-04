# Pagina di manutenzione

Pagina «aggiornamento in corso» per i quattro siti durante il passaggio alla VPS
(decisione del 4/11/2026). Un solo file HTML, servito da `server.py` con la libreria
standard di Python.

- Ogni percorso risponde `503` con `Retry-After: 3600`, `Cache-Control: no-store` e
  `X-Robots-Tag: noindex`: i motori di ricerca capiscono che il fermo è temporaneo.
- Fanno eccezione `/salute` e `/v1/salute`, che rispondono `200`: li usa il controllo di
  Railway a ogni rilascio.
- Il testo cambia col nome host: su `fascicoli`, `scranno` e `stenografo` dice che il
  servizio confluisce in ParliamentRAG. Per provarlo in locale: `?sito=fascicoli`.
  La lingua segue il browser; `?lang=en` o il pulsante EN la cambiano.
- Tema chiaro o scuro secondo il sistema (`prefers-color-scheme`).

## In locale

```sh
cd piattaforma/manutenzione
PORT=8080 python3 server.py        # http://localhost:8080/?sito=scranno
# oppure con Docker
docker build -t manutenzione . && docker run --rm -p 8080:8080 manutenzione
```

## Pubblicarla su Railway

Per ciascuno dei quattro servizi (www.parliamentrag.it, www.fascicoli.it,
www.scranno.it, www.stenografo.it). Il dominio resta collegato al servizio: cambia solo
quello che il servizio esegue.

1. Prima di tutto, nella scheda **Deployments** del servizio, annota l'ultimo rilascio
   attivo: serve per tornare indietro.
2. Dalla cartella `piattaforma/manutenzione`:
   ```sh
   railway link                      # progetto e ambiente del sito
   railway up --service <servizio> --detach
   ```
   `railway up` carica questa cartella e la costruisce con il suo `Dockerfile` e il suo
   `railway.toml` (controllo su `/salute`), senza toccare il repo del sito.
3. Controlla: `curl -sI https://www.fascicoli.it/` deve dare `HTTP/2 503` e
   `retry-after: 3600`. Poi apri la pagina nel browser.

Finché la pagina è in linea, non fare push sui repo dei siti: un push collegato al
servizio farebbe ripartire il deploy del sito vero. Se serve, in **Settings → Source**
si può staccare il repo per il tempo del passaggio.

Se Cloudflare tiene in cache le pagine dei siti, dopo il rilascio va svuotata la cache
del dominio, altrimenti qualcuno continua a vedere il sito vecchio.

## Tornare indietro

Nella scheda **Deployments** del servizio, sul rilascio annotato al passo 1:
menu `⋮` → **Rollback** (o **Redeploy**, secondo la voce che il pannello mostra).
Railway rimette in linea quella versione con la sua configurazione. In alternativa, se il servizio è collegato a GitHub, **Deploy latest
commit** riporta l'ultima versione del ramo.

Quando i DNS passano alla VPS, la pagina su Railway non serve più e i servizi si
possono chiudere.
