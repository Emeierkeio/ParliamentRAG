"""
Timeline service — Neo4j queries for the parliamentary timeline API.

Provides three async functions consumed by the timeline router:
  - get_sessions():       paginated session list with nested debate summaries
  - get_debate_detail():  phases, speakers, votes, and acts for one debate
  - get_speaker_summary(): AI-generated speaker position summary

All functions accept a Neo4jClient instance (injected by FastAPI Depends) and
a locale string ("it" or "en") to select the correct recap/summary field.

Pitfall notes (from RESEARCH.md):
  - Neo4j returns dates as neo4j.time.Date objects → convert with str(record["date"])
  - Speakers can be Deputy OR GovernmentMember nodes → use coalesce(d, g) pattern
  - Fetch limit+1 rows to detect whether more pages exist (cursor-based pagination)
"""
from __future__ import annotations

import re
import urllib.parse

from ..models.timeline import (
    ActInfo,
    DebateDetailResponse,
    DebateSummary,
    InterventionInfo,
    PhaseInfo,
    SessionCard,
    SpeakerInfo,
    SpeakerSummaryResponse,
    SpeechText,
    TimelineResponse,
    VoteActRef,
    VoteDetailResponse,
    VoteInfo,
    VoteParticipant,
    VotePartyBreakdown,
)
from .neo4j_client import Neo4jClient


def _act_public_url(uri: str | None) -> str | None:
    """Public camera.it page for a ParliamentaryAct URI, when derivable.

    - attocamera.rdf/ac19_2735          → scheda dell'atto (PDL/DDL)
    - aic.rdf/aic9_01492_027_19         → scheda AIC (ODG/mozione/risoluzione)
      con il testo integrale; il numero si ricostruisce dai segmenti dell'URI
      ("9_02911_A_028" → "9/02911-A/028": le lettere sono suffissi del
      segmento precedente).
    """
    if not uri:
        return None
    m = re.search(r"/attocamera\.rdf/ac(\d+)_(\w+)$", uri)
    if m:
        leg, num = m.group(1), m.group(2)
        return f"https://www.camera.it/leg{leg}/126?tab=1&leg={leg}&idDocumento={num}"
    m = re.search(r"/aic\.rdf/aic(.+)_(\d+)$", uri)
    if m:
        body, leg = m.group(1), m.group(2)
        segments: list[str] = []
        for part in body.split("_"):
            if part.isalpha() and segments:
                segments[-1] += f"-{part}"
            else:
                segments.append(part)
        numero = urllib.parse.quote("/".join(segments), safe="")
        return f"https://aic.camera.it/aic/scheda.html?numero={numero}&ramo=CAMERA&leg={leg}"
    return None


