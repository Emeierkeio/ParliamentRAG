"""
Enrich evaluation_set.json with baseline metrics for party coverage and citation fidelity.

For each topic in evaluation_set.json this script:
  1. Parses inline citations from baseline_answer
     (format: **Surname** (Group, DD/MM/YYYY) ... «quote»)
  2. Queries Neo4j to verify each quote against its source chunk
  3. Computes:
     - baseline_party_coverage  : unique groups cited / 10
     - baseline_citation_fidelity: verbatim-verified citations / total citations
  4. Saves the results back into evaluation_set.json under each topic entry

Results are comparable with the system metrics computed in evaluation.py because
they use the same normalization (_normalize_for_verbatim) and the same denominator
logic (citations_total, not citations_valid).

Usage (from backend/ directory, with venv active):
    python scripts/enrich_evaluation_set.py [--dry-run]

Options:
    --dry-run   Print metrics without writing to evaluation_set.json
"""

import sys
import re
import json
import unicodedata
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add backend/ to path so app.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.neo4j_client import Neo4jClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("enrich_evaluation_set")

EVAL_SET_PATH = Path(__file__).parent.parent / "evaluation_set.json"
ALL_PARTIES = 10

# Same keyword sets used in evaluation.py for party normalisation
PARTY_KEYWORDS = [
    ("Fratelli d'Italia",   ["Fratelli d'Italia", "FdI"]),
    ("Lega",                ["Lega"]),
    ("Forza Italia",        ["Forza Italia"]),
    ("Noi Moderati",        ["Noi Moderati"]),
    ("Partito Democratico", ["Partito Democratico", "PD"]),
    ("Movimento 5 Stelle",  ["Movimento 5 Stelle", "M5S"]),
    ("Azione",              ["Azione"]),
    ("Italia Viva",         ["Italia Viva"]),
    ("Alleanza Verdi e Sinistra", ["Alleanza Verdi", "AVS", "Verdi e Sinistra"]),
    ("Misto",               ["Misto"]),
]

# Pattern: **Name** (Group, DD/MM/YYYY) [text] «quote»
# Also handles plain (non-bold) format: Name (Group, DD/MM/YYYY) [text] «quote»
# The \*{0,2} makes the bold markers optional.
# Name must start with a capital letter to avoid false positives.
_CITATION_RE = re.compile(
    r'\*{0,2}'
    r'([A-ZÀÈÉÌÎÒÓÙÚ][a-zA-ZÀ-öø-ÿ\']*(?:\s+[A-ZÀÈÉÌÎÒÓÙÚ][a-zA-ZÀ-öø-ÿ\']*)*)'
    r'\*{0,2}'
    r'\s*\(([^()]*(?:\([^)]*\)[^()]*)*),\s*(\d{2}/\d{2}/\d{4})\)[^«]*«([^»]+)»'
)

# Italian role/title tokens that indicate the captured "name" is not a speaker
# surname but a parliamentary role description (e.g. "L'onorevole", "Consiglio").
_ROLE_TOKENS = frozenset({
    "onorevole", "esponente", "legislatore", "legislatrice",
    "deputata", "deputato", "parlamentare", "senatore", "senatrice",
    "consigliere", "consigliera", "presidente", "vicepresidente",
    "ministro", "ministra", "sottosegretario", "sottosegretaria",
    "consiglio",  # catches "La Presidente del Consiglio"
})

# Fallback pattern for role-based citations:
#   La deputata (Partito Democratico, 04/05/2023) ... «quote»
#   Il legislatore (Lega, 04/05/2023) ... «quote»
# Captures citations where the text before (Group, Date) starts with a
# definite article but contains lowercase role words that _CITATION_RE misses.
_CITATION_ROLE_RE = re.compile(
    r"((?:Il|La|L'|Lo|I|Gli|Le)\s+[^(«\n]+?)"
    r'\s*\(([^()]*(?:\([^)]*\)[^()]*)*),\s*(\d{2}/\d{2}/\d{4})\)[^«]*«([^»]+)»'
)


def _normalize(text: str) -> str:
    """Same normalisation as evaluation.py _normalize_for_verbatim."""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _canonical_party(group_text: str) -> Optional[str]:
    """Map a group label from the baseline text to a canonical party name."""
    group_lower = group_text.lower()
    for canonical, keywords in PARTY_KEYWORDS:
        for kw in keywords:
            if kw.lower() in group_lower:
                return canonical
    return None


