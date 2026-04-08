"""
generate_summaries.py — AI summary generation for the parliamentary timeline.

Reads Session/Debate/Speech data from Neo4j, generates AI summaries via
OpenAI gpt-4.1-mini, and writes them back as node properties or creates
SpeakerDebateSummary nodes.

Schema written:
  - Session.recapIt, Session.recapEn
  - Debate.recapIt, Debate.recapEn
  - SpeakerDebateSummary {id, summaryIt, summaryEn, speechCount, phases,
                           partySnapshot, debateId, speakerId}
  - (Deputy|GovernmentMember)-[:HAS_DEBATE_SUMMARY]->(SpeakerDebateSummary)
  - (SpeakerDebateSummary)-[:FOR_DEBATE]->(Debate)

Usage (CLI):
    python build/generate_summaries.py --dry-run
    python build/generate_summaries.py --concurrency 10

Usage (dry-run):
    python build/generate_summaries.py --dry-run
    make generate-summaries DRY_RUN=1
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI model
# ---------------------------------------------------------------------------

MODEL = "gpt-4.1-mini"

# Cost estimate constants (per million tokens, as of 2025)
# gpt-4.1-mini: $0.40/M input + $1.60/M output
COST_INPUT_PER_M = 0.40
COST_OUTPUT_PER_M = 1.60

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _session_prompt_it(date: str, debate_titles: list[str]) -> str:
    titles_str = "; ".join(debate_titles)
    return (
        f"Scrivi un riassunto di 2-3 frasi della sessione parlamentare del {date}. "
        f"Argomenti trattati: {titles_str}. "
        "Il riassunto deve essere in italiano, chiaro e conciso."
    )


def _session_prompt_en(date: str, debate_titles: list[str]) -> str:
    titles_str = "; ".join(debate_titles)
    return (
        f"Write a 2-3 sentence summary of the parliamentary session of {date}. "
        f"Topics discussed: {titles_str}. "
        "The summary must be in English, clear and concise."
    )


def _debate_prompt_it(title: str, speech_excerpts: str) -> str:
    return (
        f"Scrivi un riassunto di 3-5 frasi del seguente dibattito parlamentare: '{title}'. "
        f"Testi degli interventi: {speech_excerpts}. "
        "Il riassunto deve essere in italiano e coprire i punti principali."
    )


def _debate_prompt_en(title: str, speech_excerpts: str) -> str:
    return (
        f"Write a 3-5 sentence summary of the following parliamentary debate: '{title}'. "
        f"Speech texts: {speech_excerpts}. "
        "The summary must be in English and cover the main points."
    )


def _speaker_prompt_it(speaker_name: str, party: str, debate_title: str, speech_texts: str) -> str:
    return (
        f"Scrivi un riassunto di 2-3 frasi della posizione di {speaker_name} ({party}) "
        f"nel dibattito '{debate_title}'. "
        f"Testi: {speech_texts}."
    )


def _speaker_prompt_en(speaker_name: str, party: str, debate_title: str, speech_texts: str) -> str:
    return (
        f"Write a 2-3 sentence summary of the position of {speaker_name} ({party}) "
        f"in the debate '{debate_title}'. "
        f"Speech texts: {speech_texts}."
    )


# ---------------------------------------------------------------------------
# SummaryGenerator class
# ---------------------------------------------------------------------------

class SummaryGenerator:
    """Reads from Neo4j, generates AI summaries, writes results back."""

    def __init__(
        self,
        driver,
        openai_client,
        concurrency: int = 10,
    ) -> None:
        self._driver = driver
        self._client = openai_client
        self._sem = asyncio.Semaphore(concurrency)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_all(self) -> dict:
        """Main entry point: generate summaries for all pending sessions/debates/speakers.

        Returns stats dict with counts.
        """
        start = time.monotonic()

        # Load all pending sessions (resumable: skip sessions with recapIt already set)
        sessions = self._fetch_pending_sessions()
        logger.info("Pending sessions: %d", len(sessions))

        sessions_done = 0
        debates_done = 0
        speakers_done = 0
        api_calls = 0

        try:
            from tqdm import tqdm
            session_iter = tqdm(sessions, desc="Sessions", unit="session")
        except ImportError:
            session_iter = sessions

        for session in session_iter:
            s_id = session["id"]
            s_date = session["date"]

            # Fetch all debates for this session
            debates = self._fetch_debates_for_session(s_id)
            debate_titles = [d["title"] for d in debates if d.get("title")]

            # Generate session recap (IT + EN) in parallel
            if debate_titles:
                recap_it, recap_en = await self._generate_pair(
                    _session_prompt_it(str(s_date), debate_titles),
                    _session_prompt_en(str(s_date), debate_titles),
                    max_tokens=200,
                )
                api_calls += 2
                self._write_session_recap(s_id, recap_it, recap_en)
                sessions_done += 1
            else:
                logger.debug("Session %s has no debates — skipping recap", s_id)

            # Process each debate
            for debate in debates:
                d_id = debate["id"]
                d_title = debate.get("title", "")

                # Skip debates that already have a recap (resumability for debates)
                if debate.get("recapIt"):
                    continue

                speeches = self._fetch_speeches_for_debate(d_id)

                # Skip short debates (fewer than 3 speeches)
                if len(speeches) < 3:
                    logger.debug("Debate %s has %d speech(es) — skipping AI summary", d_id, len(speeches))
                else:
                    combined = " ".join(s["text"] for s in speeches if s.get("text"))[:4000]
                    recap_it, recap_en = await self._generate_pair(
                        _debate_prompt_it(d_title, combined),
                        _debate_prompt_en(d_title, combined),
                        max_tokens=300,
                    )
                    api_calls += 2
                    self._write_debate_recap(d_id, recap_it, recap_en)
                    debates_done += 1

                # Speaker summaries — group speeches by speaker
                speaker_map: dict[str, dict] = {}
                for speech in speeches:
                    sp_id = speech.get("speakerId")
                    if not sp_id:
                        continue
                    if sp_id not in speaker_map:
                        speaker_map[sp_id] = {
                            "speakerId": sp_id,
                            "speakerName": speech.get("speakerName", ""),
                            "party": speech.get("party", ""),
                            "texts": [],
                            "phases": set(),
                            "speechCount": 0,
                        }
                    speaker_map[sp_id]["texts"].append(speech.get("text", ""))
                    if speech.get("phaseId"):
                        speaker_map[sp_id]["phases"].add(speech["phaseId"])
                    speaker_map[sp_id]["speechCount"] += 1

                # Generate speaker summaries (can be parallel per debate)
                tasks = []
                for sp_id, sp_data in speaker_map.items():
                    combined_text = " ".join(sp_data["texts"])[:4000]
                    if len(combined_text) < 100:
                        continue  # Too short for meaningful summary
                    tasks.append(self._generate_speaker_summary(
                        debate_id=d_id,
                        debate_title=d_title,
                        speaker_id=sp_id,
                        speaker_name=sp_data["speakerName"],
                        party=sp_data["party"],
                        combined_text=combined_text,
                        speech_count=sp_data["speechCount"],
                        phases=list(sp_data["phases"]),
                    ))

                if tasks:
                    results = await asyncio.gather(*tasks)
                    created = sum(r for r in results if r)
                    speakers_done += created
                    api_calls += created * 2

            logger.info(
                "Session %s: %d debates, %d speaker summaries generated",
                s_date, len(debates), speakers_done,
            )

        elapsed = time.monotonic() - start
        logger.info(
            "Complete: sessions=%d, debates=%d, speaker_summaries=%d, api_calls=%d, elapsed=%.1fs",
            sessions_done, debates_done, speakers_done, api_calls, elapsed,
        )
        return {
            "sessions_processed": sessions_done,
            "debates_processed": debates_done,
            "speaker_summaries_created": speakers_done,
            "api_calls": api_calls,
            "elapsed_seconds": elapsed,
        }

    async def dry_run(self) -> None:
        """Count pending items, estimate tokens/cost, print report, exit."""
        sessions = self._fetch_pending_sessions()
        n_sessions = len(sessions)

        n_debates = 0
        n_speakers = 0
        total_chars = 0

        for session in sessions:
            s_id = session["id"]
            s_date = session["date"]
            debates = self._fetch_debates_for_session(s_id)
            debate_titles = [d["title"] for d in debates if d.get("title")]
            total_chars += len("; ".join(debate_titles)) * 2  # IT + EN prompts (approx)

            for debate in debates:
                if debate.get("recapIt"):
                    continue
                d_id = debate["id"]
                speeches = self._fetch_speeches_for_debate(d_id)

                if len(speeches) >= 3:
                    n_debates += 1
                    combined = " ".join(s["text"] for s in speeches if s.get("text"))[:4000]
                    total_chars += len(combined) * 2  # IT + EN

                # Count speakers
                speaker_ids: set[str] = set()
                for speech in speeches:
                    sp_id = speech.get("speakerId")
                    if not sp_id:
                        continue
                    speaker_ids.add(sp_id)

                # Rough estimate: each speaker pair
                n_speakers += len(speaker_ids)
                total_chars += len(speaker_ids) * 400  # estimated chars per speaker

        estimated_tokens = total_chars / 4
        estimated_cost = (
            (estimated_tokens / 1_000_000) * COST_INPUT_PER_M
            + (estimated_tokens * 0.3 / 1_000_000) * COST_OUTPUT_PER_M
        )

        print(f"\nDRY RUN — no data written\n{'='*50}")
        print(f"Pending: {n_sessions} sessions, {n_debates} debates, {n_speakers} speaker summaries")
        print(f"Estimated tokens : {estimated_tokens:,.0f}")
        print(f"Estimated cost   : ${estimated_cost:.2f} (at ${COST_INPUT_PER_M}/1M input + ${COST_OUTPUT_PER_M}/1M output)")
        print(f"{'='*50}\n")

    # ------------------------------------------------------------------
    # OpenAI helpers
    # ------------------------------------------------------------------

    async def _chat(self, prompt: str, max_tokens: int = 300) -> str:
        """Call gpt-4.1-mini with rate-limiting semaphore. Returns text."""
        async with self._sem:
            response = await self._client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()

    async def _generate_pair(
        self,
        prompt_it: str,
        prompt_en: str,
        max_tokens: int = 300,
    ) -> tuple[str, str]:
        """Generate IT and EN summaries in parallel."""
        results = await asyncio.gather(
            self._chat(prompt_it, max_tokens),
            self._chat(prompt_en, max_tokens),
            return_exceptions=True,
        )
        recap_it = results[0] if not isinstance(results[0], Exception) else ""
        recap_en = results[1] if not isinstance(results[1], Exception) else ""
        if isinstance(results[0], Exception):
            logger.warning("IT summary failed: %s", results[0])
        if isinstance(results[1], Exception):
            logger.warning("EN summary failed: %s", results[1])
        return recap_it, recap_en

    async def _generate_speaker_summary(
        self,
        debate_id: str,
        debate_title: str,
        speaker_id: str,
        speaker_name: str,
        party: str,
        combined_text: str,
        speech_count: int,
        phases: list[str],
    ) -> bool:
        """Generate speaker summary and write SpeakerDebateSummary node. Returns True on success."""
        try:
            summary_it, summary_en = await self._generate_pair(
                _speaker_prompt_it(speaker_name, party, debate_title, combined_text),
                _speaker_prompt_en(speaker_name, party, debate_title, combined_text),
                max_tokens=200,
            )
            sds_id = f"{debate_id}_{speaker_id}"
            self._write_speaker_summary(
                sds_id=sds_id,
                debate_id=debate_id,
                speaker_id=speaker_id,
                summary_it=summary_it,
                summary_en=summary_en,
                speech_count=speech_count,
                phases=phases,
                party_snapshot=party,
            )
            return True
        except Exception as exc:
            logger.warning("Speaker summary failed for %s in %s: %s", speaker_id, debate_id, exc)
            return False

    # ------------------------------------------------------------------
    # Neo4j read helpers
    # ------------------------------------------------------------------

    def _fetch_pending_sessions(self) -> list[dict]:
        """Return sessions WHERE recapIt IS NULL (resumable)."""
        cypher = """