async def get_sessions(
    neo4j: Neo4jClient,
    locale: str,
    before: str | None = None,
    limit: int = 20,
    chamber: str = "both",
    legislature: int = 19,
    search: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> TimelineResponse:
    """
    Return a paginated list of sessions ordered most-recent-first.

    Pagination uses cursor-based approach: `before` is an ISO date string.
    Fetches limit+1 rows — if more than limit rows returned, has_more=True
    and next_cursor is set to the ISO date of the last included session.

    Chamber mapping:
      "both"   → no chamber filter (returns all chambers)
      "camera" → ["camera"]
      "senato" → ["senato"]

    Search matches debate titles, recap text, and speaker names.
    """
    recap_field = "recapEn" if locale == "en" else "recapIt"

    # Map chamber param to list (or None for no filter)
    if chamber == "both":
        chambers = None
    else:
        chambers = [chamber]

    # Build search subquery condition (added to WHERE at debate level)
    search_clause = ""
    if search:
        search_clause = """
  AND EXISTS {
    MATCH (s)-[:HAS_DEBATE]->(sd)
    WHERE toLower(sd.title) CONTAINS toLower($search)
       OR toLower(s.recapIt) CONTAINS toLower($search)
       OR toLower(s.recapEn) CONTAINS toLower($search)
       OR EXISTS {
         MATCH (sd)-[:HAS_PHASE]->(p2)-[:CONTAINS_SPEECH]->(sp2)-[:SPOKEN_BY]->(spk2)
         WHERE (spk2:Deputy OR spk2:GovernmentMember)
           AND toLower(spk2.first_name + ' ' + spk2.last_name) CONTAINS toLower($search)
       }
  }"""

    # When searching, compute a relevance flag per debate so matching debates sort first
    relevance_expr = "0 AS relevance"
    order_debates = "d.id"
    if search:
        relevance_expr = (
            "CASE WHEN toLower(d.title) CONTAINS toLower($search) THEN 1 ELSE 0 END AS relevance"
        )
        order_debates = "relevance DESC, d.id"

    cypher = f"""
MATCH (s:Session)
WHERE ($chambers IS NULL OR s.chamber IN $chambers)
  AND s.legislature = $legislature
  AND ($before IS NULL OR s.date < date($before))
  AND ($from_date IS NULL OR s.date >= date($from_date))
  AND ($to_date IS NULL OR s.date <= date($to_date)){search_clause}
WITH s ORDER BY s.date DESC LIMIT $fetch_limit
OPTIONAL MATCH (s)-[:HAS_DEBATE]->(d)
OPTIONAL MATCH (d)-[:HAS_PHASE]->(p)-[:CONTAINS_SPEECH]->(sp)
WITH s, d, count(DISTINCT sp) AS dSpeechCount, {relevance_expr}
ORDER BY s.date DESC, {order_debates}
WITH s, collect(DISTINCT {{id: d.id, title: d.title, speechCount: dSpeechCount}}) AS debates
OPTIONAL MATCH (s)-[:HAS_VOTE]->(v)
WITH s, debates, count(DISTINCT v) AS voteCount
RETURN s.id AS id,
       toString(s.date) AS date,
       s.chamber AS chamber,
       s.number AS number,
       s.{recap_field} AS recap,
       debates,
       voteCount,
       size(debates) AS debateCount,
       reduce(total = 0, d IN debates | total + d.speechCount) AS speechCount
ORDER BY date DESC
"""

    params: dict = {
        "chambers": chambers,
        "legislature": legislature,
        "before": before,
        "from_date": from_date,
        "to_date": to_date,
        "fetch_limit": limit + 1,
    }
    if search:
        params["search"] = search

    rows = neo4j.query(cypher, params)

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    next_cursor: str | None = rows[-1]["date"] if (has_more and rows) else None

    sessions = []
    for row in rows:
        debates = [
            DebateSummary(
                id=d["id"] or "",
                title=d["title"] or "",
                speech_count=d["speechCount"] or 0,
            )
            for d in (row["debates"] or [])
            if d.get("id")  # skip null entries from OPTIONAL MATCH
        ]
        sessions.append(
            SessionCard(
                id=row["id"],
                date=str(row["date"]),
                chamber=row["chamber"] or "",
                number=row["number"] or 0,
                recap=row["recap"],
                debate_count=row["debateCount"] or 0,
                vote_count=row["voteCount"] or 0,
                speech_count=row["speechCount"] or 0,
                debates=debates,
            )
        )

    return TimelineResponse(sessions=sessions, next_cursor=next_cursor, has_more=has_more)


async def get_debate_detail(
    neo4j: Neo4jClient,
    debate_id: str,
    locale: str,
) -> DebateDetailResponse:
    """
    Return full detail for a single debate.

    Queries:
      - Debate recap (locale-aware)
      - Phases with speech counts
      - Speakers (Deputy or GovernmentMember) in chronological order
      - Votes via session (Session-[:HAS_VOTE]->Vote)
      - Parliamentary acts (Debate-[:DISCUSSES]->ParliamentaryAct)
    """
    recap_field = "recapEn" if locale == "en" else "recapIt"
    summary_field = "summaryEn" if locale == "en" else "summaryIt"  # noqa: F841 — used in speaker summary

    # --- Debate metadata ---
    debate_row = neo4j.query_single(
        f"""
        MATCH (d:Debate {{id: $debate_id}})
        RETURN d.id AS id,
               d.title AS title,
               d.{recap_field} AS recap
        """,
        {"debate_id": debate_id},
    )
    if not debate_row:
        # Return empty response if debate not found
        return DebateDetailResponse(
            id=debate_id, title="", recap=None,
            phases=[], speakers=[], votes=[], acts=[],
        )

    # --- Phases ---
    phase_rows = neo4j.query(
        """
        MATCH (d:Debate {id: $debate_id})-[:HAS_PHASE]->(p:Phase)
        OPTIONAL MATCH (p)-[:CONTAINS_SPEECH]->(sp:Speech)
        WITH p, count(DISTINCT sp) AS speechCount
        RETURN p.id AS id,
               p.title AS title,
               p.phaseType AS phase_type,
               speechCount
        ORDER BY p.id
        """,
        {"debate_id": debate_id},
    )
    phases = [
        PhaseInfo(
            id=r["id"],
            title=r["title"] or "",
            phase_type=r["phase_type"],
            speech_count=r["speechCount"] or 0,
        )
        for r in phase_rows
    ]

    # --- Speakers (chronological, Deputy or GovernmentMember via coalesce) ---
    # Party comes from MEMBER_OF_GROUP relationship (not a direct property).
    # speakingRole lives on Speech, not on the speaker node — collect first distinct role.
    speaker_rows = neo4j.query(
        """
        MATCH (d:Debate {id: $debate_id})<-[:HAS_DEBATE]-(sess:Session)
        WITH d, sess
        MATCH (d)-[:HAS_PHASE]->(p:Phase)
              -[:CONTAINS_SPEECH]->(sp:Speech)
        OPTIONAL MATCH (sp)-[:SPOKEN_BY]->(dep:Deputy)
        OPTIONAL MATCH (sp)-[:SPOKEN_BY]->(gov:GovernmentMember)
        WITH coalesce(dep, gov) AS spk,
             (dep IS NULL AND gov IS NOT NULL) AS isGov,
             p, sp, sess
        WHERE spk IS NOT NULL
        WITH spk, isGov, sess,
             collect(DISTINCT p.title) AS participatedPhases,
             count(DISTINCT sp) AS speechCount,
             min(sp.id) AS firstSpeechId,
             head(collect(DISTINCT sp.speakingRole)) AS speakingRole
        OPTIONAL MATCH (spk)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
          WHERE mg.start_date <= sess.date
            AND (mg.end_date IS NULL OR mg.end_date >= sess.date)
        WITH spk, isGov, participatedPhases, speechCount, firstSpeechId, speakingRole,
             head(collect(g.name)) AS party
        RETURN spk.id AS id,
               spk.first_name AS first_name,
               spk.last_name AS last_name,
               party,
               speakingRole AS speaking_role,
               isGov AS is_government_member,
               speechCount,
               participatedPhases AS phases,
               firstSpeechId
        ORDER BY firstSpeechId
        """,
        {"debate_id": debate_id},
    )
    speakers = [
        SpeakerInfo(
            id=r["id"],
            first_name=r["first_name"] or "",
            last_name=r["last_name"] or "",
            party=r["party"],
            speaking_role=r["speaking_role"],
            is_government_member=bool(r["is_government_member"]),
            speech_count=r["speechCount"] or 0,
            phases=[ph for ph in (r["phases"] or []) if ph],
        )
        for r in speaker_rows
    ]

    # --- Interventions (chronological: one row per speech slot, so a
    #     deputy who takes the floor twice appears twice, in order) ---
    intervention_rows = neo4j.query(
        """
        MATCH (d:Debate {id: $debate_id})<-[:HAS_DEBATE]-(sess:Session)
        MATCH (d)-[:HAS_PHASE]->(p:Phase)-[:CONTAINS_SPEECH]->(sp:Speech)
        OPTIONAL MATCH (sp)-[:SPOKEN_BY]->(dep:Deputy)
        OPTIONAL MATCH (sp)-[:SPOKEN_BY]->(gov:GovernmentMember)
        WITH sp, p, sess,
             coalesce(dep, gov) AS spk,
             (dep IS NULL AND gov IS NOT NULL) AS isGov
        WHERE spk IS NOT NULL
        OPTIONAL MATCH (spk)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
          WHERE mg.start_date <= sess.date
            AND (mg.end_date IS NULL OR mg.end_date >= sess.date)
        WITH sp, p, spk, isGov, head(collect(g.name)) AS party
        RETURN sp.id AS speech_id,
               spk.id AS speaker_id,
               spk.first_name AS first_name,
               spk.last_name AS last_name,
               party,
               sp.speakingRole AS speaking_role,
               isGov AS is_government_member,
               p.title AS phase_title
        ORDER BY sp.id
        """,
        {"debate_id": debate_id},
    )
    interventions = [
        InterventionInfo(
            speech_id=r["speech_id"],
            speaker_id=r["speaker_id"],
            first_name=r["first_name"] or "",
            last_name=r["last_name"] or "",
            party=r["party"],
            speaking_role=r["speaking_role"],
            is_government_member=bool(r["is_government_member"]),
            phase_title=r["phase_title"],
        )
        for r in intervention_rows
    ]

    # --- Votes (via session, not direct from debate) ---
    vote_rows = neo4j.query(
        """
        MATCH (d:Debate {id: $debate_id})<-[:HAS_DEBATE]-(s:Session)-[:HAS_VOTE]->(v:Vote)
        RETURN v.id AS id,
               v.number AS number,
               v.subject AS subject,
               v.description AS description,
               v.finalVote AS final_vote,
               v.outcome AS outcome,
               v.inFavor AS in_favor,
               v.against AS against,
               v.abstained AS abstained
        ORDER BY v.number
        """,
        {"debate_id": debate_id},
    )
    votes = [
        VoteInfo(
            id=r["id"],
            number=r["number"] or 0,
            subject=r["subject"],
            description=r["description"],
            final_vote=bool(r["final_vote"]),
            outcome=r["outcome"],
            in_favor=r["in_favor"],
            against=r["against"],
            abstained=r["abstained"],
        )
        for r in vote_rows
    ]

    # --- Parliamentary acts ---
    act_rows = neo4j.query(
        """
        MATCH (d:Debate {id: $debate_id})-[:DISCUSSES]->(a:ParliamentaryAct)
        RETURN a.id AS id,
               a.title AS title,
               a.type AS type
        ORDER BY a.title
        """,
        {"debate_id": debate_id},
    )
    acts = [
        ActInfo(
            id=r["id"],
            title=r["title"],
            type=r["type"],
        )
        for r in act_rows
        if r["id"]  # skip null entries from OPTIONAL MATCH
    ]

    return DebateDetailResponse(
        id=debate_row["id"],
        title=debate_row["title"] or "",
        recap=debate_row["recap"],
        phases=phases,
        speakers=speakers,
        interventions=interventions,
        votes=votes,
        acts=acts,
    )


async def get_session_votes(
    neo4j: Neo4jClient,
    session_id: str,
) -> list[VoteInfo]:
    """Return every roll-call vote of a sitting.

    Votes hang off the Session (the Camera XML records them per sitting,
    not per debate), so this is the one honest place to list them without
    the duplication of repeating the full list in each debate detail.
    """
    vote_rows = neo4j.query(
        """
        MATCH (s:Session {id: $session_id})-[:HAS_VOTE]->(v:Vote)
        RETURN v.id AS id,
               v.number AS number,
               v.subject AS subject,
               v.description AS description,
               v.finalVote AS final_vote,
               v.outcome AS outcome,
               v.inFavor AS in_favor,
               v.against AS against,
               v.abstained AS abstained
        ORDER BY v.number
        """,
        {"session_id": session_id},
    )
    return [
        VoteInfo(
            id=r["id"],
            number=r["number"] or 0,
            subject=r["subject"],
            description=r["description"],
            final_vote=bool(r["final_vote"]),
            outcome=r["outcome"],
            in_favor=r["in_favor"],
            against=r["against"],
            abstained=r["abstained"],
        )
        for r in vote_rows
    ]


async def get_vote_detail(
    neo4j: Neo4jClient,
    vote_id: str,
) -> VoteDetailResponse:
    """
    Return full roll-call detail: vote metadata, per-party breakdown, and the
    complete participant list with individual outcomes.

    Individual votes live in the graph as:
      (Person)-[:VOTED]->(IndividualVote {outcome})-[:ON_VOTE]->(Vote)
    with outcome in {"favor", "against", "abstain", "absent"}. In secret
    ballots the source data hides the expression ("Ha votato"), so every
    record is "absent" and the frontend shows a dedicated notice instead.

    Party attribution is date-aware via MEMBER_OF_GROUP; deputies in the
    Gruppo Misto are attributed to their political component
    (MEMBER_OF_COMPONENT → MistoComponent) when one is active at vote date.
    """
    meta = neo4j.query_single(
        """
        MATCH (s:Session)-[:HAS_VOTE]->(v:Vote {id: $vote_id})
        OPTIONAL MATCH (v)-[:ON_ACT]->(a:ParliamentaryAct)
        RETURN v.id AS id,
               v.number AS number,
               v.subject AS subject,
               v.description AS description,
               collect(DISTINCT {uri: a.uri, title: a.title}) AS acts,
               v.outcome AS outcome,
               v.type AS vote_type,
               v.inFavor AS in_favor,
               v.against AS against,
               v.abstained AS abstained,
               v.present AS present,
               v.voters AS voters,
               v.majority AS majority,
               v.onMission AS on_mission,
               s.date AS session_date
        """,
        {"vote_id": vote_id},
    )
    if not meta:
        return VoteDetailResponse(
            id=vote_id, number=0, breakdown=[], participants=[],
        )

    participant_rows = neo4j.query(
        """
        MATCH (s:Session)-[:HAS_VOTE]->(v:Vote {id: $vote_id})
        MATCH (v)<-[:ON_VOTE]-(iv:IndividualVote)<-[:VOTED]-(p:Person)
        OPTIONAL MATCH (p)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
          WHERE mg.start_date <= s.date
            AND (mg.end_date IS NULL OR mg.end_date >= s.date)
        OPTIONAL MATCH (p)-[mc:MEMBER_OF_COMPONENT]->(c:MistoComponent)
          WHERE mc.start_date <= s.date
            AND (mc.end_date IS NULL OR mc.end_date >= s.date)
        WITH p, iv,
             head(collect(DISTINCT g.name)) AS groupName,
             head(collect(DISTINCT c.name)) AS componentName
        RETURN p.id AS id,
               p.first_name AS first_name,
               p.last_name AS last_name,
               CASE
                 WHEN toLower(coalesce(groupName, '')) CONTAINS 'misto'
                      AND componentName IS NOT NULL
                 THEN componentName
                 ELSE groupName
               END AS party,
               iv.outcome AS outcome
        ORDER BY last_name, first_name
        """,
        {"vote_id": vote_id},
    )

    participants = [
        VoteParticipant(
            id=r["id"],
            first_name=r["first_name"] or "",
            last_name=r["last_name"] or "",
            party=r["party"],
            outcome=r["outcome"] or "absent",
        )
        for r in participant_rows
    ]

    # Aggregate per-party counts in Python (one graph roundtrip total).
    counts: dict[str, dict[str, int]] = {}
    for p in participants:
        party = p.party or "—"
        bucket = counts.setdefault(
            party, {"favor": 0, "against": 0, "abstain": 0, "absent": 0}
        )
        # Unknown outcome values count as absent instead of silently vanishing
        # (pydantic would drop an unexpected key at model construction).
        bucket[p.outcome if p.outcome in bucket else "absent"] += 1
    breakdown = sorted(
        (
            VotePartyBreakdown(party=party, **b)
            for party, b in counts.items()
        ),
        key=lambda b: b.favor + b.against + b.abstain + b.absent,
        reverse=True,
    )

    # Atti collegati: prima l'oggetto votato (ODG/mozione via aic.rdf), poi il
    # disegno di legge di contesto. I titoli dall'ingest atti hanno padding.
    # Gli AIC senza dc:title nel dataset non hanno neanche la scheda su
    # aic.camera.it (il link darebbe "FILE NON TROVATO"): niente titolo,
    # niente link.
    act_refs = []
    for a in meta["acts"]:
        if not a.get("uri"):
            continue
        title = (a["title"] or "").strip() or None
        url = _act_public_url(a["uri"])
        if url and "aic.camera.it" in url and not title:
            url = None
        act_refs.append(VoteActRef(title=title, url=url))
    acts = sorted(
        act_refs,
        key=lambda a: 0 if a.url and "aic.camera.it" in a.url else 1,
    )

    return VoteDetailResponse(
        id=meta["id"],
        number=meta["number"] or 0,
        subject=meta["subject"],
        description=meta["description"],
        acts=[a for a in acts if a.title or a.url],
        outcome=meta["outcome"],
        vote_type=meta["vote_type"],
        in_favor=meta["in_favor"],
        against=meta["against"],
        abstained=meta["abstained"],
        present=meta["present"],
        voters=meta["voters"],
        majority=meta["majority"],
        on_mission=meta["on_mission"],
        breakdown=breakdown,
        participants=participants,
    )


async def get_speaker_summary(
    neo4j: Neo4jClient,
    debate_id: str,
    speaker_id: str,
    locale: str,
) -> SpeakerSummaryResponse:
    """
    Return the AI-generated position summary for a speaker in a specific debate.

    Reads from SpeakerDebateSummary node linked via:
      (Deputy|GovernmentMember)-[:HAS_DEBATE_SUMMARY]->(SpeakerDebateSummary)-[:FOR_DEBATE]->(Debate)

    Returns an empty response (summary=None, speech_count=0, phases=[]) if no
    SpeakerDebateSummary node exists for this (debate, speaker) pair.
    """
    summary_field = "summaryEn" if locale == "en" else "summaryIt"

    row = neo4j.query_single(
        f"""
        MATCH (sds:SpeakerDebateSummary)
        WHERE sds.debateId = $debate_id AND sds.speakerId = $speaker_id
        RETURN sds.{summary_field} AS summary,
               sds.speechCount AS speech_count,
               sds.phases AS phases
        """,
        {"debate_id": debate_id, "speaker_id": speaker_id},
    )

    if not row:
        summary_text = None
        s_count = 0
        s_phases: list[str] = []
    else:
        summary_text = row["summary"]
        s_count = row["speech_count"] or 0
        s_phases = [p for p in (row["phases"] or []) if p]

    # --- Fetch full speech texts for this speaker in this debate ---
    speech_rows = neo4j.query(
        """
        MATCH (d:Debate {id: $debate_id})-[:HAS_PHASE]->(p:Phase)
              -[:CONTAINS_SPEECH]->(sp:Speech)-[:SPOKEN_BY]->(spk)
        WHERE spk.id = $speaker_id AND (spk:Deputy OR spk:GovernmentMember)
        RETURN sp.id AS id, sp.text AS text, p.title AS phase_title
        ORDER BY sp.id
        """,
        {"debate_id": debate_id, "speaker_id": speaker_id},
    )
    speeches = [
        SpeechText(
            id=r["id"],
            text=r["text"] or "",
            phase_title=r["phase_title"],
        )
        for r in speech_rows
        if r.get("text")
    ]

    return SpeakerSummaryResponse(
        summary=summary_text,
        speech_count=s_count,
        phases=s_phases,
        speeches=speeches,
    )
