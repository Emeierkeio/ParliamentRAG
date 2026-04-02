"""
db_builder.py — Neo4j database builder for the ParliamentRAG pipeline.

Takes parsed data from xml_parser.py and chunks from chunker.py and writes
everything to Neo4j using the clean English-only schema.

Schema conventions:
  - Labels: PascalCase (Session, Debate, Phase, Speech, Chunk, Deputy, …)
  - Properties: camelCase (speakingRole, phaseType, inFavor, …)
  - Relationships: SCREAMING_SNAKE_CASE (HAS_DEBATE, CONTAINS_SPEECH, …)

All write operations use UNWIND batch writes with batch_size from BuildConfig.
All transactions use execute_read/execute_write managed transactions (no auto-commit).
"""

from __future__ import annotations

import os
import re
from typing import Optional

import pandas as pd
from neo4j.time import Date as Neo4jDate

from build_config import BuildConfig
from chunker import chunk_speech
from ner import enrich_chunks_with_ner, load_ner_model

# ---------------------------------------------------------------------------
# App-config import (optional — roles won't load if missing)
# ---------------------------------------------------------------------------
try:
    from app_config import (
        GOVERNMENT_ROLES,
        PARLIAMENT_ROLES,
        CAPIGRUPPO,
        COMMISSION_ROLES,
    )
    _ROLES_AVAILABLE = True
except (ImportError, SystemExit):
    _ROLES_AVAILABLE = False


# ---------------------------------------------------------------------------
# Module-level utility helpers (ported from build_and_update.py)
# ---------------------------------------------------------------------------

def clean_generic_label(label) -> Optional[str]:
    """Remove trailing date ranges from committee/group labels."""
    if pd.isna(label):
        return None
    return re.sub(r'\s*\([^)]*\d{2}\.\d{2}\.\d{4}.*$', '', str(label)).strip()


def extract_group_info(raw_label) -> tuple[Optional[str], Optional[str]]:
    """Return (name, acronym) from a raw group label string."""
    clean_label = clean_generic_label(raw_label)
    if not clean_label:
        return None, None
    if "NM(N-C-U-I)M-CP" in clean_label:
        return clean_label.replace("(NM(N-C-U-I)M-CP)", "").strip(), "NM(N-C-U-I)M-CP"
    match = re.search(r'^(.*?)\s+\(([^)]+)\)$', clean_label)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return clean_label, None


