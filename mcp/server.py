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
_LANDING = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ParliamentRAG MCP</title>
<style>body{font-family:Georgia,serif;background:#f7f3ec;color:#1c2b41;margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center}
main{max-width:640px;padding:48px 28px}h1{font-size:2rem;margin:0 0 12px}p,li{font-size:1.05rem;line-height:1.55;color:#55606f}
code{background:#1c2b41;color:#e8dcc8;padding:3px 8px;border-radius:6px;font-size:.95rem}
a{color:#a34a28}</style></head><body><main>
<h1>ParliamentRAG &mdash; server MCP</h1>
<p>Questo &egrave; un connettore <a href="https://modelcontextprotocol.io">Model Context Protocol</a>:
non un sito, ma un servizio che d&agrave; agli assistenti AI accesso ai dati ufficiali
della Camera dei Deputati (votazioni nominali, interventi, testi degli emendamenti).</p>
<p>Per usarlo, aggiungi ai connettori del tuo assistente:</p>
<p><code>https://mcp.parliamentrag.it/mcp</code></p>
<ul>
<li><b>claude.ai</b>: Settings &rarr; Connectors &rarr; Add custom connector</li>
<li><b>ChatGPT</b>: Impostazioni &rarr; Connettori (modalit&agrave; sviluppatore)</li>
</ul>
<p>Istruzioni complete e codice: <a href="https://github.com/Emeierkeio/ParliamentRAG/tree/main/mcp">github.com/Emeierkeio/ParliamentRAG</a>
&middot; Il sistema: <a href="https://www.parliamentrag.it">parliamentrag.it</a></p>
</main></body></html>"""



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
        async def landing(_request: Request) -> HTMLResponse:
            return HTMLResponse(_LANDING)

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
