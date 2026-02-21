"""
History endpoint for chat conversation history.

Stores complete chat sessions in Neo4j for persistence across deploys.
"""
import json
import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.neo4j_client import get_neo4j_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["History"])


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting for clean preview text."""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\[CIT:[^\]]+\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class ChatHistoryItem(BaseModel):
    """A stored chat session with full response data."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    answer: str
    preview: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)

    citations: List[Dict[str, Any]] = []
    experts: List[Dict[str, Any]] = []
    commissioni: List[Dict[str, Any]] = []
    balance: Optional[Dict[str, Any]] = None
    compass: Optional[Dict[str, Any]] = None

    topic_stats: Optional[Dict[str, Any]] = None

    # A/B Baseline comparison fields (optional for backwards compatibility)
    baseline_answer: Optional[str] = None
    ab_assignment: Optional[Dict[str, str]] = None  # e.g. {"A": "system", "B": "baseline"}


class HistoryListResponse(BaseModel):
    """Response for history list endpoint."""
    history: List[Dict[str, Any]] = []


def _get_client():
    try:
        return get_neo4j_client()
    except RuntimeError:
        # Global client not initialized yet - create and register it
        from ..config import get_settings
        from ..services.neo4j_client import Neo4jClient, init_neo4j_client
        settings = get_settings()
        return init_neo4j_client(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )


def ensure_constraint():
    """Create uniqueness constraint on ChatHistory.id if not exists."""
    try:
        _get_client().query(
            "CREATE CONSTRAINT chat_history_id IF NOT EXISTS FOR (c:ChatHistory) REQUIRE c.id IS UNIQUE"
        )
    except Exception as e:
        logger.debug(f"Constraint already exists or error: {e}")


@router.get("/history")
async def get_history() -> HistoryListResponse:
    """Get chat history list for sidebar display."""
    client = _get_client()
    results = client.query("""
        MATCH (c:ChatHistory)
        RETURN c.id AS id, c.query AS query, c.preview AS preview,
               c.timestamp AS timestamp
        ORDER BY c.timestamp DESC
        LIMIT 50
    """)

    history_list = []
    for r in results:
        history_list.append({
            "id": r["id"],
            "query": r["query"],
            "preview": r.get("preview", ""),
            "timestamp": r["timestamp"],
        })
    return HistoryListResponse(history=history_list)


@router.post("/history")
async def save_chat(chat: ChatHistoryItem) -> ChatHistoryItem:
    """Save a chat session to history."""
    try:
        logger.info(f"[HISTORY-SAVE] === Saving chat to history ===")
        logger.info(f"[HISTORY-SAVE] chat.id={chat.id}")
        logger.info(f"[HISTORY-SAVE] chat.query='{chat.query[:80]}...'")
        logger.info(f"[HISTORY-SAVE] chat.answer length={len(chat.answer)}")
        logger.info(f"[HISTORY-SAVE] chat.baseline_answer: type={type(chat.baseline_answer).__name__}, value={repr(chat.baseline_answer[:200]) if chat.baseline_answer else repr(chat.baseline_answer)}")
        logger.info(f"[HISTORY-SAVE] chat.ab_assignment: type={type(chat.ab_assignment).__name__}, value={chat.ab_assignment}")

        clean_text = _strip_markdown(chat.answer)
        chat.preview = clean_text[:100] + "..." if len(clean_text) > 100 else clean_text

        client = _get_client()

        # Serialize with size limits to avoid Neo4j property size issues
        citations_json = json.dumps(chat.citations, ensure_ascii=False, default=str)
        experts_json = json.dumps(chat.experts, ensure_ascii=False, default=str)
        commissioni_json = json.dumps(chat.commissioni, ensure_ascii=False, default=str)
        balance_json = json.dumps(chat.balance, ensure_ascii=False, default=str) if chat.balance else ""
        compass_json = json.dumps(chat.compass, ensure_ascii=False, default=str) if chat.compass else ""
        topic_stats_json = json.dumps(chat.topic_stats, ensure_ascii=False, default=str) if chat.topic_stats else ""
        ab_assignment_json = json.dumps(chat.ab_assignment, ensure_ascii=False) if chat.ab_assignment else ""

        baseline_value = (chat.baseline_answer or "")[:50000]
        logger.info(f"[HISTORY-SAVE] Neo4j params: baseline_answer='{baseline_value[:100]}...' (len={len(baseline_value)}), ab_assignment='{ab_assignment_json}'")

        client.query("""
            CREATE (c:ChatHistory {
                id: $id,
                query: $query,
                answer: $answer,
                preview: $preview,
                timestamp: $timestamp,
                citations: $citations,
                experts: $experts,
                commissioni: $commissioni,
                balance: $balance,
                compass: $compass,
                topic_stats: $topic_stats,
                baseline_answer: $baseline_answer,
                ab_assignment: $ab_assignment
            })
        """, {
            "id": chat.id,
            "query": chat.query,
            "answer": chat.answer[:50000],  # Limit answer size
            "preview": chat.preview,
            "timestamp": chat.timestamp.isoformat(),
            "citations": citations_json,
            "experts": experts_json,
            "commissioni": commissioni_json,
            "balance": balance_json,
            "compass": compass_json,
            "topic_stats": topic_stats_json,
            "baseline_answer": baseline_value,
            "ab_assignment": ab_assignment_json,
        })

        # Verify what was actually saved
        verify = client.query("""
            MATCH (c:ChatHistory {id: $id})
            RETURN c.baseline_answer AS baseline_answer, c.ab_assignment AS ab_assignment
        """, {"id": chat.id})
        if verify:
            logger.info(f"[HISTORY-SAVE] VERIFICATION: Neo4j baseline_answer='{str(verify[0].get('baseline_answer', ''))[:100]}...', ab_assignment='{verify[0].get('ab_assignment', '')}'")
        else:
            logger.warning(f"[HISTORY-SAVE] VERIFICATION FAILED: Could not find chat {chat.id} after save!")

        # Keep only last 50 chats
        client.query("""
            MATCH (c:ChatHistory)
            WITH c ORDER BY c.timestamp DESC
            SKIP 50
            DELETE c
        """)

        logger.info(f"[HISTORY-SAVE] Saved chat to history: {chat.id}, query: {chat.query[:50]}...")
        return chat
    except Exception as e:
        logger.error(f"Failed to save chat to history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save chat: {str(e)}")