def parse_date_to_neo4j(date_str) -> Optional[Neo4jDate]:
    """Convert YYYYMMDD (or YYYYMMDD.0) string to neo4j.time.Date."""
    if pd.isna(date_str) or date_str == "":
        return None
    s = str(date_str).split('.')[0].strip()
    if len(s) == 8:
        return Neo4jDate(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def format_date_ddmmyyyy(date_str) -> Optional[str]:
    """Convert YYYYMMDD to DD/MM/YYYY string (used for term_of_office_start)."""
    if pd.isna(date_str) or date_str == "":
        return None
    s = str(date_str).split('.')[0].strip()
    if len(s) == 8:
        return f"{s[6:8]}/{s[4:6]}/{s[:4]}"
    return s


# Government group membership map: "LAST FIRST" -> group name
GOVERNMENT_GROUPS = {
    "MELONI GIORGIA": "FRATELLI D'ITALIA",
    "FOTI TOMMASO": "FRATELLI D'ITALIA",
    "TAJANI ANTONIO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "SALVINI MATTEO": "LEGA - SALVINI PREMIER",
    "CIRIANI LUCA": "FRATELLI D'ITALIA",
    "ZANGRILLO PAOLO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "CALDEROLI ROBERTO": "LEGA - SALVINI PREMIER",
    "MUSUMECI NELLO": "FRATELLI D'ITALIA",
    "ABODI ANDREA": "MISTO",
    "ROCCELLA EUGENIA": "FRATELLI D'ITALIA",
    "LOCATELLI ALESSANDRA": "LEGA - SALVINI PREMIER",
    "ALBERTI CASELLATI MARIA ELISABETTA": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "PIANTEDOSI MATTEO": "MISTO",
    "NORDIO CARLO": "FRATELLI D'ITALIA",
    "CROSETTO GUIDO": "FRATELLI D'ITALIA",
    "GIORGETTI GIANCARLO": "LEGA - SALVINI PREMIER",
    "URSO ADOLFO": "FRATELLI D'ITALIA",
    "LOLLOBRIGIDA FRANCESCO": "FRATELLI D'ITALIA",
    "PICHETTO FRATIN GILBERTO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "VALDITARA GIUSEPPE": "LEGA - SALVINI PREMIER",
    "BERNINI ANNA MARIA": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "GIULI ALESSANDRO": "FRATELLI D'ITALIA",
    "SCHILLACI ORAZIO": "MISTO",
    "SANTANCHE' DANIELA": "FRATELLI D'ITALIA",
    "CALDERONE MARINA ELVIRA": "MISTO",
    "MANTOVANO ALFREDO": "MISTO",
    "FAZZOLARI GIOVANBATTISTA": "FRATELLI D'ITALIA",
    "BUTTI ALESSIO": "FRATELLI D'ITALIA",
    "BARACHINI ALBERTO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "MORELLI ALESSANDRO": "LEGA - SALVINI PREMIER",
    "SBARRA LUIGI": "MISTO",
    "CASTIELLO GIUSEPPINA": "LEGA - SALVINI PREMIER",
    "SIRACUSANO MATILDE": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "CIRIELLI EDMONDO": "FRATELLI D'ITALIA",
    "SILLI GIORGIO": "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC, ITALIA AL CENTRO)-MAIE",
    "TRIPODI MARIA": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "FERRO WANDA": "FRATELLI D'ITALIA",
    "MOLTENI NICOLA": "LEGA - SALVINI PREMIER",
    "PRISCO EMANUELE": "FRATELLI D'ITALIA",
    "SISTO FRANCESCO PAOLO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "DELMASTRO DELLE VEDOVE ANDREA": "FRATELLI D'ITALIA",
    "OSTELLARI ANDREA": "LEGA - SALVINI PREMIER",
    "PEREGO DI CREMNAGO MATTEO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "RAUTI ISABELLA": "FRATELLI D'ITALIA",
    "LEO MAURIZIO": "FRATELLI D'ITALIA",
    "ALBANO LUCIA": "FRATELLI D'ITALIA",
    "FRENI FEDERICO": "LEGA - SALVINI PREMIER",
    "SAVINO SANDRA": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "VALENTINI VALENTINO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "BERGAMOTTO FAUSTA": "FRATELLI D'ITALIA",
    "IANNONE ANTONIO": "FRATELLI D'ITALIA",
    "D'ERAMO LUIGI": "LEGA - SALVINI PREMIER",
    "LA PIETRA PATRIZIO GIACOMO": "FRATELLI D'ITALIA",
    "GAVA VANNIA": "LEGA - SALVINI PREMIER",
    "BARBARO CLAUDIO": "FRATELLI D'ITALIA",
    "RIXI EDOARDO": "LEGA - SALVINI PREMIER",
    "FERRANTE TULLIO": "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "BELLUCCI MARIA TERESA": "FRATELLI D'ITALIA",
    "DURIGON CLAUDIO": "LEGA - SALVINI PREMIER",
    "FRASSINETTI PAOLA": "FRATELLI D'ITALIA",
    "MONTARULI AUGUSTA": "FRATELLI D'ITALIA",
    "MAZZI GIANMARCO": "FRATELLI D'ITALIA",
    "BORGONZONI LUCIA": "LEGA - SALVINI PREMIER",
    "GEMMATO MARCELLO": "FRATELLI D'ITALIA",
}

SIGLA_FALLBACKS = {
    "FRATELLI D'ITALIA": "FDI",
    "PARTITO DEMOCRATICO": "PD",
    "MOVIMENTO 5 STELLE": "M5S",
    "LEGA": "LEGA",
    "FORZA ITALIA": "FI",
    "AZIONE": "AZ",
    "ITALIA VIVA": "IV",
}


# ---------------------------------------------------------------------------
# DatabaseBuilder
# ---------------------------------------------------------------------------

class DatabaseBuilder:
    """Writes parsed parliamentary data into Neo4j with English-only schema.

    All writes use UNWIND batch pattern and execute_write/execute_read managed
    transactions (no auto-commit calls).

    Args:
        driver: An active neo4j.Driver instance (caller owns lifecycle).
        config: BuildConfig for chunk_size, batch_size, etc.
    """

    def __init__(self, driver, config: Optional[BuildConfig] = None) -> None:
        self._driver = driver
        self._config = config or BuildConfig()
        self._nlp = None  # Lazy-loaded spaCy NER model

    def _get_nlp(self):
        """Lazy-load the spaCy NER model.

        Returns the model on success, or None if it is not installed.
        Uses a sentinel value (False) to avoid retrying after a failed load.
        """
        if self._nlp is None:
            try:
                self._nlp = load_ner_model()
            except OSError:
                print("WARNING: spaCy model it_core_news_lg not installed. Skipping NER.")
                self._nlp = False  # Sentinel to avoid retrying
        return self._nlp if self._nlp is not False else None

    # ------------------------------------------------------------------
    # Schema setup
    # ------------------------------------------------------------------

    def nuke_database(self) -> None:
        """Drop all constraints, indexes, and data from the database."""
        print("NUKE DATABASE...")
        with self._driver.session() as neo_session:
            # Drop constraints first
            try:
                constraints = neo_session.execute_read(
                    lambda tx: list(tx.run("SHOW CONSTRAINTS"))
                )
                for rec in constraints:
                    try:
                        neo_session.execute_write(
                            lambda tx, name=rec['name']: tx.run(f"DROP CONSTRAINT {name}")
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            # Drop non-lookup indexes
            try:
                indexes = neo_session.execute_read(
                    lambda tx: list(tx.run("SHOW INDEXES WHERE type <> 'LOOKUP'"))
                )
                for rec in indexes:
                    try:
                        neo_session.execute_write(
                            lambda tx, name=rec['name']: tx.run(f"DROP INDEX {name}")
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            # Batched delete to avoid OOM
            deleted = 1
            total = 0
            while deleted > 0:
                result = neo_session.execute_write(
                    lambda tx: tx.run("""
                        MATCH (n)
                        WITH n LIMIT 10000
                        DETACH DELETE n
                        RETURN count(*) AS deleted
                    """).single()
                )
                deleted = result["deleted"]
                total += deleted
                if deleted > 0:
                    print(f"  Deleted {total} nodes...")
        print("Database cleared.")

    def create_constraints(self) -> None:
        """Create uniqueness constraints for all English-only node labels."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Debate) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Phase) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sp:Speech) REQUIRE sp.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (dep:Deputy) REQUIRE dep.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (g:ParliamentaryGroup) REQUIRE g.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (com:Committee) REQUIRE com.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (gm:GovernmentMember) REQUIRE gm.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Vote) REQUIRE v.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:ParliamentaryAct) REQUIRE a.uri IS UNIQUE",
        ]
        with self._driver.session() as neo_session:
            for cypher in constraints:
                try:
                    neo_session.execute_write(lambda tx, c=cypher: tx.run(c))
                except Exception:
                    pass
        print("Constraints created.")

    def create_indexes(self) -> None:
        """Create property indexes for common query patterns.

        Note: Speech.text is intentionally NOT indexed — text values can exceed
        Neo4j RANGE index size limits (55KB+). Full-text search uses a separate
        vector index created by create_vector_index.py.
        """
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (dep:Deputy) ON (dep.name)",
            "CREATE INDEX IF NOT EXISTS FOR (s:Session) ON (s.number)",
        ]
        with self._driver.session() as neo_session:
            for cypher in indexes:
                try:
                    neo_session.execute_write(lambda tx, c=cypher: tx.run(c))
                except Exception:
                    pass
        print("Indexes created.")

    # ------------------------------------------------------------------
    # Session ingestion
    # ------------------------------------------------------------------

    def ingest_session(self, parsed_data: dict) -> None:
        """Ingest one parsed XML file (output of StenograficoParser.parse_xml_file).

        Writes Session, Debate, Phase, Speech, Chunk, Vote nodes and
        Debate-[:DISCUSSES]->ParliamentaryAct edges in a single driver session
        using UNWIND batch writes.
        """
        session_data = parsed_data["session"]
        debates = parsed_data["debates"]
        phases = parsed_data["phases"]
        speeches = parsed_data["speeches"]
        votes = parsed_data["votes"]
        act_refs = parsed_data["act_references"]

        with self._driver.session() as neo_session:
            # 1. Session node
            neo_session.execute_write(self._create_session, session_data)

            # 2. Debates
            self._batch_write(neo_session, self._create_debates, debates)

            # 3. Phases
            self._batch_write(neo_session, self._create_phases, phases)

            # 4. Speeches + chunks
            all_chunks: list[dict] = []
            for speech in speeches:
                chunks = chunk_speech(speech["text"], speech["id"], self._config)
                for chunk in chunks:
                    chunk["speechId"] = speech["id"]
                all_chunks.extend(chunks)

            # NER enrichment (adds lawRefs and personRefs to each chunk dict)
            nlp = self._get_nlp()
            if nlp:
                enrich_chunks_with_ner(all_chunks, nlp)
            else:
                for chunk in all_chunks:
                    chunk["lawRefs"] = []
                    chunk["personRefs"] = []

            self._batch_write(neo_session, self._create_speeches, speeches)
            self._batch_write(neo_session, self._create_chunks, all_chunks)

            # 5. SPOKEN_BY relationships
            self._batch_write(neo_session, self._link_speeches_to_speakers, speeches)

            # 6. Votes (Session-[:HAS_VOTE]->Vote)
            for vote in votes:
                vote["sessionId"] = session_data["id"]
            self._batch_write(neo_session, self._create_votes, votes)

            # 7. Act references (Debate-[:DISCUSSES]->ParliamentaryAct)
            act_batch: list[dict] = []
            for deb_original_id, acts in act_refs.items():
                debate_id = self._resolve_debate_id(session_data["id"], deb_original_id)
                for act in acts:
                    act_batch.append({
                        "debateId": debate_id,
                        "actCode": act["code"],
                        "actType": act["type"],
                    })
            self._batch_write(neo_session, self._create_act_links, act_batch)

    def _resolve_debate_id(self, session_id: str, original_deb_id: str) -> str:
        """Build the full debate node ID from session ID and original XML debate ID."""
        if original_deb_id.startswith(session_id):
            return original_deb_id
        return f"{session_id}_{original_deb_id}"

    # ------------------------------------------------------------------
    # Generic batch helper
    # ------------------------------------------------------------------

    def _batch_write(self, neo_session, fn, items: list) -> None:
        """Split items into batches and call fn via execute_write for each."""
        batch_size = self._config.batch_size
        for i in range(0, len(items), batch_size):
            neo_session.execute_write(fn, items[i:i + batch_size])

    # ------------------------------------------------------------------
    # Transaction functions — session ingestion
    # ------------------------------------------------------------------

    @staticmethod
    def _create_session(tx, session_data: dict) -> None:
        tx.run("""
            MERGE (s:Session {id: $id})
            SET s.legislature = $legislature,
                s.number = $number,
                s.year = $year,
                s.month = $month,
                s.day = $day,
                s.chamber = $chamber,
                s.date = date($date)
        """,
            id=session_data["id"],
            legislature=session_data["legislature"],
            number=session_data["number"],
            year=session_data["year"],
            month=session_data["month"],
            day=session_data["day"],
            chamber=session_data.get("chamber", "camera"),
            date=session_data["date"],
        )

    @staticmethod
    def _create_debates(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (d:Debate {id: row.id})
            SET d.title = row.title
            WITH d, row
            MATCH (s:Session {id: row.sessionId})
            MERGE (s)-[:HAS_DEBATE]->(d)
        """, batch=batch)

    @staticmethod
    def _create_phases(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (p:Phase {id: row.id})
            SET p.title = row.title, p.phaseType = row.phaseType
            WITH p, row
            MATCH (d:Debate {id: row.debateId})
            MERGE (d)-[:HAS_PHASE]->(p)
        """, batch=batch)

    @staticmethod
    def _create_speeches(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (sp:Speech {id: row.id})
            SET sp.text = row.text, sp.speakingRole = row.speakingRole
            WITH sp, row
            MATCH (p:Phase {id: row.phaseId})
            MERGE (p)-[:CONTAINS_SPEECH]->(sp)
        """, batch=batch)

    @staticmethod
    def _create_chunks(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (c:Chunk {id: row.id})
            SET c.text = row.text,
                c.index = row.index,
                c.lawRefs = row.lawRefs,
                c.personRefs = row.personRefs
            WITH c, row
            MATCH (sp:Speech {id: row.speechId})
            MERGE (sp)-[:HAS_CHUNK]->(c)
        """, batch=batch)

    @staticmethod
    def _create_votes(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (v:Vote {id: row.id})
            SET v.number = row.number,
                v.type = row.type,
                v.subject = row.subject,
                v.present = row.present,
                v.voters = row.voters,
                v.abstained = row.abstained,
                v.majority = row.majority,
                v.inFavor = row.inFavor,
                v.against = row.against,
                v.onMission = row.onMission,
                v.outcome = row.outcome
            WITH v, row
            MATCH (s:Session {id: row.sessionId})
            MERGE (s)-[:HAS_VOTE]->(v)
        """, batch=batch)

    @staticmethod
    def _create_act_links(tx, batch: list) -> None:
        # uri is the canonical merge key for ParliamentaryAct.
        # Placeholder acts (from XML argomenti) get a synthetic URI derived from
        # actType and actCode. SPARQL-enriched acts (from ingest_atti_parlamentari)
        # use the real dati.camera.it URI — they will overwrite the placeholder via
        # MERGE on the same synthetic URI if the number matches, OR exist as
        # separate nodes if the real URI differs (fine — the DISCUSSES edge already
        # points to the placeholder, which carries the act number for retrieval).
        tx.run("""
            UNWIND $batch AS row
            MATCH (d:Debate {id: row.debateId})
            MERGE (a:ParliamentaryAct {uri: 'placeholder:' + row.actType + ':' + row.actCode})
            ON CREATE SET a.type = row.actType,
                          a.number = row.actCode,
                          a.isPlaceholder = true
            MERGE (d)-[:DISCUSSES]->(a)
        """, batch=batch)

    @staticmethod
    def _link_speeches_to_speakers(tx, batch: list) -> None:
        """Create SPOKEN_BY relationships from Speech to Deputy or GovernmentMember.

        For each speech with a deputatoId, match the Deputy by that URI.
        Falls back to GovernmentMember match by cognomeNome if no Deputy found.
        """
        # Primary path: match Deputy by URI (deputatoId is the XML nominativo id attribute)
        tx.run("""
            UNWIND $batch AS row
            WITH row WHERE row.deputatoId IS NOT NULL
            MATCH (sp:Speech {id: row.id})
            OPTIONAL MATCH (dep:Deputy {id: row.deputatoId})
            WITH sp, dep, row WHERE dep IS NOT NULL
            MERGE (sp)-[:SPOKEN_BY]->(dep)
        """, batch=batch)

        # Fallback: match GovernmentMember by name for speeches not yet linked
        tx.run("""
            UNWIND $batch AS row
            WITH row WHERE row.cognome_nome IS NOT NULL
            MATCH (sp:Speech {id: row.id})
            WHERE NOT (sp)-[:SPOKEN_BY]->()
            MATCH (gm:GovernmentMember)
            WHERE toUpper(gm.last_name + ' ' + gm.first_name) = toUpper(row.cognome_nome)
               OR toUpper(gm.first_name + ' ' + gm.last_name) = toUpper(row.cognome_nome)
            MERGE (sp)-[:SPOKEN_BY]->(gm)
        """, batch=batch)

    # ------------------------------------------------------------------
    # CSV loaders
    # ------------------------------------------------------------------

    def _build_gov_uri_map(self, data_path: str) -> dict[str, str]:
        """Build map of Deputy CSV URI -> GovernmentMember ID for gov deputies."""
        dep_df = pd.read_csv(os.path.join(data_path, "deputati_xix.csv"))
        gov_uri_map: dict[str, str] = {}
        for full_name in GOVERNMENT_GROUPS:
            parts = full_name.split()
            last_name = " ".join(parts[:-1]).upper()
            first_name = parts[-1].upper()
            match = dep_df[
                (dep_df['cognome'].str.strip().str.upper() == last_name) &
                (dep_df['nome'].str.strip().str.upper() == first_name)
            ]
            if len(match) > 0:
                dep_uri = match.iloc[0]['deputato']
                gov_id = f"gov_{full_name.replace(' ', '_').lower()}"
                gov_uri_map[dep_uri] = gov_id
        return gov_uri_map

    def load_deputies(self, data_path: str) -> None:
        """Load Deputy nodes from deputati_xix.csv using UNWIND batch writes."""
        dep_df = pd.read_csv(os.path.join(data_path, "deputati_xix.csv"))

        # Build set of (last_name, first_name) for GovernmentMember exclusion
        gov_names: set[tuple[str, str]] = set()
        for full_name in GOVERNMENT_GROUPS:
            parts = full_name.split()
            gov_names.add((" ".join(parts[:-1]).upper(), parts[-1].upper()))

        rows: list[dict] = []
        skipped = 0
        for _, r in dep_df.iterrows():
            cognome = str(r.get('cognome', '')).strip().upper()
            nome = str(r.get('nome', '')).strip().upper()
            if (cognome, nome) in gov_names:
                skipped += 1
                continue

            education = None
            profession = None
            desc = r.get('descrizione')
            if pd.notna(desc):
                parts_desc = str(desc).split(";", 1)
                education = parts_desc[0].strip() if parts_desc else None
                profession = parts_desc[1].strip() if len(parts_desc) > 1 else None

            rows.append({
                "id": r['deputato'],
                "firstName": r.get('nome'),
                "lastName": r.get('cognome'),
                "gender": r.get('gender'),
                "education": education,
                "profession": profession,
                "photo": r.get('foto'),
                "deputyCard": r.get('schedaCamera'),
                "termOfOffice": r.get('mandatoCamera'),
                "termOfOfficeStart": format_date_ddmmyyyy(r.get('mandatoStart')),
            })

        with self._driver.session() as neo_session:
            self._batch_write(neo_session, self._upsert_deputies, rows)
        print(f"Loaded {len(rows)} Deputy nodes (excluded {skipped} GovernmentMembers).")

    @staticmethod
    def _upsert_deputies(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (d:Deputy {id: row.id})
            SET d.first_name = row.firstName,
                d.last_name = row.lastName,
                d.gender = row.gender,
                d.education = row.education,
                d.profession = row.profession,
                d.photo = row.photo,
                d.deputy_card = row.deputyCard,
                d.term_of_office = row.termOfOffice,
                d.term_of_office_start = row.termOfOfficeStart
        """, batch=batch)

    def load_groups(self, data_path: str) -> None:
        """Load ParliamentaryGroup nodes and MEMBER_OF_GROUP relationships."""
        grp_df = pd.read_csv(os.path.join(data_path, "deputati_xix_gruppi.csv"))
        gov_uri_map = self._build_gov_uri_map(data_path)

        with_end: list[dict] = []
        without_end: list[dict] = []

        for _, r in grp_df.iterrows():
            name, acronym = extract_group_info(r.get('gruppoLabel'))
            if not name:
                continue
            if not acronym:
                for key, val in SIGLA_FALLBACKS.items():
                    if key in name:
                        acronym = val
                        break

            start_date = parse_date_to_neo4j(r.get('gruppoStart'))
            end_date = parse_date_to_neo4j(r.get('gruppoEnd'))

            dep_uri = r['deputato']
            node_id = gov_uri_map.get(dep_uri, dep_uri)
            node_label = "GovernmentMember" if dep_uri in gov_uri_map else "Deputy"

            row = {
                "name": name,
                "acronym": acronym,
                "nodeId": node_id,
                "nodeLabel": node_label,
                "startDate": start_date,
            }
            if end_date:
                row["endDate"] = end_date
                with_end.append(row)
            else:
                without_end.append(row)

        with self._driver.session() as neo_session:
            if with_end:
                self._batch_write(neo_session, self._upsert_group_membership_with_end, with_end)
            if without_end:
                self._batch_write(neo_session, self._upsert_group_membership_no_end, without_end)
        print("ParliamentaryGroup nodes and MEMBER_OF_GROUP relationships loaded.")

    @staticmethod
    def _upsert_group_membership_with_end(tx, batch: list) -> None:
        # Dynamic labels require separate queries per label type
        for row in batch:
            label = row["nodeLabel"]
            tx.run(f"""
                MERGE (g:ParliamentaryGroup {{name: $name}})
                SET g.acronym = $acronym
                WITH g
                MATCH (d:{label} {{id: $nodeId}})
                CREATE (d)-[:MEMBER_OF_GROUP {{start_date: $startDate, end_date: $endDate}}]->(g)
            """, name=row["name"], acronym=row["acronym"], nodeId=row["nodeId"],
                startDate=row["startDate"], endDate=row["endDate"])

    @staticmethod
    def _upsert_group_membership_no_end(tx, batch: list) -> None:
        for row in batch:
            label = row["nodeLabel"]
            tx.run(f"""
                MERGE (g:ParliamentaryGroup {{name: $name}})
                SET g.acronym = $acronym
                WITH g
                MATCH (d:{label} {{id: $nodeId}})
                CREATE (d)-[:MEMBER_OF_GROUP {{start_date: $startDate}}]->(g)
            """, name=row["name"], acronym=row["acronym"], nodeId=row["nodeId"],
                startDate=row["startDate"])

    def load_committees(self, data_path: str) -> None:
        """Load Committee nodes and MEMBER_OF_COMMITTEE relationships."""
        com_df = pd.read_csv(os.path.join(data_path, "deputati_xix_commissioni.csv"))
        gov_uri_map = self._build_gov_uri_map(data_path)

        with_end: list[dict] = []
        without_end: list[dict] = []

        for _, r in com_df.iterrows():
            name = clean_generic_label(r.get('organoLabel'))
            if not name:
                continue

            start_date = parse_date_to_neo4j(r.get('membroStart'))
            end_date = parse_date_to_neo4j(r.get('membroEnd'))

            dep_uri = r['deputato']
            node_id = gov_uri_map.get(dep_uri, dep_uri)
            node_label = "GovernmentMember" if dep_uri in gov_uri_map else "Deputy"

            row = {
                "name": name,
                "nodeId": node_id,
                "nodeLabel": node_label,
                "startDate": start_date,
            }
            if end_date:
                row["endDate"] = end_date
                with_end.append(row)
            else:
                without_end.append(row)

        with self._driver.session() as neo_session:
            if with_end:
                self._batch_write(neo_session, self._upsert_committee_membership_with_end, with_end)
            if without_end:
                self._batch_write(neo_session, self._upsert_committee_membership_no_end, without_end)
        print("Committee nodes and MEMBER_OF_COMMITTEE relationships loaded.")

    @staticmethod
    def _upsert_committee_membership_with_end(tx, batch: list) -> None:
        for row in batch:
            label = row["nodeLabel"]
            tx.run(f"""
                MERGE (c:Committee {{name: $name}})
                WITH c
                MATCH (d:{label} {{id: $nodeId}})
                CREATE (d)-[:MEMBER_OF_COMMITTEE {{start_date: $startDate, end_date: $endDate}}]->(c)
            """, name=row["name"], nodeId=row["nodeId"],
                startDate=row["startDate"], endDate=row["endDate"])

    @staticmethod
    def _upsert_committee_membership_no_end(tx, batch: list) -> None:
        for row in batch:
            label = row["nodeLabel"]
            tx.run(f"""
                MERGE (c:Committee {{name: $name}})
                WITH c
                MATCH (d:{label} {{id: $nodeId}})
                CREATE (d)-[:MEMBER_OF_COMMITTEE {{start_date: $startDate}}]->(c)
            """, name=row["name"], nodeId=row["nodeId"],
                startDate=row["startDate"])

    def load_government_members(self) -> None:
        """Create GovernmentMember nodes and link them to ParliamentaryGroups.

        NOTE: This method requires a data_path for CSV lookups. Provide it via
        load_government_members_from_path(data_path) in production code that has
        access to the CSV files. This stub creates nodes without CSV enrichment.
        """
        # Build gov member rows from GOVERNMENT_GROUPS constant
        rows: list[dict] = []
        for full_name, group_name in GOVERNMENT_GROUPS.items():
            parts = full_name.split()
            last_name = " ".join(parts[:-1])
            first_name = parts[-1]
            fid = f"gov_{full_name.replace(' ', '_').lower()}"
            rows.append({
                "id": fid,
                "firstName": first_name,
                "lastName": last_name,
                "groupName": group_name,
            })

        with self._driver.session() as neo_session:
            self._batch_write(neo_session, self._upsert_government_members, rows)
        print(f"Created {len(rows)} GovernmentMember nodes.")

    def load_government_members_from_path(self, data_path: str) -> None:
        """Create GovernmentMember nodes with CSV enrichment (photo, gender, etc.)."""
        dep_df = pd.read_csv(os.path.join(data_path, "deputati_xix.csv"))
        dep_lookup: dict[str, dict] = {}
        for _, r in dep_df.iterrows():
            key = f"{str(r.get('cognome', '')).strip().upper()} {str(r.get('nome', '')).strip().upper()}"
            dep_lookup[key] = dict(r)

        rows: list[dict] = []
        for full_name, group_name in GOVERNMENT_GROUPS.items():
            parts = full_name.split()
            last_name = " ".join(parts[:-1])
            first_name = parts[-1]
            fid = f"gov_{full_name.replace(' ', '_').lower()}"

            csv_data = dep_lookup.get(full_name)
            photo = csv_data.get('foto') if csv_data and pd.notna(csv_data.get('foto')) else None
            deputy_card = csv_data.get('schedaCamera') if csv_data and pd.notna(csv_data.get('schedaCamera')) else None
            gender = csv_data.get('gender') if csv_data and pd.notna(csv_data.get('gender')) else None
            term_of_office = csv_data.get('mandatoCamera') if csv_data and pd.notna(csv_data.get('mandatoCamera')) else None
            tos = format_date_ddmmyyyy(csv_data.get('mandatoStart')) if csv_data else None

            rows.append({
                "id": fid,
                "firstName": first_name,
                "lastName": last_name,
                "groupName": group_name,
                "photo": photo,
                "deputyCard": deputy_card,
                "gender": gender,
                "termOfOffice": term_of_office,
                "termOfOfficeStart": tos,
            })

        with self._driver.session() as neo_session:
            self._batch_write(neo_session, self._upsert_government_members_enriched, rows)
        print(f"Created {len(rows)} GovernmentMember nodes (with CSV enrichment).")

    @staticmethod
    def _upsert_government_members(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (d:GovernmentMember {id: row.id})
            SET d.first_name = row.firstName,
                d.last_name = row.lastName,
                d.is_government = true
            WITH d, row
            MATCH (g:ParliamentaryGroup {name: row.groupName})
            MERGE (d)-[mg:MEMBER_OF_GROUP]->(g)
            SET mg.start_date = date('2022-10-18')
        """, batch=batch)

    @staticmethod
    def _upsert_government_members_enriched(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (d:GovernmentMember {id: row.id})
            SET d.first_name = row.firstName,
                d.last_name = row.lastName,
                d.is_government = true,
                d.gender = row.gender,
                d.photo = row.photo,
                d.deputy_card = row.deputyCard,
                d.term_of_office = row.termOfOffice,
                d.term_of_office_start = row.termOfOfficeStart
            WITH d, row
            MATCH (g:ParliamentaryGroup {name: row.groupName})
            MERGE (d)-[mg:MEMBER_OF_GROUP]->(g)
            SET mg.start_date = date('2022-10-18')
        """, batch=batch)

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------

    def load_roles(self) -> None:
        """Assign institutional roles to Deputy and GovernmentMember nodes."""
        if not _ROLES_AVAILABLE:
            print("  (skip — app_config.py not available)")
            return

        REL_MAP = {
            "Presidente": "IS_PRESIDENT",
            "Vicepresidente": "IS_VICE_PRESIDENT",
            "Segretario": "IS_SECRETARY",
            "Riferimento Governo": "GOVERNMENT_REFERENCE",
        }

        with self._driver.session() as neo_session:
            # Clear existing role properties and relationships
            neo_session.execute_write(lambda tx: tx.run("""
                MATCH (d) WHERE d:Deputy OR d:GovernmentMember
                REMOVE d.institutional_role, d.role_type, d.committee_role
            """))
            neo_session.execute_write(lambda tx: tx.run("""
                MATCH (d)-[r:IS_PRESIDENT|IS_VICE_PRESIDENT|IS_SECRETARY|GOVERNMENT_REFERENCE]->()
                WHERE d:Deputy OR d:GovernmentMember
                DELETE r
            """))

            all_configs = [
                (GOVERNMENT_ROLES, 'governo'),
                (PARLIAMENT_ROLES, 'camera'),
                (CAPIGRUPPO, 'capogruppo'),
                (COMMISSION_ROLES, 'commissione'),
            ]

            matched = 0
            for role_dict, dict_type in all_configs:
                for nome, (ruolo_base, tipo_ruolo, target_entity) in role_dict.items():
                    dep_id = self._find_person(neo_session, nome)
                    if not dep_id:
                        continue
                    matched += 1

                    if tipo_ruolo == 'capogruppo':
                        full_role = f"Presidente del Gruppo {target_entity}"
                        neo_session.execute_write(lambda tx, did=dep_id, r=full_role: tx.run("""
                            MATCH (d) WHERE (d:Deputy OR d:GovernmentMember) AND d.id = $id
                            SET d.institutional_role = $role, d.role_type = 'capogruppo'
                        """, id=did, role=r))
                        if target_entity:
                            neo_session.execute_write(
                                lambda tx, did=dep_id, t=target_entity: tx.run("""
                                    MATCH (d) WHERE (d:Deputy OR d:GovernmentMember) AND d.id = $id
                                    MATCH (g:ParliamentaryGroup) WHERE g.name CONTAINS $target
                                    MERGE (d)-[:IS_PRESIDENT]->(g)
                                """, id=did, target=t))
                    elif tipo_ruolo == 'commissione':
                        full_role = f"{ruolo_base} {target_entity}"
                        neo_session.execute_write(
                            lambda tx, did=dep_id, r=full_role, t=target_entity: tx.run("""
                                MATCH (d) WHERE (d:Deputy OR d:GovernmentMember) AND d.id = $id
                                SET d.institutional_role = $role, d.role_type = 'commissione',
                                    d.committee_role = $committee
                            """, id=did, role=r, committee=t))
                        if target_entity:
                            rel_type = None
                            for key, val in REL_MAP.items():
                                if key in ruolo_base:
                                    rel_type = val
                                    break
                            if rel_type:
                                neo_session.execute_write(
                                    lambda tx, did=dep_id, rt=rel_type, t=target_entity: tx.run(f"""
                                        MATCH (d) WHERE (d:Deputy OR d:GovernmentMember) AND d.id = $id
                                        MATCH (c:Committee) WHERE c.name = $target
                                        MERGE (d)-[:{rt}]->(c)
                                    """, id=did, target=t))
                    else:
                        neo_session.execute_write(
                            lambda tx, did=dep_id, r=ruolo_base, rt=tipo_ruolo, t=target_entity: tx.run("""
                                MATCH (d) WHERE (d:Deputy OR d:GovernmentMember) AND d.id = $id
                                SET d.institutional_role = $role, d.role_type = $rtype,
                                    d.committee_role = $committee
                            """, id=did, role=r, rtype=rt, committee=t))
                        if tipo_ruolo == 'governo' and target_entity:
                            neo_session.execute_write(
                                lambda tx, did=dep_id, t=target_entity: tx.run("""
                                    MATCH (d) WHERE (d:Deputy OR d:GovernmentMember) AND d.id = $id
                                    MATCH (c:Committee) WHERE c.name = $target
                                    MERGE (d)-[:GOVERNMENT_REFERENCE]->(c)
                                """, id=did, target=t))

            # Reconcile orphan Speech nodes (no SPOKEN_BY relationship yet)
            neo_session.execute_write(lambda tx: tx.run("""
                MATCH (sp:Speech) WHERE NOT (sp)-[:SPOKEN_BY]->()
                WITH sp, sp.speakingRole AS full_name
                WHERE full_name IS NOT NULL
                MATCH (d) WHERE (d:Deputy OR d:GovernmentMember)
                  AND (toUpper(d.last_name + ' ' + d.first_name) = toUpper(full_name)
                       OR toUpper(d.first_name + ' ' + d.last_name) = toUpper(full_name))
                MERGE (sp)-[:SPOKEN_BY]->(d)
            """))

            print(f"  Roles assigned: {matched}")

    def _find_person(self, neo_session, full_name: str) -> Optional[str]:
        """Find a Deputy or GovernmentMember ID by full name (last first)."""
        parts = full_name.strip().upper().split()
        if len(parts) < 2:
            return None
        for i in range(1, len(parts)):
            cognome = " ".join(parts[:i])
            nome = " ".join(parts[i:])
            result = neo_session.execute_read(
                lambda tx, c=cognome, n=nome: tx.run("""
                    MATCH (d) WHERE (d:Deputy OR d:GovernmentMember)
                      AND toUpper(d.last_name) = $cognome
                      AND toUpper(d.first_name) STARTS WITH $nome
                    RETURN d.id AS id LIMIT 1
                """, cognome=c, nome=n).single()
            )
            if result:
                return result['id']
        return None

    # ------------------------------------------------------------------
    # Vector index and session utilities
    # ------------------------------------------------------------------

    def create_vector_index(self) -> None:
        """Create the vector index on Chunk.embedding for semantic search."""
        with self._driver.session() as neo_session:
            neo_session.execute_write(lambda tx: tx.run("""
                CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
            """))
        print("Vector index created.")

    def create_fulltext_index(self) -> None:
        """Create full-text index on Chunk.text for BM25 sparse retrieval."""
        with self._driver.session() as neo_session:
            try:
                neo_session.execute_write(lambda tx: tx.run("""
                    CREATE FULLTEXT INDEX chunk_fulltext IF NOT EXISTS
                    FOR (n:Chunk) ON EACH [n.text]
                    OPTIONS {indexConfig: {`fulltext.analyzer`: 'italian'}}
                """))
                print("Full-text index created (italian analyzer).")
            except Exception as e:
                # Fallback if italian analyzer not available in this Neo4j instance
                print(f"Italian analyzer failed ({e}), trying standard analyzer...")
                neo_session.execute_write(lambda tx: tx.run("""
                    CREATE FULLTEXT INDEX chunk_fulltext IF NOT EXISTS
                    FOR (n:Chunk) ON EACH [n.text]
                """))
                print("Full-text index created (standard analyzer).")

    def get_existing_session_numbers(self) -> set[int]:
        """Return set of session numbers already persisted in Neo4j."""
        with self._driver.session() as neo_session:
            records = neo_session.execute_read(
                lambda tx: list(tx.run("MATCH (s:Session) RETURN s.number AS number"))
            )
        return {r['number'] for r in records}
