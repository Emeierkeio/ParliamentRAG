"""
Rewrite the data-volume lines in README.md from live Neo4j counts.

Run automatically at the end of `make update-data`; can also be run by hand:
    python build/update_readme_stats.py [--neo4j-uri bolt://localhost:7690]

Credentials come from NEO4J_USER / NEO4J_PASSWORD (repo-root .env is loaded).
The script targets three specific lines, matched by stable anchors:
  - "- **<N>k+ text chunks** from ..."
  - "- **<N>k roll-call votes** with ..."
  - "- **XIX Legislature — data as of ...** (updated incrementally): ..."
"""
import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"


def k(n: int) -> str:
    return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"


def kplus(n: int) -> str:
    return f"{n // 1000}k+"


def m(n: int) -> str:
    return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"


def main():
    parser = argparse.ArgumentParser(description="Refresh README data stats from Neo4j")
    parser.add_argument("--neo4j-uri", default=None)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    uri = args.neo4j_uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        sys.exit("NEO4J_PASSWORD not set")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    counts = {}
    with driver.session() as session:
        for key, label in {
            "chunks": "Chunk", "sessions": "Session", "speeches": "Speech",
            "acts": "ParliamentaryAct", "votes": "Vote", "ivotes": "IndividualVote",
        }.items():
            counts[key] = session.run(f"MATCH (n:`{label}`) RETURN count(n) AS c").single()["c"]
        # Last `make update-data` run; falls back to newest Session date for
        # DBs stamped before SchemaMeta.updated_at existed
        last = session.run(
            "OPTIONAL MATCH (m:SchemaMeta {id: 'singleton'}) "
            "WITH date(m.updated_at) AS stamped "
            "OPTIONAL MATCH (s:Session) "
            "WITH stamped, max(s.date) AS newest "
            "RETURN coalesce(stamped, newest) AS d"
        ).single()["d"]
    driver.close()
    last_date = str(last.to_native() if hasattr(last, "to_native") else last)

    text = README.read_text(encoding="utf-8")
    replacements = [
        (
            re.compile(r"^- \*\*[\d.,]+k\+ text chunks\*\* from .*$", re.M),
            f"- **{kplus(counts['chunks'])} text chunks** from "
            f"**{counts['sessions']} plenary sessions**, updated through {last_date}",
        ),
        (
            re.compile(r"^- \*\*[\d.,]+k roll-call votes\*\* with .*$", re.M),
            f"- **{k(counts['votes'])} roll-call votes** with **{m(counts['ivotes'])} "
            "individual vote records** linked to deputies",
        ),
        (
            re.compile(r"^- \*\*XIX Legislature[,—\s]+data as of .*$", re.M),
            f"- **XIX Legislature, data as of {last_date}** (updated incrementally): "
            f"{counts['sessions']} sessions · {k(counts['speeches'])} speeches · "
            f"{kplus(counts['chunks'])} chunks · {k(counts['acts'])} acts · "
            f"{k(counts['votes'])} roll calls with {m(counts['ivotes'])} individual votes",
        ),
    ]
    changed = 0
    for pattern, replacement in replacements:
        text, n = pattern.subn(lambda _match, r=replacement: r, text)
        if n != 1:
            print(f"WARNING: anchor matched {n} times (expected 1): {pattern.pattern}")
        changed += n
    README.write_text(text, encoding="utf-8")
    print(f"README.md: {changed}/3 stat lines refreshed (data as of {last_date})")


if __name__ == "__main__":
    main()
