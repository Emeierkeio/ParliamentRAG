# PIANO UFFICIALE — Rebuild DB v2 e Qualità Citazioni

> Stato: **ATTIVO** · Creato: 2026-07-22 · Documento master
> Piani di dettaglio: `PLAN_db_schema_v2.md` (schema + rebuild) · `PLAN_citation_quality.md` (citazioni/intro)
> Repo pipeline: `ParliamentRAG/build/` · Repo backend demo: `ParliamentRAG-demo/backend/`

## Decisioni prese (log)

| Data | Decisione |
|---|---|
| 2026-07-22 | Full rebuild side-by-side, NON patch incrementale. Costo re-embedding accettato (mitigato da `build/embeddings_cache.db`) |
| 2026-07-22 | Schema v2 allineato Semantic Web (C10/C11: URI LOD, mapping ontologico OCD/FOAF/ORG/SKOS/PROV-O/AKN) — funzionale al paper |
| 2026-07-22 | Rimodellamento `Person` incluso nel primo rebuild (raccomandato: evita un secondo rebuild; confermare allo start) |
| 2026-07-22 | Citability (PLAN_citation_quality Fase 1-2) gira SOLO sul DB v2 — non si spreca il batch sul vecchio schema |

## Sequenza ufficiale

```
ORA (pre-rebuild, indipendenti dal DB):
  [A] PLAN_citation_quality Fase 0 — quick wins su prompt/filtri (solo codice backend demo)

NOTTE 1 (rebuild):
  [B] Implementazione pipeline v2 (PLAN_db_schema_v2 §3) — ordine:
      1. build/validate_db.py         (test-first: gli invarianti definiscono il target)
      2. embedding_service.py         (list[float] nativi, cache riusata)
      3. initialize_db.py/db_builder  (constraint v2, date native, SchemaMeta, no label morte)
      4. chunker.py                   (testo pulito + assert substring, via offset raw)
      5. ingest_atti_parlamentari.py  (date, embedding nativi, EurovocConcept da cache URI)
      6. Modello Person               (csv_loader, populate_ruoli, HOLDS_OFFICE/MEMBER_OF_*)
      7. xml_parser.py                (speaker_name_raw, unica versione testo)
  [C] Container nuovo + lancio ingest notturno (comandi sotto)

MATTINA DOPO:
  [D] validate_db.py sul DB nuovo → iterare finché verde (DB vecchio intatto, zero fretta)

GIORNI SEGUENTI (prove):
  [E] ✅ FATTO 2026-07-23 — branch `demo-db-v2` (NB: i due folder sono WORKTREE dello
      stesso repo; `db-schema-v2` è checked-out in ParliamentRAG). Tutto DUAL-COMPAT
      (gira su v1 7691 E v2 7692, smoke test passed su entrambi):
      · search.py: 3 query atti su nomi v2 + date normalizzate + EuroVoc da concetti
      · evidence/query/chat: span via compute_chunk_span (find(), offset v1 solo fallback)
      · ruoli commissione: IS_* (v1) + MEMBER_OF_COMMITTEE.role (v2) in authority,
        chat, query, scorer
      · retrieval: coalesce(parent_debate_title, title) ovunque
      · deps.py: SchemaMeta version check a startup (log-only fino al cutover)
      · parse_embedding: già dual, nessun cambio
      Feature risorte su v2 (morte silenziose su v1): ricerca semantica atti,
      rerank semantico graph channel (len(stringa)≠1536 → skippato), filtro
      recency ActsComponent (string vs date → null)
  [F] Prove comparative vecchio/nuovo (flip di NEO4J_URI nel .env) sui criteri §Criteri
  [G] PLAN_citation_quality Fase 1-2 sul DB v2 (batch citability + quote picker LLM)

CUTOVER (quando criteri verdi):
  [H] Export ChatHistory + SurveyEvaluation dal DB remoto attuale → import nel nuovo
      (unici dati NON rigenerabili: valutazioni del paper)
  [I] Dump DB v2 → server Hetzner (VPS 89.167.54.206, container `parliament-neo4j`,
      /opt/parliament-rag/docker-compose.yml — il DB NON è su Railway, su Railway
      girano solo frontend+backend che puntano al VPS):
      scp del dump → neo4j-admin database load nel container → restart.
      Volume/dump vecchio conservato sul VPS fino a discussione paper (rollback)
  [J] Merge branch, PLAN_citation_quality Fase 3 (demolizione pattern zoo),
      aggiornamento CLAUDE.md/memoria con schema v2

POST-CUTOVER (espansioni su schema stabile):
  [K] Senato come :Person:Senator (pipeline senate_* esistente)
  [L] Voti: girare enrich-sparql sul DB v2 col modello IndividualVote ESISTENTE
      (Fase 8+14 di v2-dev ci sono costruite sopra — vedi rettifica §2.4 dello
      schema plan; refactor CAST = piano separato futuro)
  [M] Export RDF via n10s (deliverable paper, opzionale)

FEATURES EREDITATE DA v2-dev (dentro db-schema-v2, non richiedono lavoro DB oltre [L]):
  Fase 14 vote intelligence (7/8 plan fatti) · transcript viewer (WIP non committato)
  · summaries AI (generate_summaries) · compass · multilingua

STRATEGIA BRANCH (decisione utente 2026-07-22, NON ancora ufficiale):
  `db-schema-v2` (⊇ v2-dev, 309 commit sopra main) diventa la linea mantenuta;
  niente più merge verso v2-dev; NESSUN branch si elimina finché la scelta
  non è ufficializzata.
```

