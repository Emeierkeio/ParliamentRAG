# ParliamentRAG

A multi-perspective retrieval-augmented generation (RAG) system for Italian parliamentary records. The system retrieves evidence from parliamentary speeches and acts, computes query-dependent speaker authority, discovers ideological axes via PCA, and generates structured multi-party responses with deterministic verbatim citations.

For the academic overview, see [thesis.md](thesis.md).

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
- A populated Neo4j database (corpus ingestion is a separate offline step)

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
├── thesis.md                       # Academic system overview
└── thesis_knowledge/               # Detailed thesis documentation
    ├── SYSTEM_OVERVIEW.md
    ├── ARCHITECTURE.md
    ├── DATA_PIPELINE.md
    ├── IDEOLOGICAL_SCORING.md
    ├── RETRIEVAL_STRATEGY.md
    ├── GENERATION_LOGIC.md
    ├── EXPERIMENTS.md
    ├── DESIGN_DECISIONS.md
    ├── LIMITATIONS_AND_FUTURE_WORK.md
    └── GLOSSARY.md
```

---

## Evaluation

The evaluation framework compares system responses against a NotebookLM baseline on predefined topics from `backend/evaluation_set.json`.

**Automated metrics** (available at `/api/evaluation/dashboard`): party coverage, citation relevance, coalition balance, authority distribution.

**Human A/B survey** (available in the frontend at `/valutazione?evaluator=`): blind comparative rating of system vs. baseline on 7 dimensions.

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

## License

MIT — see [LICENSE](LICENSE).
