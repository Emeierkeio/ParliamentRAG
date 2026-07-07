"""
Unified expert computation service.

Single source of truth for all expert-related logic:
- compute_experts(): select top-authority speaker per party from evidence list
- patch_experts_for_cited_speakers(): post-generation correction to align experts
  with the speakers actually cited in the generated answer
- _fetch_speaker_details(): low-level Neo4j helper (sync, for use with executor)

Design decision (locked):
  Combined ranking formula: 0.70 * authority_score + 0.30 * best_chunk_similarity
  This is the canonical formula; query.py's authority-only variant is available
  via ranking_formula="authority_only".

Callers:
  - app.routers.chat (process_chat_streaming / process_chat_background)
  - app.routers.query (process_query_streaming)
  - backend/scripts/seed_evaluation_topic.py
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal Neo4j helper (sync — intended for use with run_in_executor)
# ---------------------------------------------------------------------------

def _fetch_speaker_details(neo4j_client: Neo4jClient, speaker_id: str) -> Dict[str, Any]:
    """Fetch detailed speaker information from Neo4j.

    Tries Deputy first, then GovernmentMember. Returns an empty dict if the
    speaker is not found (caller must handle the missing-data case).
    """
    # Try Deputy first — includes committee membership and institutional roles
    cypher = """
    MATCH (d:Deputy {id: $speaker_id})
    OPTIONAL MATCH (d)-[mc:MEMBER_OF_COMMITTEE]->(c:Committee)
    WHERE mc.end_date IS NULL OR mc.end_date >= date()
    WITH d, collect(c.name)[0] AS current_committee

    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rp:IS_PRESIDENT]->(cp:Committee)
        RETURN collect(DISTINCT {role: 'Presidente ' + cp.name, active: rp.end_date IS NULL OR rp.end_date >= date()}) AS president_roles
    }
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rv:IS_VICE_PRESIDENT]->(cv:Committee)
        RETURN collect(DISTINCT {role: 'Vicepresidente ' + cv.name, active: rv.end_date IS NULL OR rv.end_date >= date()}) AS vice_roles
    }
    CALL {
        WITH d
        OPTIONAL MATCH (d)-[rs:IS_SECRETARY]->(cs:Committee)
        RETURN collect(DISTINCT {role: 'Segretario ' + cs.name, active: rs.end_date IS NULL OR rs.end_date >= date()}) AS secretary_roles
    }
    WITH d, current_committee, president_roles + vice_roles + secretary_roles AS all_roles

    // Prefer active roles, fall back to any role
    WITH d, current_committee, all_roles,
         [r IN all_roles WHERE r.active | r.role] AS active_roles,
         [r IN all_roles | r.role] AS any_roles

    RETURN d.id AS id,
           d.first_name AS first_name,
           d.last_name AS last_name,
           d.profession AS profession,
           d.education AS education,
           d.deputy_card AS camera_profile_url,
           d.photo AS photo,
           current_committee,
           CASE
               WHEN size(active_roles) > 0 THEN active_roles[0]
               WHEN size(any_roles) > 0 THEN any_roles[0]
               ELSE null
           END AS institutional_role
    """
    with neo4j_client.session() as session:
        result = session.run(cypher, speaker_id=speaker_id)
        record = result.single()
        if record:
            return dict(record)

    # Try GovernmentMember
    cypher_gov = """
    MATCH (m:GovernmentMember {id: $speaker_id})
    RETURN m.id AS id,
           m.first_name AS first_name,
           m.last_name AS last_name,
           m.institutional_role AS institutional_role,
           m.deputy_card AS camera_profile_url
    """
    with neo4j_client.session() as session:
        result = session.run(cypher_gov, speaker_id=speaker_id)
        record = result.single()
        if record:
            data = dict(record)
            data["profession"] = None
            data["education"] = None
            data["current_committee"] = None
            return data

    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def compute_experts(
    evidence_list: list,
    authority_scores: Dict[str, float],
    authority_details: Dict[str, Dict],
    neo4j_client: Neo4jClient,
    ranking_formula: str = "combined",
) -> List[Dict[str, Any]]:
    """Compute the top-authority expert per parliamentary group.

    Parameters
    ----------
    evidence_list:
        Iterable of evidence objects with attributes: speaker_id, speaker_name,
        speaker_role, party, party_changed, current_party, similarity.
    authority_scores:
        Mapping of speaker_id → total authority score [0, 1].
    authority_details:
        Mapping of speaker_id → full authority breakdown dict (includes
        'components' and 'institutional_role').
    neo4j_client:
        Shared Neo4j client (fetching speaker profile data).
    ranking_formula:
        ``"combined"`` (default) — 0.70 * authority + 0.30 * best_chunk_similarity
        ``"authority_only"``       — authority_score alone (legacy query.py behaviour)

    Returns
    -------
    List of expert dicts in the frozen shape expected by the frontend.
    """
    from .authority.coalition_logic import CoalitionLogic

    coalition_logic = CoalitionLogic()
    party_speakers: Dict[str, Dict[str, Any]] = {}

    for evidence in evidence_list:
        # GovernmentMember speakers are excluded from the experts panel entirely.
        # They are not deputies and must not appear in the per-party authority ranking.
        if evidence.speaker_role == "GovernmentMember":
            continue

        # Use current party if the speaker has changed group (same logic as pipeline.py)
        party = (
            evidence.current_party
            if evidence.party_changed and evidence.current_party
            else evidence.party
        )
        speaker_id = evidence.speaker_id
        speaker_name = evidence.speaker_name

        if party not in party_speakers:
            party_speakers[party] = {}

        if speaker_id not in party_speakers[party]:
            party_speakers[party][speaker_id] = {
                "speaker_name": speaker_name,
                "authority_score": authority_scores.get(speaker_id, 0.5),
                "best_similarity": evidence.similarity if hasattr(evidence, "similarity") else 0.0,
                "count": 0,
                "party": party,
            }
        else:
            # Track best chunk similarity for this speaker (used in combined formula)
            sim = evidence.similarity if hasattr(evidence, "similarity") else 0.0
            if sim > party_speakers[party][speaker_id]["best_similarity"]:
                party_speakers[party][speaker_id]["best_similarity"] = sim

        party_speakers[party][speaker_id]["count"] += 1

    # Select top speaker per party using the ranking formula
    top_speakers_info = []
    for party, speakers in party_speakers.items():
        if not speakers:
            continue
        if ranking_formula == "authority_only":
            def _score(s, _spk=speakers):
                return _spk[s]["authority_score"]
        else:  # "combined" (default)
            def _score(s, _spk=speakers):
                return 0.70 * _spk[s]["authority_score"] + 0.30 * _spk[s]["best_similarity"]

        top_speaker_id = max(speakers.keys(), key=_score)
        top_speakers_info.append((party, top_speaker_id, speakers[top_speaker_id]))

    if not top_speakers_info:
        return []

    # Fetch all speaker details in parallel using a thread pool
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(top_speakers_info)))) as pool:
        detail_futures = [
            loop.run_in_executor(pool, _fetch_speaker_details, neo4j_client, info[1])
            for info in top_speakers_info
        ]
        speaker_details_list = await asyncio.gather(*detail_futures)

    experts = []
    for (party, top_speaker_id, top_speaker), speaker_info in zip(top_speakers_info, speaker_details_list):
        coalition = coalition_logic.get_coalition(party)

        name_parts = top_speaker["speaker_name"].split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        details = authority_details.get(top_speaker_id, {})
        components = details.get("components", {})

        experts.append({
            "id": top_speaker_id,
            "first_name": first_name,
            "last_name": last_name,
            "group": party,
            "coalition": coalition,
            "authority_score": round(top_speaker["authority_score"], 2),
            "relevant_speeches_count": top_speaker["count"],
            "photo": speaker_info.get("photo"),
            "camera_profile_url": speaker_info.get("camera_profile_url"),
            "profession": speaker_info.get("profession"),
            "education": speaker_info.get("education"),
            "committee": speaker_info.get("current_committee"),
            "institutional_role": details.get("institutional_role") or speaker_info.get("institutional_role"),
            "score_breakdown": {
                "speeches": round(components.get("interventions", 0), 2),
                "acts": round(components.get("acts", 0), 2),
                "committee": round(components.get("committee", 0), 2),
                "profession": round(components.get("profession", 0), 2),
                "education": round(components.get("education", 0), 2),
                "role": round(components.get("role", 0), 2),
            },
        })

    return experts


async def patch_experts_for_cited_speakers(
    experts: List[Dict[str, Any]],
    gen_citations: List[Dict[str, Any]],
    evidence_dicts: List[Dict[str, Any]],
    authority_scores: Dict[str, float],
    authority_details: Dict[str, Dict],
    neo4j_client: Neo4jClient,
) -> Optional[List[Dict[str, Any]]]:
    """Post-generation expert correction.

    The pre-generation ranking picks the top-authority speaker per party.
    After generation, the writer may have cited a different speaker whose
    evidence produced a stronger verbatim quote.  When that happens, update
    the affected expert entries to show the actually-cited speaker.

    Parameters
    ----------
    experts:
        Expert list returned by compute_experts() before generation.
    gen_citations:
        Citation list from the generation result (each has 'evidence_id', 'party').
    evidence_dicts:
        Raw evidence dicts with 'evidence_id' and 'speaker_id' fields.
    authority_scores, authority_details:
        Same mappings passed to compute_experts().
    neo4j_client:
        Shared Neo4j client.

    Returns
    -------
    Updated experts list if any entries changed, ``None`` otherwise.
    """
    from .authority.coalition_logic import CoalitionLogic

    coalition_logic = CoalitionLogic()

    # evidence_id → evidence dict
    eid_to_ev: Dict[str, Dict[str, Any]] = {
        e["evidence_id"]: e
        for e in evidence_dicts
        if e.get("evidence_id") and e.get("speaker_id")
    }

    # First cited speaker per party (from generation citations)
    # Skip GovernmentMember — they belong in "Governo", not in party sections
    party_to_cited: Dict[str, Dict[str, Any]] = {}
    for cit in gen_citations:
        party = cit.get("party", "")
        if not party or party in party_to_cited:
            continue
        ev = eid_to_ev.get(cit.get("evidence_id", ""))
        if ev and ev.get("speaker_id"):
            # Don't let GovernmentMember speakers overwrite party experts
            if ev.get("speaker_role") == "GovernmentMember":
                continue
            party_to_cited[party] = ev

    # Index current experts by party
    party_to_idx: Dict[str, int] = {e.get("group", ""): i for i, e in enumerate(experts)}

    # Find mismatches between pre-gen top speaker and post-gen cited speaker
    to_update = []  # list of (expert_idx, cited_ev)
    for party, cited_ev in party_to_cited.items():
        idx = party_to_idx.get(party)
        if idx is None:
            continue
        if experts[idx].get("id") != cited_ev["speaker_id"]:
            to_update.append((idx, cited_ev))
            logger.info(
                "[EXPERTS_PATCH] %s: top_ranked=%s → cited=%s",
                party,
                experts[idx].get("last_name"),
                cited_ev.get("speaker_name"),
            )

    if not to_update:
        return None

    # Fetch details for all updated speakers in parallel
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=min(10, len(to_update))) as pool:
        futures = [
            loop.run_in_executor(pool, _fetch_speaker_details, neo4j_client, cited_ev["speaker_id"])
            for _, cited_ev in to_update
        ]
        speaker_details_list = await asyncio.gather(*futures)

    updated = list(experts)
    for (idx, cited_ev), speaker_info in zip(to_update, speaker_details_list):
        sid = cited_ev["speaker_id"]
        party = cited_ev.get("party", "")
        name_parts = cited_ev.get("speaker_name", "").split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        details = authority_details.get(sid, {})
        components = details.get("components", {})
        coalition = coalition_logic.get_coalition(party)
        relevant_count = sum(1 for e in evidence_dicts if e.get("speaker_id") == sid)

        updated[idx] = {
            "id": sid,
            "first_name": first_name,
            "last_name": last_name,
            "group": party,
            "coalition": coalition,
            "authority_score": round(authority_scores.get(sid, 0.5), 2),
            "relevant_speeches_count": relevant_count,
            "photo": speaker_info.get("photo"),
            "camera_profile_url": speaker_info.get("camera_profile_url"),
            "profession": speaker_info.get("profession"),
            "education": speaker_info.get("education"),
            "committee": speaker_info.get("current_committee"),
            "institutional_role": details.get("institutional_role") or speaker_info.get("institutional_role"),
            "score_breakdown": {
                "speeches": round(components.get("interventions", 0), 2),
                "acts": round(components.get("acts", 0), 2),
                "committee": round(components.get("committee", 0), 2),
                "profession": round(components.get("profession", 0), 2),
                "education": round(components.get("education", 0), 2),
                "role": round(components.get("role", 0), 2),
            },
        }

    return updated
