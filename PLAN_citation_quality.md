# Piano: Introduzione e Citazioni Significative

> Stato: **DA FARE** · Creato: 2026-07-22 · Aggiornato: 2026-07-22 (allineato a PLAN_db_schema_v2)
> Repo: ParliamentRAG-demo (backend FastAPI + Neo4j)
> Riferimento visivo: `Screenshot 2026-07-22 alle 17.47.16.png` (intro boilerplate + quote Tajani irrilevante)
> ⚠️ Subordinato a `PLAN_master.md`: la Fase 0 si fa SUBITO (solo codice backend),
> le Fasi 1-2 girano SOLO sul DB v2 dopo il rebuild (PLAN_db_schema_v2), la Fase 4 è
> stata ASSORBITA dallo schema v2.

## 1. Problema

Due sintomi ricorrenti nelle risposte generate:

1. **Introduzione non significativa** — dump statistico formulaico ("84 interventi, 45 deputati,
   sedute N. 175, 180, …") agganciato a un titolo dibattito procedurale ("Si riprende la
   discussione") invece del provvedimento reale. Zero contenuto di merito.
2. **Citazioni non significative** — quote retoriche/auto-referenziali che non parlano del tema
   della query (es. Tajani su «un principio che il centrodestra, guidato da Silvio Berlusconi,
   ha affermato… quando si è trovato all'opposizione» in una risposta sul supporto a Israele).

## 2. Root cause (perché i fix precedenti spostavano il problema)

Il giudizio di "significatività" — una proprietà **semantica** — è implementato con **string
matching**: `backend/app/services/citation/sentence_extractor.py` è ~685 righe di regex
(`_OPINION_PATTERNS`, `_PROCEDURAL_PATTERNS`, `_META_COMMENT_PATTERNS`,
`_ARGUMENTATION_PATTERNS`, euristiche su verbi/frammenti). Ogni bug produce un pattern nuovo;
la coda di casi limite è infinita per costruzione. Inoltre il giudizio avviene a **query-time**
sul chunk che il retrieval ha già scelto per authority/similarity: se il chunk migliore ha solo
frasi deboli, l'extractor cita comunque "il meglio del peggio" (fallback `or sorted_by_score[:1]`
in `_select_best`, `MIN_QUALITY_SCORE = 0.15` di fatto mai bloccante).

**Principio guida del piano**: spostare il giudizio semantico (a) su un LLM, (b) a index-time
dove possibile, così la spazzatura non entra mai in pipeline. Analogo a quanto già fatto con
`baseline_experts` pre-calcolati in `evaluation_set.json`.

## 3. Architettura target

```
INGESTION (una tantum + incrementale nel db-update)
  └─ Batch LLM (gpt-4o-mini) classifica ogni chunk:
     citability_score [0,1] + citability_class {sostanza|procedurale|retorica|meta}
     → salvati come proprietà del nodo Chunk in Neo4j

RETRIEVAL (query-time, zero costo aggiunto)
  └─ merger usa citability stored al posto di compute_chunk_salience() regex
  └─ filtro hard: chunk con class=procedurale/retorica esclusi dal pool citabile

GENERAZIONE (query-time)
  └─ Quote picker LLM: dati 2-3 chunk top del partito + query,
     seleziona la quote verbatim più sostanziale
  └─ Verifica verbatim esistente (surgeon) resta come guardia
  └─ Intro: 1 frase di merito + 1 frase di scala; niente elenco sedute in prosa
```

---

## Fase 0 — Quick wins (indipendenti, ~1h, fare subito)

### 0.1 Filtro titoli dibattito procedurali
- **File**: `backend/app/services/generation/pipeline.py` → `_compute_topic_statistics`
  (righe ~532-540, `Counter` su `debate_titles`).
- Escludere dal conteggio i titoli puramente procedurali prima del `most_common(1)`:
  - regex: `^si riprende la discussione`, `^seguito della discussione\.?$`,
    `^ripresa della discussione`, `^discussione congiunta$`, titoli < 25 char senza
    sostantivi di contenuto.
- Se dopo il filtro non resta nulla → `debate_title = None` (il prompt gestisce già l'assenza).

### 0.2 Riscrittura spec introduzione nel prompt integrator
- **File**: `backend/app/services/generation/integrator.py` → `SYSTEM_PROMPT` (righe 39-46)
  e user prompt (riga ~250).
- Nuova spec:
  - **Frase 1**: inquadramento nel merito — cosa si discute concretamente (provvedimenti,
    poste in gioco). L'integrator vede già le sezioni di partito: può derivarlo da lì senza
    anticipare le posizioni.
  - **Frase 2**: dati di scala (N interventi, N deputati, periodo).
  - **Rimuovere** "CITA le sedute specifiche" — l'elenco "N. 175, 180, … e altre 26" esce
    dalla prosa. I numeri di seduta restano disponibili al frontend via `sessions_detail`
    (già stat cliccabile).
- Aggiornare coerentemente `_format_statistics` (togliere la riga "Sedute parlamentari: N. …"
  o marcarla "NON citare in prosa").

### 0.3 Gate di citabilità minimo (tampone in attesa di Fase 1-2)
- **File**: `backend/app/services/citation/sentence_extractor.py` → `_select_best` / `extract`.
- Regola: frase citabile solo se `overlap_query > 0` **oppure** `salience ≥ 0.7`.
  Se nessuna frase del chunk passa → return `""` (il contratto esiste già: "No sentence passed
  quality threshold — return empty").
- **Verificare i chiamanti** gestiscano `""` scalando all'evidenza successiva dello stesso
  partito (in `sectional.py` e `surgeon.py`); se non lo fanno, aggiungere il fallback.

---

## Fase 1 — Citabilità pre-calcolata a index-time (il fix definitivo)

### 1.1 Schema Neo4j
Nuove proprietà sul nodo `Chunk` (label esistente, cfr. `dense_channel.py`: `c.id`, `c.text`):
```
c.citability_score  : float [0,1]
c.citability_class  : string {substance | procedural | rhetoric | meta}
c.best_quote        : string   # frase verbatim più citabile del chunk (pre-estratta)
c.citability_v      : int      # versione classificatore, per re-run selettivi
```

### 1.2 Script batch di classificazione
- **Nuovo file**: `ParliamentRAG/build/classify_chunk_citability.py` — vive nella pipeline
  di build (non in `backend/scripts/` del demo): è uno step di ingestion, non di runtime.
  Gira sul DB v2 dopo il rebuild (PLAN_master [G]); NIENTE backfill sul DB vecchio.
- Loop su tutti i Chunk senza `citability_v` corrente, batch da ~20 chunk per call.
- Modello: `gpt-4o-mini`, structured output JSON:
  ```json
  {"chunk_id": "...", "class": "substance", "score": 0.85,
   "best_quote": "frase verbatim estratta dal chunk"}
  ```
- Prompt: "Sei un analista parlamentare. Per ogni frammento di intervento classifica se
  contiene una posizione politica/argomentazione di merito (substance), formule procedurali
  (procedural), retorica auto-celebrativa o di schieramento senza contenuto sul tema
  (rhetoric), o meta-commento sul dibattito stesso (meta). Estrai la singola frase verbatim
  più citabile, se esiste."
- **Guardia verbatim**: `best_quote` accettata solo se substring esatta di `c.text`
  (normalizzando whitespace); altrimenti scartata e si tiene solo score/class.
- Idempotente e riprendibile (checkpoint su `citability_v`), rate-limit friendly.
- Costo stimato: una tantum, pochi euro sull'intero corpus (chunk finiti e statici).
- **Integrazione pipeline dati**: aggiungere step alla pipeline `db-update-all` così i chunk
  nuovi vengono classificati a ogni aggiornamento dati.

### 1.3 Integrazione retrieval
- **File**: `backend/app/services/retrieval/dense_channel.py` e `graph_channel.py` —
  aggiungere `c.citability_score AS citability, c.citability_class AS citability_class,
  c.best_quote AS best_quote` alle RETURN.
- **File**: `backend/app/services/retrieval/merger.py` (righe ~158-171) — usare lo score
  stored al posto di `compute_chunk_salience()` regex; fallback alla regex solo se la
  proprietà manca (chunk non ancora classificati). `salience_weight` (0.20) resta invariato.
- Filtro hard nel pool citazioni: `citability_class in {procedural, rhetoric}` → il chunk
  può contribuire al contesto ma **non** può diventare citazione.

---

## Fase 2 — Quote picker LLM a generation-time

### 2.1 Selezione quote
- **File**: `backend/app/services/generation/sectional.py` (+ `evidence_first_writer.py`).
- Per ogni sezione partito: invece di `extract_best_sentences` (scoring regex), un call a
  `gpt-4o-mini` con i top 2-3 chunk del partito (già ordinati per authority/similarity) + query:
  "Seleziona la citazione verbatim più sostanziale e pertinente alla domanda. Se nessun
  passaggio è pertinente, rispondi NONE."
- Se il chunk ha `best_quote` pre-calcolata (Fase 1) e pertinente, usarla direttamente:
  il call diventa una scelta tra candidati pre-estratti → più economico e robusto.
- `NONE` → si scala all'evidenza successiva del partito; se nessuna passa → messaggio
  `no_evidence_message` esistente (meglio nessuna quote che una quote vuota).

### 2.2 Guardie esistenti da mantenere
- Verifica verbatim del `surgeon` (`_build_verified_citations`) resta l'ultima barriera.
- Dedup semantico cross-speaker (`_deduplicate_citations_across_speakers`) invariato.
- Citation guard dell'integrator (preservazione `[CIT:N]`) invariato.

---

## Fase 3 — Demolizione del pattern zoo

Solo quando Fase 1+2 sono live e validate:
- `sentence_extractor.py` si riduce a utility di splitting frasi + boundary cleanup
  (`_split_sentences`, `_truncate_at_boundary`, `_clean_result`).
- **Eliminare**: `_OPINION_PATTERNS`, `_PROCEDURAL_PATTERNS`, `_META_COMMENT_PATTERNS`,
  `_ARGUMENTATION_PATTERNS`, `_political_salience_score`, `compute_chunk_salience`
  (sostituita dallo score stored; tenere solo come fallback finché tutto il corpus non è
  classificato, poi rimuovere).
- Da ~685 righe a ~200.

---

## Fase 4 — Fix titoli a ingestion — ✅ ASSORBITA DA PLAN_db_schema_v2

Lo schema v2 introduce `Debate.parent_debate_title` risolto a ingest
(PLAN_db_schema_v2 §2.2): i titoli-continuazione ("Si riprende la discussione…")
vengono collegati al provvedimento padre durante il build. Questa fase non ha più
lavoro proprio. Il quick-win 0.1 resta come difesa in profondità nel backend e va
aggiornato post-rebuild per preferire `parent_debate_title` quando presente.

---

## Validazione

1. **Set di regressione**: le query di `evaluation_set.json` + la query Israele dello
   screenshot. Prima/dopo per ogni fase.
2. **Metrica citazioni**: % di citazioni con `class=substance` e pertinenza LLM-judged
   (riusare l'impianto di valutazione esistente in `evaluation.py`).
3. **Metrica intro**: checklist — nomina provvedimento reale? contiene frase di merito?
   niente elenco sedute in prosa?
4. **Latency budget**: il quote picker aggiunge ~1 call piccolo per sezione partito;
   misurare che il p95 della generazione non peggiori oltre ~1s.

## Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| LLM inventa quote non verbatim | substring check + surgeon già esistente |
| Chunk non ancora classificati dopo db-update | fallback a regex salience finché `citability_v` assente |
| Filtro hard troppo aggressivo → partiti senza citazioni | soglia conservativa iniziale (esclude solo `procedural`/`rhetoric` con score alto); monitorare `no_evidence_message` rate |
| Costo batch iniziale | gpt-4o-mini, batch da 20, corpus finito → pochi euro, una tantum |

## Ordine di esecuzione (allineato a PLAN_master)

1. **Fase 0** — subito, solo codice backend demo, indipendente dal DB (PLAN_master [A])
2. **Fase 1** — dopo il rebuild v2, come step della pipeline di build (PLAN_master [G]);
   lo schema Chunk v2 nasce già con i campi citability (PLAN_db_schema_v2 §2.2)
3. **Fase 2** — quote picker LLM, insieme alla Fase 1 (PLAN_master [G])
4. **Fase 3** — demolizione pattern zoo, dopo il cutover (PLAN_master [J])
5. ~~Fase 4~~ — assorbita dallo schema v2
