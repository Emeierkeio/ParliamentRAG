# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2.0,<2", "httpx>=0.27", "pillow>=10"]
# ///
"""
ParliamentRAG MCP server — Italian Chamber of Deputies data as Claude tools.

Exposes the read-only public API of www.parliamentrag.it: semantic search over
floor speeches and parliamentary acts, sitting-by-sitting proceedings, roll-call
votes with per-deputy outcomes, and the exact text of voted amendments/articles.
All data comes from official sources (dati.camera.it, stenographic records) for
the 19th legislature. Contents are in Italian.

Run:  uv run mcp/server.py          (stdio transport, no install needed)
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import Image as FastMCPImage
from mcp.types import ToolAnnotations

API_BASE = os.environ.get("PARLIAMENTRAG_API", "https://www.parliamentrag.it/api")

# Icona del server (mostrata dai client accanto al nome del connettore).
# Il tipo Icon esiste solo dalle versioni recenti dell'SDK: senza, si va
# avanti senza logo invece di crashare sui client con mcp vecchio.
try:
    from mcp.types import Icon

    _ICONS = [
        Icon(
            src="https://mcp.parliamentrag.it/icon.png",
            mimeType="image/png",
            sizes=["512x512"],
        )
    ]
except ImportError:
    _ICONS = None

mcp = FastMCP(
    "ParliamentRAG",
    website_url="https://www.parliamentrag.it",
    instructions=(
        "Tools over official Italian Chamber of Deputies data (19th legislature, "
        "via parliamentrag.it). Data is in Italian. Every speech and vote links "
        "back to the official record: cite those links when reporting facts. "
        "When you report the results of a specific roll-call vote, also call "
        "get_vote_hemicycle for that vote_id so the user sees the seating chart "
        "alongside the numbers (skip it for secret ballots). "
        "Always answer in the language of the conversation (English, French, "
        "Italian, ...): translate summaries and labels, but keep verbatim "
        "quotes in the original Italian. "
        "The backend may cold-start: if a call times out, retry once."
    ),
    **({"icons": _ICONS} if _ICONS else {}),
)

# Il backend Railway va in sleep: la prima chiamata può metterci decine di
# secondi. Timeout largo + un retry sono parte del contratto, non paranoia.
_TIMEOUT = httpx.Timeout(90.0, connect=30.0)


def _ro(title: str) -> ToolAnnotations:
    """Annotazioni standard: tutti i tool sono letture idempotenti di dati
    pubblici (richiesto dalla directory dei connettori)."""
    return ToolAnnotations(
        title=title,
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )


async def _get(path: str, params: dict | None = None) -> Any:
    import asyncio

    params = {k: v for k, v in (params or {}).items() if v is not None}
    # UA dedicato: rende l'uso del connettore misurabile nei log del backend.
    headers = {"User-Agent": "parliamentrag-mcp/0.1.0"}
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, headers=headers
    ) as client:
        for attempt in range(1, 4):
            try:
                resp = await client.get(f"{API_BASE}{path}", params=params)
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == 3:
                    raise
                await asyncio.sleep(2 * attempt)
    return None  # unreachable


def _trim(text: Optional[str], limit: int = 600) -> Optional[str]:
    if text and len(text) > limit:
        return text[:limit].rsplit(" ", 1)[0] + "…"
    return text


@mcp.tool(annotations=_ro("Search parliamentary records"))
async def search_parliament(
    query: str,
    doc_type: str = "all",
    group: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 10,
) -> dict:
    """Search Italian parliamentary records: floor speeches and parliamentary
    acts (bills, motions, written questions) of the Chamber of Deputies,
    19th legislature (Oct 2022 - today).

    Uses hybrid search (full-text + semantic), so Italian queries work best
    ("salario minimo", "intelligenza artificiale", company names, people).

    Args:
        query: Search query, ideally in Italian.
        doc_type: "all", "speech" (floor speeches) or "act" (parliamentary acts).
        group: Optional parliamentary group name filter (e.g. "MOVIMENTO 5 STELLE").
        start_date: Optional YYYY-MM-DD lower bound.
        end_date: Optional YYYY-MM-DD upper bound.
        max_results: How many results to return (1-30).
    """
    data = await _get(
        "/search/results",
        {
            "q": query,
            "search_type": "hybrid",
            "doc_type": doc_type,
            "group": group,
            "start_date": start_date,
            "end_date": end_date,
            "page_size": max(1, min(max_results, 30)),
        },
    )
    results = []
    for r in data.get("results", [])[: max(1, min(max_results, 30))]:
        results.append({
            k: (_trim(v) if isinstance(v, str) else v)
            for k, v in r.items()
            if v not in (None, "") and k not in ("embedding",)
        })
    return {"total": data.get("total"), "results": results}


@mcp.tool(annotations=_ro("List plenary sittings"))
async def list_sessions(
    limit: int = 10,
    before: Optional[str] = None,
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    """List plenary sittings of the Chamber of Deputies, most recent first,
    each with an AI recap (Italian), its debates and counts of speeches/votes.

    Args:
        limit: Sittings per page (1-30).
        before: ISO date cursor for pagination (returns sittings before it).
        search: Optional keyword filter on debate titles/recaps.
        from_date / to_date: Optional YYYY-MM-DD bounds.
    """
    data = await _get(
        "/timeline",
        {
            "limit": max(1, min(limit, 30)),
            "before": before,
            "search": search,
            "from_date": from_date,
            "to_date": to_date,
        },
    )
    sessions = []
    for s in data.get("sessions", []):
        sessions.append({
            "id": s["id"],
            "number": s["number"],
            "date": s["date"],
            "recap": _trim(s.get("recap"), 800),
            "vote_count": s.get("vote_count"),
            "speech_count": s.get("speech_count"),
            "debates": [
                {"id": d["id"], "title": _trim(d["title"], 200)}
                for d in s.get("debates", [])
            ],
        })
    return {
        "sessions": sessions,
        "next_cursor": data.get("next_cursor"),
        "has_more": data.get("has_more"),
    }


@mcp.tool(annotations=_ro("List roll-call votes of a sitting"))
async def get_session_votes(session_id: str) -> dict:
    """List every roll-call vote of one sitting: subject, description, kind
    (final vote flag), outcome and aggregate counts.

    Args:
        session_id: Session id from list_sessions (e.g. "leg19_sed700").
    """
    votes = await _get(f"/timeline/sessions/{session_id}/votes")
    return {
        "session_id": session_id,
        "votes": [
            {
                "id": v["id"],
                "number": v["number"],
                "subject": v.get("subject"),
                "description": v.get("description"),
                "final_vote": v.get("final_vote"),
                "outcome": v.get("outcome"),
                "in_favor": v.get("in_favor"),
                "against": v.get("against"),
                "abstained": v.get("abstained"),
            }
            for v in votes
        ],
    }


@mcp.tool(annotations=_ro("Get roll-call vote details"))
async def get_vote_details(
    vote_id: str,
    include_individual_votes: bool = False,
    deputy: Optional[str] = None,
    group: Optional[str] = None,
) -> dict:
    """Full detail of one roll-call vote: aggregates, per-group breakdown,
    linked act (with official page and full-text PDF), secret-ballot flag,
    and optionally the ~400 individual per-deputy votes.

    After presenting these results, call get_vote_hemicycle with the same
    vote_id to show the seating chart as well (unless the ballot was secret).

    In secret ballots individual expressions are not public (only abstentions
    are on record) — the "secret_vote" flag tells you when that is the case.

    Args:
        vote_id: Vote id from get_session_votes.
        include_individual_votes: Return the full per-deputy list (large).
        deputy: Return only individual votes of deputies whose name contains
            this string (case-insensitive). Overrides include_individual_votes.
        group: Return only individual votes of this parliamentary group
            (substring match). Overrides include_individual_votes.
    """
    d = await _get(f"/timeline/votes/{vote_id}")
    out = {
        "id": d["id"],
        "subject": d.get("subject"),
        "description": d.get("description"),
        "outcome": d.get("outcome"),
        "secret_vote": d.get("secret_vote"),
        "in_favor": d.get("in_favor"),
        "against": d.get("against"),
        "abstained": d.get("abstained"),
        "present": d.get("present"),
        "majority": d.get("majority"),
        "acts": d.get("acts"),
        "breakdown_by_group": d.get("breakdown"),
    }
    participants = d.get("participants", [])
    if deputy or group:
        needle_d = (deputy or "").lower()
        needle_g = (group or "").lower()
        filtered = [
            p for p in participants
            if (not needle_d or needle_d in f"{p['first_name']} {p['last_name']}".lower())
            and (not needle_g or needle_g in (p.get("party") or "").lower())
        ]
        out["individual_votes"] = filtered
    elif include_individual_votes:
        out["individual_votes"] = participants
    else:
        out["individual_votes_available"] = len(participants)
    return out


@mcp.tool(annotations=_ro("Get the voted amendment/article text"))
async def get_voted_text(vote_id: str) -> dict:
    """Exact full text of the amendment or article a roll call voted on,
    extracted from the official sitting minutes (Allegato A).

    Only works for votes on amendments and articles; returns a clear message
    for other vote kinds (final votes, agenda items, procedural votes).

    Args:
        vote_id: Vote id from get_session_votes.
    """
    try:
        d = await _get(f"/timeline/votes/{vote_id}/act-text")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return {
                "available": False,
                "reason": "No extractable text: this vote is not on an "
                          "amendment/article, or the text was not published.",
            }
        raise
    return {"available": True, "paragraphs": d["paragraphs"], "source_url": d["source_url"]}


@mcp.tool(annotations=_ro("Get debate details"))
async def get_debate(debate_id: str) -> dict:
    """Detail of one debate: AI recap (Italian), discussed acts, phases and
    the list of speakers with their groups and speech counts.

    Args:
        debate_id: Debate id from list_sessions.
    """
    d = await _get(f"/timeline/debates/{debate_id}")
    return {
        "id": d["id"],
        "title": d.get("title"),
        "recap": _trim(d.get("recap"), 1200),
        "acts": d.get("acts"),
        "phases": [
            {"title": p["title"], "speech_count": p["speech_count"]}
            for p in d.get("phases", [])
        ],
        "speakers": [
            {
                "name": f"{s['first_name']} {s['last_name']}",
                "party": s.get("party"),
                "role": s.get("speaking_role"),
                "government_member": s.get("is_government_member"),
                "speech_count": s.get("speech_count"),
            }
            for s in d.get("speakers", [])
        ],
        "votes": [
            {
                "id": v["id"],
                "subject": v.get("subject"),
                "description": v.get("description"),
                "outcome": v.get("outcome"),
            }
            for v in d.get("votes", [])
        ],
    }



@mcp.tool(annotations=_ro("Render vote hemicycle image"))
async def get_vote_hemicycle(vote_id: str) -> FastMCPImage:
    """Render the hemicycle chart of a roll-call vote as an image: one dot per
    deputy, coloured by outcome (green=in favour, red=against, amber=abstained,
    grey=absent), grouped by parliamentary group as in the ParliamentRAG UI.
    Dots show group totals, not the real seat of each deputy — the image says
    so in its caption.

    Use together with get_vote_details: this tool shows the picture, that one
    returns the numbers and names.

    Args:
        vote_id: Vote id from get_session_votes.
    """
    d = await _get(f"/timeline/votes/{vote_id}")
    if d.get("secret_vote"):
        raise ValueError(
            "Secret ballot: individual votes are not public, no hemicycle to draw "
            "(only abstentions are on record)."
        )
    participants = d.get("participants", [])
    has_data = any(p.get("outcome") in ("favor", "against") for p in participants)
    if not has_data:
        raise ValueError("No individual vote data available for this roll call.")
    title = (d.get("subject") or "Votazione") + (
        f" · {d['description']}" if d.get("description") and d.get("subject") in (None, "Votazione", "Votazione finale") else ""
    )
    sub = (f"Favorevoli {d.get('in_favor')} · Contrari {d.get('against')} · "
           f"Astenuti {d.get('abstained')} · voti individuali: {len(participants)}")
    png = _render_hemicycle_png(participants, title, sub)
    return FastMCPImage(data=png, format="png")


# Pagina umana sulla radice del dominio: chi apre l'URL nel browser (dal
# post o per curiosità) deve capire cos'è, non vedere un errore JSON-RPC.
# Pagina localizzata: la lingua si sceglie dall'Accept-Language del browser,
# stesse sei lingue del sito principale, fallback italiano.
_LANDING_TEMPLATE = """<!doctype html><html lang="§lang§"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ParliamentRAG MCP</title>
<link rel="icon" type="image/png" href="/icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&display=swap" rel="stylesheet">
<style>
:root{--bg:#fbfaf7;--fg:#1c2433;--primary:#1B3A5C;--muted:#6b7280;--border:#e8e5df;--display:'Fraunces',Georgia,serif}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:var(--bg);color:var(--fg);margin:0;min-height:100vh;display:flex;flex-direction:column}
a{color:var(--primary)}
header{border-bottom:2px solid var(--fg)}
.shell{max-width:1152px;margin:0 auto;padding:0 24px;width:100%}
.edition{display:flex;justify-content:space-between;gap:12px;padding:8px 0;font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border)}
.wordmark{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:20px 0;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--fg)}
.brand span{font-family:var(--display);font-size:1.7rem;font-weight:600;letter-spacing:-.02em}
.cta{background:var(--primary);color:#f4f1ea;padding:10px 16px;font-size:13px;letter-spacing:.02em;text-decoration:none}
.cta:hover{background:var(--fg)}
.band{display:block;border-top:1px solid var(--border);background:rgba(27,58,92,.05);text-decoration:none;text-align:center;padding:8px 16px;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:rgba(28,36,51,.6)}
.band b{font-family:var(--display);text-transform:none;letter-spacing:0;font-size:13px;color:var(--primary)}
main{max-width:1152px;margin:0 auto;padding:48px 24px 64px;width:100%;flex:1}
.intro{max-width:760px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px 64px;margin-top:8px}
@media(max-width:860px){.cols{grid-template-columns:1fr}}
h1{font-family:var(--display);font-size:2rem;font-weight:600;letter-spacing:-.02em;margin:0 0 12px}
h2{font-family:var(--display);font-size:1.2rem;font-weight:600;margin:36px 0 8px}
.cols h2{margin-top:28px}
p,li{font-size:1.0rem;line-height:1.6;color:#4b5563}li{margin:4px 0}
code{background:var(--primary);color:#f4f1ea;padding:3px 8px;border-radius:5px;font-size:.9rem}
li code{background:#edeae2;color:var(--fg)}
footer{border-top:1px solid var(--border);padding:36px 24px;font-size:12px;color:var(--muted)}
footer .row{max-width:1152px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px}
footer .brand span{font-family:var(--display);font-size:.95rem;font-weight:500}
footer nav{display:flex;flex-wrap:wrap;gap:8px 20px}
footer nav a{color:var(--muted);text-decoration:none;border-bottom:1px solid var(--border)}
footer nav a:hover{color:var(--fg);border-color:var(--fg)}
footer .credits{max-width:1152px;margin:20px auto 0;padding-top:16px;border-top:1px solid var(--border);line-height:1.6}
</style></head><body>
<header>
<div class="shell">
<div class="edition"><span>Server MCP</span><span>§institution§</span></div>
<div class="wordmark">
<a class="brand" href="https://www.parliamentrag.it"><img src="https://www.parliamentrag.it/logo-blue.svg" alt="" width="46" height="32"><span>ParliamentRAG</span></a>
<a class="cta" href="https://www.parliamentrag.it/home">§cta§ &rarr;</a>
</div>
</div>
<a class="band" href="https://iswc2026.semanticweb.org"><b>ISWC 2026</b> &nbsp;&middot;&nbsp; §iswc§</a>
</header>
<main>
<h1>ParliamentRAG MCP</h1>
<div class="intro">
<p>§intro§</p>
</div>
<div class="cols">
<section>
<h2>§caps_h§</h2>
<ul>
<li>§cap1§</li>
<li>§cap2§</li>
<li>§cap3§</li>
<li>§cap4§</li>
<li>§cap5§</li>
</ul>
<p>§example§</p>
<p>§source§</p>
</section>
<section>
<h2>§connect_h§</h2>
<p>§endpoint_line§</p>
<p><code>https://mcp.parliamentrag.it/mcp</code></p>
<ul>
<li><b>claude.ai</b>: §settings§ &rarr; §connectors§ &rarr; §add_custom§</li>
<li><b>ChatGPT</b>: §settings§ &rarr; §apps_conn§ (§dev_mode§) &rarr; §create§</li>
<li><b>Claude Code</b>: <code>claude mcp add -t http parliamentrag https://mcp.parliamentrag.it/mcp</code></li>
<li><b>Gemini CLI</b>: <code>gemini mcp add -t http parliamentrag https://mcp.parliamentrag.it/mcp</code></li>
<li><b>Perplexity</b> (§desktop_app§): §settings§ &rarr; §connectors§ &rarr; §add_conn§</li>
<li><b>Le Chat</b> (Mistral): §settings§ &rarr; §connectors§ &rarr; §add_mcp§</li>
<li><b>Cursor</b>: Settings &rarr; MCP &rarr; Add server, §with§ <code>"url"</code> = endpoint</li>
<li><b>VS Code</b> (Copilot): §in§ <code>.vscode/mcp.json</code>, §server_with§ <code>"type": "http"</code></li>
<li><b>Windsurf</b>: §in§ <code>mcp_config.json</code>, §server_with§ <code>"serverUrl"</code> = endpoint</li>
</ul>
</section>
</div>
</main>
<footer>
<div class="row">
<a class="brand" href="https://www.parliamentrag.it"><img src="https://www.parliamentrag.it/logo-blue.svg" alt="" width="26" height="18"><span>ParliamentRAG</span></a>
<nav>
<a href="https://github.com/Emeierkeio/ParliamentRAG">GitHub</a>
<a href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/Who_Speaks_Matters_ISWC2026-Camera_Ready_Draft.pdf">§paper_inuse§</a>
<a href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/Tritella_Pozzi_Palmonari_ISWC2026_Demo.pdf">§paper_demo§</a>
<a href="https://orkg.org/papers/R1909763">ORKG</a>
<a href="https://doi.org/10.5281/zenodo.21560331">Zenodo</a>
<a href="https://www.parliamentrag.it/data">§footer_data§</a>
<a href="https://www.parliamentrag.it/privacy">Privacy</a>
</nav>
</div>
<div class="credits">§thesis§ &middot; Prof. Matteo Palmonari &middot; Dott. Riccardo Pozzi &middot;
<a href="https://www.unimib.it/" style="color:inherit">Universit&agrave; di Milano-Bicocca</a></div>
</footer>
</body></html>"""

_MCP_URL_ANCHOR = '<a href="https://github.com/Emeierkeio/ParliamentRAG/tree/main/mcp">github.com/Emeierkeio/ParliamentRAG</a>'
_MCP_PROTO_ANCHOR = '<a href="https://modelcontextprotocol.io">Model Context Protocol</a>'
_DATI_ANCHOR = '<a href="https://dati.camera.it">dati.camera.it</a>'

_L10N: dict[str, dict[str, str]] = {
    "it": {
        "institution": "Camera dei Deputati &middot; XIX Legislatura",
        "cta": "Accedi alla consultazione",
        "iswc": "Accettato &middot; In-Use Track",
        "intro": f"Questo indirizzo è un server {_MCP_PROTO_ANCHOR}. Aperto nel browser "
                 "mostra solo questa pagina; aggiunto a un assistente AI gli dà accesso "
                 "ai dati ufficiali della Camera dei Deputati (XIX legislatura): votazioni "
                 "nominali, interventi in Aula, testi degli emendamenti votati. Sola "
                 "lettura, senza registrazione, gratuito.",
        "caps_h": "Cosa sa fare",
        "cap1": "Ricerca negli interventi in Aula e negli atti parlamentari",
        "cap2": "Sedute con riassunto, dibattiti e votazioni",
        "cap3": "Dettaglio di ogni voto nominale: aggregati, voti per gruppo e per singolo deputato",
        "cap4": "Testo esatto dell'emendamento o articolo votato, dall'Allegato A del resoconto",
        "cap5": "Grafico dell'emiciclo di un voto, come immagine nella chat",
        "example": "Esempio: &laquo;Come hanno votato i deputati del PD sul voto finale "
                   "del DDL 2961?&raquo;. La risposta arriva dai resoconti ufficiali, "
                   "con i numeri reali e i link alle fonti.",
        "source": f"I dati vengono da {_DATI_ANCHOR} e dai resoconti stenografici della "
                  "Camera. Progetto indipendente, non affiliato alla Camera dei Deputati. "
                  f"Istruzioni complete e codice: {_MCP_URL_ANCHOR}.",
        "connect_h": "Come collegarlo",
        "endpoint_line": "L'endpoint da aggiungere ai connettori del tuo assistente:",
        "settings": "Impostazioni", "connectors": "Connettori",
        "add_custom": "Aggiungi connettore personalizzato",
        "apps_conn": "App e connettori", "dev_mode": "modalità sviluppatore",
        "create": "Crea", "desktop_app": "app desktop",
        "add_conn": "Aggiungi connettore", "add_mcp": "Aggiungi connettore MCP",
        "with": "con", "in": "in", "server_with": "server con",
        "paper_inuse": "Paper di ricerca", "paper_demo": "Paper demo",
        "footer_data": "Dati aperti (RDF)",
        "thesis": "Un progetto di Mirko Tritella",
    },
    "en": {
        "institution": "Italian Chamber of Deputies &middot; 19th Legislature",
        "cta": "Start consulting",
        "iswc": "Accepted &middot; In-Use Track",
        "intro": f"This address is a {_MCP_PROTO_ANCHOR} server. Opened in a browser it "
                 "only shows this page; added to an AI assistant it gives it access to "
                 "the official data of the Italian Chamber of Deputies (19th "
                 "legislature): roll-call votes, floor speeches, the texts of voted "
                 "amendments. Read-only, no sign-up, free.",
        "caps_h": "What it can do",
        "cap1": "Search across floor speeches and parliamentary acts",
        "cap2": "Sittings with summary, debates and votes",
        "cap3": "Detail of every roll-call vote: totals, votes by group and by individual deputy",
        "cap4": "The exact text of the voted amendment or article, from annex A of the official report",
        "cap5": "The hemicycle chart of a vote, as an image in the chat",
        "example": "Example: &ldquo;How did PD deputies vote on the final vote on bill "
                   "2961?&rdquo;. The answer comes from the official records, with the "
                   "real numbers and links to the sources.",
        "source": f"The data comes from {_DATI_ANCHOR} and the Chamber's verbatim "
                  "reports. Independent project, not affiliated with the Chamber of "
                  f"Deputies. Full instructions and code: {_MCP_URL_ANCHOR}.",
        "connect_h": "How to connect it",
        "endpoint_line": "The endpoint to add to your assistant's connectors:",
        "settings": "Settings", "connectors": "Connectors",
        "add_custom": "Add custom connector",
        "apps_conn": "Apps &amp; connectors", "dev_mode": "developer mode",
        "create": "Create", "desktop_app": "desktop app",
        "add_conn": "Add connector", "add_mcp": "Add MCP connector",
        "with": "with", "in": "in", "server_with": "server with",
        "paper_inuse": "Research paper", "paper_demo": "Demo paper",
        "footer_data": "Open data (RDF)",
        "thesis": "A project by Mirko Tritella",
    },
    "es": {
        "institution": "Cámara de Diputados de Italia &middot; XIX Legislatura",
        "cta": "Acceda a la consulta",
        "iswc": "Aceptado &middot; In-Use Track",
        "intro": f"Esta dirección es un servidor {_MCP_PROTO_ANCHOR}. Abierta en el "
                 "navegador solo muestra esta página; añadida a un asistente de IA le "
                 "da acceso a los datos oficiales de la Cámara de Diputados de Italia "
                 "(XIX legislatura): votaciones nominales, intervenciones en el pleno, "
                 "textos de las enmiendas votadas. Solo lectura, sin registro, gratuito.",
        "caps_h": "Qué sabe hacer",
        "cap1": "Búsqueda en las intervenciones del pleno y en los actos parlamentarios",
        "cap2": "Sesiones con resumen, debates y votaciones",
        "cap3": "Detalle de cada votación nominal: totales, votos por grupo y por diputado",
        "cap4": "El texto exacto de la enmienda o del artículo votado, del anexo A del acta",
        "cap5": "El gráfico del hemiciclo de una votación, como imagen en el chat",
        "example": "Ejemplo: &laquo;¿Cómo votaron los diputados del PD en la votación "
                   "final del proyecto de ley 2961?&raquo;. La respuesta llega de las "
                   "actas oficiales, con los números reales y los enlaces a las fuentes.",
        "source": f"Los datos provienen de {_DATI_ANCHOR} y de las actas taquigráficas "
                  "de la Cámara. Proyecto independiente, no afiliado a la Cámara de "
                  f"Diputados. Instrucciones completas y código: {_MCP_URL_ANCHOR}.",
        "connect_h": "Cómo conectarlo",
        "endpoint_line": "El endpoint que hay que añadir a los conectores de tu asistente:",
        "settings": "Configuración", "connectors": "Conectores",
        "add_custom": "Añadir conector personalizado",
        "apps_conn": "Apps y conectores", "dev_mode": "modo desarrollador",
        "create": "Crear", "desktop_app": "app de escritorio",
        "add_conn": "Añadir conector", "add_mcp": "Añadir conector MCP",
        "with": "con", "in": "en", "server_with": "servidor con",
        "paper_inuse": "Artículo de investigación", "paper_demo": "Artículo demo",
        "footer_data": "Datos abiertos (RDF)",
        "thesis": "Un proyecto de Mirko Tritella",
    },
    "fr": {
        "institution": "Chambre des députés italienne &middot; XIXe législature",
        "cta": "Accéder à la consultation",
        "iswc": "Accepté &middot; In-Use Track",
        "intro": f"Cette adresse est un serveur {_MCP_PROTO_ANCHOR}. Ouverte dans un "
                 "navigateur, elle n'affiche que cette page ; ajoutée à un assistant "
                 "IA, elle lui donne accès aux données officielles de la Chambre des "
                 "députés italienne (XIXe législature) : votes nominaux, interventions "
                 "en séance, textes des amendements votés. Lecture seule, sans "
                 "inscription, gratuit.",
        "caps_h": "Ce qu'il sait faire",
        "cap1": "Recherche dans les interventions en séance et les actes parlementaires",
        "cap2": "Séances avec résumé, débats et votes",
        "cap3": "Détail de chaque vote nominal : totaux, votes par groupe et par député",
        "cap4": "Le texte exact de l'amendement ou de l'article voté, tiré de l'annexe A du compte rendu",
        "cap5": "Le graphique de l'hémicycle d'un vote, en image dans la conversation",
        "example": "Exemple : &laquo; Comment les députés du PD ont-ils voté lors du "
                   "vote final sur le projet de loi 2961 ? &raquo;. La réponse vient des "
                   "comptes rendus officiels, avec les vrais chiffres et les liens vers "
                   "les sources.",
        "source": f"Les données proviennent de {_DATI_ANCHOR} et des comptes rendus "
                  "sténographiques de la Chambre. Projet indépendant, sans lien avec la "
                  f"Chambre des députés. Instructions complètes et code : {_MCP_URL_ANCHOR}.",
        "connect_h": "Comment le connecter",
        "endpoint_line": "L'endpoint à ajouter aux connecteurs de votre assistant :",
        "settings": "Paramètres", "connectors": "Connecteurs",
        "add_custom": "Ajouter un connecteur personnalisé",
        "apps_conn": "Applications et connecteurs", "dev_mode": "mode développeur",
        "create": "Créer", "desktop_app": "application de bureau",
        "add_conn": "Ajouter un connecteur", "add_mcp": "Ajouter un connecteur MCP",
        "with": "avec", "in": "dans", "server_with": "serveur avec",
        "paper_inuse": "Article de recherche", "paper_demo": "Article démo",
        "footer_data": "Données ouvertes (RDF)",
        "thesis": "Un projet de Mirko Tritella",
    },
    "de": {
        "institution": "Italienische Abgeordnetenkammer &middot; XIX. Legislaturperiode",
        "cta": "Zur Konsultation",
        "iswc": "Angenommen &middot; In-Use Track",
        "intro": f"Diese Adresse ist ein {_MCP_PROTO_ANCHOR}-Server. Im Browser zeigt "
                 "sie nur diese Seite; einem KI-Assistenten hinzugefügt, gibt sie ihm "
                 "Zugriff auf die offiziellen Daten der italienischen "
                 "Abgeordnetenkammer (XIX. Legislaturperiode): namentliche "
                 "Abstimmungen, Redebeiträge im Plenum, Texte der abgestimmten "
                 "Änderungsanträge. Nur Lesezugriff, ohne Registrierung, kostenlos.",
        "caps_h": "Was er kann",
        "cap1": "Suche in Plenarreden und parlamentarischen Akten",
        "cap2": "Sitzungen mit Zusammenfassung, Debatten und Abstimmungen",
        "cap3": "Detail jeder namentlichen Abstimmung: Summen, Stimmen nach Fraktion und einzelnen Abgeordneten",
        "cap4": "Der genaue Text des abgestimmten Änderungsantrags oder Artikels, aus Anlage A des Protokolls",
        "cap5": "Die Halbkreis-Grafik einer Abstimmung, als Bild im Chat",
        "example": "Beispiel: &bdquo;Wie haben die PD-Abgeordneten bei der "
                   "Schlussabstimmung über Gesetzentwurf 2961 gestimmt?&ldquo;. Die Antwort kommt aus den "
                   "offiziellen Protokollen, mit den echten Zahlen und Links zu den Quellen.",
        "source": f"Die Daten stammen von {_DATI_ANCHOR} und aus den stenografischen "
                  "Protokollen der Kammer. Unabhängiges Projekt, nicht mit der "
                  "Abgeordnetenkammer verbunden. Vollständige Anleitung und Code: "
                  f"{_MCP_URL_ANCHOR}.",
        "connect_h": "So wird er verbunden",
        "endpoint_line": "Der Endpoint für die Konnektoren deines Assistenten:",
        "settings": "Einstellungen", "connectors": "Konnektoren",
        "add_custom": "Eigenen Konnektor hinzufügen",
        "apps_conn": "Apps &amp; Konnektoren", "dev_mode": "Entwicklermodus",
        "create": "Erstellen", "desktop_app": "Desktop-App",
        "add_conn": "Konnektor hinzufügen", "add_mcp": "MCP-Konnektor hinzufügen",
        "with": "mit", "in": "in", "server_with": "Server mit",
        "paper_inuse": "Forschungsartikel", "paper_demo": "Demo-Artikel",
        "footer_data": "Offene Daten (RDF)",
        "thesis": "Ein Projekt von Mirko Tritella",
    },
    "pt": {
        "institution": "Câmara dos Deputados de Itália &middot; XIX Legislatura",
        "cta": "Aceder à consulta",
        "iswc": "Aceito &middot; In-Use Track",
        "intro": f"Este endereço é um servidor {_MCP_PROTO_ANCHOR}. Aberto no navegador "
                 "mostra apenas esta página; adicionado a um assistente de IA, dá-lhe "
                 "acesso aos dados oficiais da Câmara dos Deputados de Itália (XIX "
                 "legislatura): votações nominais, intervenções no plenário, textos "
                 "das emendas votadas. Somente leitura, sem registo, gratuito.",
        "caps_h": "O que ele faz",
        "cap1": "Pesquisa nas intervenções do plenário e nos atos parlamentares",
        "cap2": "Sessões com resumo, debates e votações",
        "cap3": "Detalhe de cada votação nominal: totais, votos por grupo e por deputado",
        "cap4": "O texto exato da emenda ou do artigo votado, do anexo A da ata",
        "cap5": "O gráfico do hemiciclo de uma votação, como imagem no chat",
        "example": "Exemplo: &laquo;Como votaram os deputados do PD na votação final "
                   "do projeto de lei 2961?&raquo;. A resposta vem das atas oficiais, "
                   "com os números reais e as ligações às fontes.",
        "source": f"Os dados vêm de {_DATI_ANCHOR} e das atas estenográficas da "
                  "Câmara. Projeto independente, não afiliado à Câmara dos Deputados. "
                  f"Instruções completas e código: {_MCP_URL_ANCHOR}.",
        "connect_h": "Como conectá-lo",
        "endpoint_line": "O endpoint a adicionar aos conectores do teu assistente:",
        "settings": "Definições", "connectors": "Conectores",
        "add_custom": "Adicionar conector personalizado",
        "apps_conn": "Apps e conectores", "dev_mode": "modo de programador",
        "create": "Criar", "desktop_app": "app de desktop",
        "add_conn": "Adicionar conector", "add_mcp": "Adicionar conector MCP",
        "with": "com", "in": "em", "server_with": "servidor com",
        "paper_inuse": "Artigo de pesquisa", "paper_demo": "Artigo demo",
        "footer_data": "Dados abertos (RDF)",
        "thesis": "Um projeto de Mirko Tritella",
    },
}


def _pick_lang(accept_language: str) -> str:
    """Prima lingua supportata nell'Accept-Language, per qualità decrescente."""
    ranked = []
    for i, part in enumerate(accept_language.split(",")):
        code = part.split(";")[0].strip().lower()[:2]
        q = 1.0
        if ";q=" in part:
            try:
                q = float(part.split(";q=")[1].split(",")[0])
            except ValueError:
                q = 0.0
        ranked.append((-q, i, code))
    for _, _, code in sorted(ranked):
        if code in _L10N:
            return code
    return "it"


def _render_landing(accept_language: str) -> str:
    lang = _pick_lang(accept_language)
    html = _LANDING_TEMPLATE.replace("§lang§", lang)
    for key, value in _L10N[lang].items():
        html = html.replace(f"§{key}§", value)
    return html



# ---------------------------------------------------------------------------
# Emiciclo come immagine (stessa disposizione della grafica del sito)
# ---------------------------------------------------------------------------

_WEDGE_ORDER = [
    ("VERDI E SINISTRA", 0), ("PARTITO DEMOCRATICO", 1), ("MOVIMENTO 5 STELLE", 2),
    ("AZIONE", 3), ("ITALIA VIVA", 4), ("MISTO", 5), ("NOI MODERATI", 6),
    ("FORZA ITALIA", 7), ("LEGA", 8), ("FRATELLI D'ITALIA", 9),
]

_OUTCOME_COLOR = {
    "favor": (5, 150, 105),      # verde
    "against": (220, 38, 38),    # rosso
    "abstain": (245, 158, 11),   # ambra
    "absent": (200, 196, 186),   # grigio caldo
}
_OUTCOME_ORDER = {"favor": 0, "against": 1, "abstain": 2, "absent": 3}


def _wedge_rank(party: str | None) -> float:
    up = (party or "").upper()
    if not up:
        return 5.5
    if up != (party or "") and "MISTO" not in up:
        pass
    if "MISTO" in up or (party and party != party.upper()):
        # componenti del Misto (nomi in minuscolo/misto) stanno col Misto
        return 5.0
    for needle, rank in _WEDGE_ORDER:
        if needle in up:
            return float(rank)
    return 5.5


def _render_hemicycle_png(participants: list[dict], title: str, subtitle: str) -> bytes:
    import io as _io
    import math

    from PIL import Image as PILImage, ImageDraw, ImageFont

    W, H = 1400, 880
    CX, CY = W // 2, 700
    INNER, OUTER = 220, 500

    ordered = sorted(participants, key=lambda p: (
        _wedge_rank(p.get("party")),
        (p.get("party") or "").upper(),
        _OUTCOME_ORDER.get(p.get("outcome"), 3),
        p.get("last_name", ""),
    ))
    total = len(ordered)
    if total == 0:
        raise ValueError("No individual votes to draw")

    rows = max(4, round(total / 50))
    row_gap = (OUTER - INNER) / (rows - 1)
    radii = [INNER + i * row_gap for i in range(rows)]
    radii_sum = sum(radii)
    exact = [total * r / radii_sum for r in radii]
    counts = [int(v) for v in exact]
    rest = total - sum(counts)
    for _, i in sorted(((v - int(v), i) for i, v in enumerate(exact)), reverse=True)[:rest]:
        counts[i] += 1

    seats = []
    for row, (r, n) in enumerate(zip(radii, counts)):
        for k in range(n):
            ang = math.pi / 2 if n == 1 else math.pi - (math.pi * k) / (n - 1)
            seats.append((CX + r * math.cos(ang), CY - r * math.sin(ang), ang, row))
    seats.sort(key=lambda s: (-s[2], s[3]))

    inner_seats = counts[0] or 1
    arc_spacing = math.pi * INNER / inner_seats
    dot = max(6.0, min(13.0, row_gap * 0.34, arc_spacing * 0.42))

    img = PILImage.new("RGB", (W, H), (247, 243, 236))
    draw = ImageDraw.Draw(img)
    f_title = ImageFont.load_default(34)
    f_sub = ImageFont.load_default(22)
    f_leg = ImageFont.load_default(24)

    draw.text((40, 34), title, fill=(28, 43, 65), font=f_title)
    draw.text((40, 84), subtitle, fill=(85, 96, 111), font=f_sub)
    draw.text(
        (40, 118),
        "Rappresentazione schematica: i punti mostrano i totali di voto "
        "per gruppo, non il seggio reale dei singoli deputati.",
        fill=(141, 135, 121),
        font=ImageFont.load_default(18),
    )

    for (x, y, _a, _r), p in zip(seats, ordered):
        color = _OUTCOME_COLOR.get(p.get("outcome"), _OUTCOME_COLOR["absent"])
        draw.circle((x, y), dot, fill=color)

    tally = {"favor": 0, "against": 0, "abstain": 0, "absent": 0}
    for p in ordered:
        tally[p.get("outcome") if p.get("outcome") in tally else "absent"] += 1
    labels = [("favor", "Favorevoli"), ("against", "Contrari"),
              ("abstain", "Astenuti"), ("absent", "Assenti")]
    x = 130
    for key, label in labels:
        if key == "abstain" and tally[key] == 0:
            continue
        draw.circle((x, CY + 90), 11, fill=_OUTCOME_COLOR[key])
        text = f"{label} {tally[key]}"
        draw.text((x + 22, CY + 78), text, fill=(28, 43, 65), font=f_leg)
        x += 40 + draw.textlength(text, font=f_leg) + 40
    draw.text((40, H - 36), "parliamentrag.it", fill=(141, 135, 121),
              font=ImageFont.load_default(18))

    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _install_rate_limit() -> None:
    """Rate limit per IP sull'endpoint remoto.

    Il server è pubblico e senza chiave: i tool sono in sola lettura su dati
    pubblici, quindi l'unico rischio è il martellamento dell'API a monte.
    Finestra scorrevole da 60 richieste/minuto per IP: una conversazione
    tipica di un assistente fa 1-20 chiamate, chi ne fa di più sta facendo
    scraping e può usare direttamente l'API o il dump Zenodo.
    """
    import time
    from collections import deque

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    WINDOW = 60.0
    LIMIT = int(os.environ.get("MCP_RATE_LIMIT", "60"))
    hits: dict[str, deque] = {}

    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path in ("/", "/icon.png", "/favicon.ico"):
                return await call_next(request)
            fwd = request.headers.get("x-forwarded-for", "")
            ip = fwd.split(",")[0].strip() or (request.client.host if request.client else "?")
            now = time.monotonic()
            q = hits.setdefault(ip, deque())
            while q and now - q[0] > WINDOW:
                q.popleft()
            if len(q) >= LIMIT:
                return JSONResponse(
                    {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32000,
                               "message": "Rate limit exceeded: max "
                                          f"{LIMIT} requests/minute. For bulk access use "
                                          "the public API or the Zenodo dump."}},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            q.append(now)
            if len(hits) > 10000:  # niente crescita illimitata della mappa
                for k in [k for k, v in hits.items() if not v]:
                    hits.pop(k, None)
            return await call_next(request)

    # L'app streamable-http è costruita da FastMCP: il middleware va montato lì.
    original = mcp.streamable_http_app

    def with_middleware(*args, **kwargs):
        app = original(*args, **kwargs)
        app.add_middleware(RateLimitMiddleware)
        return app

    mcp.streamable_http_app = with_middleware


def main() -> None:
    # Due modi di esecuzione:
    # - stdio (default): client locali (Claude Code/Desktop, Cursor, ...)
    # - streamable-http (MCP_TRANSPORT=http): server remoto per i connettori
    #   di ChatGPT e claude.ai; stateless così regge dietro un load balancer.
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("http", "streamable-http"):
        from mcp.server.transport_security import TransportSecuritySettings

        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = int(os.environ.get("PORT", "8080"))
        mcp.settings.stateless_http = True
        # La protezione DNS-rebinding dell'SDK serve ai server locali: su un
        # dominio pubblico dietro TLS rifiuterebbe l'Host legittimo
        # ("Invalid Host header" per mcp.parliamentrag.it).
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )

        from starlette.requests import Request
        from starlette.responses import HTMLResponse

        @mcp.custom_route("/", methods=["GET"])
        async def landing(request: Request) -> HTMLResponse:
            # ?lang= vince sull'Accept-Language: il sito principale lo passa
            # per mantenere la lingua scelta dall'utente nella UI.
            lang = request.query_params.get("lang", "").lower()[:2]
            accept = lang if lang in _L10N else request.headers.get("accept-language", "")
            return HTMLResponse(
                _render_landing(accept),
                headers={"Vary": "Accept-Language"},
            )

        # Logo dichiarato negli icons del server: i client lo scaricano da qui.
        # Nel container il file è in /app (cwd), in sviluppo accanto allo script.
        from pathlib import Path

        from starlette.responses import PlainTextResponse, Response

        def _serve_asset(filename: str, media_type: str) -> Response:
            for candidate in (Path(__file__).parent / filename, Path(filename)):
                if candidate.is_file():
                    return Response(
                        candidate.read_bytes(),
                        media_type=media_type,
                        headers={"Cache-Control": "public, max-age=86400"},
                    )
            return PlainTextResponse(f"{filename} not found", status_code=404)

        @mcp.custom_route("/icon.png", methods=["GET"])
        async def icon(_request: Request) -> Response:
            return _serve_asset("icon.png", "image/png")

        # Alcuni client mostrano la favicon del dominio come logo del connettore.
        @mcp.custom_route("/favicon.ico", methods=["GET"])
        async def favicon(_request: Request) -> Response:
            return _serve_asset("favicon.ico", "image/x-icon")

        _install_rate_limit()
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
