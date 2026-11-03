# Passaggio del server MCP a v3

Il server MCP di v3 (`POST /mcp` in `api/main.py`) risponde come quello di produzione su https://mcp.parliamentrag.it/mcp. Dopo il cambio di DNS, il connettore di claude.ai, ChatGPT e Claude Desktop continuano a chiamare gli stessi strumenti con gli stessi argomenti.

## Cosa è compatibile

- Gli otto strumenti con nomi e argomenti di produzione: `search_parliament`, `verify_answer`, `list_sessions`, `get_session_votes`, `get_vote_details`, `get_voted_text`, `get_debate`, `get_vote_hemicycle` (`api/pubblico.py`).
- Le risposte hanno le stesse chiavi e gli stessi tipi dei campioni di produzione del 2/11. Lo controlla `tests/test_mcp_pubblico.py` contro `tests/fixtures/mcp_produzione_forme.json`.
- In entrata valgono gli id vecchi (`leg19_sed736`, `sen_leg19_sed469`, `camera_leg19_sed734_v001`, `senato_leg19_sed469_v006`, `leg19_sed736_tit00010`) e gli uri v3. In uscita escono gli id vecchi, quindi i link del sito `#/strumenti/voto/<id>` restano validi. Gli slug vecchi dei dibattiti del Senato (`sen_leg19_sed469_discussione_..._1919_...`) si risolvono sul punto v3 con lo stesso titolo e gli stessi numeri d'atto. I dibattiti del Senato nuovi escono come `sen_leg19_sed469_d-d1e455`.
- Protocollo: versioni 2025-06-18, 2025-03-26 e 2024-11-05 (il server ripete quella del client, se la conosce); `serverInfo` con nome, versione, `websiteUrl` e icona; `ping`, `resources/list`, `prompts/list`; risposta SSE se il client accetta `text/event-stream`, altrimenti JSON; `Mcp-Session-Id` sulla risposta a `initialize` (la produzione, senza stato, non lo manda; i client lo rimandano e v3 lo ignora); notifiche con 202 e corpo vuoto; blocchi JSON-RPC rifiutati con 400; GET e DELETE con 405 e `Allow: POST`; CORS su `/mcp`; `structuredContent` accanto al testo; `isError` per argomenti sbagliati, id inesistenti e query troppo lunghe; `/icon.png` servita da `api/icona.png`.
- I dodici strumenti italiani dell'agente non compaiono in `tools/list`. Con `MCP_STRUMENTI_INTERNI=1` compaiono e si possono chiamare.

## Cosa cambia rispetto alla produzione

- **Ricerca solo per parole.** v3 non ha embedding: `search_parliament` usa `cerca_interventi` e `cerca_atti`. `score` è null, `match_type` vale `keyword`, `is_exact` è vero se la frase compare tale e quale. `total` conta gli interventi e gli atti trovati, molti meno della ricerca semantica (21 contro 1414 per «tartufo»). Gli atti si cercano solo nel titolo. Tra gli interventi ci sono anche quelli di commissione. `act_kind` usa i codici v3 (`bill`, `written_question`), non quelli italiani della produzione.
- **Verifica divisa in due.** Le citazioni le controlla `verifica_citazioni` dentro v3, solo quelle tra «…». Gruppi e autorevolezza li calcola il verificatore di Fascicoli (`FASCICOLI_URL`, `POST /api/verify`). Se Fascicoli non risponde, la chiamata riesce lo stesso: le due righe del verdetto dicono «not checked» e `outcome` le segna `na`. v3 non produce lo stato `modified` con `closest_passage`: una citazione sbagliata risulta `not_found`.
- **Nessun emiciclo disegnato.** `get_vote_hemicycle` restituisce totali, gruppi e controllo dei conti. `seat_map`, `image_png_url` e `image_svg_url` sono null e manca il blocco immagine. Gli URL `/vote/<id>/hemicycle.png` citati nelle conversazioni passate daranno 404.
- **Riassunti senza modello.** `recap` di `list_sessions` elenca i titoli dei punti non procedurali; in `get_debate` contiene il titolo e chi interviene.
- **Campi null o approssimati:** `act_subject` e `acts[].subject` (di cosa parla una mozione); in `law` Gazzetta Ufficiale, `eli` e Normattiva; i nomi dei gruppi nella grafia di v3 («Fratelli d'Italia», non «FRATELLI D'ITALIA»); `individual_votes[].id` con l'uri v3 della persona; `speech_count` e `phases` (una sola fase per dibattito, il conteggio esclude solo il Presidente); il testo votato solo per gli emendamenti d'Aula della Camera; `get_debate.votes` solo per i voti legati all'atto in `vote_act`; `matches` di `list_sessions` con `search` assente.
- **Argomenti in più rifiutati.** Come nel registro, un argomento sconosciuto dà `isError`; la produzione lo ignorava.
- Mancano la pagina `/` del dominio MCP e le viste MCP Apps (`ui://parliamentrag/...`).

## Il giorno del cambio

1. Variabili d'ambiente del servizio API:
   - `FASCICOLI_URL`: l'indirizzo del backend di Fascicoli raggiungibile dall'API (in produzione `https://api-production-a731.up.railway.app`), più `FASCICOLI_API_KEY` se il backend la chiede;
   - `FASCICOLI_TIMEOUT` (predefinito 120 secondi);
   - `API_PROXY=1` dietro Cloudflare o Railway, perché il limite per IP legga `X-Forwarded-For`;
   - `MCP_STRUMENTI_INTERNI` non impostata.
2. Prova sul nuovo host prima del DNS (sostituisci `HOST`):

   ```sh
   U=https://HOST/mcp
   curl -si $U -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}'
   curl -s $U -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
   for a in 'list_sessions|{"limit":1}' 'get_session_votes|{"session_id":"leg19_sed734"}' \
            'get_vote_details|{"vote_id":"camera_leg19_sed734_v001"}' 'get_voted_text|{"vote_id":"camera_leg19_sed734_v001"}' \
            'get_debate|{"debate_id":"leg19_sed736_tit00040"}' 'get_vote_hemicycle|{"vote_id":"camera_leg19_sed734_v001"}' \
            'search_parliament|{"query":"salario minimo","max_results":3}' \
            'verify_answer|{"answer":"Ricciardi: «Chiedo di illustrare l interpellanza».","question":"farmaci"}'; do
     curl -s $U -H 'Content-Type: application/json' -H 'Accept: application/json' \
       -d "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"${a%%|*}\",\"arguments\":${a#*|}}}" | head -c 300; echo
   done
   curl -so /dev/null -w '%{http_code}\n' https://HOST/icon.png
   ```

   Ogni chiamata deve avere `"isError": false`. verify_answer deve avere `outcome.groups` diverso da `na`: se vale `na`, l'API non raggiunge Fascicoli.
3. Su Cloudflare punta `mcp.parliamentrag.it` al servizio v3. Il percorso resta `/mcp`.
4. Ripeti il punto 2 con `HOST=mcp.parliamentrag.it`, poi apri una conversazione su claude.ai con il connettore e chiedi un voto e una citazione.
5. Per tornare indietro, rimetti il record DNS di prima: il vecchio servizio non cambia.
