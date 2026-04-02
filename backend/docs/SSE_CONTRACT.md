# SSE Event Contract — FROZEN

**Status: FROZEN**

This document describes every Server-Sent Event (SSE) emitted by the backend query
and chat pipelines. Event type names, payload field names, and emission order are a
**frozen frontend contract**. Do not rename, reorder, or restructure any event without
a coordinated frontend change.

Created: 2026-04-02
Phase: 02-backend Plan 01

---

## Rules

- Event names use `snake_case`.
- Payload field names use `snake_case` (`authority_score`, `group`, `first_name`, etc.).
- The `chunk` event uses **different payload keys** in each pipeline:
  - `chat.py` → `"content"` key
  - `query.py` → `"data"` key
  Both are frozen. The frontend handles both.
- Dual `experts` emission is **intentional**: first before generation (pre-generation pool),
  second after citation verification (citation-aligned expert per party).
- All events are JSON-encoded and emitted as `data: {json}\n\n`.

---

## chat.py Pipeline

Functions: `process_chat_background` and `process_chat_streaming`

Both functions emit the same logical event sequence. `process_chat_background` stores
events in TaskStore; `process_chat_streaming` yields them directly to the HTTP response.

| # | Event Type        | Payload Fields                                                                                          | When Emitted                                               |
|---|-------------------|---------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| 1 | `waiting`         | `queue_position`, `ahead_count`, `active_count`, `elapsed_seconds`                                      | Only if the pipeline semaphore is locked (queue backpressure) |
| 2 | `progress`        | `step: 1`, `total: 8`, `message: "Analisi query"`                                                       | Immediately on pipeline start                             |
| 3 | `progress`        | `step: 2`, `total: 8`, `message: "Commissioni"`                                                          | Before commission matching                                 |
| 4 | `commissioni`     | `commissioni: List[{name, url, ...}]`                                                                   | After commission matching                                  |
| 5 | `progress`        | `step: 3`, `total: 8`, `message: "Esperti"`                                                             | Before retrieval and authority scoring                     |
| 6 | `experts`         | `experts: List[ExpertDict]`                                                                             | After first `_compute_experts_for_frontend` (pre-generation) |
| 7 | `progress`        | `step: 4`, `total: 8`, `message: "Interventi"`                                                          | Before initial citation list build                         |
| 8 | `citations`       | `citations: List[CitationDict]`                                                                         | After building the initial citation list                   |
| 9 | `progress`        | `step: 5`, `total: 8`, `message: "Statistiche"`                                                         | Before balance computation                                 |
| 10 | `balance`        | `maggioranza_percentage`, `opposizione_percentage`, `bias_score`, (other balance metrics)               | After balance metrics computed                             |
| 11 | `progress`       | `step: 6`, `total: 8`, `message: "Bussola Ideologica"`                                                  | Before compass computation                                 |
| 12 | `compass`        | `meta`, `axes`, `groups`, `scatter_sample`                                                              | After ideological compass computed                         |
| 13 | `progress`       | `step: 7`, `total: 8`, `message: "Generazione"`                                                         | Before LLM generation                                      |
| 14 | `topic_stats`    | `intervention_count`, `speaker_count`, `first_date`, `last_date`, `speakers_detail`, `interventions_detail`, `sessions_detail` | After generation, only if `topic_statistics` present       |
| 15 | `chunk`          | `content: str` (50 characters at a time)                                                                | During LLM text streaming                                  |
| 16 | `citation_details` | `citations: List[VerifiedCitationDict]`                                                               | After text streaming complete, all citations verified      |
| 17 | `experts`        | `experts: List[ExpertDict]`                                                                             | Second emission after `_patch_experts_for_cited_speakers` (only if patched) |
| 18 | `hq_variants`    | `variants: [{text, score, is_best}]`                                                                    | Only in `high_quality` mode                               |
| 19 | `complete`       | `metadata: {timing, dense_channel_count, graph_channel_count, ...}`                                     | Final event — pipeline complete                            |
| 20 | `error`          | `message: str`                                                                                          | On any unhandled exception                                 |

---

## query.py Pipeline

Function: `process_query_streaming`

Shorter pipeline — no background task pattern, no commission matching, no balance event.

