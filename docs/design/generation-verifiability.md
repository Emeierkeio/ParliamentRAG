# Generation verifiability refactor

Data: 2026-09-19 — branch `feat/generation-verifiability`

Obiettivo: aumentare verificabilità, faithfulness e precisione di attribuzione
della pipeline di generazione senza toccare retrieval, authority scoring,
formato SSE, formato dei citation ID, contratto frontend e modelli LLM in uso
(writer/integrator `gpt-4.1`, soglia di coerenza 0.22 calibrata su quel
modello; picker/rewriter/domain/traduzioni `gpt-5.6-luna` in prova).

## Stato di fatto (ricostruito dal codice, non da docs/Prompts.md)

Flusso runtime: `routers/query.py` → retrieval (con `QueryRewriter`) →
`check_domain` (parallelo) → authority → `GenerationPipeline.generate()`:
analyst → sectional writer (con `_pick_quote` per-partito e position brief) →
integrator LLM con guard → coherence validator → hard-removal/sostituzioni →
surgeon deterministico → cleanup regex. Compass e traduzione fuori pipeline.

Problemi osservati leggendo il codice:

1. **L'analyst è vestigiale**: `claims` arriva a `_write_section` ma non entra
   in nessun prompt. Il costo del claim decomposition non produce grounding.
2. **Il quote picker è generativo, non selettivo**: il modello riscrive la
   citazione e `_reconstruct_verbatim` prova a rimapparla sulle frasi
   originali. Il modello resta la fonte della stringa; la selezione tra
   candidati deterministici elimina la classe di errori non-verbatim.
3. **L'integrator LLM riscrive tutto**: da qui derivano perdita di citazioni
   (retry dedicato), paragrafi doppi (`_dedupe_party_paragraphs`), quote
   copiate nel partito sbagliato (`_dedupe_citation_occurrences`), partiti
   mancanti (`_inject_missing_party_paragraphs`). Le sezioni sono già
   validate: riscriverle è il punto di massimo rischio a valore aggiunto
   minimo (solo l'introduzione è davvero generativa).
4. **La position brief è trattata come ground truth**: "VIETATO citare frasi
   che sembrano difendere la proposta" trasforma un prior lessicale
   (regex PRO/CONTRO) in un vincolo duro → bias di conferma e appiattimento
   di posizioni condizionali/evolutive su un'unica etichetta.
5. **Nessun prompt delimita i dati**: query utente ed evidenze entrano nei
   prompt senza delimitatori né istruzione anti prompt-injection.
6. **La traduzione può corrompere i citation ID**: la preservazione dei
   target `](leg19_…)` è affidata a una regola di prompt.
7. **I summary build-time non vincolano all'evidenza**: nessuna regola
   "solo informazioni presenti nei testi".
8. **Gli assi della compass derivano dalla sola query**: dimensioni
   plausibili, non necessariamente emerse dal dibattito recuperato.

## Decisioni

### D1 — Quote picker a candidati deterministici (sectional.py + nuovo modulo)
Nuovo modulo `generation/quote_candidates.py`: estrazione deterministica di
span candidati (1–2 frasi consecutive, 80–350 char, filtri su connettivi
iniziali, ellissi «…», discorso riportato in apertura, contenuto
procedurale). Il picker LLM riceve i candidati numerati e risponde JSON
(structured output) con l'indice selezionato + flag di validità. La stringa
finale è il testo del candidato preso dalla fonte: verbatim per costruzione.
Fallback: se l'estrazione non produce candidati, si mantiene il percorso
attuale (free pick + verifica substring + ricostruzione).
Firma `_pick_quote → (eid, quote)` invariata: pipeline non toccata.

### D2 — Integrator assemblativo (integrator.py)
Nuova modalità `generation.integrator_mode: assembler` (default) accanto a
`llm` (comportamento attuale, conservato per confronto A/B):
- le sezioni validate sono assemblate deterministicamente nei blocchi
  Governo/Maggioranza/Opposizione/Misto con prefisso "Per {partito}, …";
- l'LLM scrive SOLO l'introduzione (2 frasi: merito + scala), senza marcatori
  {CIT:N} in input → impossibile perderli o duplicarli;
- citazioni, attribuzioni e stance preservate per costruzione; il guard,
  i dedupe e le injection di riparazione diventano no-op su questo percorso.
In modalità `llm` il prompt viene riscritto come "editor strutturale, non
autore" con priorità preservation > citazioni > attribuzione > ordine >
leggibilità; rimossa la regola "ogni verbo diverso" (la varietà linguistica
è subordinata alla correttezza).

### D3 — Position brief come ipotesi editoriale (position_brief.py)
- direzione calcolata per periodo (bucket per anno) oltre che complessiva;
- etichette estese: FAVOREVOLE / CONTRARIO / CONDIZIONALE / IN EVOLUZIONE /
  CONFLITTUALE / NON DETERMINATO;
- il testo del brief dichiara esplicitamente che si tratta di un'ipotesi
  derivata da pattern lessicali, da verificare contro le evidenze, non di un
  vincolo; il divieto assoluto diventa un'istruzione calibrata (una
  citazione in apparente contrasto con l'orientamento va ricontrollata, non
  scartata a priori — la critica è evidenza valida quanto il sostegno).

