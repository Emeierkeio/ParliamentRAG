"""NER entity retrieval channel.

Retrieves chunks that contain specific law references or person names
in their lawRefs/personRefs properties (populated by Phase 4 NER enrichment).
Only activated when query contains entity patterns (gated by engine).
"""
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..neo4j_client import Neo4jClient
from ...models.evidence import normalize_speaker_name, normalize_party_name
from ...config import get_config

logger = logging.getLogger(__name__)


class NERChannel:
    """Retrieves chunks by NER entity match on lawRefs/personRefs."""

    def __init__(self, neo4j_client: Neo4jClient):
        self.client = neo4j_client
        self.config = get_config()

    def retrieve(
        self,
        entity_filter: Dict[str, list],
        top_k: int = 50,
        chambers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks matching entity patterns.

        Args:
            entity_filter: {"laws": ["decreto 231", ...], "persons": ["Meloni", ...]}
            top_k: Max results
            chambers: Optional chamber filter

        Returns:
            List of result dicts matching sparse_channel format
        """
        chambers = chambers or ["camera", "senato"]

        # Build WHERE clause for lawRefs and personRefs
        where_parts: list[str] = []
        params: dict = {"chambers": chambers, "top_k": top_k}

        if entity_filter.get("laws"):
            law_conditions = []
            for i, term in enumerate(entity_filter["laws"]):
                param_key = f"law_{i}"
                law_conditions.append(
                    f"ANY(ref IN c.lawRefs WHERE toLower(ref) CONTAINS toLower(${param_key}))"
                )
                params[param_key] = term
            where_parts.append(f"({' OR '.join(law_conditions)})")

        if entity_filter.get("persons"):
            person_conditions = []
            for i, term in enumerate(entity_filter["persons"]):
                param_key = f"person_{i}"
                person_conditions.append(
                    f"ANY(ref IN c.personRefs WHERE toLower(ref) CONTAINS toLower(${param_key}))"
                )
                params[param_key] = term
            where_parts.append(f"({' OR '.join(person_conditions)})")

        if not where_parts:
            logger.debug("NER channel: no entity filters, skipping")
            return []

        entity_clause = " OR ".join(where_parts)

        cypher = f"""
        MATCH (c:Chunk)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
        WHERE ({entity_clause})
        MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
        WHERE s.chamber IN $chambers
        OPTIONAL MATCH (speaker)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
        WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= date())
        OPTIONAL MATCH (speaker)-[mg_now:MEMBER_OF_GROUP]->(g_now:ParliamentaryGroup)
        WHERE mg_now.end_date IS NULL
        RETURN c.id AS chunk_id,
               c.text AS chunk_text,
               c.embedding AS embedding,
               i.id AS speech_id,
               i.text AS text,
               speaker.id AS speaker_id,
               speaker.first_name AS speaker_first_name,
               speaker.last_name AS speaker_last_name,
               CASE WHEN 'GovernmentMember' IN labels(speaker) THEN 'GovernmentMember' ELSE 'Deputy' END AS speaker_type,
               g.name AS party,
               g_now.name AS current_party,
               s.id AS session_id,
               s.date AS session_date,
               s.number AS session_number,
               d.title AS debate_title
        LIMIT $top_k
        """

        try:
            t0 = time.perf_counter()
            records = self.client.query(cypher, params)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info("NER channel Cypher: %.1fms, %d results", elapsed_ms, len(records))
            return self._process_results(records)
        except Exception as e:
            logger.warning(
                "NER channel: query failed (lawRefs/personRefs may not be populated yet): %s. "
                "Returning empty list.",
                e,
            )
            return []

    def _process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert raw Neo4j records to structured evidence dicts."""
        processed = []
        config = get_config()

        for row in results:
            try:
                party = row.get("party")
                current_party_raw = row.get("current_party")
                speaker_role = row.get("speaker_type", "Deputy")

                if party is None and speaker_role != "GovernmentMember":
                    logger.debug(
                        "Skipping chunk %s: no historical group for speaker %s at %s",
                        row.get("chunk_id"),
                        row.get("speaker_last_name"),
                        row.get("session_date"),
                    )
                    continue

                if speaker_role == "GovernmentMember":
                    party = party or "GOVERNO"
                    coalition = "governo"
                    party_changed = False
                    current_party_display = None
                else:
                    coalition = config.get_coalition(party) if party else "opposizione"
                    historical_display = normalize_party_name(party)
                    current_party_display = (
                        normalize_party_name(current_party_raw) if current_party_raw else None
                    )
                    party_changed = bool(
                        current_party_display and current_party_display != historical_display
                    )

                # Parse session date
                session_date = row.get("session_date")
                if session_date is not None:
                    if hasattr(session_date, "to_native"):
                        date_obj = session_date.to_native()
                    elif isinstance(session_date, str) and session_date:
                        try:
                            date_obj = datetime.strptime(session_date, "%Y-%m-%d").date()
                        except ValueError:
                            try:
                                date_obj = datetime.strptime(session_date, "%d/%m/%Y").date()
                            except ValueError:
                                date_obj = datetime.now().date()
                    else:
                        date_obj = datetime.now().date()
                else:
                    date_obj = datetime.now().date()

                chunk_text = row.get("chunk_text", "")

                processed.append({
                    "evidence_id": row.get("chunk_id", ""),
                    "doc_id": row.get("session_id", ""),
                    "speech_id": row.get("speech_id", ""),
                    "speaker_id": row.get("speaker_id", ""),
                    "speaker_name": normalize_speaker_name(
                        row.get("speaker_first_name", ""),
                        row.get("speaker_last_name", ""),
                    ),
                    "speaker_role": speaker_role,
                    "party": normalize_party_name(party),
                    "coalition": coalition,
                    "party_changed": party_changed,
                    "current_party": current_party_display if party_changed else None,
                    "date": date_obj,
                    "chunk_text": chunk_text,
                    "quote_text": chunk_text,
                    "text": row.get("text", ""),
                    "debate_title": row.get("debate_title"),
                    "session_number": row.get("session_number", 0),
                    # similarity=1.0 for entity matches — RRF uses rank position, not raw score
                    "similarity": 1.0,
                    "embedding": row.get("embedding"),
                    "retrieval_channel": "ner",
                })

            except Exception as e:
                logger.error("NER channel: error processing result: %s", e)
                continue

        return processed
