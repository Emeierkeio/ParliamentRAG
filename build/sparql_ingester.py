"""
sparql_ingester.py — SPARQL enrichment from dati.camera.it

Fetches per-deputy individual vote records and committee officer roles from the
Italian Chamber of Deputies SPARQL endpoint, then writes the data to Neo4j.

Schema changes:
  - IndividualVote {id, outcome} nodes with VOTED and ON_VOTE relationships
  - MEMBER_OF_COMMITTEE.officerRole, officerRoleStart, officerRoleEnd properties

Usage (CLI):
    python build/sparql_ingester.py --neo4j-uri bolt://localhost:7689

Usage (library):
    from sparql_ingester import SparqlIngester
    ingester = SparqlIngester(driver)
    stats = ingester.ingest_votes()
    stats = ingester.ingest_committee_roles()
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SPARQL_ENDPOINT = "https://dati.camera.it/sparql"

OUTCOME_MAP: dict[str, str] = {
    "Favorevole": "favor",
    "Contrario": "against",
    "Astenuto": "abstain",
    "Non ha votato": "absent",
    "In missione": "on_mission",
}

BATCH_SIZE = 500          # Neo4j write batch size
SPARQL_PAGE_SIZE = 1000   # HTTP pagination page size
SPARQL_TIMEOUT = 30       # seconds

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_DEP_URI_RE = re.compile(r"/d(\d+)_19$")
_VOTAZIONE_URI_RE = re.compile(r"/vs19_(\d+)_(\d+)$")
_PERSONA_ID_RE = re.compile(r"/p(\d+)$")


# ---------------------------------------------------------------------------
# URI parsing helpers (pure functions, easily testable)
# ---------------------------------------------------------------------------

def sparql_dep_uri_to_neo4j_id(uri: str) -> Optional[str]:
    """Convert a SPARQL deputato URI to a Neo4j Deputy.id (persona.rdf).

    Example:
        "http://dati.camera.it/ocd/deputato.rdf/d308908_19"
        -> "http://dati.camera.it/ocd/persona.rdf/p308908"
    """
    m = _DEP_URI_RE.search(uri)
    if not m:
        return None
    person_id = m.group(1)
    return f"http://dati.camera.it/ocd/persona.rdf/p{person_id}"


def parse_votazione_uri(uri: str) -> tuple[Optional[int], Optional[int]]:
    """Extract (session_number, vote_number) from a votazione URI.

    Example:
        "http://dati.camera.it/ocd/votazione.rdf/vs19_029_089"
        -> (29, 89)
    """
    m = _VOTAZIONE_URI_RE.search(uri)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _extract_person_id_from_neo4j_id(neo4j_id: str) -> Optional[str]:
    """Extract numeric person_id string from a Neo4j Deputy.id (persona.rdf/p{id})."""
    m = _PERSONA_ID_RE.search(neo4j_id)
    if not m:
        return None
    return m.group(1)


# ---------------------------------------------------------------------------
# SPARQL HTTP helper
# ---------------------------------------------------------------------------

def _sparql_get(query: str, timeout: int = SPARQL_TIMEOUT) -> list[dict]:
    """Execute a SPARQL SELECT query and return the bindings list.

    Uses urllib (stdlib) to avoid additional dependencies.
    Returns an empty list on any network/HTTP/parse error — never raises.
    """
    # Use POST to avoid URL length limits on complex SPARQL queries
    post_data = urllib.parse.urlencode({
        "query": query,
        "format": "application/sparql-results+json",
    }).encode("utf-8")
    req = urllib.request.Request(
        SPARQL_ENDPOINT,
        data=post_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            data = json.loads(raw)
            return data.get("results", {}).get("bindings", [])
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        logger.warning("SPARQL request failed: %s", exc)
        return []
    except Exception as exc:
        logger.warning("Unexpected error during SPARQL request: %s", exc)
        return []


# ---------------------------------------------------------------------------
# SparqlIngester class
# ---------------------------------------------------------------------------

class SparqlIngester:
    """Enriches the Neo4j graph from dati.camera.it SPARQL endpoint."""

    def __init__(self, driver) -> None:
        self._driver = driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_votes(self, limit_deputies: int = 0) -> dict:
        """Fetch individual vote records from SPARQL and write IndividualVote nodes.

        Args:
            limit_deputies: If > 0, only process that many deputies (for testing).

        Returns:
            Stats dict: {"deputies_processed": N, "votes_written": N, "votes_skipped": N}
        """
        deputies = self._fetch_all_deputies()
        if limit_deputies > 0:
            deputies = deputies[:limit_deputies]

        total_written = 0
        total_skipped = 0

        for i, deputy in enumerate(deputies):
            neo4j_id = deputy["id"]
            person_id = _extract_person_id_from_neo4j_id(neo4j_id)
            if not person_id:
                logger.warning("Cannot extract person_id from Deputy.id=%s", neo4j_id)
                continue

            dep_sparql_uri = f"http://dati.camera.it/ocd/deputato.rdf/d{person_id}_19"
            written, skipped = self._ingest_deputy_votes(neo4j_id, person_id, dep_sparql_uri)
            total_written += written
            total_skipped += skipped

            if (i + 1) % 50 == 0:
                logger.info(
                    "Progress: %d/%d deputies — votes written=%d skipped=%d",
                    i + 1, len(deputies), total_written, total_skipped,
                )

        logger.info(
            "Vote ingestion complete: deputies=%d, votes_written=%d, votes_skipped=%d",
            len(deputies), total_written, total_skipped,
        )
        return {
            "deputies_processed": len(deputies),
            "votes_written": total_written,
            "votes_skipped": total_skipped,
        }

    def ingest_committee_roles(self) -> dict:
        """Fetch committee officer roles from SPARQL and enrich MEMBER_OF_COMMITTEE.

        Returns:
            Stats dict: {"deputies_processed": N, "roles_written": N}
        """
        deputies = self._fetch_all_deputies()
        total_roles = 0

        for i, deputy in enumerate(deputies):
            neo4j_id = deputy["id"]
            person_id = _extract_person_id_from_neo4j_id(neo4j_id)
            if not person_id:
                continue

            dep_sparql_uri = f"http://dati.camera.it/ocd/deputato.rdf/d{person_id}_19"
            bindings = self._get_committee_roles(dep_sparql_uri)
            if not bindings:
                continue

            batch = self._prepare_committee_role_batch(bindings, neo4j_id)
            if not batch:
                continue

            roles_written = self._write_committee_roles(batch)
            total_roles += roles_written

            if (i + 1) % 50 == 0:
                logger.info(
                    "Progress: %d/%d deputies — roles_written=%d",
                    i + 1, len(deputies), total_roles,
                )

        logger.info(
            "Committee role ingestion complete: deputies=%d, roles_written=%d",
            len(deputies), total_roles,
        )
        return {
            "deputies_processed": len(deputies),
            "roles_written": total_roles,
        }

    # ------------------------------------------------------------------
    # Batch preparation helpers (testable without DB)
    # ------------------------------------------------------------------

    def _prepare_vote_batch(
        self,
        bindings: list[dict],
        deputy_neo4j_id: str,
        person_id: str,
    ) -> list[dict]:
        """Convert SPARQL vote bindings to Neo4j batch dicts.

        Skips any binding where the votazione URI cannot be parsed.
        """
        batch = []
        for row in bindings:
            votazione_uri = row.get("votazione", {}).get("value", "")
            tipo = row.get("tipo", {}).get("value", "")
            session_num, vote_num = parse_votazione_uri(votazione_uri)
            if session_num is None or vote_num is None:
                continue
            outcome = OUTCOME_MAP.get(tipo, "absent")
            iv_id = f"iv_{person_id}_{session_num}_{vote_num}"
            batch.append({
                "id": iv_id,
                "deputyId": deputy_neo4j_id,
                "sessionNumber": session_num,
                "voteNumber": vote_num,
                "outcome": outcome,
            })
        return batch

    def _prepare_committee_role_batch(
        self,
        bindings: list[dict],
        deputy_neo4j_id: str,
    ) -> list[dict]:
        """Convert SPARQL committee role bindings to Neo4j batch dicts."""
        batch = []
        for row in bindings:
            committee_name = row.get("organoLabel", {}).get("value", "")
            role = row.get("carica", {}).get("value", "")
            start_date = row.get("startDate", {}).get("value", None)
            end_date = row.get("endDate", {}).get("value", None) if "endDate" in row else None
            if not committee_name or not role:
                continue
            batch.append({
                "deputyId": deputy_neo4j_id,
                "committeeName": committee_name,
                "role": role,
                "startDate": start_date,
                "endDate": end_date,
            })
        return batch

    # ------------------------------------------------------------------
    # SPARQL query methods
    # ------------------------------------------------------------------

    def _get_deputy_votes_page(self, dep_sparql_uri: str, offset: int = 0) -> list[dict]:
        """Fetch one page of vote records for a deputy from the SPARQL endpoint."""
        query = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT ?voto ?votazione ?tipo
WHERE {{
  ?voto a ocd:voto ;
        ocd:rif_deputato <{dep_sparql_uri}> ;
        ocd:rif_votazione ?votazione ;
        ocd:tipo ?tipo .
}}
LIMIT {SPARQL_PAGE_SIZE}
OFFSET {offset}
"""
        return _sparql_get(query)

    def _get_committee_roles(self, dep_sparql_uri: str) -> list[dict]:
        """Fetch committee officer roles for a deputy from the SPARQL endpoint."""
        query = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?organoLabel ?carica ?startDate ?endDate