def _date_to_iso(date_str: str) -> Optional[str]:
    """Convert DD/MM/YYYY → YYYY-MM-DD for Neo4j date() comparisons."""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_citations(baseline_answer: str) -> list[dict]:
    """
    Extract structured citations from a baseline answer text.

    Handles two formats:
    1. Name-based: **Surname** (Group, DD/MM/YYYY) ... «quote»
                   Surname (Group, DD/MM/YYYY) ... «quote»
    2. Role-based: La deputata (Group, DD/MM/YYYY) ... «quote»
                   Il legislatore (Group, DD/MM/YYYY) ... «quote»
                   L'onorevole (Group, DD/MM/YYYY) ... «quote»

    For role-based citations, speaker_name is None and the group+date are used
    for Neo4j lookup instead of the speaker's last name.
    """
    citations = []
    covered_spans: list[tuple[int, int]] = []

    def _spans_overlap(a: tuple, b: tuple) -> bool:
        return a[0] < b[1] and b[0] < a[1]

    def _make_citation(speaker_name, role_text, group_raw, date_raw, quote_raw):
        return {
            "speaker_name": speaker_name,
            "role_text": role_text,
            "group_raw": group_raw.strip(),
            "group_canonical": _canonical_party(group_raw),
            "date": date_raw.strip(),
            "quote": quote_raw.strip(),
            "chunk_id": None,
            "verbatim_verified": False,
        }

    # Pass 1: standard name-based citations (capitalized surnames)
    for m in _CITATION_RE.finditer(baseline_answer):
        name_raw, group_raw, date_raw, quote_raw = m.groups()
        name_clean = re.sub(r'\*+', '', name_raw).strip()

        # Detect false-name matches: the captured word is a role token
        # (e.g. "L'onorevole", "L'esponente", "Consiglio" from "del Consiglio (...")
        last_word = re.sub(r"['\-]", " ", name_clean.lower()).split()[-1]
        is_role = last_word in _ROLE_TOKENS

        covered_spans.append(m.span())
        citations.append(_make_citation(
            speaker_name=None if is_role else name_clean,
            role_text=name_clean if is_role else None,
            group_raw=group_raw,
            date_raw=date_raw,
            quote_raw=quote_raw,
        ))

    # Pass 2: role-based citations starting with a definite article
    # (La deputata, Il legislatore, etc.) not already captured above.
    for m in _CITATION_ROLE_RE.finditer(baseline_answer):
        if any(_spans_overlap(m.span(), s) for s in covered_spans):
            continue
        role_raw, group_raw, date_raw, quote_raw = m.groups()
        covered_spans.append(m.span())
        citations.append(_make_citation(
            speaker_name=None,
            role_text=role_raw.strip(),
            group_raw=group_raw,
            date_raw=date_raw,
            quote_raw=quote_raw,
        ))

    return citations


def _find_chunks_for_group_date(client: Neo4jClient, canonical_party: str, date_iso: str) -> list[dict]:
    """
    Return all chunks from any speaker on a session date.

    Used as fallback for role-based citations (La deputata, Il legislatore, etc.)
    where the citation contains a party group and date but no speaker surname.
    canonical_party is kept for logging context; verbatim matching handles filtering.
    """
    logger.debug(f"  Fetching all chunks on {date_iso} for party '{canonical_party}'")
    results = client.query(
        """
        MATCH (c:Chunk)<-[:HAS_CHUNK]-(i:Speech)
        MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
        WHERE s.date = date($date_iso)
        RETURN c.id AS chunk_id, c.text AS chunk_text
        LIMIT 600
        """,
        {"date_iso": date_iso},
    )
    return [{"chunk_id": r["chunk_id"], "chunk_text": r["chunk_text"]} for r in results]


def _find_chunks_for_speaker_date(client: Neo4jClient, last_name: str, date_iso: str) -> list[dict]:
    """
    Return all chunks whose speech was delivered by a speaker with the given
    last name on the given session date.

    We match on last_name (case-insensitive) so compound names like
    "Della Vedova" are handled by passing the last token.
    """
    # Use only the last token of the name for the match to handle
    # compound surnames ("Della Vedova" → match last_name = "Vedova")
    last_token = last_name.split()[-1]
    results = client.query(
        """
        MATCH (c:Chunk)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
        MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
        WHERE toLower(speaker.last_name) = toLower($last_name)
          AND s.date = date($date_iso)
        RETURN c.id AS chunk_id, c.text AS chunk_text
        """,
        {"last_name": last_token, "date_iso": date_iso},
    )
    return [{"chunk_id": r["chunk_id"], "chunk_text": r["chunk_text"]} for r in results]