MATCH (s:Session)
WHERE s.recapIt IS NULL
RETURN s.id AS id, s.date AS date
ORDER BY s.date
"""
        with self._driver.session() as neo_session:
            result = neo_session.run(cypher)
            return [{"id": r["id"], "date": r["date"]} for r in result]

    def _fetch_debates_for_session(self, session_id: str) -> list[dict]:
        """Return debates for a session, including their current recapIt (for resumability)."""
        cypher = """
MATCH (s:Session {id: $session_id})-[:HAS_DEBATE]->(d:Debate)
RETURN d.id AS id, d.title AS title, d.recapIt AS recapIt
ORDER BY d.id
"""
        with self._driver.session() as neo_session:
            result = neo_session.run(cypher, session_id=session_id)
            return [
                {"id": r["id"], "title": r["title"], "recapIt": r["recapIt"]}
                for r in result
            ]

    def _fetch_speeches_for_debate(self, debate_id: str) -> list[dict]:
        """Return all speeches for a debate, with speaker info."""
        cypher = """
MATCH (d:Debate {id: $debate_id})<-[:HAS_DEBATE]-(:Session)
MATCH (d)<-[:BELONGS_TO_DEBATE]-(p:Phase)-[:CONTAINS_SPEECH]->(sp:Speech)
OPTIONAL MATCH (sp)-[:SPOKEN_BY]->(dep:Deputy)
OPTIONAL MATCH (sp)-[:SPOKEN_BY]->(gm:GovernmentMember)
WITH sp, p,
     coalesce(dep, gm) AS speaker,
     CASE WHEN dep IS NOT NULL THEN dep.id
          WHEN gm IS NOT NULL THEN gm.id
          ELSE NULL END AS speakerId,
     CASE WHEN dep IS NOT NULL THEN dep.firstName + ' ' + dep.lastName
          WHEN gm IS NOT NULL THEN gm.firstName + ' ' + gm.lastName
          ELSE NULL END AS speakerName,
     CASE WHEN dep IS NOT NULL THEN dep.party
          WHEN gm IS NOT NULL THEN gm.role
          ELSE NULL END AS party