WHERE {{
  ?ufficio a ocd:ufficioParlamentare ;
           ocd:rif_deputato <{dep_sparql_uri}> ;
           ocd:rif_organo ?organo ;
           ocd:carica ?carica ;
           ocd:startDate ?startDate .
  ?organo rdfs:label ?organoLabel .
  OPTIONAL {{ ?ufficio ocd:endDate ?endDate . }}
}}
"""
        return _sparql_get(query)

    # ------------------------------------------------------------------
    # Neo4j write helpers
    # ------------------------------------------------------------------

    def _fetch_all_deputies(self) -> list[dict]:
        """Return list of {id: ...} dicts for all Deputy nodes in Neo4j."""
        with self._driver.session() as neo_session:
            result = neo_session.run("MATCH (d:Deputy) RETURN d.id AS id")
            return [{"id": record["id"]} for record in result if record["id"]]

    def _ingest_deputy_votes(
        self,
        neo4j_id: str,
        person_id: str,
        dep_sparql_uri: str,
    ) -> tuple[int, int]:
        """Page through all votes for one deputy and write them to Neo4j.

        Returns (votes_written, votes_skipped).
        """
        written = 0
        skipped = 0
        offset = 0

        while True:
            bindings = self._get_deputy_votes_page(dep_sparql_uri, offset=offset)
            if not bindings:
                break

            batch = self._prepare_vote_batch(bindings, neo4j_id, person_id)
            skipped += len(bindings) - len(batch)  # bindings without valid votazione URI

            if batch:
                w, s = self._write_votes(batch)
                written += w
                skipped += s

            if len(bindings) < SPARQL_PAGE_SIZE:
                break
            offset += SPARQL_PAGE_SIZE

        return written, skipped

    def _write_votes(self, batch: list[dict]) -> tuple[int, int]:
        """Write a batch of IndividualVote nodes to Neo4j.

        Returns (written, skipped) where skipped = rows with no matching Vote node.
        """
        cypher = """
