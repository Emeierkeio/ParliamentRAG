# Piano: Organizzazione Codice e Pulizia Repository

> Stato: **DA FARE (post-paper, insieme al cutover — PLAN_master [J])** · Creato: 2026-07-22
> Repo coinvolti: `ParliamentRAG` (pipeline + app main) · `ParliamentRAG-demo` (app demo)
> Evidenze: inventario riferimenti del 2026-07-22 (grep su Makefile + build/*.py)

## Principi

1. **Git è l'archivio**: i file legacy non si tengono "per sicurezza" — si eliminano
   con `git rm`; la history li conserva per sempre. Un file morto nel repo è debito:
   confonde chi legge, appare nelle grep, finge di essere manutenuto (è successo
   con `initialize_db.py`: schema italiano morto ma constraint ancora vivi nel DB).
2. **Una sola definizione per ogni funzione**: niente helper copia-incollati tra moduli.
3. **Codice, dati e materiale tesi separati**: un repo applicativo non contiene
   PDF di paper, backup di database o appunti.
4. **Cache e artefatti mai tracciati**: solo `.gitignore`.
5. Ogni eliminazione va preceduta da `grep -rn "<nome>" .` su TUTTI i repo
   (main, demo, v2-dev branches) — l'inventario sotto è la baseline, non il verdetto finale.

---

## 1. `ParliamentRAG/build/` — pipeline

### 1a. File morti da eliminare (0 riferimenti verificati)

| File | Evidenza |
|---|---|
| `initialize_db.py` | Schema italiano legacy (Deputato/MembroGoverno), 0 refs, fuori dal flusso db-populate |
| `ingest_stenografici.py` | Percorso ingest legacy (quello degli offset `start_char_raw` rotti), 0 refs |
| `migrate_foti.py` | Migration one-shot già eseguita, 0 refs |
| `populate_ruoli.py` | Scriveva proprietà italiane legacy (`ruoloIstituzionale`), 0 refs — sostituito da `load_roles()` v2 |
| `create_vector_index.py` | Referenziato SOLO da un commento stantio in db_builder.py:301 (gli indici li crea `create_vector_index()` del builder) — eliminare file E aggiornare il commento |
| `precalculate_baseline_experts.py` | 0 refs da pipeline/Makefile — MA è tool manuale per evaluation_set: **verificare con l'utente** prima di eliminare; se serve, va in `tools/` documentato |

### 1b. Duplicazioni da consolidare

- `parse_date_to_neo4j` e `format_date_ddmmyyyy` definite DUE volte
  (csv_loader.py:120,133 e db_builder.py:76,86) → una sola definizione in
  csv_loader (o nuovo `build/dates.py`), db_builder importa. Il drift tra le due
  copie è una bomba a orologeria classica.
- `format_date_ddmmyyyy` dopo lo schema v2 non ha più usi runtime (date native)
  → probabile eliminazione totale al passo [J].

### 1c. Struttura target

```
build/
├── build_and_update.py      # CLI unica (entry point, cfr. PLAN_db_schema_v2 §3b)
├── db_builder.py            # scrittura Neo4j
├── xml_parser.py / senate_parser.py
├── chunker.py / ner.py / embedding_service.py
├── csv_loader.py            # helpers CSV + date (unica definizione)
├── ingest_atti_parlamentari.py
├── sparql_ingester.py / senate_sparql_ingester.py
├── download*.py             # (valutare merge dei 5 download_* in un modulo)
├── validate_db.py           # gate invarianti
├── classify_chunk_citability.py   # (da PLAN_citation_quality Fase 1)
├── generate_summaries.py / repair_spoken_by.py
├── config.yaml / build_config.py / app_config.py
└── tests/                   # fixtures/ + test attuali, .pytest_cache in .gitignore
```

- `.pytest_cache/` presente su disco: aggiungere a `.gitignore` radice se non c'è.
- Valutare (bassa priorità): `pyproject.toml` per build/ con dipendenze pinned
  separate da backend (`requirements-build.txt` già esiste — formalizzarlo).

## 2. `ParliamentRAG-demo/` — root ripulita

Oggi la root mescola app, tesi e artefatti:

| Elemento | Destinazione |
|---|---|
| `main.tex`, `appendice_valutazione.tex`, `Who_Speaks_Matters...pdf`, `thesis/`, `Prompts.md` | → `thesis/` unica directory (o meglio: repo/Overleaf separato — il paper non deve stare nel repo dell'app) |
| `Screenshot 2026-07-22*.png` (untracked in root) | → eliminare o `docs/assets/` se serve alla documentazione |
| `todo.txt` | → convertire in issue/plan e eliminare |
| `PLAN_*.md` (4 file) | → `docs/plans/` con un `docs/plans/README.md` indice |
| `neo4j-local-backups/` | → FUORI dal repo (directory locale ignorata); i backup non si versionano |
| `outputs/` | → verificare contenuto: se artefatti generati → .gitignore |
| `.env.bak` | → eliminare (le credenziali non si backuppano nel repo) |
| `scripts/` root | → verificare sovrapposizione con `backend/scripts/`, consolidare |

## 3. Strategia due-repo (decisione post-paper)

`ParliamentRAG-demo` è un fork divergente di `ParliamentRAG` (il porting multilingua
ha già creato drift: bug fixati in uno e non nell'altro — es. l'ingestion atti rotta
solo su v2-dev). Opzioni:

- **A (raccomandata)**: un solo repo, la demo diventa configurazione di deploy
  (env + branch `demo` o flag). Un fix, un posto.
- B: demo resta fork ma con sync periodico documentato (cherry-pick list).

Decidere DOPO il cutover v2 — non aggiungere questa migrazione al carico attuale.

## 4. Igiene trasversale

- `.gitignore` audit su entrambi i repo: `__pycache__`, `.pytest_cache`, `*.log`
  (`build_v2.log`!), `embeddings_cache.db` (già ok), dump/backup, `.env*` tranne `.env.example`
- Rimuovere credenziali hardcoded residue negli script legacy (initialize_db.py e
  ingest_atti hanno `NEO4J_PASSWORD = "thesis2026"` nel codice — spariscono con la
  pulizia, ma verificare che non ne restino altrove: `grep -rn "thesis2026" --include='*.py'`)
- README di `build/` (10 righe): flusso della pipeline, comandi principali, dove
  sta la cache — l'onboarding oggi è "leggi 9.600 righe"

## Ordine di esecuzione

1. **Dopo cutover v2 validato** (PLAN_master [J]) — mai eliminare `ingest_stenografici.py`
   e soci finché il DB v1 è ancora quello attivo
2. Branch `chore/code-cleanup` su ciascun repo
3. Per ogni file in tabella 1a: `grep` di conferma su tutti i repo → `git rm` → commit atomico per file
4. Consolidamento helper duplicati (1b) + fix commento db_builder.py:301
5. Riorganizzazione root demo (2) + gitignore audit (4)
6. Aggiornare CLAUDE.md/memoria con la nuova struttura
7. La decisione due-repo (3) è un piano a sé, dopo