RETURN sp.text AS text,
       sp.id AS speechId,
       p.id AS phaseId,
       speakerId,
       speakerName,
       party
ORDER BY p.id, sp.id
"""
        with self._driver.session() as neo_session:
            result = neo_session.run(cypher, debate_id=debate_id)
            return [
                {
                    "text": r["text"] or "",
                    "speechId": r["speechId"],
                    "phaseId": r["phaseId"],
                    "speakerId": r["speakerId"],
                    "speakerName": r["speakerName"] or "",
                    "party": r["party"] or "",
                }
                for r in result
            ]

    # ------------------------------------------------------------------
    # Neo4j write helpers
    # ------------------------------------------------------------------

    def _write_session_recap(self, session_id: str, recap_it: str, recap_en: str) -> None:
        """Write recapIt and recapEn to a Session node."""
        cypher = """
MATCH (s:Session {id: $id})
SET s.recapIt = $recap_it,
    s.recapEn = $recap_en
"""
        with self._driver.session() as neo_session:
            neo_session.run(cypher, id=session_id, recap_it=recap_it, recap_en=recap_en)

    def _write_debate_recap(self, debate_id: str, recap_it: str, recap_en: str) -> None:
        """Write recapIt and recapEn to a Debate node."""
        cypher = """
MATCH (d:Debate {id: $id})
SET d.recapIt = $recap_it,
    d.recapEn = $recap_en