@router.get("/history/{chat_id}")
async def get_chat(chat_id: str) -> Dict[str, Any]:
    """Get a specific chat session by ID."""
    client = _get_client()
    result = client.query("""
        MATCH (c:ChatHistory {id: $id})
        RETURN c.id AS id, c.query AS query, c.answer AS answer,
               c.timestamp AS timestamp, c.citations AS citations,
               c.experts AS experts, c.commissioni AS commissioni,
               c.balance AS balance, c.compass AS compass,
               c.topic_stats AS topic_stats,
               c.baseline_answer AS baseline_answer, c.ab_assignment AS ab_assignment
    """, {"id": chat_id})

    if not result:
        raise HTTPException(status_code=404, detail="Chat not found")

    r = result[0]
    return {
        "id": r["id"],
        "query": r["query"],
        "answer": r["answer"],
        "timestamp": r["timestamp"],
        "citations": json.loads(r["citations"]) if r.get("citations") else [],
        "experts": json.loads(r["experts"]) if r.get("experts") else [],
        "commissioni": json.loads(r["commissioni"]) if r.get("commissioni") else [],
        "balance": json.loads(r["balance"]) if r.get("balance") else None,
        "compass": json.loads(r["compass"]) if r.get("compass") else None,
        "topic_stats": json.loads(r["topic_stats"]) if r.get("topic_stats") else None,
        "baseline_answer": r.get("baseline_answer") or None,
        "ab_assignment": json.loads(r["ab_assignment"]) if r.get("ab_assignment") else None,
    }


class BaselineExpertsRequest(BaseModel):
    """Request body for baseline-experts endpoint."""
    baseline_text: Optional[str] = None