| # | Event Type         | Payload Fields                                                                                         | When Emitted                                                  |
|---|--------------------|--------------------------------------------------------------------------------------------------------|---------------------------------------------------------------|
| 1 | `waiting`          | `message: str`                                                                                         | If the pipeline semaphore is at capacity                     |
| 2 | `progress`         | `step: 1`, `message: "Avvio retrieval..."`                                                              | Start                                                         |
| 3 | `progress`         | `step: 2`, `message: f"Trovate {n} evidenze"`                                                           | After retrieval completes                                     |
| 4 | `progress`         | `step: 3`, `message: "Calcolo authority scores..."`                                                     | Before authority scoring                                      |
| 5 | `experts`          | `data: List[ExpertDict]`                                                                               | After `_compute_experts` (pre-generation)                    |
| 6 | `progress`         | `step: 4`, `message: "Analisi compass ideologico..."`                                                   | Before compass computation                                    |
| 7 | `compass`          | `data: {meta, axes, groups, scatter_sample}`                                                           | After compass computed                                        |
| 8 | `progress`         | `step: 5`, `message: "Generazione risposta multi-view..."`                                              | Before LLM generation                                         |
| 9 | `topic_stats`      | `intervention_count`, `speaker_count`, `first_date`, `last_date`, `speakers_detail`, `interventions_detail`, `sessions_detail` | After generation, only if `topic_statistics` present |
| 10 | `citations`        | `data: List[CitationDict]`                                                                             | After initial citation list built                            |
| 11 | `citation_details` | `citations: List[VerifiedCitationDict]`                                                               | After citation verification complete                         |
| 12 | `experts`          | `data: List[ExpertDict]`                                                                               | Second emission after citation-aligned expert update         |
| 13 | `chunk`            | `data: str` (100 characters at a time)                                                                 | During LLM text streaming                                     |
| 14 | `complete`         | `metadata: dict`                                                                                       | Final event — pipeline complete                              |
| 15 | `error`            | `message: str`                                                                                         | On any unhandled exception                                    |

---

## Expert Dict Shape (FROZEN)

Both pipelines emit expert dicts with exactly this shape. Field names are frozen.

```json
{
  "id": "d300001",
  "first_name": "Mario",
  "last_name": "Rossi",
  "group": "Partito Democratico - Italia Democratica e Progressista",
  "coalition": "opposizione",
  "authority_score": 0.72,
  "relevant_speeches_count": 5,
  "camera_profile_url": "https://www.camera.it/leg19/26?idpersona=300001",
  "photo": "https://www.camera.it/img/deputati/300001.jpg",
  "profession": "Avvocato",
  "education": "Laurea in Giurisprudenza",
  "committee": "Commissione Giustizia",
  "institutional_role": null,
  "score_breakdown": {
    "speeches": 0.81,
    "acts": 0.63,
    "committee": 0.55,
    "profession": 0.40,
    "education": 0.35,
    "role": 0.00
  }
}
```

---

## Key Differences Between Pipelines

| Aspect                  | chat.py                        | query.py                       |
|-------------------------|--------------------------------|--------------------------------|
| `chunk` payload key     | `"content"`                    | `"data"`                       |
| `experts` payload key   | `"experts"`                    | `"data"`                       |
| `compass` payload key   | direct fields                  | `"data"` wrapper               |
| `citations` payload key | `"citations"`                  | `"data"`                       |
| Commission matching     | Yes (`commissioni` event)      | No                             |
| Balance event           | Yes (`balance` event)          | No                             |
| Background task support | Yes (`process_chat_background`) | No (streaming only)           |
| Chunk size              | 50 chars                       | 100 chars                      |
| Dual experts emission   | Yes (events 6 and 17)          | Yes (events 5 and 12)          |
| Total events (normal)   | ~19 (no waiting, no hq)        | ~14 (no waiting)               |

---

## Notes

1. **Dual experts emission is intentional.** The first emission represents the top-authority
   speaker per party from the retrieved evidence pool. The second emission is updated after
   citation verification to reflect the actual cited speaker per party (post-generation).

2. **Do not add fields to expert dicts.** The frontend destructures the object shape directly.
   Adding unexpected fields is safe; removing or renaming fields is breaking.

3. **Error event terminates the stream.** After emitting `error`, no further events are sent.
   The client should treat `error` as the terminal event in error scenarios.

4. **The `waiting` event** may not be emitted in single-worker deployments with low traffic.
   It is emitted only when a new request arrives while another pipeline is actively running.
