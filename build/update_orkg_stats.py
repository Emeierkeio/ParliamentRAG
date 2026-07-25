"""
Sync the dataset statistics of the ORKG entry with the live Neo4j graph.

The paper entry https://orkg.org/papers/R1909763 describes the knowledge graph
in resource R1909775 (number of nodes/edges/deputies/acts/speeches/chunks and
snapshot date). This script reads the live counts and rewrites those literals
via the ORKG REST API, so the entry stays aligned after `make update-data`.

Auth: set ORKG_EMAIL and ORKG_PASSWORD in the repo-root .env (the same
credentials used to log in on orkg.org); the script obtains a short-lived
JWT via the OIDC password grant (public client `orkg-client`). A pre-made
ORKG_API_TOKEN env var, if present, is used directly instead. Without
credentials the script prints a notice and exits 0, so the Makefile
pipeline never breaks on it.

Usage:
    python build/update_orkg_stats.py [--neo4j-uri bolt://localhost:7690] [--dry-run]
"""
import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

REPO_ROOT = Path(__file__).resolve().parent.parent
ORKG_API = "https://orkg.org/api"
ORKG_TOKEN_URL = "https://accounts.orkg.org/realms/orkg/protocol/openid-connect/token"
KG_RESOURCE = "R1909775"  # "ParliamentRAG knowledge graph" inside paper R1909763


def obtain_token() -> str | None:
    """JWT from ORKG_API_TOKEN, or via OIDC password grant with ORKG_EMAIL/PASSWORD."""
    token = os.environ.get("ORKG_API_TOKEN")
    if token:
        return token
    email = os.environ.get("ORKG_EMAIL")
    password = os.environ.get("ORKG_PASSWORD")
    if not (email and password):
        return None
    resp = requests.post(
        ORKG_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": "orkg-client",
            "username": email,
            "password": password,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        sys.exit(f"ORKG login failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()["access_token"]


def live_counts(uri: str, user: str, password: str) -> dict:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        def one(cypher):
            return session.run(cypher).single()[0]
        counts = {
            "number of deputies": one("MATCH (n:Deputy) RETURN count(n)"),
            "number of acts": one("MATCH (n:ParliamentaryAct) RETURN count(n)"),
            "number of speeches": one("MATCH (n:Speech) RETURN count(n)"),
            "number of chunks": one("MATCH (n:Chunk) RETURN count(n)"),
            "number of nodes": one("MATCH (n) RETURN count(n)"),
            "number of edges": one("MATCH ()-[r]->() RETURN count(r)"),
        }
        last = one("MATCH (s:Session) RETURN max(s.date)")
        counts["snapshot date"] = str(last.to_native() if hasattr(last, "to_native") else last)
    driver.close()
    return counts


def main():
    parser = argparse.ArgumentParser(description="Sync ORKG KG statistics with Neo4j")
    parser.add_argument("--neo4j-uri", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    token = obtain_token()
    if not token and not args.dry_run:
        print("ORKG sync skipped: set ORKG_EMAIL and ORKG_PASSWORD in .env")
        return

    uri = args.neo4j_uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        sys.exit("NEO4J_PASSWORD not set")
    counts = live_counts(uri, user, password)

    # Map predicate label (normalized) -> literal id, from the public bundle
    bundle = requests.get(
        f"{ORKG_API}/statements/{KG_RESOURCE}/bundle",
        params={"maxLevel": 1},
        headers={"Accept": "application/json"},
        timeout=30,
    )
    bundle.raise_for_status()
    literal_by_stat = {}
    current_value = {}
    for st in bundle.json().get("statements", []):
        label = st["predicate"]["label"].strip().lower()
        if label in {k.lower() for k in counts} and st["object"]["_class"] == "literal":
            literal_by_stat[label] = st["object"]["id"]
            current_value[label] = st["object"]["label"]

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    updated = skipped = 0
    for stat, value in counts.items():
        key = stat.lower()
        literal_id = literal_by_stat.get(key)
        if literal_id is None:
            print(f"WARNING: no literal found on {KG_RESOURCE} for '{stat}'")
            continue
        new_label = str(value)
        if current_value.get(key) == new_label:
            skipped += 1
            continue
        print(f"{stat}: {current_value.get(key)} -> {new_label} ({literal_id})")
        if args.dry_run:
            updated += 1
            continue
        resp = session.put(
            f"{ORKG_API}/literals/{literal_id}",
            json={"label": new_label},
            timeout=30,
        )
        resp.raise_for_status()
        updated += 1
    mode = "DRY-RUN, " if args.dry_run else ""
    print(f"ORKG {KG_RESOURCE}: {mode}{updated} updated, {skipped} already current")


if __name__ == "__main__":
    main()
