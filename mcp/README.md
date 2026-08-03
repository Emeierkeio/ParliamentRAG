# ParliamentRAG MCP server

Porta i dati della Camera dei Deputati (XIX legislatura) dentro Claude e
qualunque client [MCP](https://modelcontextprotocol.io): ricerca ibrida su
interventi e atti, sedute con riassunti, votazioni con i voti dei singoli
deputati, testo esatto degli emendamenti votati.

Il server interroga l'API pubblica di [parliamentrag.it](https://www.parliamentrag.it)
in sola lettura: nessuna credenziale, nessun database locale.

## Strumenti

| Tool | Cosa fa |
|---|---|
| `search_parliament` | Ricerca ibrida (full-text + semantica) su interventi in Aula e atti parlamentari |
| `list_sessions` | Sedute con riassunto AI, dibattiti e conteggi, paginate |
| `get_session_votes` | Tutte le votazioni di una seduta |
| `get_vote_details` | Dettaglio votazione: aggregati, breakdown per gruppo, atto collegato (scheda + PDF), voti individuali filtrabili per deputato/gruppo, flag scrutinio segreto |
| `get_voted_text` | Testo integrale dell'emendamento/articolo votato, dall'Allegato A del resoconto |
| `get_debate` | Dettaglio dibattito: riassunto, atti discussi, oratori |

## Installazione

Serve [uv](https://docs.astral.sh/uv/) (le dipendenze sono dichiarate inline
nello script, non si installa nulla).

**Claude Code:**

```bash
claude mcp add parliamentrag -- uv run /percorso/assoluto/ParliamentRAG/mcp/server.py
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "parliamentrag": {
      "command": "uv",
      "args": ["run", "/percorso/assoluto/ParliamentRAG/mcp/server.py"]
    }
  }
}
```

**Da GitHub, senza clonare il repo:**

```bash
claude mcp add parliamentrag -- uvx --from "git+https://github.com/Emeierkeio/ParliamentRAG.git#subdirectory=mcp" parliamentrag-mcp
```

## Note

- I contenuti (interventi, riassunti, testi) sono in italiano.
- Il backend può essere in sleep: la prima chiamata a volte impiega 30-60
  secondi; il server ritenta da solo una volta.
- Endpoint override per sviluppo locale: `PARLIAMENTRAG_API=http://localhost:8000/api`.

## Esempi di domande (in Claude)

- «Come hanno votato i deputati del PD sul voto finale del DDL 2961?»
- «Cosa si è detto in Aula sull'intelligenza artificiale a luglio 2026?»
- «Leggimi il testo dell'emendamento 6.21 della seduta 700 e dimmi chi l'ha respinto.»
