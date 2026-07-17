"""
Transcript service — Neo4j queries for the debate transcript viewer API.

Provides four async functions consumed by the transcript router:
  - get_transcript_speeches(): all speeches for a debate in chronological order
  - get_speech_text():          full text of a single speech (lazy-loaded)
  - get_debate_suggestions():   LLM-generated starter questions from debate recap
  - debate_chat_streaming():    debate-scoped RAG chatbot as SSE async generator

All functions accept a Neo4jClient instance (injected by FastAPI Depends).
get_transcript_speeches and get_debate_suggestions also accept a locale string
("it" or "en") to select the correct recap field.

Pitfall notes:
  - Neo4j returns dates as neo4j.time.Date objects -> convert with str(record["date"])
  - Speakers can be Deputy OR GovernmentMember nodes -> use coalesce(dep, gov) pattern
  - ORDER BY p.id, sp.id gives chronological ordering within the debate structure
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from app.config import get_settings
from app.models.transcript import (
    SearchMatch,
    SpeechTextResponse,
    SuggestionsResponse,
    TranscriptResponse,
    TranscriptSearchResponse,
    TranscriptSpeechRow,
)
from app.services.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

_FALLBACK_QUESTIONS_IT = [
    "Chi sono i principali oratori?",
    "Quali temi sono stati discussi?",
    "Quali posizioni politiche sono emerse?",
    "Ci sono stati voti o decisioni?",
]

_FALLBACK_QUESTIONS_EN = [
    "Who are the main speakers?",
    "What topics were discussed?",
    "What political positions emerged?",
    "Were there any votes or decisions?",
]


async def get_transcript_speeches(
    neo4j: Neo4jClient,
    debate_id: str,
    locale: str,
) -> TranscriptResponse:
    """
    Return all speeches for a debate in chronological phase/speech order.

    Two queries:
      1. Debate metadata: title, session date/id/chamber.
      2. All speeches with speaker metadata (Deputy or GovernmentMember via coalesce).

    Returns an empty response (speeches=[]) if the debate is not found.
    """
    recap_field = "recapEn" if locale == "en" else "recapIt"

    # --- Debate metadata + session info ---
    meta_row = neo4j.query_single(
        f"""
        MATCH (d:Debate {{id: $debate_id}})<-[:HAS_DEBATE]-(s:Session)
        RETURN d.title AS title,
               d.{recap_field} AS recap,
               toString(s.date) AS session_date,
               s.id AS session_id,
               s.chamber AS chamber
        """,
        {"debate_id": debate_id},
    )

    if not meta_row:
        return TranscriptResponse(
            debate_id=debate_id,
            debate_title="",
            session_date="",
            session_id="",
            chamber="",
            speeches=[],
        )

    # --- All speeches in chronological order ---
    speech_rows = neo4j.query(
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
        OPTIONAL MATCH (spk)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
          WHERE mg.start_date <= sess.date
            AND (mg.end_date IS NULL OR mg.end_date >= sess.date)
        WITH spk, isGov, p, sp, head(collect(g.name)) AS party
        RETURN sp.id AS speech_id,
               p.id AS phase_id,
               p.title AS phase_title,
               spk.id AS speaker_id,
               spk.first_name AS first_name,
               spk.last_name AS last_name,
               party,
               sp.speakingRole AS speaking_role,
               isGov AS is_government_member
        ORDER BY p.id, sp.id
        """,
        {"debate_id": debate_id},
    )

    speeches = [
        TranscriptSpeechRow(
            speech_id=r["speech_id"],
            phase_id=r["phase_id"],
            phase_title=r["phase_title"] or "",
            speaker_id=r["speaker_id"],
            first_name=r["first_name"] or "",
            last_name=r["last_name"] or "",
            party=r["party"],
            speaking_role=r["speaking_role"],
            is_government_member=bool(r["is_government_member"]),
        )
        for r in speech_rows
    ]

    return TranscriptResponse(
        debate_id=debate_id,
        debate_title=meta_row["title"] or "",
        session_date=str(meta_row["session_date"]),
        session_id=meta_row["session_id"] or "",
        chamber=meta_row["chamber"] or "",
        speeches=speeches,
    )