## Comandi operativi

### Setup container v2 (porta 7692 — 7691 è il demo attuale, 7689 il main)
```bash
docker run -d --name parliament-neo4j-v2 \
  -p 7692:7687 -p 7478:7474 \
  -v parliament_v2_data:/data \
  -e NEO4J_AUTH=neo4j:<password> \
  -e NEO4J_PLUGINS='["apoc"]' \
  neo4j:5    # allineare versione/config al container demo esistente
```

### Lancio ingest notturno
```bash
cd ~/Desktop/ParliamentRAG
git checkout db-schema-v2
NEO4J_URI=bolt://localhost:7692 caffeinate -i nohup make db-populate > build_v2.log 2>&1 &
# caffeinate: il Mac non dorme a metà ingest
# embeddings: quasi tutti cache hit da build/embeddings_cache.db
```

### Verifica mattutina
```bash
NEO4J_URI=bolt://localhost:7692 python build/validate_db.py   # gate: tutti gli invarianti
tail -50 build_v2.log
```

### Flip backend per le prove (una riga)
```bash
# in ParliamentRAG-demo/.env:  NEO4J_URI=bolt://localhost:7692  (nuovo) / 7691 (vecchio)
```

## Criteri di sostituzione (oggettivi, tutti richiesti)

1. `validate_db.py` verde: 0 embedding STRING, vector index atti popolato (>0 risultati,
   oggi 0), 0 Speech senza SPOKEN_BY, invariante substring 100%, 0 date stringa,
   0 placeholder vuoti, URI conformi ai pattern LOD, EurovocConcept collegati
2. Evaluation set (`evaluation_set.json`): top-10 retrieval overlap ≥90% vs DB vecchio
3. Quote nel viewer esatte al carattere (campione manuale 20 citazioni)
4. Ricerca semantica atti funzionante end-to-end dal frontend
5. Latenza query pipeline non peggiorata (p95 ±10%)

## Rollback

- Prima del cutover: nessun rischio, il DB vecchio non viene mai toccato
- Dopo il cutover Railway: riavvio sul volume/dump vecchio (conservato fino a
  discussione paper) + revert del merge backend

## Cosa NON si tocca

- ChatHistory e SurveyEvaluation esistenti (dati valutazione paper): solo export/reimport
- Id gerarchici Session/Speech/Chunk (`leg19_sed79_…`): invariati, referenziati ovunque
- Il DB di produzione demo su Railway fino a criteri verdi
