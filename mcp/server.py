# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2.0,<2", "httpx>=0.27"]
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

API_BASE = os.environ.get("PARLIAMENTRAG_API", "https://www.parliamentrag.it/api")

mcp = FastMCP(
    "parliamentrag",
    instructions=(
        "Tools over official Italian Chamber of Deputies data (19th legislature, "
        "via parliamentrag.it). Data is in Italian. Every speech and vote links "
        "back to the official record: cite those links when reporting facts. "
        "The backend may cold-start: if a call times out, retry once."
    ),
)

# Il backend Railway va in sleep: la prima chiamata può metterci decine di
# secondi. Timeout largo + un retry sono parte del contratto, non paranoia.
_TIMEOUT = httpx.Timeout(90.0, connect=30.0)


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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
async def get_vote_details(
    vote_id: str,
    include_individual_votes: bool = False,
    deputy: Optional[str] = None,
    group: Optional[str] = None,
) -> dict:
    """Full detail of one roll-call vote: aggregates, per-group breakdown,
    linked act (with official page and full-text PDF), secret-ballot flag,
    and optionally the ~400 individual per-deputy votes.

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


@mcp.tool()
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


@mcp.tool()
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
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