"""
        with self._driver.session() as neo_session:
            neo_session.run(cypher, id=debate_id, recap_it=recap_it, recap_en=recap_en)

    def _write_speaker_summary(
        self,
        sds_id: str,
        debate_id: str,
        speaker_id: str,
        summary_it: str,
        summary_en: str,
        speech_count: int,
        phases: list[str],
        party_snapshot: str,
    ) -> None:
        """Create or update SpeakerDebateSummary node with relationships."""
        # Step 1: MERGE the SpeakerDebateSummary node and set properties
        merge_cypher = """
MERGE (sds:SpeakerDebateSummary {id: $id})
SET sds.summaryIt = $summary_it,
    sds.summaryEn = $summary_en,
    sds.speechCount = $speech_count,
    sds.phases = $phases,
    sds.partySnapshot = $party_snapshot,
    sds.debateId = $debate_id,
    sds.speakerId = $speaker_id
"""
        with self._driver.session() as neo_session:
            neo_session.run(
                merge_cypher,
                id=sds_id,
                summary_it=summary_it,
                summary_en=summary_en,
                speech_count=speech_count,
                phases=phases,
                party_snapshot=party_snapshot,
                debate_id=debate_id,
                speaker_id=speaker_id,
            )

        # Step 2: Link to speaker (Deputy or GovernmentMember) via HAS_DEBATE_SUMMARY
        # Use coalesce to handle both node types
        link_speaker_cypher = """
