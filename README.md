# Who Speaks Matters: Authority-Aware Multi-View Parliamentary RAG

> **Thesis repository** — Università degli Studi di Milano-Bicocca
> Master's Degree in Data Science, A.Y. 2024–2025
> Author: Mirko Tritella · Supervisor: Prof. Matteo Luigi Palmonari · Co-supervisor: Dott. Riccardo Pozzi
>
> **Live demo**: [parliamentrag.it](https://www.parliamentrag.it/)

---

## Abstract

Citizens seeking balanced information on political issues face a fundamental challenge: parliamentary proceedings are voluminous, fragmented, and difficult to navigate without bias. Large Language Models offer quick summaries of parliamentary debates but risk favouring dominant actors, providing out-of-context quotes, and failing to represent all points of view.

This work addresses the challenge with a primary objective: to treat equally both *what is said* and *who is saying it*, presenting citizens with multiple viewpoints on parliamentary debate. The system combines a **Topic-Aware Speaker Authority Score** — that dynamically estimates speaker credibility given the topic — with a **multi-view representation** of political positions, built upon a Retrieval-Augmented Generation (RAG) system applied to Italian parliamentary transcripts (XIX Legislature, Camera dei Deputati).

The system is evaluated against Google NotebookLM on 15 policy topics through a two-level protocol combining automated metrics with a blind A/B evaluation by 6 domain experts. ParliamentRAG outperforms NotebookLM on parliamentary group coverage (97% vs. 95%) and citation faithfulness (100% vs. 95%). Human evaluators rate the system higher on source and balance dimensions (Cohen's *d* up to 0.35), while overall satisfaction is essentially at parity (4.24 vs. 4.27 out of 5).

The full thesis is available at [`Who_Speaks_Matters__Authority_Aware_Multi_View_Parliamentary_RAG.pdf`](Who_Speaks_Matters__Authority_Aware_Multi_View_Parliamentary_RAG.pdf).

---

## System Overview

ParliamentRAG is composed of four interconnected modules:

1. **Topic-Dependent Authority Scoring** — estimates speaker credibility from six weighted components (profession, education, committee memberships, legislative acts, speech interventions, institutional role) with a coalition-crossing invalidation mechanism and exponential temporal decay.

2. **Dual-Channel Retrieval** — combines dense semantic search (vector similarity over 1536-dimensional embeddings) with knowledge graph traversal to identify speeches relevant to the query and representative of all ten parliamentary groups.

3. **Offset-Based Citation Module** — extracts citations deterministically from character-level spans in source transcripts, providing fully verifiable verbatim quotes with zero hallucination.

4. **Four-Stage Generation Pipeline** — Claim Analyst → Sectional Writer → Narrative Integrator → Citation Surgeon — implements a citation-first principle to ensure semantic correspondence between the generated narrative and the quoted evidence.

An additional **Ideological Compass** module discovers latent political axes from retrieved evidence via weighted PCA, enabling visual positioning of parliamentary groups on the debate.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend: Next.js 16 + React 19 (TypeScript)           │
│  Chat UI · Compass · Expert Cards · A/B Evaluation      │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP + SSE
┌────────────────────▼────────────────────────────────────┐
│  Backend: FastAPI (Python 3.13)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │Retrieval │ │Authority │ │ Compass  │ │Generation │  │
│  │Dense +   │ │6-compon. │ │IC-1→IC-6 │ │4-stage +  │  │
│  │Graph ch. │ │query-dep.│ │Weighted  │ │det. citns │  │
│  └──────────┘ └──────────┘ │ PCA      │ └───────────┘  │
└────────────────────┬────────┴──────────┴────────────────┘
                     │ Bolt
┌────────────────────▼────────────────────────────────────┐
│  Neo4j 5.15  (graph + native vector index)              │
│  Speech chunks · Act graph · Speaker metadata           │
└─────────────────────────────────────────────────────────┘
```

**LLM**: OpenAI `gpt-4o` (generation stages 1–3)
**Embeddings**: OpenAI `text-embedding-3-small` (1536 dimensions, all semantic operations)
**Vector index**: Neo4j native `chunk_embedding_index` on `Chunk.embedding`

---

## Prerequisites

- Docker and Docker Compose
- Python 3.13+
- Node.js 20+ and npm
- OpenAI API key(s)
- A populated Neo4j database (corpus ingestion is a separate offline step; see §4.3 of the thesis for data acquisition and preprocessing details)

---

## Setup

### 1. Clone and configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
#   OPENAI_API_KEY=sk-...
#   NEO4J_URI=bolt://localhost:7689
#   NEO4J_USER=neo4j
#   NEO4J_PASSWORD=your_password_here
#   NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

Multiple OpenAI keys can be provided as a comma-separated list to distribute API rate limits:

```
OPENAI_API_KEY=sk-key1...,sk-key2...,sk-key3...
```

### 2. Start Neo4j

```bash
docker-compose up -d neo4j
```

Neo4j will be available at:
- Web UI: [http://localhost:7475](http://localhost:7475)
- Bolt: `bolt://localhost:7689`

Default credentials: `neo4j` / `your_password_here` (set in `docker-compose.yml`).

### 3. Start the backend

```bash
cd backend
pip install -r requirements.txt
python -m spacy download it_core_news_sm   # Italian tokenizer for keyword extraction
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at [http://localhost:8000](http://localhost:8000).
Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000).

---

## Configuration

Backend configuration is split across two files:

### `backend/config/default.yaml`

Controls all algorithmic parameters:

| Section | Key Settings |
|---------|-------------|
| `retrieval.dense_channel` | `top_k: 200`, `similarity_threshold: 0.3` |
| `retrieval.graph_channel` | `lexical_keywords_min_match: 1`, `semantic_similarity_threshold: 0.4` |
| `retrieval.merger` | Weights: relevance 0.35, diversity 0.15, coverage 0.20, authority 0.05, salience 0.25 |
| `authority.weights` | profession 0.15, education 0.10, committee 0.25, acts 0.20, interventions 0.25, role 0.05 |
| `authority.time_decay` | `acts_half_life_days: 548`, `speeches_half_life_days: 548` |
| `generation.models` | `analyst: "gpt-4o"`, `writer: "gpt-4o"`, `integrator: "gpt-4o"` |
| `coalitions` | Defines maggioranza and opposizione group lists |

### `backend/config/commissioni_topics.yaml`

Maps parliamentary commission names to topic areas for commission-based retrieval filtering.

### Environment Variables (`.env`)

| Variable | Description |
|----------|-------------|
| `NEO4J_URI` | Bolt connection URI (e.g., `bolt://localhost:7689`) |
| `NEO4J_USER` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |
| `OPENAI_API_KEY` | Single key or comma-separated list |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `NEXT_PUBLIC_API_URL` | Backend API URL as seen from the browser |

---

## API Reference

### Query endpoint (streaming)

```
POST /api/chat
Content-Type: application/json

{
  "query": "Qual è la posizione sulla immigrazione?",
  "top_k": 100,
  "date_start": "2024-01-01",
  "date_end": "2025-12-31",
  "stream": true
}
```

Responds with Server-Sent Events. Event types in order:

| Event type | Contents |
|------------|---------|
| `progress` | Step number and label |
| `experts` | One top-authority expert per parliamentary group |
| `citations` | Retrieved evidence items |
| `section` | Per-party narrative section |
| `compass` | Ideological axis analysis |
| `complete` | Full response object |

### Other endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/evidence/{id}` | Full evidence item detail |
| GET | `/api/history` | Chat history |
| GET | `/api/evaluation/dashboard` | Automated metrics + A/B results |
| POST | `/api/survey/submit` | Submit A/B evaluation |
| GET | `/api/authority` | Authority ranking by topic |
| GET | `/api/search` | Parliamentary record search |
| GET | `/api/graph` | Graph exploration |

---

## Project Structure

```
ParliamentRAG/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + lifespan
│   │   ├── config.py               # YAML + .env configuration loader
│   │   ├── key_pool.py             # OpenAI key round-robin
│   │   ├── models/                 # Pydantic data models
│   │   ├── routers/                # HTTP route handlers
│   │   └── services/
│   │       ├── neo4j_client.py     # Connection pooling + vector search
│   │       ├── retrieval/          # Dense channel, graph channel, merger
│   │       ├── authority/          # 6-component authority scorer
│   │       ├── compass/            # IC-1→IC-6 ideological pipeline
│   │       ├── generation/         # 4-stage generation + citation integrity
│   │       └── citation/           # Salience computation
│   ├── config/
│   │   ├── default.yaml            # All algorithmic parameters
│   │   └── commissioni_topics.yaml
│   ├── evaluation_set.json         # Ground truth topics + baseline experts
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js App Router pages
│   │   ├── components/             # Chat, compass, survey, graph UI
│   │   ├── hooks/                  # Chat state, local history
│   │   ├── lib/                    # API clients, constants, utils
│   │   └── types/                  # TypeScript interfaces
│   └── package.json
├── neo4j/                          # Neo4j data and plugin volumes
├── docker-compose.yml              # Neo4j service definition
└── Who_Speaks_Matters__Authority_Aware_Multi_View_Parliamentary_RAG.pdf
```

---

## Evaluation

The evaluation framework compares system responses against a NotebookLM baseline on 15 predefined policy topics from `backend/evaluation_set.json`.

**Automated metrics** (available at `/api/evaluation/dashboard`): party coverage, citation relevance, coalition balance, authority distribution.

**Human A/B survey** (available in the frontend at `/valutazione?evaluator=`): blind comparative rating of system vs. baseline on 9 dimensions by 6 domain experts. Rating scale: 1–5 (Likert). Statistical analysis: Mann-Whitney U test, Cohen's *d* effect size, Krippendorff's *α* inter-rater agreement.

---

## Dependencies

| Component | Technology | Version |
|-----------|-----------|---------|
| Web framework | FastAPI + Uvicorn | ≥0.109 |
| Database | Neo4j | 5.15 |
| LLM / Embeddings | OpenAI (`gpt-4o`, `text-embedding-3-small`) | ≥1.10 |
| Numerical | NumPy + SciPy | ≥1.24 / ≥1.11 |
| NLP tokenization | spaCy (Italian) | ≥3.5 |
| Data validation | Pydantic v2 | ≥2.5 |
| Frontend | Next.js + React | 16.1.4 / 19.2.3 |
| Graph visualization | react-force-graph-2d | ≥1.29 |

---

## Citation

If you use this system or build upon this work, please cite:

```bibtex
@mastersthesis{tritella2025parliamentrag,
  author  = {Tritella, Mirko},
  title   = {Who Speaks Matters: Authority-Aware Multi-View Parliamentary {RAG}},
  school  = {Università degli Studi di Milano-Bicocca},
  year    = {2025},
  type    = {Master's Thesis in Data Science}
}
```

---

## License

APACHE 2.0 — see [LICENSE](LICENSE).