def _verify_citation(client: Neo4jClient, cit: dict) -> dict:
    """
    Try to verify a single citation against Neo4j.
    Returns the citation dict with chunk_id and verbatim_verified updated.

    For name-based citations: looks up by speaker last_name + session date.
    For role-based citations (speaker_name is None): looks up by canonical
    party + session date, checking the quote against all matching chunks.
    """
    date_iso = _date_to_iso(cit["date"])
    label = cit["speaker_name"] or cit.get("role_text", "?")
    if not date_iso:
        logger.warning(f"  Cannot parse date '{cit['date']}' for {label}")
        return cit

    if cit["speaker_name"] is None:
        # Role-based citation: search by canonical party + date
        canonical = cit.get("group_canonical")
        if not canonical:
            logger.debug(f"  No canonical party for role citation on {date_iso}")
            return cit
        chunks = _find_chunks_for_group_date(client, canonical, date_iso)
    else:
        chunks = _find_chunks_for_speaker_date(client, cit["speaker_name"], date_iso)

    if not chunks:
        logger.info(f"  No chunks found for {label} on {date_iso}")
        return cit

    norm_quote = _normalize(cit["quote"])
    for chunk in chunks:
        norm_chunk = _normalize(chunk["chunk_text"] or "")
        if norm_quote == norm_chunk or norm_quote in norm_chunk or norm_chunk in norm_quote:
            cit["chunk_id"] = chunk["chunk_id"]
            cit["verbatim_verified"] = True
            return cit

    # quote not found verbatim — record the first matching chunk anyway for inspection
    cit["chunk_id"] = chunks[0]["chunk_id"]
    return cit


def process_topic(client: Neo4jClient, topic: str, entry: dict) -> dict:
    """Compute baseline metrics for one topic entry and return the enriched entry."""
    baseline_answer = entry.get("baseline_answer", "")
    if not baseline_answer:
        logger.warning(f"[{topic}] No baseline_answer found, skipping.")
        return entry

    citations = _parse_citations(baseline_answer)
    logger.info(f"[{topic}] {len(citations)} inline citations parsed.")

    # Verify each citation against Neo4j
    verified_citations = []
    for cit in citations:
        cit = _verify_citation(client, cit)
        verified_citations.append(cit)
        status = "✓" if cit["verbatim_verified"] else "✗"
        label = cit["speaker_name"] or cit.get("role_text", "?")
        logger.info(
            f"  {status} {label} ({cit['group_raw']}, {cit['date']}) "
            f"chunk={cit['chunk_id']}"
        )

    # Party coverage: unique canonical groups among cited speakers / 10
    unique_groups = {
        cit["group_canonical"]
        for cit in verified_citations
        if cit["group_canonical"] is not None
    }
    # Exclude None (unrecognised groups like "Governo")
    baseline_party_coverage = round(min(len(unique_groups) / ALL_PARTIES, 1.0), 4)

    # Citation fidelity: verified / total
    total = len(verified_citations)
    verified_count = sum(1 for c in verified_citations if c["verbatim_verified"])
    baseline_citation_fidelity = round(verified_count / max(total, 1), 4) if total > 0 else 0.0

    logger.info(
        f"[{topic}] party_coverage={baseline_party_coverage} "
        f"({len(unique_groups)}/{ALL_PARTIES} groups)  "
        f"citation_fidelity={baseline_citation_fidelity} "
        f"({verified_count}/{total} verified)"
    )

    enriched = dict(entry)
    enriched["baseline_metrics"] = {
        "baseline_party_coverage": baseline_party_coverage,
        "baseline_citation_fidelity": baseline_citation_fidelity,
        "parties_cited": sorted(unique_groups),
        "citations_total": total,
        "citations_verified": verified_count,
        "citations": [
            {
                "speaker": c["speaker_name"] or c.get("role_text"),
                "group": c["group_raw"],
                "group_canonical": c["group_canonical"],
                "date": c["date"],
                "quote": c["quote"],
                "chunk_id": c["chunk_id"],
                "verbatim_verified": c["verbatim_verified"],
            }
            for c in verified_citations
        ],
    }
    return enriched


def main():
    dry_run = "--dry-run" in sys.argv

    logger.info(f"Loading evaluation_set from {EVAL_SET_PATH}")
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        data: dict = json.load(f)

    settings = get_settings()
    logger.info(f"Connecting to Neo4j at {settings.neo4j_uri}")
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)

    enriched_data = {}
    for topic, entry in data.items():
        # Normalise: old entries may be plain strings
        if isinstance(entry, str):
            entry = {"baseline_answer": entry, "baseline_experts": []}
        enriched_data[topic] = process_topic(client, topic, entry)

    if dry_run:
        logger.info("Dry-run mode: not writing to disk.")
        print(json.dumps(
            {k: v.get("baseline_metrics") for k, v in enriched_data.items()},
            indent=2, ensure_ascii=False,
        ))
        return

    with open(EVAL_SET_PATH, "w", encoding="utf-8") as f:
        json.dump(enriched_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved enriched evaluation_set to {EVAL_SET_PATH}")


if __name__ == "__main__":
    main()
