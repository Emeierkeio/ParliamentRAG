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
# Legislature mapping: legislature number → roman suffix used in CSV/XML names
# Intentionally not imported from download_deputies_csv.py to keep build/
# scripts standalone (no cross-script coupling — see Phase 01-04 decision).
# ---------------------------------------------------------------------------

ROMAN_MAP = {17: "xvii", 18: "xviii", 19: "xix", 20: "xx"}

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


def normalize_photo_url(raw_photo, legislature: int = 19) -> Optional[str]:
    """Normalize Camera photo URLs to the https fotoDefinitivo pattern.

    The CSV carries 'http://documenti.camera.it/apps/nuovosito/deputato/
    getFoto.asp?id=N&legislatura=19' — plain http, blocked as mixed content
    when the frontend is served over https. The stable https equivalent is
    the fotoDefinitivo/big JPEG (verified 200 on 2026-07-23).
    """
    if raw_photo is None or (isinstance(raw_photo, float) and pd.isna(raw_photo)):
        return None
    url = str(raw_photo)
    if 'getFoto.asp?id=' in url:
        num = url.split('id=')[1].split('&')[0]
        return (f"https://documenti.camera.it/_dati/leg{legislature}"
                f"/schededeputatinuovosito/fotoDefinitivo/big/d{num}.jpg")
    return url


def format_date_ddmmyyyy(date_str) -> Optional[str]:
    """Convert YYYYMMDD to DD/MM/YYYY string (used for term_of_office_start)."""
    if pd.isna(date_str) or date_str == "":
        return None
    s = str(date_str).split('.')[0].strip()
    if len(s) == 8:
        return f"{s[6:8]}/{s[4:6]}/{s[:4]}"
    return s