async def get_speech_text(
    neo4j: Neo4jClient,
    debate_id: str,
    speech_id: str,
) -> SpeechTextResponse:
    """
    Return the full text of a single speech.

    Used by the accordion expand handler to lazy-load speech content.
    Returns empty text if the speech is not found.
    """
    row = neo4j.query_single(
        """
        MATCH (d:Debate {id: $debate_id})-[:HAS_PHASE]->(:Phase)
              -[:CONTAINS_SPEECH]->(sp:Speech {id: $speech_id})
        RETURN sp.id AS speech_id, sp.text AS text
        """,
        {"debate_id": debate_id, "speech_id": speech_id},
    )

    if not row:
        return SpeechTextResponse(speech_id=speech_id, text="")

    return SpeechTextResponse(
        speech_id=row["speech_id"],
        text=row["text"] or "",
    )


async def search_speeches(
    neo4j: Neo4jClient,
    debate_id: str,
    query: str,
) -> TranscriptSearchResponse:
    """
    Full-text search across all speech texts in a debate.

    Uses case-insensitive CONTAINS on sp.text. Returns matching speech IDs
    with a short snippet around the first match occurrence.
    """
    if not query or len(query) < 2:
        return TranscriptSearchResponse(query=query, matches=[])

    rows = neo4j.query(
        """
        MATCH (d:Debate {id: $debate_id})-[:HAS_PHASE]->(p:Phase)
              -[:CONTAINS_SPEECH]->(sp:Speech)
        WHERE toLower(sp.text) CONTAINS toLower($query)
        RETURN sp.id AS speech_id, sp.text AS text
        ORDER BY p.id, sp.id
        """,
        {"debate_id": debate_id, "query": query},
    )

    matches = []
    q_lower = query.lower()
    for r in rows:
        text = r["text"] or ""
        idx = text.lower().find(q_lower)
        # Extract a ~120 char snippet around the match
        start = max(0, idx - 50)
        end = min(len(text), idx + len(query) + 70)
        snippet = ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")
        matches.append(SearchMatch(speech_id=r["speech_id"], snippet=snippet))

    return TranscriptSearchResponse(query=query, matches=matches)


async def get_debate_suggestions(
    neo4j: Neo4jClient,
    debate_id: str,
    locale: str,
) -> SuggestionsResponse:
    """
    Return 3-4 starter questions for the debate chatbot.

    If the debate has a recap, calls gpt-4.1-mini to generate locale-aware
    questions. Falls back to hardcoded questions on LLM error or missing recap.
    """
    recap_field = "recapEn" if locale == "en" else "recapIt"
    fallback = _FALLBACK_QUESTIONS_EN if locale == "en" else _FALLBACK_QUESTIONS_IT

    row = neo4j.query_single(
        f"""
        MATCH (d:Debate {{id: $debate_id}})
        RETURN d.{recap_field} AS recap, d.recapIt AS recapIt, d.title AS title
        """,
        {"debate_id": debate_id},
    )

    # Use Italian recap as universal fallback when locale-specific recap is absent
    recap_text: str | None = None
    if row:
        recap_text = row.get("recap") or row.get("recapIt")

    if not recap_text:
        return SuggestionsResponse(questions=fallback)

    # Generate questions via LLM
    try:
        from openai import AsyncOpenAI

        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        lang_instruction = "Italian" if locale == "it" else "English"
        system_prompt = (
            f"Given this parliamentary debate summary, generate exactly 4 short questions "
            f"(each under 80 characters) in {lang_instruction} that a user might want to ask "
            f"about this debate. Return only the questions, one per line, no numbering."
        )

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": recap_text},
            ],
            max_tokens=200,
            temperature=0.7,
        )

        raw = response.choices[0].message.content or ""
        questions = [line.strip() for line in raw.splitlines() if line.strip()]
        if questions:
            return SuggestionsResponse(questions=questions[:4])

    except Exception:
        pass  # Fall through to hardcoded fallback

    return SuggestionsResponse(questions=fallback)


