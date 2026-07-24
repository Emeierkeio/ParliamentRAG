# Piano: Schema DB v2 — Rebuild Totale Post-Paper

> Stato: **DA FARE (dopo consegna paper)** · Creato: 2026-07-22
> Strategia: **full rebuild** con re-ingest, non migration incrementale. Accettato il costo
> di re-embedding (mitigato: `build/embeddings_cache.db` → i testi invariati sono cache hit).
> Codice pipeline: `ParliamentRAG/build/` (db_builder.py, chunker.py, embedding_service.py,
> xml_parser.py, ingest_atti_parlamentari.py, senate_*). Piano complementare:
> `PLAN_citation_quality.md` (la citability entra nello schema v2 da subito).

## Perché rebuild e non patch

Audit 2026-07-22 sul DB demo (bolt 7691) ha trovato: embeddings come stringhe JSON
(~1.5GB morti su Speech + vector index atti VUOTO → ricerca semantica atti rotta),
offset chunk sbagliati (43% span errati: riferiti al testo raw pre-pulizia), 4 formati
data diversi, label morte con indici vivi, proprietà sempre-vuote, type mismatch
cross-label. Sono errori di *ingestion*: patcharli nel DB lascia la pipeline che li
rigenera al prossimo update. Si sistema la pipeline, si ricostruisce, si valida.

---

## 1. Convenzioni non negoziabili (il contratto dello schema)

Queste regole valgono per ogni nodo/proprietà presente e FUTURA:

| # | Regola | Oggi violata da |
|---|--------|-----------------|
| C1 | Date sempre `date`/`datetime` nativi Neo4j. Mai stringhe. | `term_of_office_start` ('30/09/2022'), `presentation_date` ('20250909'), timestamp ISO string |
| C2 | Embedding sempre `LIST OF FLOAT` + vector index. Mai JSON string. | Deputy, ParliamentaryAct, Speech (tutti tranne Chunk) |
| C3 | Niente valori-placeholder: proprietà assente invece di `''`, `[]`, 0 fittizio | `presentation_date=''` (2.995 atti), `merged_from_ids=[]` (40.416), ChatHistory ('' su 4 prop × 57 nodi) |
| C4 | Stesso nome proprietà = stesso tipo e semantica su tutte le label | `deputy_card` (STRING URL su Deputy, INTEGER su GovernmentMember) |
| C5 | Niente proprietà derivabili (si calcolano in query) | `day/month/year/complete_date` (da `date`), `char_count` (da `size(text)`), `is_government` (dalla label) |
| C6 | Nomi proprietà in inglese, snake_case, coerenti | residui italiani nello schema morto (`tipo`, `dataPresentazione`) |
| C7 | Ogni label ha constraint UNIQUE su `id` + niente label/indici senza nodi | AttoParlamentare (0 nodi, 4 indici), Vote/IndividualVote vuoti |
| C8 | Offset/derivati testuali validati a write-time con invariante verificabile | `start_char_raw/end_char_raw` (riferiti al testo raw, applicati al testo pulito) |
| C9 | Un nodo `(:SchemaMeta)` traccia versione schema, modello embedding, dimensioni, data build | assente |
| C10 | **Linked Data first**: ogni entità con URI canonica in un dataset LOD pubblico la conserva come identificatore (`uri`, dereferenziabile). Id locali coniati SOLO dove non esiste URI autoritativa | EuroVoc appiattito a stringa di label (le URI arrivano già dallo SPARQL EU e vengono scartate); URI votazioni OCD non conservate |
| C11 | Ogni tipo di nodo/relazione ha un mapping documentato verso un'ontologia standard (OCD, FOAF, ORG, SKOS, PROV-O, AKN) — vedi §2.7 | mapping implicito, non documentato |

---

## 2. Schema target v2

### 2.1 Persone (il cambiamento strutturale principale)

Oggi: `Deputy` e `GovernmentMember` sono label disgiunte con proprietà duplicate e
sparse (GovernmentMember ha i campi da deputato solo per il 37% che è anche deputato;
`_compute_experts` deve escludere i GovernmentMember a mano). Il Senato (già in roadmap,
pipeline `senate_*` esistente) aggiungerebbe una terza label fotocopia.

V2: **una label base `Person` + label secondarie multiple** (feature nativa Neo4j) +
ruoli come relazioni temporali:

```
(:Person:Deputy {uri,                    # URI OCD dati.camera.it — resta l'identificatore (C10)
                 first_name, last_name, gender, birth_date,
                 profession, profession_embedding,
                 education, education_embedding,
                 photo_url, camera_numeric_id,
                 wikidata_id})           # opzionale, per interlinking futuro (LOD cloud)

(:Person:Senator {... senato_numeric_id})          # futura espansione, stesso pattern
(:Person:Deputy:GovernmentMember ...)               # Meloni: entrambe le label, UNA persona

(p:Person)-[:HOLDS_OFFICE {role: 'Ministro delle Infrastrutture',
                           office_type: 'minister'|'pm'|'undersecretary',
                           start_date: date, end_date: date|null}]->(gov:Government {id: 'meloni_1'})

(p:Person)-[:MEMBER_OF_GROUP {start_date: date, end_date: date|null}]->(g:ParliamentaryGroup)
(p:Person)-[:MEMBER_OF_COMMITTEE {role: 'president'|'vice_president'|'secretary'|'member',
                                  start_date, end_date}]->(c:Committee)
(p:Person)-[:HAS_MANDATE {chamber: 'camera'|'senato', legislature: 19,
                          start_date, end_date}]->(:Legislature {number: 19})
```

Cosa risolve:
- Fine del type-mismatch `deputy_card`: → `camera_numeric_id` (INTEGER) solo su chi è deputato.
- Fine di `is_government`, `role_type`, `institutional_role`, `committee_role` come stringhe
  sparse sul nodo: diventano relazioni con date → interrogabili ("chi era ministro QUANDO
  ha parlato?") — oggi impossibile.
- `IS_PRESIDENT`/`IS_VICE_PRESIDENT`/`IS_SECRETARY` (3 tipi di relazione per la stessa
  semantica) → un solo `MEMBER_OF_COMMITTEE {role}`.
- Il Senato si aggiunge con una label, zero refactoring.
- `SPOKEN_BY` punta sempre a `Person`: query uniformi su tutta la produzione orale.

### 2.2 Struttura documentale (già buona, solo pulizia)

La catena `Session → Debate → Phase → Speech → Chunk` e gli id gerarchici
(`leg19_sed79_tit00030.sub00010.int00080_chunk_0`) funzionano: **si tengono**.
Non si churnano id che funzionano — ChatHistory, citazioni salvate e frontend li referenziano.

```
(:Session {id, chamber: 'camera'|'senato', legislature: int, number: int, date: date})
   # VIA: day, month, year, complete_date (C5)

(:Debate {id, title, order: int})
   # VIA: originalId (12% coverage, 0 usi)
   # NUOVO: parent_debate_title — risolve i titoli-continuazione
   #        ("Si riprende la discussione…" → titolo del provvedimento padre,
   #        risolto a ingest seguendo la seduta/odg precedente; cfr. PLAN_citation_quality Fase 4)

(:Phase {id, title, order})
   # VIA: originalId, phaseType (12%, valore quasi sempre 'other')

(:Speech {id, text, speaker_name_raw})
   # text = testo PULITO (unica versione salvata; il raw non serve a runtime)
   # speaker_name_raw = com'era nel transcript ('DEL BARBA Mauro'), utile per re-link/debug
   # VIA: text_embedding (~1.5GB, 0 usi — il retrieval usa i chunk)
   # VIA: preprocessed_text (duplicato di text), char_count, merged_from_ids
   #      (merged_from_ids si tiene SOLO se non vuota — C3)
   # INVARIANTE ingest: ogni Speech DEVE avere SPOKEN_BY (repair_spoken_by.py entra
   #      nella pipeline come step obbligatorio con fail se >0 orfani, oggi 53)

(:Chunk {id, text, index: int,
         embedding: LIST OF FLOAT,          # già corretto oggi, unico che lo è
         citability_score: float,           # da PLAN_citation_quality Fase 1
         citability_class: string,
         best_quote: string|assente,
         citability_v: int})
   # VIA: start_char_raw, end_char_raw (sbagliati nel 43% dei casi + ridondanti)
   # INVARIANTE ingest (C8): speech.text CONTAINS chunk.text — verificata a write-time,
   #   build FALLISCE se violata. Gli offset si calcolano a runtime con text.find(chunk_text)
   #   (verificato: substring esatta in 500/500 casi)
   # VIA: char_count, start/end ridondanti
```

### 2.3 Atti parlamentari

```
(:ParliamentaryAct {uri,                              # URI OCD, resta l'id (C10)
                    number, type, title, description,
                    presentation_date: date,          # C1: da 'YYYYMMDD' string a date; '' → assente
                    recipient,
                    title_embedding: LIST OF FLOAT,   # C2: da JSON string a nativo
                    description_embedding: LIST OF FLOAT})

VECTOR INDEX su description_embedding (e title_embedding)  → la ricerca semantica atti TORNA A FUNZIONARE
(p:Person)-[:PRIMARY_SIGNATORY|CO_SIGNATORY]->(a)           # invariati
(a)-[:DISCUSSED_IN]->(d:Debate)                             # rinomina di DISCUSSES per direzione chiara
```

**EuroVoc come nodi SKOS, non stringa** (C10 — le URI sono GIÀ scaricate dall'endpoint
SPARQL dell'EU Publications Office in `ingest_atti_parlamentari.py`, cache `data/eurovoc.csv`
uri→label, e oggi vengono appiattite in `eurovoc: 'label; label'`):

```
(:EurovocConcept {uri,                    # http://eurovoc.europa.eu/... — dereferenziabile
                  label_it,
                  embedding: LIST OF FLOAT})   # UN embedding per concetto, non per atto
(a:ParliamentaryAct)-[:HAS_SUBJECT]->(ev:EurovocConcept)     # ≈ dcterms:subject
# opzionale futuro: (ev)-[:BROADER]->(ev2) importando la gerarchia SKOS
#   → query expansion tematica gratis ("sanità" ⊃ "spesa sanitaria")
```

Cosa risolve: `eurovoc_embedding` per-atto sparisce (era l'embedding della stringa
concatenata — 32K embedding ridondanti; i concetti distinti sono ~centinaia, embeddati
una volta sola); faceting tematico reale nel frontend; aggancio diretto al LOD europeo.
`eurovoc` stringa si elimina (derivabile: `collect(ev.label_it)`).

### 2.4 Voti (predisposizione espansione — schema pronto, popolamento futuro)

Constraint esistono già (Vote/IndividualVote vuoti). Si definisce ORA lo schema così
l'ingest Senato/Camera votes (dati SPARQL già individuati) atterra su binari fissi:

```
(:Vote {uri,                                  # URI OCD della votazione (ocd:rif_votazione,
                                              # già presente nelle query di sparql_ingester.py) — C10
        date: date, chamber, legislature, title, outcome: 'approved'|'rejected',
        yes_count, no_count, abstention_count})
(v:Vote)-[:ON_ACT]->(:ParliamentaryAct)      # oppure ON_DEBATE quando manca l'atto
(p:Person)-[:CAST {choice: 'yes'|'no'|'abstention'|'absent'}]->(v)
```

⚠️ **RETTIFICA 2026-07-22 sera**: il modello CAST resta il TARGET, ma la migrazione è
DIFFERITA. Scoperto che la Fase 8 (ingestion voti SPARQL) e la Fase 14 (vote
intelligence: coerenza discorso-voto, compass da voti, indici coesione, votes
explorer — 7/8 plan completati su v2-dev) sono GIÀ costruite e testate sul modello
`IndividualVote/VOTED/ON_VOTE`. Quindi: si mantiene quel modello (il vote ingester
crea da sé i propri constraint), il refactor a CAST diventa un piano a sé da fare
SOLO insieme alla migrazione delle query di Fase 14. Per popolare i voti sul DB v2:
girare lo step `enrich-sparql` (non incluso nel rebuild notturno del 2026-07-22).

### 2.5 Dati applicativi (ChatHistory, SurveyEvaluation)

Restano in Neo4j per ora (volumi minimi), ma:
- via le proprietà sempre-vuote (`ab_assignment`, `balance`, `baseline_answer`,
  `commissioni` su ChatHistory — 57/57 vuote)
- `timestamp` → `datetime` nativo con timezone (oggi string, formati misti)
- label con prefisso `App` (`:AppChatHistory`, `:AppSurveyEvaluation`) per separare
  visivamente corpus (immutabile, rigenerabile) da dati applicativi (preziosi, da backuppare
  a parte). Un domani migrano a Postgres senza toccare il corpus.

### 2.6 Metadata di schema (C9)

```
(:SchemaMeta {version: 2, embedding_model: 'text-embedding-3-small',
              embedding_dims: 1536, built_at: datetime, build_tool_commit: string,
              source_datasets: ['http://dati.camera.it/ocd/', 'http://dati.senato.it/',
                                'http://eurovoc.europa.eu/']})   # ≈ prov:used
```
Il backend a startup verifica `version` e rifiuta di partire su schema incompatibile
(oggi il mismatch schema morto/vivo in search.py è passato inosservato per mesi).
Il nodo funge anche da record di provenance della build (≈ `prov:Activity`).

### 2.7 Allineamento Semantic Web (C10-C11) — la scelta di base per il paper

Le fonti sono GIÀ Linked Data (SPARQL dati.camera.it con ontologia OCD, AKN per il
Senato, EuroVoc/SKOS dall'EU Publications Office). Lo schema v1 le appiattisce; lo
schema v2 le conserva: **il property graph è una vista materializzata del LOD sorgente,
con mapping ontologico documentato**. Per il paper questo trasforma il DB da dettaglio
implementativo ad artefatto: KG interoperabile, FAIR, ri-esportabile in RDF.

**Tabella di mapping (da includere nel paper come appendice):**

| Schema v2 | Ontologia standard |
|---|---|
| `Person` | `foaf:Person` / `ocd:deputato` (via `uri`) |
| `MEMBER_OF_GROUP {start,end}` | `org:Membership` + `org:memberDuring` (W3C ORG) |
| `HOLDS_OFFICE {role,start,end}` | `org:Post` / `org:holdsPost` |
| `MEMBER_OF_COMMITTEE {role}` | `org:Membership` verso `ocd:organo` |
| `ParliamentaryGroup`, `Committee`, `Government` | `org:Organization` / `ocd:gruppoParlamentare`, `ocd:organo` |
| `ParliamentaryAct` | `ocd:atto` (opz. allineamento ELI per estensioni EU) |
| `HAS_SUBJECT → EurovocConcept` | `dcterms:subject` → `skos:Concept` (EuroVoc) |
| `Session / Debate / Phase / Speech` | struttura Akoma Ntoso (`akn:debate`, `akn:debateSection`, `akn:speech`) — il Senato arriva già in AKN |
| `SPOKEN_BY` | `akn:by` / `ocd:rif_deputato` |
| `Vote / CAST` | `ocd:votazione` / `ocd:voto` |
| `SchemaMeta`, `source_uri`, `ingested_at` | `prov:Activity`, `prov:wasDerivedFrom`, `prov:generatedAtTime` |

**Regole operative:**
- Ogni nodo derivato da una fonte LOD porta `uri` (canonica, C10); Session/Speech/Chunk
  (senza URI autoritativa: gli stenografici Camera sono XML non-LOD) tengono gli id
  locali gerarchici, che sono comunque compatibili con lo stile di naming AKN.
- `ingested_at: datetime` sui nodi corpus (provenance leggera, un campo, ≈ PROV-O).
- **Export RDF come deliverable**: step opzionale post-build con n10s (neosemantics)
  o serializzatore dedicato che usa la tabella di mapping → il KG diventa pubblicabile
  (Zenodo/sito paper) e citabile. Nel paper: "the property graph preserves source URIs
  and documented ontology alignments, enabling round-trip RDF export".
- Motivazione architetturale da esplicitare nel paper: property graph scelto per
  vector index + traversal performance (retrieval RAG), URI e mapping conservati per
  l'interoperabilità — non è un lock-in, è una materializzazione.

---

### 2.8 Estensioni previste dal design (non implementate ora, ma garantite dallo schema)

**Legislature precedenti (leg 18, 17, …)** — sforzo basso, solo dati+config:
- `Person.id` = URI persona.rdf è stabile cross-legislatura (una persona = un nodo,
  sempre); la mappatura verso `deputato.rdf/dN_<leg>` per SPARQL è meccanica e
  parametrizzata (`legislature` nell'ingester atti, fix 2026-07-22)
- `Session.legislature` + prefisso id `leg<N>_` + `HAS_MANDATE→(:Legislature)` già previsti
- Da fare quando serve: config ruoli PER governo/legislatura (`app_config.py` oggi
  è Meloni-only; il nodo Government già supporta `draghi_1`, `conte_2`, …) e CSV/XML
  della legislatura target (target Makefile leg18 già esistenti)

**Altri parlamenti/stati** — struttura portabile, id da namespace-are:
- Portabile gratis: catena AKN (standard internazionale), EuroVoc multilingue,
  Person/ORG, citability LLM (language-agnostic, a differenza delle regex v1)
- Lavoro per-fonte inevitabile: ingester, config coalizioni/ruoli, prompt
- **CONVENZIONE ID (dichiarata ora, costa zero; retrofit costosissimo)**: gli id
  locali senza prefisso paese sono impliciti Italia/Camera+Senato. Ogni corpus
  NON italiano usa prefisso ISO: `fr_leg16_sed12_...`, e nodo
  `(:Parliament {id, country, chamber})` collegato alle Session. Nessun rename
  dei dati esistenti richiesto, mai.
- Embeddings: text-embedding-3-small è multilingue — nessun cambio di modello
  richiesto per corpus non italiani (verificare qualità retrieval per lingua)

## 3. Interventi sulla pipeline di build (`ParliamentRAG/build/`)

| File | Intervento |
|---|---|
| `embedding_service.py` | Output SEMPRE `list[float]`, mai `json.dumps`. La cache (`embeddings_cache.db`) resta valida: si ri-serializza dal cache hit |
| `chunker.py` | Calcolare chunk sul testo PULITO (stesso testo che si salva) + assert substring invariante; via il calcolo offset raw |
| `db_builder.py` / `initialize_db.py` | Tipi nativi per date; niente stringhe vuote; constraint v2; via creazione label/indici morti; scrittura SchemaMeta |
| `xml_parser.py` | `speaker_name_raw` preservato; testo pulito come unica versione |
| `ingest_atti_parlamentari.py` | `presentation_date` → date; embeddings nativi; via property italiane; **EurovocConcept nodes dalle URI già in cache** (`data/eurovoc.csv`) invece dell'appiattimento a stringa; embedding per concetto (una volta) invece che per atto |
| `repair_spoken_by.py` | Da script una-tantum a step pipeline con hard fail |
| NUOVO `classify_chunk_citability.py` | Da PLAN_citation_quality Fase 1, gira nel build |
| NUOVO `validate_db.py` | Suite invarianti post-build (vedi §5) |
| `Makefile` | Ridisegno completo, vedi §3b |

### 3b. Interfaccia operativa: CLI Python + Makefile sottile

Principio: la LOGICA sta nella CLI Python (`build_and_update.py`, che è già una CLI a
subcommand), il Makefile è solo façade parametrizzata. Niente logica nei target.

```makefile
# Config SOLO da .env / variabili (mai hardcodata):
NEO4J_URI  ?= $(shell grep ^NEO4J_URI .env | cut -d= -f2)
NEO4J_PASS ?= $(shell grep ^NEO4J_PASSWORD .env | cut -d= -f2)

db-build:      ## Full rebuild (nuke + ingest + embeddings + citability + VALIDATE)
db-update:     ## Incrementale completo (camera+senato+atti+sparql+summaries+citability+VALIDATE)
db-validate:   ## Solo suite invarianti (validate_db.py)
db-backup:     ## Dump del volume corrente con timestamp
db-restore:    ## Restore da dump (DUMP=path)
db-shell:      ## cypher-shell sul DB configurato
```

Regole:
1. Ogni target accetta `NEO4J_URI=bolt://localhost:7692 make db-build` — mai più
   bypass a mano come stasera.
2. `db-build` e `db-update` TERMINANO con `validate_db.py`: se gli invarianti
   falliscono il target fallisce (exit≠0). La validazione non è opzionale.
3. I vecchi target sovrapposti (`db-populate`, `db-senate`, `db-update-senate`,
   `db-update-all`, `enrich-sparql`, `generate-summaries`) diventano step interni
   della CLI (`build_and_update.py update --with-senate --with-sparql ...`);
   nel Makefile restano solo alias deprecati per un ciclo, poi via.
4. Password mai nel Makefile: solo da .env/ambiente.

Alternative valutate (2026-07-22): `just` (bello ma dipendenza in più a guadagno
marginale), DVC/Snakemake (riproducibilità formale per il paper — solo se richiesta
dai reviewer), Airflow/Dagster (overkill single-machine). Decisione: CLI Python +
Make sottile.

## 4. Interventi sul backend (dopo rebuild)

- `search.py`: nomi proprietà corretti (`type/presentation_date/number/recipient` al posto
  di `tipo/dataPresentazione/numero/destinatario`) — fix del bug attivo
- `evidence.py` (+ query.py, chat.py): offset con `text.find(chunk_text)`, via span da DB
- `authority/components.py`: via `parse_embedding()` — gli embedding arrivano già come liste
- `graph_channel.py`: cosine via vector index dove possibile invece di parse in Python
- Query su Deputy/GovernmentMember → pattern `Person` con label (grep sistematico
  `MATCH.*Deputy|GovernmentMember` su tutti i router)
- Ministri competenti a data intervento: usare `HOLDS_OFFICE` con date (miglioria
  del filtro competenza nell'integrator)

## 5. Validazione post-build (gate obbligatorio, `validate_db.py`)

1. **Invarianti hard** (fail = build respinta):
   - 0 embedding STRING; ogni vector index restituisce k risultati su query dummy
   - 0 Speech senza SPOKEN_BY; 0 Chunk senza HAS_CHUNK
   - `speech.text CONTAINS chunk.text` su campione 5.000 = 100%
   - 0 proprietà `''` o liste vuote; 0 date STRING
   - 0 label con 0 nodi che abbiano indici/constraint
2. **Parità funzionale** vs DB v1:
   - conteggi nodi/relazioni entro ±1% (al netto delle rimozioni pianificate)
   - le query di `evaluation_set.json` producono retrieval sovrapponibile (top-10 overlap ≥90%)
   - le risposte con citazioni: quote nel viewer esatte al carattere (campione manuale 20)
3. **Ricerca atti**: `db.index.vector.queryNodes` sull'indice atti > 0 risultati (oggi: 0)
4. **Linked Data** (C10): ogni `uri` matcha il pattern del dataset sorgente
   (dati.camera.it/ocd/…, eurovoc.europa.eu/…); campione di 20 URI dereferenziate
   con successo; 0 atti senza almeno un `HAS_SUBJECT` se l'atto aveva EuroVoc in v1

## 6. Esecuzione (side-by-side, zero downtime demo)

1. Branch `db-schema-v2` su ParliamentRAG (pipeline) + ParliamentRAG-demo (backend)
2. Build in container Neo4j nuovo su porta separata (pattern già usato: 7689/7690/7691)
3. `validate_db.py` sul nuovo DB → iterare finché verde
4. Backend demo puntato al nuovo DB in locale, smoke test manuale + evaluation set
5. Cutover: dump nuovo DB → server Hetzner (VPS 89.167.54.206, container
   `parliament-neo4j` — su Railway girano solo frontend+backend); il vecchio DB
   resta come backup sul VPS finché il paper non è discusso (le ChatHistory della
   valutazione NON si toccano: export a parte prima del cutover, re-import nel nuovo)
6. Merge + aggiornare memoria progetto e CLAUDE.md con lo schema v2

## 7. Stima costi/tempi

| Voce | Stima |
|---|---|
| Re-embedding | Quasi zero per testi invariati (cache hit su `embeddings_cache.db`); da ripagare solo Speech il cui testo pulito cambia + citability batch (~pochi €, gpt-4o-mini) |
| Pipeline fixes | 1-2 giorni |
| Backend updates | 1 giorno (il grosso è il pattern Person nei router) |
| Rebuild + validazione | mezza giornata macchina + iterazioni |
| Rischio principale | Query backend dimenticate sul vecchio pattern → mitigato da SchemaMeta version check + grep sistematico + evaluation set come regression |

## Ordine

1. Congelare questo schema (review insieme prima di scrivere codice)
2. `validate_db.py` PRIMA del resto (test-first: gli invarianti definiscono il target)
3. Pipeline fixes → rebuild locale → validazione
4. Backend updates → smoke test → cutover Railway
5. PLAN_citation_quality Fasi 1-2 girano sul DB nuovo (non sprecare il batch citability sul vecchio)