# Group RENAME chains: historical label -> canonical current label.
# dati.camera.it models an adesione as one continuous membership: when a group
# RENAMES itself (e.g. Azione-IV joint group -> Azione-PER-RE after the IV split),
# members who stayed keep the old label with no end date, while members who left
# get a fresh adesione. Mapping old labels to the canonical name keeps ONE group
# node per real group (verified 2026-07-23: Richetti vs Faraone rows).
GROUP_RENAMES = {
    "AZIONE - ITALIA VIVA - RENEW EUROPE":
        "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE",
    "NOI MODERATI":
        "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE",
    "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC, ITALIA AL CENTRO)-MAIE":
        "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE",
}

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
        # Schema v2 (C8): counter of chunks dropped for substring violations
        self.invariant_violations = 0

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
        """Create uniqueness constraints for all English-only node labels.

        Schema v2 (C7): no constraints for labels the builder does not create.
        IndividualVote is gone — individual votes are CAST relationships,
        created by the SPARQL enrichment step which owns its own schema.
        """
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Debate) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Phase) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sp:Speech) REQUIRE sp.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (dep:Deputy) REQUIRE dep.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (g:ParliamentaryGroup) REQUIRE g.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (com:Committee) REQUIRE com.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (gm:GovernmentMember) REQUIRE gm.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (gov:Government) REQUIRE gov.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Vote) REQUIRE v.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:ParliamentaryAct) REQUIRE a.uri IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ev:EurovocConcept) REQUIRE ev.uri IS UNIQUE",
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
                    # Schema v2 (C8) — invariante: ogni chunk deve essere
                    # substring esatta del testo salvato dello Speech (gli offset
                    # a runtime si ricavano con speech.text.find(chunk.text)).
                    # Un chunk violante NON entra nel DB: si scarta e si conta,
                    # validate_db.py fa da gate finale sul totale.
                    if chunk["text"] not in speech["text"]:
                        self.invariant_violations += 1
                        print(
                            f"  [C8 VIOLATION] chunk {chunk['index']} of speech "
                            f"{speech['id']} is not an exact substring — dropped"
                        )
                        continue
                    chunk["speechId"] = speech["id"]
                    all_chunks.append(chunk)

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
        # Schema v2 (C5): year/month/day derivabili da s.date — non si salvano.
        tx.run("""
            MERGE (s:Session {id: $id})
            SET s.legislature = $legislature,
                s.number = $number,
                s.chamber = $chamber,
                s.date = date($date)
        """,
            id=session_data["id"],
            legislature=session_data["legislature"],
            number=session_data["number"],
            chamber=session_data.get("chamber", "camera"),
            date=session_data["date"],
        )

    @staticmethod
    def _create_debates(tx, batch: list) -> None:
        # Schema v2 (C5): originalId derivabile dall'id gerarchico — non si salva.
        tx.run("""
            UNWIND $batch AS row
            MERGE (d:Debate {id: row.id})
            SET d.title = row.title,
                d.order = row.order
            WITH d, row
            MATCH (s:Session {id: row.sessionId})
            MERGE (s)-[:HAS_DEBATE]->(d)
        """, batch=batch)

    @staticmethod
    def _create_phases(tx, batch: list) -> None:
        # phaseType si tiene: usato da timeline_service.py nel backend.
        tx.run("""
            UNWIND $batch AS row
            MERGE (p:Phase {id: row.id})
            SET p.title = row.title,
                p.phaseType = row.phaseType,
                p.order = row.order
            WITH p, row
            MATCH (d:Debate {id: row.debateId})
            MERGE (d)-[:HAS_PHASE]->(p)
        """, batch=batch)

    @staticmethod
    def _create_speeches(tx, batch: list) -> None:
        tx.run("""
            UNWIND $batch AS row
            MERGE (sp:Speech {id: row.id})
            SET sp.text = row.text,
                sp.speakingRole = row.speakingRole,
                sp.deputatoId = row.deputatoId,
                sp.cognomeNome = row.cognome_nome
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
        # Primary path: match Deputy by id. Camera XMLs carry a bare numeric
        # nominativo id ("303089") while Deputy.id is the full persona URI;
        # Senate AKNs carry the full senatore URI directly.
        tx.run("""
            UNWIND $batch AS row
            WITH row WHERE row.deputatoId IS NOT NULL
            MATCH (sp:Speech {id: row.id})
            WITH sp, row,
                 CASE WHEN row.deputatoId STARTS WITH 'http'
                      THEN row.deputatoId
                      ELSE 'http://dati.camera.it/ocd/persona.rdf/p' + row.deputatoId
                 END AS depUri
            OPTIONAL MATCH (dep:Deputy {id: depUri})
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

    def _build_gov_uri_map(self, data_path: str, legislature: int = 19) -> dict[str, str]:
        """Build map of Deputy CSV URI -> GovernmentMember ID for gov deputies."""
        roman = ROMAN_MAP.get(legislature, f"leg{legislature}")
        dep_df = pd.read_csv(os.path.join(data_path, f"deputati_{roman}.csv"))
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

    def load_deputies(self, data_path: str, legislature: int = 19) -> None:
        """Load Deputy nodes from deputati_{roman}.csv using UNWIND batch writes."""
        roman = ROMAN_MAP.get(legislature, f"leg{legislature}")
        dep_df = pd.read_csv(os.path.join(data_path, f"deputati_{roman}.csv"))

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
                # C3: '' non è un valore — proprietà assente invece di stringa vuota
                education = (parts_desc[0].strip() or None) if parts_desc else None
                profession = (parts_desc[1].strip() or None) if len(parts_desc) > 1 else None

            rows.append({
                "id": r['deputato'],
                "firstName": r.get('nome'),
                "lastName": r.get('cognome'),
                "gender": r.get('gender'),
                "education": education,
                "profession": profession,
                "photo": normalize_photo_url(r.get('foto')),
                "deputyCard": r.get('schedaCamera'),
                "termOfOffice": r.get('mandatoCamera'),
                # Schema v2 (C1): data nativa, non stringa DD/MM/YYYY
                "termOfOfficeStart": parse_date_to_neo4j(r.get('mandatoStart')),
            })

        with self._driver.session() as neo_session:
            self._batch_write(neo_session, self._upsert_deputies, rows)
        print(f"Loaded {len(rows)} Deputy nodes (excluded {skipped} GovernmentMembers).")

    @staticmethod
    def _upsert_deputies(tx, batch: list) -> None:
        # Schema v2: label base Person (2.1) + date native (C1).
        tx.run("""
            UNWIND $batch AS row
            MERGE (d:Deputy {id: row.id})
            SET d:Person,
                d.first_name = row.firstName,
                d.last_name = row.lastName,
                d.gender = row.gender,
                d.education = row.education,
                d.profession = row.profession,
                d.photo = row.photo,
                d.deputy_card = row.deputyCard,
                d.term_of_office = row.termOfOffice,
                d.term_of_office_start = row.termOfOfficeStart
        """, batch=batch)

    def load_groups(self, data_path: str, legislature: int = 19) -> None:
        """Load ParliamentaryGroup nodes and MEMBER_OF_GROUP relationships."""
        roman = ROMAN_MAP.get(legislature, f"leg{legislature}")
        grp_df = pd.read_csv(os.path.join(data_path, f"deputati_{roman}_gruppi.csv"))
        gov_uri_map = self._build_gov_uri_map(data_path, legislature=legislature)

        with_end: list[dict] = []
        without_end: list[dict] = []

        for _, r in grp_df.iterrows():
            name, acronym = extract_group_info(r.get('gruppoLabel'))
            if not name:
                continue
            # Rename chains: map historical labels to the canonical group name
            name = GROUP_RENAMES.get(name, name)
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

    def load_committees(self, data_path: str, legislature: int = 19) -> None:
        """Load Committee nodes and MEMBER_OF_COMMITTEE relationships."""
        roman = ROMAN_MAP.get(legislature, f"leg{legislature}")
        com_df = pd.read_csv(os.path.join(data_path, f"deputati_{roman}_commissioni.csv"))
        gov_uri_map = self._build_gov_uri_map(data_path, legislature=legislature)

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

    # ------------------------------------------------------------------
    # Senate CSV loaders
    # ------------------------------------------------------------------

    def load_senators(self, data_path: str, legislature: int = 19) -> None:
        """Load Senator Deputy nodes from senatori_{roman}.csv.

        Senators are modelled as Deputy nodes with chamber='senato'.
        The id field is the senatore URI (e.g. http://dati.senato.it/senatore/17542).
        """
        roman = ROMAN_MAP.get(legislature, f"leg{legislature}")
        csv_path = os.path.join(data_path, f"senatori_{roman}.csv")
        if not os.path.exists(csv_path):
            print(f"  Skipping senators — {csv_path} not found")
            return

        sen_df = pd.read_csv(csv_path)

        rows: list[dict] = []
        for _, r in sen_df.iterrows():
            rows.append({
                "id": r["senatore"],
                "firstName": r.get("nome"),
                "lastName": r.get("cognome"),
                "gender": r.get("gender"),
                "photo": r.get("foto"),
                "deputyCard": str(r.get("schedaCamera", "")),
                # Schema v2 (C1): data nativa, non stringa DD/MM/YYYY
                "termOfOfficeStart": parse_date_to_neo4j(r.get("mandatoStart")),
                "chamber": "senato",
            })

        with self._driver.session() as neo_session:
            self._batch_write(neo_session, self._upsert_senators, rows)
        print(f"Loaded {len(rows)} Senator Deputy nodes.")

    @staticmethod
    def _upsert_senators(tx, batch: list) -> None:
        # Schema v2: label Person + Senator addizionali; :Deputy resta per
        # compatibilità con le query backend esistenti (documentato in §2.1).
        tx.run("""
            UNWIND $batch AS row
            MERGE (d:Deputy {id: row.id})
            SET d:Person, d:Senator,
                d.first_name = row.firstName,
                d.last_name = row.lastName,
                d.gender = row.gender,
                d.photo = row.photo,
                d.deputy_card = row.deputyCard,
                d.term_of_office_start = row.termOfOfficeStart,
                d.chamber = row.chamber
        """, batch=batch)

    def load_senator_groups(self, data_path: str, legislature: int = 19) -> None:
        """Load ParliamentaryGroup nodes and MEMBER_OF_GROUP rels for senators."""
        roman = ROMAN_MAP.get(legislature, f"leg{legislature}")
        csv_path = os.path.join(data_path, f"senatori_{roman}_gruppi.csv")
        if not os.path.exists(csv_path):
            print(f"  Skipping senator groups — {csv_path} not found")
            return

        grp_df = pd.read_csv(csv_path)

        with_end: list[dict] = []
        without_end: list[dict] = []

        for _, r in grp_df.iterrows():
            name = str(r.get("gruppoLabel", "")).strip()
            if not name:
                continue
            acronym = str(r.get("gruppoBreve", "")).strip() or None

            start_date = parse_date_to_neo4j(r.get("gruppoStart"))
            end_date = parse_date_to_neo4j(r.get("gruppoEnd"))

            row = {
                "name": name,
                "acronym": acronym,
                "nodeId": r["senatore"],
                "nodeLabel": "Deputy",
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
        print("Senator ParliamentaryGroup nodes and MEMBER_OF_GROUP relationships loaded.")

    def load_senator_committees(self, data_path: str, legislature: int = 19) -> None:
        """Load Committee nodes and MEMBER_OF_COMMITTEE rels for senators."""
        roman = ROMAN_MAP.get(legislature, f"leg{legislature}")
        csv_path = os.path.join(data_path, f"senatori_{roman}_commissioni.csv")
        if not os.path.exists(csv_path):
            print(f"  Skipping senator committees — {csv_path} not found")
            return

        com_df = pd.read_csv(csv_path)

        with_end: list[dict] = []
        without_end: list[dict] = []

        for _, r in com_df.iterrows():
            name = clean_generic_label(r.get("organoLabel"))
            if not name:
                continue

            start_date = parse_date_to_neo4j(r.get("membroStart"))
            end_date = parse_date_to_neo4j(r.get("membroEnd"))

            row = {
                "name": name,
                "nodeId": r["senatore"],
                "nodeLabel": "Deputy",
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
        print("Senator Committee nodes and MEMBER_OF_COMMITTEE relationships loaded.")

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

    def load_government_members_from_path(self, data_path: str, legislature: int = 19) -> None:
        """Create GovernmentMember nodes with CSV enrichment (photo, gender, etc.)."""
        roman = ROMAN_MAP.get(legislature, f"leg{legislature}")
        dep_df = pd.read_csv(os.path.join(data_path, f"deputati_{roman}.csv"))
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
            photo = normalize_photo_url(csv_data.get('foto')) if csv_data and pd.notna(csv_data.get('foto')) else None
            deputy_card = csv_data.get('schedaCamera') if csv_data and pd.notna(csv_data.get('schedaCamera')) else None
            gender = csv_data.get('gender') if csv_data and pd.notna(csv_data.get('gender')) else None
            term_of_office = csv_data.get('mandatoCamera') if csv_data and pd.notna(csv_data.get('mandatoCamera')) else None
            # Schema v2 (C1): data nativa, non stringa DD/MM/YYYY
            tos = parse_date_to_neo4j(csv_data.get('mandatoStart')) if csv_data else None

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
        # Schema v2 (C5): via is_government — la label GovernmentMember basta.
        tx.run("""
            UNWIND $batch AS row
            MERGE (d:GovernmentMember {id: row.id})
            SET d:Person,
                d.first_name = row.firstName,
                d.last_name = row.lastName
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
            SET d:Person,
                d.first_name = row.firstName,
                d.last_name = row.lastName,
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

    # Governo in carica — ancora per le relazioni HOLDS_OFFICE (schema v2 §2.1)
    GOVERNMENT_ID = "meloni_1"
    GOVERNMENT_NAME = "Governo Meloni"
    GOVERNMENT_START = "2022-10-22"

    @staticmethod
    def _office_type(role: str) -> str:
        """Classify a government role string into an office_type enum."""
        r = role.lower()
        if "presidente del consiglio" in r and "vicepresidente" not in r:
            return "pm"
        if "vicepresidente del consiglio" in r:
            return "deputy_pm"
        if "sottosegretario" in r:
            return "undersecretary"
        if "viceministro" in r:
            return "deputy_minister"
        return "minister"

    def load_roles(self) -> None:
        """Assign institutional roles (schema v2).

        - Government roles -> (d)-[:HOLDS_OFFICE {role, office_type, start_date}]->(:Government)
          plus GOVERNMENT_REFERENCE to the competent Committee.
        - Committee officer roles -> role property on MEMBER_OF_COMMITTEE
          (org:Membership-style, no separate IS_PRESIDENT/... rel types).
        - Group leadership -> role property on the active MEMBER_OF_GROUP rel.
        - institutional_role stays as a human-readable display property;
          role_type/committee_role are gone (derivable from relationships).
        """
        if not _ROLES_AVAILABLE:
            print("  (skip — app_config.py not available)")
            return

        COMMITTEE_ROLE_MAP = {
            "Presidente": "president",
            "Vicepresidente": "vice_president",
            "Segretario": "secretary",
        }

        with self._driver.session() as neo_session:
            # Clear existing role data (idempotent re-run)
            neo_session.execute_write(lambda tx: tx.run("""
                MATCH (d:Person)
                REMOVE d.institutional_role, d.role_type, d.committee_role
            """))
            neo_session.execute_write(lambda tx: tx.run("""
                MATCH (d:Person)-[r:HOLDS_OFFICE|GOVERNMENT_REFERENCE]->()
                DELETE r
            """))
            neo_session.execute_write(lambda tx: tx.run("""
                MATCH (d:Person)-[r:MEMBER_OF_COMMITTEE|MEMBER_OF_GROUP]->()
                REMOVE r.role
            """))

            # Government node (anchor for HOLDS_OFFICE)
            neo_session.execute_write(lambda tx: tx.run("""
                MERGE (gov:Government {id: $id})
                SET gov.name = $name, gov.start_date = date($start)
            """, id=self.GOVERNMENT_ID, name=self.GOVERNMENT_NAME,
                start=self.GOVERNMENT_START))

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
                            MATCH (d:Person {id: $id})
                            SET d.institutional_role = $role
                        """, id=did, role=r))
                        if target_entity:
                            # Group leadership on the ACTIVE membership rel
                            neo_session.execute_write(
                                lambda tx, did=dep_id, t=target_entity: tx.run("""
                                    MATCH (d:Person {id: $id})-[r:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
                                    WHERE g.name CONTAINS $target AND r.end_date IS NULL
                                    SET r.role = 'president'
                                """, id=did, target=t))
                    elif tipo_ruolo == 'commissione':
                        full_role = f"{ruolo_base} {target_entity}"
                        neo_session.execute_write(
                            lambda tx, did=dep_id, r=full_role: tx.run("""
                                MATCH (d:Person {id: $id})
                                SET d.institutional_role = $role
                            """, id=did, role=r))
                        if target_entity:
                            committee_role = None
                            for key, val in COMMITTEE_ROLE_MAP.items():
                                if key in ruolo_base:
                                    committee_role = val
                                    break
                            if committee_role:
                                # Officer role as property on the membership rel
                                # (org:Membership). MERGE creates the rel if the
                                # CSV membership is missing for this person.
                                neo_session.execute_write(
                                    lambda tx, did=dep_id, cr=committee_role, t=target_entity: tx.run("""
                                        MATCH (d:Person {id: $id})
                                        MATCH (c:Committee) WHERE c.name = $target
                                        MERGE (d)-[r:MEMBER_OF_COMMITTEE]->(c)
                                        SET r.role = $crole
                                    """, id=did, target=t, crole=cr))
                    else:
                        neo_session.execute_write(
                            lambda tx, did=dep_id, r=ruolo_base: tx.run("""
                                MATCH (d:Person {id: $id})
                                SET d.institutional_role = $role
                            """, id=did, role=r))
                        if tipo_ruolo == 'governo':
                            # HOLDS_OFFICE with temporal + type semantics
                            neo_session.execute_write(
                                lambda tx, did=dep_id, r=ruolo_base: tx.run("""
                                    MATCH (d:Person {id: $id})
                                    MATCH (gov:Government {id: $gov_id})
                                    MERGE (d)-[o:HOLDS_OFFICE]->(gov)
                                    SET o.role = $role,
                                        o.office_type = $otype,
                                        o.start_date = date($start)
                                """, id=did, role=r, otype=self._office_type(r),
                                    gov_id=self.GOVERNMENT_ID,
                                    start=self.GOVERNMENT_START))
                            if target_entity:
                                neo_session.execute_write(
                                    lambda tx, did=dep_id, t=target_entity: tx.run("""
                                        MATCH (d:Person {id: $id})
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
        """Create vector indexes for semantic search.

        Schema v2: gli embedding degli atti sono liste native (C2), quindi
        gli indici vettoriali su title/description funzionano davvero
        (in v1 la proprietà era una stringa JSON e l'indice restava vuoto).
        """
        index_specs = [
            ("chunk_embedding_index", "Chunk", "embedding"),
            ("act_description_embedding_index", "ParliamentaryAct", "description_embedding"),
            ("act_title_embedding_index", "ParliamentaryAct", "title_embedding"),
        ]
        with self._driver.session() as neo_session:
            for name, label, prop in index_specs:
                neo_session.execute_write(lambda tx, n=name, l=label, p=prop: tx.run(f"""
                    CREATE VECTOR INDEX {n} IF NOT EXISTS
                    FOR (x:{l}) ON (x.{p})
                    OPTIONS {{indexConfig: {{
                        `vector.dimensions`: 1536,
                        `vector.similarity_function`: 'cosine'
                    }}}}
                """))
        print("Vector indexes created (chunk + act title/description).")

    # Cypher =~ usa full-match: "seguito della discussione" nudo è procedurale,
    # ma "Seguito della discussione del disegno di legge X" ha contenuto e NON matcha.
    PROCEDURAL_TITLE_PATTERN = (
        r'(?i)(si riprende la discussione.*'
        r'|seguito della discussione\.?'
        r'|ripresa della discussione.*'
        r'|discussione congiunta\.?)'
    )

    def resolve_continuation_titles(self) -> None:
        """Set Debate.parent_debate_title for procedural continuation titles.

        Schema v2 §2.2: sedute con titolo "Si riprende la discussione…" vengono
        collegate al provvedimento reale via l'atto in DISCUSSES (numero/titolo),
        così l'introduzione generata può nominare il provvedimento vero.
        """
        with self._driver.session() as neo_session:
            result = neo_session.execute_write(lambda tx: tx.run("""
                MATCH (d:Debate)
                WHERE d.title =~ $pattern
                OPTIONAL MATCH (d)-[:DISCUSSES]->(a:ParliamentaryAct)
                WITH d, collect(a)[0] AS act
                WHERE act IS NOT NULL
                SET d.parent_debate_title = coalesce(
                    act.title,
                    act.type + ' ' + act.number
                )
                RETURN count(d) AS resolved
            """, pattern=self.PROCEDURAL_TITLE_PATTERN).single())
            print(f"Continuation titles resolved: {result['resolved']}")

    def write_schema_meta(self, build_tool_commit: str | None = None) -> None:
        """Write the SchemaMeta node (v2 C9) — provenance + version check anchor."""
        with self._driver.session() as neo_session:
            neo_session.execute_write(lambda tx: tx.run("""
                MERGE (m:SchemaMeta {id: 'singleton'})
                SET m.version = 2,
                    m.embedding_model = $model,
                    m.embedding_dims = 1536,
                    m.built_at = datetime(),
                    m.build_tool_commit = $commit,
                    m.source_datasets = [
                        'http://dati.camera.it/ocd/',
                        'http://dati.senato.it/',
                        'http://eurovoc.europa.eu/'
                    ]
            """, model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
                commit=build_tool_commit))
        print("SchemaMeta written (version 2).")

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

    def get_existing_session_numbers(self, chamber: str | None = None, legislature: int = 19) -> set[int]:
        """Return set of session numbers already persisted in Neo4j for a chamber+legislature.

        Session numbers restart per legislature, so BOTH chamber and legislature must
        scope the query — otherwise a leg18 update sees leg19 numbers as already ingested.
        """
        query = "MATCH (s:Session) WHERE s.legislature = $legislature RETURN s.number AS number"
        params: dict = {"legislature": legislature}
        if chamber is not None:
            query = (
                "MATCH (s:Session) "
                "WHERE coalesce(s.chamber, 'camera') = $chamber "
                "AND s.legislature = $legislature "
                "RETURN s.number AS number"
            )
            params = {"chamber": chamber, "legislature": legislature}
        with self._driver.session() as neo_session:
            records = neo_session.execute_read(
                lambda tx: list(tx.run(query, **params))
            )
        return {r['number'] for r in records}

    def relink_senate_speeches(self) -> dict[str, int]:
        """Create missing SPOKEN_BY rels for Senate speeches.

        Handles three cases:
        1. Legacy speeches whose deputatoId is the short form 'sen_XXXX'
           (older parser output) — rewritten to the full senatore URI.
        2. Speeches with a senatore-URI deputatoId not yet linked.
        3. Speeches with only a surname in cognomeNome — linked to the
           unique matching senator, or GovernmentMember as fallback.

        Returns counts per phase for logging.
        """
        counts: dict[str, int] = {}
        with self._driver.session() as neo_session:
            # 1. Normalize legacy short-form ids to full URIs
            result = neo_session.execute_write(lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.deputatoId STARTS WITH 'sen_'
                SET sp.deputatoId = 'http://dati.senato.it/senatore/'
                    + substring(sp.deputatoId, 4)
                RETURN count(sp) AS c
            """).single())
            counts["normalized_ids"] = result["c"]

            # 2. Link by senatore URI
            result = neo_session.execute_write(lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.deputatoId STARTS WITH 'http://dati.senato.it/senatore/'
                  AND NOT (sp)-[:SPOKEN_BY]->()
                MATCH (d:Deputy {id: sp.deputatoId})
                MERGE (sp)-[:SPOKEN_BY]->(d)
                RETURN count(sp) AS c
            """).single())
            counts["linked_by_uri"] = result["c"]

            # 3a. Fallback: unique senator surname match
            result = neo_session.execute_write(lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.id STARTS WITH 'sen_'
                  AND NOT (sp)-[:SPOKEN_BY]->()
                  AND sp.cognomeNome IS NOT NULL AND sp.cognomeNome <> ''
                MATCH (d:Deputy {chamber: 'senato'})
                WHERE toUpper(d.last_name) = toUpper(trim(sp.cognomeNome))
                WITH sp, collect(d) AS matches
                WHERE size(matches) = 1
                WITH sp, matches[0] AS d
                MERGE (sp)-[:SPOKEN_BY]->(d)
                RETURN count(sp) AS c
            """).single())
            counts["linked_by_surname"] = result["c"]

            # 3b. Fallback: government member by surname
            result = neo_session.execute_write(lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.id STARTS WITH 'sen_'
                  AND NOT (sp)-[:SPOKEN_BY]->()
                  AND sp.cognomeNome IS NOT NULL AND sp.cognomeNome <> ''
                MATCH (gm:GovernmentMember)
                WHERE toUpper(gm.last_name) = toUpper(trim(sp.cognomeNome))
                WITH sp, collect(gm) AS matches
                WHERE size(matches) = 1
                WITH sp, matches[0] AS gm
                MERGE (sp)-[:SPOKEN_BY]->(gm)
                RETURN count(sp) AS c
            """).single())
            counts["linked_gov_by_surname"] = result["c"]

            result = neo_session.execute_read(lambda tx: tx.run("""
                MATCH (sp:Speech)
                WHERE sp.id STARTS WITH 'sen_' AND NOT (sp)-[:SPOKEN_BY]->()
                RETURN count(sp) AS c
            """).single())
            counts["still_orphan"] = result["c"]

        print(f"Senate speech relink: {counts}")
        return counts