async def debate_chat_streaming(
    debate_id: str,
    query: str,
    history: list[dict],
    locale: str,
    neo4j: Neo4jClient,
) -> AsyncGenerator[str, None]:
    """
    Debate-scoped RAG chatbot as an async SSE generator.

    Embeds the user query, retrieves chunks only from the specified debate's
    speeches via vector index with debate_id filter, generates a streaming
    answer with citation references, and yields SSE events.

    SSE event types: progress, citations, chunk, done, error.

    Does NOT use _pipeline_semaphore from query.py — operates independently.
    """
    try:
        # Step 1: Embed query
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Embedding query...'})}\n\n"

        settings = get_settings()
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        embed_resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        query_embedding = embed_resp.data[0].embedding

        # Step 2: Retrieve debate-scoped chunks
        # Fetch all chunks from this debate with their embeddings, then rank
        # by cosine similarity in Python. The global vector index misses
        # debates whose chunks aren't in the top-K globally.
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Searching debate content...'})}\n\n"

        import numpy as np

        all_chunks = neo4j.query("""
            MATCH (d:Debate {id: $debate_id})<-[:HAS_DEBATE]-(sess:Session)
            WITH d, sess
            MATCH (d)-[:HAS_PHASE]->(:Phase)-[:CONTAINS_SPEECH]->(sp:Speech)-[:HAS_CHUNK]->(c:Chunk)
            WHERE c.embedding IS NOT NULL
            MATCH (sp)-[:SPOKEN_BY]->(spk)
            WHERE spk:Deputy OR spk:GovernmentMember
            OPTIONAL MATCH (spk)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
              WHERE mg.start_date <= sess.date
                AND (mg.end_date IS NULL OR mg.end_date >= sess.date)
            WITH c, sp, spk, head(collect(g.name)) AS party, c.embedding AS emb
            RETURN c.id AS chunk_id,
                   c.text AS chunk_text,
                   sp.id AS speech_id,
                   spk.id AS speaker_id,
                   spk.first_name + ' ' + spk.last_name AS speaker_name,
                   party,
                   emb
        """, {
            "debate_id": debate_id,
        })

        # Compute cosine similarity in Python
        logger.info("Debate chat: fetched %d chunks for debate %s", len(all_chunks), debate_id)
        if all_chunks:
            q_vec = np.array(query_embedding, dtype=np.float32)
            q_norm = np.linalg.norm(q_vec)
            scored = []
            for ch in all_chunks:
                emb = ch.get("emb")
                if not emb:
                    continue
                c_vec = np.array(emb, dtype=np.float32)
                score = float(np.dot(q_vec, c_vec) / (q_norm * np.linalg.norm(c_vec) + 1e-10))
                if score >= 0.25:
                    scored.append({**ch, "score": score})
            scored.sort(key=lambda x: x["score"], reverse=True)
            chunks = scored[:15]
        else:
            chunks = []

        # Step 3: Handle no results
        if not chunks:
            yield f"data: {json.dumps({'type': 'chunk', 'content': 'No relevant content found in this debate for your question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Step 4: Build citations — deduplicate by speech_id
        seen_speeches: dict[str, int] = {}
        citations: list[dict] = []
        for chunk in chunks:
            sid = chunk["speech_id"]
            if sid not in seen_speeches:
                idx = len(citations) + 1
                citation = {
                    "index": idx,
                    "speech_id": sid,
                    "speaker_name": chunk["speaker_name"] or "",
                    "party": chunk["party"],
                    "chunk_text": (chunk["chunk_text"] or "")[:200],
                }
                citations.append(citation)
                seen_speeches[sid] = idx

        # Step 5: Yield citations event before text generation
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

        # Step 6: Build LLM context and generate streaming response
        context_parts = []
        for chunk in chunks:
            ref = seen_speeches.get(chunk["speech_id"], "?")
            context_parts.append(
                f"[{ref}] {chunk['speaker_name']} ({chunk['party'] or 'N/A'}): {chunk['chunk_text']}"
            )
        context_text = "\n\n".join(context_parts)

        lang = "Italian" if locale == "it" else "English"
        system_prompt = (
            f"You are an expert assistant analyzing a specific parliamentary debate transcript.\n"
            f"Answer the user's question based ONLY on the provided speech excerpts.\n"
            f"Use citation references like [1], [2] to indicate which speech your answer draws from.\n"
            f"Respond in {lang}.\n"
            f"If the provided excerpts don't contain enough information, say so honestly.\n\n"
            f"Speech excerpts:\n{context_text}"
        )

        messages_for_llm = [{"role": "system", "content": system_prompt}]
        for h in history:
            messages_for_llm.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages_for_llm.append({"role": "user", "content": query})

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Generating answer...'})}\n\n"

        stream = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages_for_llm,
            max_tokens=1500,
            temperature=0.3,
            stream=True,
        )

        async for event in stream:
            delta = event.choices[0].delta
            if delta.content:
                yield f"data: {json.dumps({'type': 'chunk', 'content': delta.content})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception:
        logger.exception("Error in debate_chat_streaming for debate_id=%s", debate_id)
        yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred while processing your question.'})}\n\n"