MATCH (sds:SpeakerDebateSummary {id: $sds_id})
OPTIONAL MATCH (d:Deputy {id: $speaker_id})
OPTIONAL MATCH (g:GovernmentMember {id: $speaker_id})
WITH sds, coalesce(d, g) AS sp
WHERE sp IS NOT NULL
MERGE (sp)-[:HAS_DEBATE_SUMMARY]->(sds)
"""
        with self._driver.session() as neo_session:
            neo_session.run(link_speaker_cypher, sds_id=sds_id, speaker_id=speaker_id)

        # Step 3: Link to Debate via FOR_DEBATE
        link_debate_cypher = """
MATCH (sds:SpeakerDebateSummary {id: $sds_id})
MATCH (d:Debate {id: $debate_id})
MERGE (sds)-[:FOR_DEBATE]->(d)
"""
        with self._driver.session() as neo_session:
            neo_session.run(link_debate_cypher, sds_id=sds_id, debate_id=debate_id)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import os
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Generate AI summaries for parliamentary timeline"
    )
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7689")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="thesis2026")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count pending items and estimate cost, without writing",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max parallel OpenAI calls (default: 10)",
    )
    args = parser.parse_args()

    # Validate dependencies
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Error: neo4j package not installed. Run: pip install neo4j", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import AsyncOpenAI
    except ImportError:
        print("Error: openai package not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)

    if not args.dry_run:
        try:
            import tqdm  # noqa: F401
        except ImportError:
            print("Warning: tqdm not installed — no progress bar. Run: pip install tqdm", file=sys.stderr)

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        args.neo4j_uri,
        auth=(args.neo4j_user, args.neo4j_password),
    )

    # OpenAI client — reads OPENAI_API_KEY from environment
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key and not args.dry_run:
        print(
            "Error: OPENAI_API_KEY environment variable not set.",
            file=sys.stderr,
        )
        driver.close()
        sys.exit(1)

    openai_client = AsyncOpenAI(api_key=openai_api_key, max_retries=3)

    generator = SummaryGenerator(
        driver=driver,
        openai_client=openai_client,
        concurrency=args.concurrency,
    )

    try:
        if args.dry_run:
            asyncio.run(generator.dry_run())
        else:
            stats = asyncio.run(generator.generate_all())
            print(
                f"\nSummary generation complete!\n"
                f"  Sessions processed        : {stats['sessions_processed']}\n"
                f"  Debates processed         : {stats['debates_processed']}\n"
                f"  Speaker summaries created : {stats['speaker_summaries_created']}\n"
                f"  Total API calls           : {stats['api_calls']}\n"
                f"  Elapsed time              : {stats['elapsed_seconds']:.1f}s\n"
            )
    finally:
        driver.close()