@router.post("/history/{chat_id}/baseline-experts")
async def get_baseline_experts(chat_id: str, body: BaselineExpertsRequest) -> Dict[str, Any]:
    """
    Extract deputies mentioned in the baseline text and compute their authority scores.
    Used for A/B comparison: shows which deputies the baseline cited, with computed
    authority scores for side-by-side comparison with the system's expert selection.

    The baseline text is passed in the request body (from evaluation_set.json on the client)
    since Neo4j may not have it stored for older chats.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from .query import get_services
    from ..services.authority.coalition_logic import CoalitionLogic
    from ..models.evidence import normalize_party_name

    client = _get_client()

    # Get chat query from Neo4j
    result = client.query("""
        MATCH (c:ChatHistory {id: $id})
        RETURN c.query AS query, c.baseline_answer AS baseline_answer
    """, {"id": chat_id})

    if not result:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat_data = result[0]
    query_text = chat_data.get("query") or ""

    # Prefer baseline text from request body (always up-to-date from evaluation_set.json),
    # fall back to what's stored in Neo4j for backwards compatibility
    baseline_text = body.baseline_text or chat_data.get("baseline_answer") or ""

    if not baseline_text:
        return {"experts": []}

    # Fetch all deputies with names from Neo4j.
    # Group name lives on the ParliamentaryGroup node connected via MEMBER_OF_GROUP,
    # not as a direct property on Deputy.
    deputies_result = client.query("""
        MATCH (d:Deputy)
        WHERE d.first_name IS NOT NULL AND d.last_name IS NOT NULL
        OPTIONAL MATCH (d)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WHERE mg.end_date IS NULL
        WITH d, collect(g.name)[0] AS group_name
        RETURN d.id AS id, d.first_name AS first_name, d.last_name AS last_name,
               coalesce(group_name, 'MISTO') AS group_name,
               d.deputy_card AS camera_profile_url,
               d.profession AS profession, d.education AS education
    """)

    # Check which deputy names appear in the baseline text.
    # Try both "Nome Cognome" and "Cognome Nome" orderings:
    # Italian parliamentary texts (and NotebookLM) often cite deputies as "Cognome Nome".
    text_lower = baseline_text.lower()
    matched_deputies = []
    for dep in deputies_result:
        fn = (dep.get("first_name") or "").strip()
        ln = (dep.get("last_name") or "").strip()
        if not fn or not ln:
            continue
        if f"{fn} {ln}".lower() in text_lower or f"{ln} {fn}".lower() in text_lower:
            matched_deputies.append(dep)

    logger.info(f"[BASELINE-EXPERTS] Deputies from Neo4j: {len(deputies_result)}, matched: {len(matched_deputies)}")
    logger.info(f"[BASELINE-EXPERTS] Matched names: {[(d.get('first_name'), d.get('last_name')) for d in matched_deputies]}")
    if not matched_deputies:
        # Log a sample of names to diagnose mismatches
        sample = [(dep.get("first_name"), dep.get("last_name")) for dep in deputies_result[:10]]
        logger.info(f"[BASELINE-EXPERTS] No match. baseline_text length={len(baseline_text)}, sample deputies={sample}")
        return {"experts": []}

    matched_ids = [d["id"] for d in matched_deputies]

    # Compute authority scores for matched deputies
    services = get_services()
    query_embedding = await asyncio.get_running_loop().run_in_executor(
        None, lambda: services["retrieval"].embed_query(query_text)
    )

    def _compute_single(sid):
        return sid, services["authority"].compute_authority(sid, query_embedding)

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(matched_ids)))) as pool:
        futures = [loop.run_in_executor(pool, _compute_single, sid) for sid in matched_ids]
        auth_results = await asyncio.gather(*futures)

    authority_scores = {sid: res["total_score"] for sid, res in auth_results}
    authority_details = {sid: res for sid, res in auth_results}

    # Fetch committee membership for matched deputies
    committees_result = client.query("""
        UNWIND $ids AS sid
        MATCH (d:Deputy {id: sid})
        OPTIONAL MATCH (d)-[mc:MEMBER_OF_COMMITTEE]->(c:Committee)
        WHERE mc.end_date IS NULL OR mc.end_date >= date()
        RETURN sid, collect(c.name)[0] AS current_committee,
               d.institutional_role AS institutional_role
    """, {"ids": matched_ids})

    committees_map = {r["sid"]: r for r in committees_result}
    dep_map = {d["id"]: d for d in matched_deputies}

    coalition_logic = CoalitionLogic()
    experts = []

    for dep_id in matched_ids:
        dep = dep_map.get(dep_id)
        if not dep:
            continue

        auth = authority_details.get(dep_id, {})
        components = auth.get("components", {})
        committee_info = committees_map.get(dep_id, {})
        coalition = coalition_logic.get_coalition(dep.get("group_name", ""))

        experts.append({
            "id": dep_id,
            "first_name": dep.get("first_name", ""),
            "last_name": dep.get("last_name", ""),
            "group": normalize_party_name(dep.get("group_name", "")),
            "coalition": coalition,
            "authority_score": round(authority_scores.get(dep_id, 0.0), 2),
            "relevant_speeches_count": 0,
            "camera_profile_url": dep.get("camera_profile_url"),
            "profession": dep.get("profession"),
            "education": dep.get("education"),
            "committee": committee_info.get("current_committee"),
            "institutional_role": committee_info.get("institutional_role"),
            "score_breakdown": {
                "speeches": round(components.get("interventions", 0), 2),
                "acts": round(components.get("acts", 0), 2),
                "committee": round(components.get("committee", 0), 2),
                "profession": round(components.get("profession", 0), 2),
                "education": round(components.get("education", 0), 2),
                "role": round(components.get("role", 0), 2),
            },
        })

    experts.sort(key=lambda e: e["authority_score"], reverse=True)
    return {"experts": experts}


@router.delete("/history/{chat_id}")
async def delete_chat(chat_id: str) -> Dict[str, Any]:
    """Delete a chat from history and its associated survey/rating."""
    client = _get_client()
    # Delete associated A/B survey and simple rating if any
    client.query("""
        MATCH (s:SurveyEvaluation {chat_id: $id})
        DELETE s
    """, {"id": chat_id})
    client.query("""
        MATCH (r:SimpleRating {chat_id: $id})
        DELETE r
    """, {"id": chat_id})
    result = client.query("""
        MATCH (c:ChatHistory {id: $id})
        DELETE c
        RETURN count(*) AS deleted
    """, {"id": chat_id})

    if not result or result[0]["deleted"] == 0:
        raise HTTPException(status_code=404, detail="Chat not found")

    return {"deleted": True, "id": chat_id}


@router.delete("/history")
async def clear_history() -> Dict[str, Any]:
    """Clear all chat history and associated surveys/ratings."""
    client = _get_client()
    # Delete all A/B surveys and simple ratings first
    client.query("MATCH (s:SurveyEvaluation) DELETE s")
    client.query("MATCH (r:SimpleRating) DELETE r")
    result = client.query("""
        MATCH (c:ChatHistory)
        WITH c, count(*) AS total
        DELETE c
        RETURN total
    """)
    count = result[0]["total"] if result else 0
    return {"cleared": True, "count": count}
