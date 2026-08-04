# Dossier submission — Anthropic Connectors Directory

Portale: dalle impostazioni del tuo account claude.ai (sezione connettori /
submission portal). Campi pronti da incollare. Requisiti tecnici già
soddisfatti nel server: transport Streamable HTTP, tool annotati read-only,
nomi < 64 caratteri, hosting di produzione.

## Server basics

- **Name**: ParliamentRAG
- **Tagline**: Italian Chamber of Deputies open data for your AI assistant
- **Server URL**: `https://mcp.parliamentrag.it/mcp`
- **Connector type**: Remote MCP server
- **Transport**: Streamable HTTP
- **Auth type**: None (open, read-only public data)
- **Read/write**: read-only (all 6 tools annotated `readOnlyHint: true`)

## Primary use cases (2-3 frasi)

ParliamentRAG gives assistants direct access to the open data of the
Italian Chamber of Deputies (19th legislature), as published in the official records: floor speeches, roll-call
votes with per-deputy outcomes, and the exact text of voted amendments.
Journalists, researchers and citizens can ask questions like "how did PD
deputies vote on bill 2961?" and get answers grounded in the official
stenographic record instead of model memory. Every result links back to the
official source on camera.it.

## Tools

| Tool | Title | Read-only |
|---|---|---|
| `search_parliament` | Search parliamentary records | ✓ |
| `list_sessions` | List plenary sittings | ✓ |
| `get_session_votes` | List roll-call votes of a sitting | ✓ |
| `get_vote_details` | Get roll-call vote details | ✓ |
| `get_voted_text` | Get the voted amendment/article text | ✓ |
| `get_debate` | Get debate details | ✓ |

Tutti annotati con `readOnlyHint: true`, `destructiveHint: false`,
`idempotentHint: true`, `openWorldHint: true`. Nessun tool di scrittura.

## Link richiesti

- **Documentation URL**: https://github.com/Emeierkeio/ParliamentRAG/tree/main/mcp
- **Privacy policy URL**: https://www.parliamentrag.it/privacy
- **Support channel**: https://github.com/Emeierkeio/ParliamentRAG/issues
- **Website**: https://www.parliamentrag.it
- **Icon**: `frontend/src/app/icon.svg` (32×32) o `apple-icon.png` dal repo

## Note per il form

- Nessun OAuth callback: il connettore è senza autenticazione (dati pubblici
  in sola lettura). Se il form chiede l'auth, selezionare "None".
- Test account: non necessario (nessun login).
- Rate limit lato server: 60 richieste/minuto per IP.
- I contenuti restituiti sono in italiano (dati parlamentari ufficiali).

## Stato ecosistema OpenAI

ChatGPT accetta il connettore da subito in modalità sviluppatore (nessuna
review). La distribuzione tipo-directory passa dall'Apps SDK / app review di
OpenAI, pensata per app interattive più che per connettori dati puri: da
rivalutare quando apriranno le submission generali.
