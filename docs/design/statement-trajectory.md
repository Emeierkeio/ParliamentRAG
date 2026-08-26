# Statement Trajectory ("Traiettorie") — Design Document

Status: design only, no implementation. Date: 2026-08-26.

Given one statement by an MP (a citation the user clicked, or a chunk picked from
search), the feature reconstructs how that position evolved: what the same speaker
and their parliamentary group said and signed on the same topic across the XIX
Legislature, with typed relations between statements and a temporal visualisation.
Every claim resolves to verbatim, offset-verified excerpts through the existing
citation machinery.

---

## 1. Codebase findings

### 1.1 Files read

Backend, graph and retrieval:

| File | What it taught |
|---|---|
| `backend/app/services/retrieval/dense_channel.py` | Vector index `chunk_embedding_index` on `Chunk.embedding` (1536-d); canonical Cypher path `Chunk ← HAS_CHUNK ← Speech → SPOKEN_BY → Deputy\|GovernmentMember`, session date via `Speech ← CONTAINS_SPEECH ← Phase ← HAS_PHASE ← Debate ← HAS_DEBATE ← Session`; group resolved temporally with `mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= ...)`; Misto resolved to `MistoComponent`, never to the monolithic group. |
| `backend/app/services/retrieval/graph_channel.py` | Acts carry `title_embedding`, `description_embedding`, `eurovoc_embedding`; the graph channel walks `PRIMARY_SIGNATORY\|CO_SIGNATORY` to reach speeches by act signatories. Topic-to-act linking already works via embedding similarity on act embeddings. |
| `backend/app/services/retrieval/engine.py` | Channel fusion, thresholds, and where the query embedding is produced (executor, batched). |
| `backend/app/services/authority/components.py` | `MEMBER_OF_COMMITTEE` has `start_date`/`end_date`/`officerRole`; act weights (primary 1.0, co 0.3); time-decay half-lives (acts 365d, speeches 180d) reusable for trajectory ranking. |
| `backend/app/services/compass/stance.py` | Per-fragment stance scoring with `gpt-4.1-mini`: batches of 25 fragments, up to 8 workers, text clipped to 700 chars, output in [-1, +1] or null per axis, embedding-projection fallback. This is the engine trajectory reuses for per-statement stance. |
| `backend/app/services/compass/semantic_axes.py`, `pipeline.py` | Axis objects carry `name`, `positive_pole`, `negative_pole` with descriptions; axes are derived per query, not persisted. |
| `backend/app/models/evidence.py` | `UnifiedEvidence` schema; `span_start`/`span_end` are offsets into the **full speech text**; `compute_chunk_span(speech_text, chunk_text)` at `evidence.py:202` is the existing offset producer. `quote_text` vs `chunk_text` separation. |
| `backend/app/services/generation/surgeon.py` | `_extract_quote(text, span_start, span_end)` (`surgeon.py:315-349`) is the only valid citation source: direct slicing, no fuzzy matching; on mismatch it falls back to `extract_best_sentences`, never to approximate matching. |
| `backend/app/services/citation/sentence_extractor.py` | `SentenceExtractor.extract()` picks citable sentences; citability is precomputed at index time (`Chunk.citability_score`, `citability_class`, `best_quote`). |
| `backend/app/routers/query.py` | Full SSE catalog (§3.5); global `asyncio.Semaphore` at `query.py:37-45` with waiting event, acquire, `finally: release`; `_build_verified_citations` output shape (the `citation_details` payload the frontend already renders); `ThreadPoolExecutor(max_workers=10)` pattern for parallel graph fetches. |
| `backend/app/routers/chat.py`, `history.py` | Queue `waiting` event, persistence of citations/experts as JSON on `ChatHistory`. |
| `backend/app/key_pool.py`, `tracing.py`, `llm_recorder.py`, `log_context.py` | `make_client()` = key rotation + LangSmith wrapper + recorder wrapper; `@stage("name")` decorator for traced stages; recorder is a ContextVar, so any LLM call made inside the request context lands in `trace.llm_calls` for free. |
| `backend/app/services/timeline_service.py` | An unrelated "timeline" feature already exists (session browser at `/timeline`). The new feature must not reuse that name. Hence: **trajectory**. |
| `backend/app/main.py`, `services/deps.py`, `config.py` | Router registration pattern, lazy singleton services dict, model names in config (`generation.models.*`, `compass.stance.model`), `ContextPropagatingExecutor` as default executor. |
| `build/db_builder.py`, `build/sparql_ingester.py`, `build/ingest_misto_componenti.py`, `build/ingest_atti_parlamentari.py` | Ground-truth ingest Cypher: every node label, relationship type and property listed in §1.2 comes from these writers, cross-checked against reader queries. |