UNWIND $batch AS row
MATCH (d:Deputy {id: row.deputyId})
MATCH (s:Session {number: row.sessionNumber})-[:HAS_VOTE]->(v:Vote {number: row.voteNumber})
MERGE (iv:IndividualVote {id: row.id})
SET iv.outcome = row.outcome
MERGE (d)-[:VOTED]->(iv)
MERGE (iv)-[:ON_VOTE]->(v)
RETURN count(*) AS written
"""
        count_cypher = """
UNWIND $batch AS row
OPTIONAL MATCH (s:Session {number: row.sessionNumber})-[:HAS_VOTE]->(v:Vote {number: row.voteNumber})
WITH row, v
WHERE v IS NULL
RETURN count(*) AS skipped
"""
        written = 0
        skipped = 0
        chunk_size = BATCH_SIZE

        for i in range(0, len(batch), chunk_size):
            chunk = batch[i:i + chunk_size]
            with self._driver.session() as neo_session:
                result = neo_session.run(cypher, batch=chunk)
                record = result.single()
                written += record["written"] if record else 0
                skip_result = neo_session.run(count_cypher, batch=chunk)
                skip_record = skip_result.single()
                skipped += skip_record["skipped"] if skip_record else 0

        return written, skipped

    def _write_committee_roles(self, batch: list[dict]) -> int:
        """Enrich MEMBER_OF_COMMITTEE relationships with officer role data.

        Returns the number of relationships updated.
        """
        cypher = """
UNWIND $batch AS row
MATCH (d:Deputy {id: row.deputyId})-[r:MEMBER_OF_COMMITTEE]->(c:Committee)
WHERE toLower(c.name) CONTAINS toLower(row.committeeName)
SET r.officerRole = row.role,
    r.officerRoleStart = CASE WHEN row.startDate IS NOT NULL THEN date(row.startDate) ELSE NULL END,
    r.officerRoleEnd = CASE WHEN row.endDate IS NOT NULL THEN date(row.endDate) ELSE NULL END
RETURN count(*) AS updated
"""
        total = 0
        chunk_size = BATCH_SIZE
        for i in range(0, len(batch), chunk_size):
            chunk = batch[i:i + chunk_size]
            with self._driver.session() as neo_session:
                result = neo_session.run(cypher, batch=chunk)
                record = result.single()
                total += record["updated"] if record else 0
        return total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="SPARQL enrichment from dati.camera.it")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7689")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="thesis2026")
    parser.add_argument(
        "--limit-deputies",
        type=int,
        default=0,
        help="Limit to N deputies for testing (0 = all)",
    )
    parser.add_argument("--skip-votes", action="store_true", help="Skip vote ingestion")
    parser.add_argument("--skip-committees", action="store_true", help="Skip committee roles")
    args = parser.parse_args()

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Error: neo4j package not installed. Run: pip install neo4j", file=sys.stderr)
        sys.exit(1)

    driver = GraphDatabase.driver(
        args.neo4j_uri,
        auth=(args.neo4j_user, args.neo4j_password),
    )
    try:
        ingester = SparqlIngester(driver)

        if not args.skip_votes:
            print("==> Ingesting individual votes...")
            vote_stats = ingester.ingest_votes(limit_deputies=args.limit_deputies)
            print(
                f"    Deputies processed : {vote_stats['deputies_processed']}\n"
                f"    Votes written      : {vote_stats['votes_written']}\n"
                f"    Votes skipped      : {vote_stats['votes_skipped']}"
            )

        if not args.skip_committees:
            print("==> Enriching committee officer roles...")
            role_stats = ingester.ingest_committee_roles()
            print(
                f"    Deputies processed : {role_stats['deputies_processed']}\n"
                f"    Roles written      : {role_stats['roles_written']}"
            )
    finally:
        driver.close()
