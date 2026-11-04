"""Come ha votato ogni gruppo sull'atto del tema, per chi scrive le sezioni.

Quando i dibattiti giudicati sul tema (debate_relevance.py) discutono un atto arrivato al voto finale, la posizione
che una sezione dà a un gruppo non deve contraddire quel voto: Italia Viva aveva votato contro l'S.1786 e la risposta
parlava di «astensione critica» partendo da una frase su un altro atto (19/10/2026). Per ogni gruppo, l'ultimo voto
finale di ogni ramo su quegli atti. Il Misto conta per componente, come nella risposta."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .contesto import VOTI_GRUPPI
from .debate_relevance import ON_TOPIC
from .gruppi import nome_partito

logger = logging.getLogger(__name__)

_SQL_VOTI = """
SELECT DISTINCT ON (v.chamber) v.uri, v.date, v.chamber, a.title AS act_title
FROM agenda_item ai JOIN sitting s ON s.uri = ai.sitting
JOIN agenda_item_act x ON x.item = ai.uri AND x.act IS NOT NULL
JOIN act a ON a.uri = x.act
JOIN vote_act va ON va.act = a.uri
JOIN vote v ON v.uri = va.vote
WHERE ai.title = ANY(%(titoli)s) AND s.chamber = ANY(%(rami)s) AND v.chamber = ANY(%(rami)s) AND v.legislature = 19
  AND (v.final OR v.kind = 'final') AND NOT coalesce(v.secret, false)
  AND NOT lower(coalesce(a.status, '')) LIKE 'assorbit%%'
ORDER BY v.chamber, v.date DESC, v.number DESC"""

_SQL_SCHEDE = """
SELECT b.result, g.name, g.kind FROM ballot b LEFT JOIN grp g ON g.uri = b.grp WHERE b.vote = %s"""

_CHAMBER_NAME = {"camera": "alla Camera", "senato": "al Senato"}


def set_group_votes(notes: dict[str, str] | None):
    return VOTI_GRUPPI.set(dict(notes or {}))


def group_vote_note(party: str) -> str:
    return VOTI_GRUPPI.get().get(party, "")


def _verb(c: dict[str, int]) -> str:
    f, a, s = c.get("favor", 0), c.get("against", 0), c.get("abstain", 0)
    if f and not a and not s:
        return "ha votato a favore"
    if a and not f and not s:
        return "ha votato contro"
    if s and not f and not a:
        return "si è astenuto"
    if not f and not a and not s:
        return "non ha votato"
    return "si è diviso"


def _counts(c: dict[str, int]) -> str:
    words = (("favor", "favorevoli"), ("against", "contrari"), ("abstain", "astenuti"), ("absent", "assenti"))
    return ", ".join(f"{c[k]} {w}" for k, w in words if c.get(k))


def _day(d) -> str:
    return d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d or "")


def _act_name(title: str | None) -> str:
    """Il nome dell'atto dentro il titolo: la parte tra virgolette di un titolo della Camera, se no il titolo."""
    plain = " ".join((title or "").split())
    m = re.search(r'["“«]([^"”»]{8,})["”»]', plain)
    name = m.group(1) if m else re.sub(r"\s*\(\d+\)\s*$", "", plain)
    return " ".join(name.split())


def notes_from_participants(vote: dict[str, Any], participants: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Una riga per partito su come hanno votato i suoi membri in una votazione."""
    by_party: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for p in participants:
        party = nome_partito(p.get("party") or "")
        outcome = p.get("outcome") if p.get("outcome") in ("favor", "against", "abstain") else "absent"
        by_party[party][outcome] += 1
    act = _act_name(vote.get("act_title"))
    where = _CHAMBER_NAME.get(vote.get("chamber"), "")
    # niente «»: nella risposta restano solo per le citazioni verificate
    return {party: f"Al voto finale del {_day(vote.get('date'))} {where} ({act}) il gruppo {_verb(c)}: {_counts(c)}."
            for party, c in by_party.items()}


def merge_notes(per_vote: list[dict[str, str]]) -> dict[str, str]:
    merged: dict[str, list[str]] = defaultdict(list)
    for notes in per_vote:
        for party, line in notes.items():
            merged[party].append(line)
    return {p: " ".join(lines) for p, lines in merged.items()}


def compute_group_votes(c, evidence: Iterable[dict[str, Any]], chambers: tuple[str, ...]) -> dict[str, str]:
    """Le righe sui voti finali degli atti discussi nei dibattiti sul tema, per partito; {} senza dibattiti, senza
    voti o se il database non risponde."""
    titles = sorted({(e.get("debate_title") or "").strip() for e in evidence
                     if e.get("debate_relevance") == ON_TOPIC and e.get("debate_title")})
    if not titles:
        return {}
    try:
        per_vote = []
        voti = c.execute(_SQL_VOTI, {"titoli": titles, "rami": list(chambers)}).fetchall()
        for v in voti:
            schede = c.execute(_SQL_SCHEDE, (v["uri"],)).fetchall()
            per_vote.append(notes_from_participants(
                {"date": v["date"], "chamber": v["chamber"], "act_title": v["act_title"]},
                ({"party": s["name"], "outcome": s["result"]} for s in schede if s["name"])))
        notes = merge_notes(per_vote)
    except Exception as exc:                         # noqa: BLE001 — la risposta va avanti senza i voti
        logger.warning("[GROUP_VOTES] unavailable: %s", exc)
        return {}
    if notes:
        logger.info("[GROUP_VOTES] final votes on %d vote(s) of the topic, %d groups", len(voti), len(notes))
    return notes