Frontend:

| File | What it taught |
|---|---|
| `frontend/src/app/globals.css` | OKLch token set: `--primary` (institutional blue ≈ #1B3A5C), `--destructive` (parliamentary bordeaux), 5-slot chart palette, radius scale from 0.75rem, Fraunces as `--font-display`, Geist sans/mono, dark variant via `.dark`. Custom keyframes already in use (`hemicycle-dot-in`, `trace-grow`) set the animation vocabulary. |
| `frontend/src/components/chat/CitationCard.tsx` | `CitationCard` (inline) + `CitationModal` (detail) live in one file; the modal takes `{citation, isOpen, onClose}` and renders full text with quote highlighting, translation, camera.it links. The modal is **not exported**, only the card is. |
| `frontend/src/components/chat/ExpertCard.tsx` | `ExpertCard`/`ExpertRow`/`ExpertModal`; party color via `config.politicalGroups[group].color`; authority breakdown grid. |
| `frontend/src/components/chat/CompassCard.tsx` | The house style for data viz: hand-rolled SVG, pointer-capture pan, wheel zoom, Radix tooltips, no charting library. Group color/abbrev map duplicated locally (`CompassCard.tsx:138-150`). |
| `frontend/src/components/chat/TraceCard.tsx` | Newest design language: waterfall bars with `animate-trace-grow`, tabbed dialog, monospace metrics. |
| `frontend/src/hooks/use-chat.ts` | SSE consumption: `fetch` POST → `body.getReader()` → buffer split on `\n\n` → `switch(data.type)`. The pattern to clone for a `use-trajectory` hook. |
| `frontend/src/types/chat.ts` | `Citation`, `Expert`, `CompassData`, `TraceData` verbatim; `Citation.chunk_id` is the join key everywhere. |
| `frontend/src/config/index.ts` | Canonical party color map keyed by full group names; authority thresholds. |
| `frontend/src/app/api/chat/route.ts`, `api/[[...path]]/route.ts` | Server-side proxy pattern: named route for SSE pass-through (forwards `Accept-Language`, client IP), catch-all for plain REST. |
| `package.json` | No D3, no Recharts. Radix + lucide + custom SVG. `react-force-graph-2d` present but unused in chat. Adding a charting dependency would be off-pattern. |

### 1.2 Schema actually available (as written by ingest, read by retrieval)

Nodes: `Session{id, date, number, chamber}`, `Debate{id, title}`, `Phase`, `Speech{id, text, speakingRole}`, `Chunk{id, text, index, embedding, citability_score, citability_class, best_quote, lawRefs, personRefs}`, `Deputy:Person`, `GovernmentMember:Person`, `ParliamentaryGroup{name}`, `MistoComponent{uri, name}`, `Committee{name}`, `ParliamentaryAct{uri, type, number, title, description, presentation_date, eurovoc, title_embedding, description_embedding, eurovoc_embedding}`, `Vote`, `IndividualVote{outcome}`, `EurovocConcept{uri, label}`.

Relationships: `HAS_DEBATE`, `HAS_PHASE`, `CONTAINS_SPEECH`, `HAS_CHUNK`, `NEXT` (chunk chain), `SPOKEN_BY`, `MEMBER_OF_GROUP{start_date, end_date}`, `MEMBER_OF_COMPONENT{start_date, end_date}`, `MEMBER_OF_COMMITTEE{start_date, end_date, officerRole}`, `PRIMARY_SIGNATORY`, `CO_SIGNATORY`, `DISCUSSES` (Debate→Act), `HAS_VOTE`, `VOTED` (IndividualVote→Person), `ON_ACT` (Vote→Act), `HAS_SUBJECT` (Act→EuroVoc), `MENTIONS`, `CITES`.

### 1.3 Gaps between what the feature needs and what the graph stores

1. **No topic linking between chunks.** Nothing connects two statements "about the
   same thing" except (a) same Debate, (b) same discussed Act, (c) embedding
   similarity. Topic membership must be derived at query time and, once derived,
   is worth caching (§2). No ingest change required for the MVP.
2. **No date on Chunk.** Every temporal operation pays a 5-hop traversal to
   `Session.date`. Acceptable at trajectory scale (≤ ~150 chunks per query); a
   denormalized `Chunk.session_date` written at ingest is a cheap optimization,
   listed as optional in Phase 2.
3. **No committee speech text.** The corpus holds floor stenographic records.
   `MEMBER_OF_COMMITTEE` gives membership and officer roles, not what was said in
   committee. "Committee activity" in a trajectory therefore means *role context*
   (badge on the timeline: "president of Commissione X during this period"), not
   statements. The brief's "committee activity" is supported only at this level;
   stating otherwise would fabricate data.
4. **Stance is ephemeral.** Compass computes per-fragment stance on demand and
   discards it. Trajectory needs stance per statement anchored to a stable topic;
   §2 introduces a persistence point for exactly this.
5. **Votes are linked and usable** (`IndividualVote → VOTED → Deputy`,
   `Vote → ON_ACT → Act`). Speech-vs-vote consistency is in reach and scheduled
   for Phase 4, not the MVP.
6. **`CitationModal` is not exported** from `CitationCard.tsx`. One-line export
   change; the trajectory view must open that modal, not clone it.

---

## 2. Data model

### 2.1 Principle

MVP writes nothing to the graph. Phase 2 adds a cache layer so that a computed
trajectory is reusable, shareable by URL, and benchmarkable. All derived data is
versioned (`model`, `version`, `created_at`) and lives in clearly-marked labels
so a rebuild can drop it wholesale (`MATCH (t:TrajectoryTopic) DETACH DELETE t`).

### 2.2 New labels and relationships (Phase 2)

```
(:TrajectoryTopic {
  id: string,              // hash(origin_chunk_id + axis fingerprint)
  label: string,           // human topic label, LLM-generated once
  embedding: [float; 1536],// topic centroid used for retrieval
  axis_positive: string,   // pole labels, reusing compass axis semantics
  axis_negative: string,
  origin_chunk_id: string,
  model: string, version: int, created_at: datetime
})

(:Chunk)-[:HAS_STANCE {
  score: float,            // [-1, +1], null never stored (null = no edge)
  model: string, version: int, created_at: datetime
}]->(:TrajectoryTopic)

// direction: chronologically earlier chunk → later chunk
(:Chunk)-[:STANCE_REL {
  topic_id: string,
  type: string,            // reaffirms | refines | shifts | contradicts
  confidence: float,       // [0, 1] from the adjudicator
  same_speaker: boolean,   // false ⇒ speaker↔group pair
  model: string, version: int, created_at: datetime
}]->(:Chunk)
```

`silence` and `diverges_from_group` are **not** stored as relationships: both are
deterministic functions of `HAS_STANCE` edges and the activity histogram (§3.3),
recomputed at read time. Storing them would denormalize something a single
aggregation query answers.

### 2.3 Retrieval Cypher patterns

Statement pool for a trajectory (speaker thread), anchored to the origin chunk's
speaker and filtered by topic similarity:

```cypher
CALL db.index.vector.queryNodes('chunk_embedding_index', $k, $topic_embedding)
YIELD node AS c, score
WHERE score >= $topic_threshold
MATCH (c)<-[:HAS_CHUNK]-(sp:Speech)-[:SPOKEN_BY]->(p) WHERE p.id = $speaker_id
MATCH (sp)<-[:CONTAINS_SPEECH]-(:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
OPTIONAL MATCH (p)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup)
  WHERE mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
OPTIONAL MATCH (p)-[mc:MEMBER_OF_COMPONENT]->(comp:MistoComponent)
  WHERE mc.start_date <= s.date AND (mc.end_date IS NULL OR mc.end_date >= s.date)
RETURN c.id, c.text, c.citability_score, c.best_quote, sp.id AS speech_id,
       s.date AS date, s.number, d.title AS debate, g.name AS party_at_date,
       comp.name AS misto_component, score
ORDER BY s.date
```

Group thread: same pattern, replacing the speaker filter with temporal group
membership (group resolved *at the origin statement's date*, honoring the
Misto-component rule):

```cypher
MATCH (p:Deputy)-[mg:MEMBER_OF_GROUP]->(g:ParliamentaryGroup {name: $group_name})
WHERE p.id <> $speaker_id
  AND mg.start_date <= s.date AND (mg.end_date IS NULL OR mg.end_date >= s.date)
```

Signed acts on the topic (rendered as square markers on the speaker thread):

```cypher
MATCH (p {id: $speaker_id})-[r:PRIMARY_SIGNATORY|CO_SIGNATORY]->(a:ParliamentaryAct)
WHERE a.description_embedding IS NOT NULL
  AND vector.similarity.cosine(a.description_embedding, $topic_embedding) >= $act_threshold
RETURN a.uri, a.type, a.title, a.presentation_date, type(r) AS role
ORDER BY a.presentation_date
```

Cached-trajectory read (Phase 2), one query per topic:

```cypher
MATCH (c:Chunk)-[hs:HAS_STANCE]->(t:TrajectoryTopic {id: $topic_id})
OPTIONAL MATCH (c)-[rel:STANCE_REL {topic_id: $topic_id}]->(c2:Chunk)
RETURN c.id, hs.score, collect({to: c2.id, type: rel.type, confidence: rel.confidence})
```

Activity baseline for silence detection (whole-corpus topic activity by month):

```cypher
CALL db.index.vector.queryNodes('chunk_embedding_index', 500, $topic_embedding)
YIELD node AS c, score WHERE score >= $topic_threshold
MATCH (c)<-[:HAS_CHUNK]-(:Speech)<-[:CONTAINS_SPEECH]-(:Phase)
      <-[:HAS_PHASE]-(:Debate)<-[:HAS_DEBATE]-(s:Session)
RETURN s.date.year AS y, s.date.month AS m, count(c) AS n ORDER BY y, m
```

---

## 3. Backend design

### 3.1 Service domain layout

```
backend/app/services/trajectory/
  __init__.py
  pipeline.py        # orchestrator: stages, SSE generator
  retrieval.py       # Cypher from §2.3; builds UnifiedEvidence-shaped records
  topic.py           # topic embedding + axis derivation from the origin chunk
  stance_adapter.py  # thin adapter over services/compass/stance.py
  candidates.py      # deterministic pair pruning (no LLM)
  classifier.py      # gpt-4o pair adjudication, structured output
  silence.py         # activity histogram + silence/divergence intervals
backend/app/routers/trajectory.py
```

Dependency rules, to keep domains clean:

- `trajectory` **imports from** `models.evidence` (`UnifiedEvidence`,
  `compute_chunk_span`), `services.citation.sentence_extractor`, and
  `services.compass.stance` (through `stance_adapter`, which is the single
  compass touchpoint).
- `trajectory` **never imports** `generation` or `retrieval.engine`. It runs its
  own Cypher through `Neo4jClient`, same as `timeline_service` does today.
- No existing domain imports `trajectory`. The only shared-state change is
  extracting the pipeline semaphore out of `routers/query.py` into
  `app/concurrency.py` (`get_pipeline_semaphore()`), with `query.py` switched to
  the import. That is the entire diff to existing backend code, plus router
  registration in `main.py`.

The stance adapter deserves a note: compass's `stance.py` scores fragments
against two axes derived from a free query. Trajectory needs one axis derived
from a chunk. The adapter builds a single-axis request (the second axis slot set
to None) and reuses batching, worker pool, clipping and the embedding fallback
as-is. If `stance.py`'s signature can't express a single axis today, the minimal
diff is an optional `axis2=None` path, not a fork.

### 3.2 Pipeline stages

```
POST /api/trajectory  { chunk_id }            — origin = a citation/search chunk
POST /api/trajectory  { speaker_id, topic }   — origin = expert card + query text
GET  /api/trajectory/{topic_id}               — cached read, no semaphore needed
```

The POST handler acquires the shared pipeline semaphore (emitting the same
`waiting` event `chat.py` uses), starts the LLM recorder, then streams:

1. **Anchor** (~200 ms). Fetch origin chunk + speech + speaker + group-at-date.
   Compute `span_start/span_end` via `compute_chunk_span`.
2. **Topic derivation** (1 LLM call, `gpt-4.1-mini`). Input: origin chunk text +
   debate title + discussed act titles. Output (strict JSON schema): topic label,
   axis pole labels ("favorevole a X" / "contrario a X"), 3 paraphrase strings.
   Topic embedding = mean of embeddings of origin chunk + paraphrases. This is
   the step that decides trajectory quality; it is deliberately isolated and
   cheap to re-run.
3. **Statement retrieval** (§2.3). Caps: 40 speaker statements, 60 group
   statements, 20 signed acts. Everything becomes a `UnifiedEvidence`-shaped
   record with offsets. Emit skeleton immediately.
4. **Stance scoring** via the adapter: ≤100 fragments → 4 batches of 25,
   parallel. Emit scores in batches as they land.
5. **Silence & divergence** (deterministic, no LLM): activity histogram, speaker
   gaps vs activity, per-bucket speaker-vs-group-median deltas.
6. **Candidate pruning** (§3.3) then **pair classification** (§3.4), relations
   emitted in batches.
7. **Trace + complete**, recorder totals included, `finally: release()`.

### 3.3 Pruning strategy and complexity

Let `n ≤ 100` statements. All numeric work is NumPy over already-fetched
embeddings; the LLM only ever sees a capped constant number of pairs.

Candidate generation:

- **Chain pairs**: consecutive speaker statements in time, `n_s − 1 ≤ 39` pairs.
  These carry the reaffirm/refine/shift narrative.
- **Contradiction candidates**: any speaker pair with `|Δstance| ≥ 0.8`, any
  distance in time. Stance disagreement is a necessary condition for
  contradiction, so this filter loses little and cuts almost everything.
- **Cross-thread pairs**: for each speaker statement, the nearest-in-time group
  statement with cosine ≥ 0.55, one per speaker statement max.

Dedup, then rank by `0.5·|Δstance| + 0.3·cos_sim + 0.2·mean(citability)` and
keep the **top 30 pairs**. Pairwise cosine over 100 embeddings is 10⁴ dot
products (<5 ms); complexity O(n²) in NumPy, O(1) in LLM calls. The naive
approach (LLM on all pairs) would be ~4,950 calls; this design makes 6.

Silence needs no pairs: an interval `[t₁, t₂]` is silent when corpus topic
activity in the interval is ≥ the legislature median and the speaker (or group)
has zero statements in it despite ≥1 statement before `t₁`. Emitted as intervals
with the activity counts that justify them, so the UI can show *why* absence is
a signal and the claim stays auditable without an LLM opinion.

`diverges_from_group` likewise: bucket group stances by quarter, flag buckets
where `|speaker − group_median| ≥ 0.6` with ≥3 group statements in the bucket.

### 3.4 Relation classifier

Model `gpt-4o`, temperature 0.1, `response_format: json_schema, strict: true`,
5 pairs per call, 6 calls in parallel through the existing executor pattern.
Client from `make_client()`, stage wrapped in `@stage("trajectory_classifier")`,
so recording and LangSmith tracing come for free.

The LLM adjudicates **four** labels plus an escape hatch. `silence` and
`diverges_from_group` left the typology in §3.3 because deterministic evidence
beats model opinion where both are available; `unrelated` enters it because
pruning is heuristic and the classifier needs a way to reject a bad pair rather
than force a label. This is the revised typology and its justification.

Prompt sketch (system):

```
Confronti coppie di dichiarazioni parlamentari sullo stesso tema.
Per ogni coppia (A precede B nel tempo) classifica la relazione di B rispetto ad A:
- reaffirms: stessa posizione, ribadita senza elementi nuovi
- refines: stessa direzione, con condizioni, distinzioni o ambiti aggiunti
- shifts: la posizione si sposta in modo misurabile ma non opposto
- contradicts: le due posizioni non possono essere vere insieme
- unrelated: le dichiarazioni non parlano della stessa questione
Basati solo sul testo fornito. Cita l'evidenza: per ciascuna dichiarazione
riporta la frase esatta (copiata carattere per carattere) che fonda il giudizio.
```

Output schema per pair:

```json
{
  "pair_id": "string",
  "relation": "reaffirms|refines|shifts|contradicts|unrelated",
  "confidence": 0.0,
  "evidence_a": "verbatim sentence from statement A",
  "evidence_b": "verbatim sentence from statement B",
  "note": "one sentence, user-facing, in Italian"
}
```

**Citation integrity.** `evidence_a/b` are candidate strings, not citations. The
backend validates each with `str.find()` inside the statement's `quote_text`
(itself offset-verified against the full speech). Found → the relation ships
with two sub-spans expressed as offsets into the speech text (chunk span start +
local index). Not found → retry once with the mismatch flagged; still failing →
the relation degrades to whole-chunk evidence (the chunk's own verified span).
No fuzzy matching at any point, same doctrine as `surgeon._extract_quote`. The
citation service needs **zero changes**: `compute_chunk_span` and the
`SentenceExtractor` fallback already cover every path.

### 3.5 Cost and latency per trajectory

| Stage | Calls | Model | Tokens (in/out) | Cost |
|---|---|---|---|---|
| Topic derivation | 1 | gpt-4.1-mini | ~1.5k / 0.3k | <$0.01 |
| Stance (100 stmts) | 4 | gpt-4.1-mini | ~30k / 2k | ~$0.02 |
| Relations (30 pairs) | 6 | gpt-4o | ~14k / 3k | ~$0.07 |
| Embeddings (paraphrases) | 1 | text-embedding-3-small | ~0.5k | negligible |

Total ≈ 50k tokens, **~$0.10 per uncached trajectory**, comparable to one chat
query. Latency: retrieval ~2 s, stance ~6 s (parallel), relations ~10 s
(parallel); the skeleton is on screen in under 3 s and the view fills in over
~20 s. Cached trajectories cost zero LLM tokens.

### 3.6 SSE event contract

Same wire format as `query.py` (`data: {json}\n\n`, `type` discriminator),
emitted in this order:

| Event | Payload | When |
|---|---|---|
| `waiting` | as in `chat.py` | queued behind semaphore |
| `progress` | `{step, message}` | each stage |
| `trajectory_meta` | `{topic: {id, label, axis_positive, axis_negative}, speaker: Expert-lite, group, misto_component, date_range}` | after topic derivation |
| `statements` | `{speaker: TrajectoryStatement[], group: [...], acts: [...]}` | skeleton, no stances yet |
| `stances` | `{scores: [{chunk_id, stance}]}` | per batch, ≤4 times |
| `activity` | `{histogram: [{month, count}], silences: [{from, to, thread, activity_count}], divergences: [{from, to, delta}]}` | after stance |
| `relations` | `{relations: TrajectoryRelation[]}` | per batch, ≤6 times |
| `trace` | recorder totals + stage timings | end |
| `complete` | `{topic_id}` (the shareable id) | end |
| `error` | `{code, message}` | on failure |

`TrajectoryStatement` reuses the `citation_details` field names verbatim
(`chunk_id`, `quote_text`, `full_text`, `span_start`, `span_end`, `group`,
`date`, `debate`, `intervention_id`, ...) plus `stance: float|null`,
`citability: float`, `thread: "speaker"|"group"`, `kind: "speech"|"act"`. The
frontend can hand any statement straight to `CitationModal` with no mapping.

`TrajectoryRelation`: `{id, from_chunk_id, to_chunk_id, type, confidence,
evidence_a: {text, span_start, span_end}, evidence_b: {...}, note}`.

---

## 4. Frontend design

### 4.1 Chosen visualisation: braided stance–time chart

Two candidates were rejected first. A stance river aggregates statements into a
flow, which reads well but hides the individual, clickable, citable statement;
this product's whole identity is "every pixel resolves to a verbatim quote", so
aggregation fights the concept. A radial layout makes early dates cramped and
late dates sprawling, and relation arcs across a circle are unreadable past ~15
nodes.

The braided chart keeps both threads literal:

- **X axis**: time, clipped to the topic's active range. Fraunces serif for the
  axis labels, matching the editorial voice of the product.
- **Y axis**: stance in [-1, +1], pole labels from `trajectory_meta` at top and
  bottom (same convention as CompassCard's axis labels).
- **Origin as anchor**: the selected statement is the root of the graph. Its
  node is larger, ringed in `--primary`, labeled "origine", and the view opens
  centered on it. Statements after it render at full strength (the trajectory
  the user asked to follow); statements before it render at ~55% opacity, kept
  on screen because "contradicts what they said in March" needs the March node.
  The reading is a graph growing rightward from the chosen statement, not a
  neutral timeline.
- **Speaker thread**: a line in the party color through circular statement
  nodes (radius ∝ citability). Square nodes for signed acts. A party switch
  mid-legislature splits the line color at the switch date, honoring temporal
  group membership.
- **Group thread**: not a line but a translucent **band** (median ± IQR of group
  stances per quarter, party color at ~12% opacity) with small hollow dots for
  individual group statements. The visual metaphor is exact: the band is the
  group's line, the speaker either swims inside it or leaves it.
- **Relations** are arcs between nodes, styled by the loud/quiet rule:
  `contradicts` = 2.5px bordeaux (`--destructive`) arc with a small ✕ marker at
  apex; `shifts` = 1.5px gold (`--chart-3`) dashed; `refines` = 1px
  institutional blue; `reaffirms` = 1px `--muted-foreground` at 40% opacity,
  legible but silent. Confidence maps to opacity.
- **`diverges_from_group`**: wherever the speaker line exits the band, the band
  edge sharpens and the gap region tints bordeaux at 6%; no arc needed, the
  geometry itself is the claim.
- **`silence`**: the speaker line breaks into a dotted gray segment and the
  activity sparkline (a quiet bar strip under the X axis, showing corpus
  activity on the topic) turns solid under the gap: the room kept talking, the
  speaker did not. Hovering states exactly that, with counts.
- Node click → `CitationModal`. Arc click → a small popover with the relation
  note and the two verbatim evidence sentences, each opening the modal with
  that sub-span highlighted (the modal already highlights `quote_text`; the
  sub-span rides in the same field).

Interaction copies CompassCard: pointer-capture pan on X, wheel zoom, hover
dimming of the non-hovered thread. Rendering is hand-rolled SVG; no new
dependency. Streaming animation reuses the existing vocabulary: nodes enter
with the `hemicycle-dot-in` scale-in, arcs draw with a stroke-dashoffset
transition in the spirit of `trace-grow`.

### 4.2 Component tree

```
app/trajectory/page.tsx                 // landing: search + example statements
app/trajectory/[origin]/page.tsx        // origin = chunk_id or topic_id (cached)
app/api/trajectory/route.ts             // SSE proxy, clone of api/chat/route.ts
hooks/use-trajectory.ts                 // SSE consumer, clone of use-chat pattern

components/trajectory/
  TrajectoryView.tsx        // layout, state machine, modal wiring
  TrajectoryHeader.tsx      // speaker (photo, name, group badge — ExpertRow style),
                            // topic label in Fraunces, date range, share button
  TrajectoryCanvas.tsx      // the SVG; owns pan/zoom
    TimeAxis / StanceAxis
    GroupBand.tsx
    SpeakerPath.tsx         // includes dotted SilenceSegments
    StatementNode.tsx       // circle | square(act) | hollow(group) variants
    RelationArc.tsx
    ActivitySparkline.tsx
  RelationLedger.tsx        // chronological list of relations with evidence
                            // quotes; primary UI on mobile, a11y layer on desktop
  TrajectoryLegend.tsx
```

Reused, not rebuilt: `CitationModal` (exported from `CitationCard.tsx`, the one
existing-code diff), `ExpertModal`, `Card`/`Dialog`/`Tooltip` primitives,
`config.politicalGroups` colors, i18n via a new `Trajectory` namespace in the
six locale files.

### 4.3 Entry points

0. **Landing page** `/trajectory`: "Seleziona una dichiarazione". A search box
   over chunks (backed by the existing vector search, same machinery as
   `/search`) plus 4–6 curated example statements rendered as `CitationCard`s
   (seeded from `evaluation_set.json` topics; later, from cached trajectories
   with the most `contradicts` relations, which are the interesting ones).
   Clicking a card starts the trajectory from that statement. This is the
   discovery path for users who arrive without a chat context.
1. **Citation marker**: a "Traiettoria" action (lucide `GitBranch` or `Route`
   icon) in the `CitationModal` footer → `router.push('/trajectory/' +
   citation.chunk_id)`.
2. **Expert card**: action in `ExpertModal` → POST variant `{speaker_id, topic:
   currentQuery}`; the chat page passes the query down as it already does for
   other panels.
3. **Direct URL**: `/trajectory/<topic_id>` hits the cached GET, renders without
   the semaphore or any LLM call. `/trajectory/<chunk_id>` on a cache miss
   triggers computation with the standard `waiting` treatment.

### 4.4 States

- **Loading**: axes + gray band skeleton with shimmer, header immediately (meta
  arrives first).
- **Streaming**: nodes pop in per `statements`/`stances` batch, at first
  vertically centered (stance unknown) then animating to their stance position;
  arcs draw per `relations` batch. A thin `nav-progress`-style bar under the
  header tracks stages.
- **Empty**: origin has no topic-mates (rare topic, one-off statement). Show the
  origin as a single node with its citation card and the sentence "Nessun altro
  intervento di questo deputato o del suo gruppo su questo tema" plus the
  activity sparkline, which is informative even alone.
- **Error / rate-limited**: same error card + retry the chat view uses, same
  `waiting` queue messaging.

---

## 5. Evaluation plan

Designed to be benchmark-able for the journal extension (this slots into the
future-work list already tracked for the ISWC line of work).

1. **Gold set.** ~40 trajectories from `evaluation_set.json` topics → ~200
   candidate pairs stratified by predicted label, plus 50 random *non-candidate*
   pairs (to measure what pruning throws away). Two annotators, Italian
   politics-literate, label the 5 classes; report Cohen's κ; adjudicate
   disagreements. Export as JSONL of `(chunk_id_a, chunk_id_b, span_a, span_b,
   label)`: chunk ids + offsets over open dati.camera.it text make the benchmark
   releasable without licensing issues.
2. **Classifier metrics.** Per-class precision/recall/F1, macro-F1, confusion
   matrix, with `contradicts` precision as the headline number (it is the loud
   red arc; a false contradiction is the worst failure the UI can produce).
   Evidence-sentence validity rate (share of `evidence_a/b` that verify by exact
   find) reported alongside.
3. **Stance quality.** Annotators score a 100-statement sample on a 5-point
   scale; report Spearman ρ against model stance and MAE after linear mapping.
   Compass's stance machinery gets an evaluation it never had, for free.
4. **Pruning recall.** On 5 small trajectories (n ≤ 25), run the exhaustive
   O(n²) classification once, offline. Recall of pruned candidates against
   exhaustive non-`unrelated` relations; target ≥ 0.85. This directly justifies
   the cost design.
5. **Silence audit.** Manual verification of 50 flagged silence intervals
   against the corpus (precision) and 50 hand-found gaps (recall); silence is
   deterministic, so this audits the *definition*, not a model.
6. **Model ablation.** gpt-4o vs gpt-4.1-mini vs one open-weight judge on the
   gold pairs; cost/quality frontier table for the paper.
7. **Provenance.** Frozen prompts, model ids, config snapshot, git tag, same
   discipline as the `iswc2026-eval` tag; predictions stored per run.

---

## 6. Phased implementation plan

Ordered by risk: topic retrieval quality is the failure mode that kills the
feature (garbage statements make elegant relations meaningless), so it ships
first and alone.

**Phase 1 — Trajectory MVP (position over time, no relations).**
Backend: `services/trajectory/` with anchor, topic derivation, retrieval,
stance adapter; SSE endpoint behind the shared semaphore (`app/concurrency.py`
extraction); no persistence. Frontend: route, hook, canvas with speaker path +
group band + act markers, `CitationModal` reuse (export diff), entry points 0
(landing with curated examples) and 1 (citation marker),
loading/streaming/empty states, `RelationLedger` shell
listing statements only. *Shippable*: "how this position moved over time" with
verifiable quotes is standalone value. *Risk retired*: topic coherence,
measurable by eyeballing 20 trajectories before any classifier work.

**Phase 2 — Relations + cache.**
Candidate pruning, gpt-4o classifier with evidence verification, `relations`
SSE batches, arcs + ledger entries + relation popovers. Persistence:
`TrajectoryTopic`, `HAS_STANCE`, `STANCE_REL`, cached GET, shareable
`/trajectory/<topic_id>` (entry point 3). Optional: `Chunk.session_date`
denormalization if the 5-hop traversal shows up in timings. *Shippable*: the
full braid. *Risk retired*: classifier quality and cost envelope.

**Phase 3 — Absence and divergence.**
Activity histogram, silence intervals, divergence buckets, sparkline, band-exit
styling, expert-card entry point 2, i18n for all six locales, dark mode pass.
*Shippable*: the interpretive layer. *Risk retired*: the silence definition
survives contact with real data before it is claimed in any paper.

**Phase 4 — Cross-modal + benchmark.**
Speech-vs-vote overlay (`IndividualVote` + `ON_ACT` against stance: "said X,
voted Y" as a distinct marker, deterministic like silence), committee-role
badges, the §5 evaluation executed end to end, benchmark JSONL release, journal
extension experiments. *Shippable*: the research contribution.

Each phase leaves `main` deployable; nothing in Phase N+1 is load-bearing for
Phase N.
