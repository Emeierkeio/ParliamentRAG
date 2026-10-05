# Server MCP di ParliamentRAG

Con il server MCP il tuo assistente AI legge i dati della Camera dei Deputati, XIX legislatura: cerca
negli interventi e negli atti, apre le sedute con il riassunto, mostra come ha votato ogni deputato e
riporta il testo esatto degli emendamenti votati. Funziona con Claude e con qualunque client
[MCP](https://modelcontextprotocol.io).

Il server legge l'API di ParliamentRAG e non scrive nulla. Non ti servono credenziali né un database.

## Endpoint remoto

Aggiungi `https://mcp.parliamentrag.it/mcp` ai connettori del tuo assistente. Non installi niente.

- **claude.ai**: Settings → Connectors → Add custom connector, poi incolla l'URL.
- **ChatGPT**: Impostazioni → Connettori, in modalità sviluppatore, poi aggiungi l'URL.

## Strumenti

| Tool | Cosa fa |
|---|---|
| `search_parliament` | Ricerca full-text e semantica su interventi in Aula e atti parlamentari |
| `list_sessions` | Sedute con riassunto, dibattiti e conteggi, a pagine |
| `get_session_votes` | Le votazioni di una seduta |
| `get_vote_details` | Una votazione: totali, voti per gruppo, atto collegato con scheda e PDF, voto di ogni deputato, scrutinio segreto |
| `get_voted_text` | Il testo dell'emendamento o dell'articolo votato, dall'Allegato A del resoconto |
| `get_debate` | Un dibattito: riassunto, atti discussi, oratori |
| `get_vote_hemicycle` | L'emiciclo della votazione come immagine, un punto per deputato colorato per voto |

## Installazione in locale

Ti serve [uv](https://docs.astral.sh/uv/). Il codice del server sta in
[parliamentrag-iswc/mcp](https://github.com/Emeierkeio/parliamentrag-iswc/tree/main/mcp) e uv lo scarica
da lì.

**Claude Code**

```bash
claude mcp add parliamentrag -- uvx --from "git+https://github.com/Emeierkeio/parliamentrag-iswc.git#subdirectory=mcp" parliamentrag-mcp
```

**Claude Desktop, Cursor, VS Code, Gemini CLI, Windsurf**

Copia questo blocco nel file di configurazione del client (`claude_desktop_config.json`,
`~/.cursor/mcp.json`, `.vscode/mcp.json`, `~/.gemini/settings.json`):

```json
{
  "mcpServers": {
    "parliamentrag": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Emeierkeio/parliamentrag-iswc.git#subdirectory=mcp", "parliamentrag-mcp"]
    }
  }
}
```

**Senza uv**

```bash
pip install "parliamentrag-mcp @ git+https://github.com/Emeierkeio/parliamentrag-iswc.git#subdirectory=mcp"
claude mcp add parliamentrag -- parliamentrag-mcp
```

## Da sapere

- Interventi, riassunti e testi sono in italiano. L'assistente ti risponde nella tua lingua e lascia le
  citazioni in originale.
- Se il backend dorme, la prima chiamata può durare 30-60 secondi. Il server riprova una volta da solo.
- Per puntare a un backend locale imposta `PARLIAMENTRAG_API=http://localhost:8000/api`.

## Domande da provare

- «Come hanno votato i deputati del PD sul voto finale del DDL 2961?»
- «Cosa si è detto in Aula sull'intelligenza artificiale a luglio 2026?»
- «Leggimi il testo dell'emendamento 6.21 della seduta 700 e dimmi chi l'ha respinto.»

<br>

<sub>Dati: Camera dei Deputati, <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.it">CC BY-SA 4.0</a>. Progetto indipendente, non affiliato alla Camera dei Deputati.</sub>