### D4 — Analyst evidence-grounded e finalmente usato (analyst.py, sectional.py)
Schema claims esteso: `evidence_status` (supported/partial/absent/
conflicting), `evidence_ids` (validati in codice contro gli ID mostrati),
`stance`, `temporal_scope`. Il prompt vieta di inventare posizioni per
partiti senza evidenza (evidence_status=absent, claim descrittivo).
I claim del partito entrano nel prompt del sectional writer come ipotesi
editoriale aggiuntiva; gli `evidence_ids` non validi vengono rimossi
deterministicamente.

### D5 — Prompt security (tutti i servizi LLM)
Delimitatori espliciti (`<QUERY>`, `<EVIDENZE>`, `<TESTO>`) e istruzione a
trattare il contenuto come dati, ignorando eventuali istruzioni contenute.

### D6 — Traduzione con placeholder deterministici (translation.py)
Prima della traduzione i target dei link citazione `](leg19_…)` sono
sostituiti con `__CIT_N__`; dopo la traduzione i placeholder sono
ripristinati. Se un placeholder è perso/corrotto si ritorna il testo
originale non tradotto (fallback sicuro, invariante: mai un ID alterato).

### D7 — Summaries build-time vincolati all'evidenza (generate_summaries.py)
Regola "usa solo informazioni esplicitamente contenute nei testi forniti",
divieto di inferire intenzioni/consenso/causalità/successo, delimitatori.

### D8 — Compass evidence-grounded (semantic_axes.py, compass/pipeline.py)
Il generatore di assi riceve un campione di frammenti recuperati (testi
clippati, delimitati) e deve derivare gli assi dal disaccordo effettivo nel
campione, non da dimensioni plausibili a priori. Cache invariata (chiave =
query normalizzata: la stabilità inter-finestra resta necessaria per la
timeline). Payload frontend invariato.

### D9 — Claim/citation validation deterministica + metrica
- `surgeon.extract_unsupported_claims` resta la base; nuova metrica
  `unsupported_claim_rate` in `routers/evaluation.py` (campo additivo su
  `AutomatedMetrics`, calcolata dal testo risposta, nessun dato nuovo da
  memorizzare);
- enforcement post-integrazione dei nomi in grassetto senza citazione nella
  stessa frase (estensione del principio già applicato nel sectional).

### D10 — Query rewriter e domain check
Rewriter: regole di preservazione (nomi propri, leggi, vincoli temporali,
negazioni, termini di posizione), divieto di introdurre posizioni non
presenti, orientamento retrieval; API a stringa invariata. Domain check:
terzo stato `ambiguous` (mai bloccante — la decisione resta all'evidence
gate), delimitatori.

## Cosa NON si fa (e perché)

- **Nessun cambio di modello**: gpt-4.1 writer/integrator e soglia 0.22
  restano; migrazioni modello sono un binario separato (branch
  test/modelli-gpt56).
- **Nessun cambio a SSE, citation ID `[«quote»](leg19_…)`, API pubbliche.**
- **Il rewriter non restituisce l'oggetto strutturato** (original/expanded/
  entities): il router consuma una stringa via metadata `rewritten_query`;
  introdurre l'oggetto ora toccherebbe retrieval senza beneficio misurabile.
- **Nessuna riscrittura LLM dei claim falliti** (punto 11 della richiesta):
  in assenza di eval umana, un rewrite automatico rischia di introdurre
  nuovo testo non verificato; i claim non supportati vengono riportati in
  metrica e trace, non riscritti.
- **Filtro competenza ministri in modalità assembler**: il filtro attuale è
  un giudizio dell'integrator LLM; in assembler la sezione GOVERNO passa
  com'è (già filtrata per rilevanza a monte, min_similarity 0.35). Un
  filtro deterministico ministro↔tema richiederebbe una mappa delega→tema
  che oggi non esiste nel grafo.

## Verifica

Baseline pre-modifiche: `backend/tests` 28 passed (2026-09-19).
Nuova suite `backend/tests/test_generation_regression.py` con i casi
offline-testabili dei 20 richiesti (candidati, verbatim, duplicati,
preservazione CIT in assembler, placeholder di traduzione, brief temporale,
Misto, no-evidence). I casi che richiedono LLM/Neo4j live restano fuori
dalla suite unit e vanno coperti dall'eval set esistente.
