<div align="center">

# ParliamentRAG

### Multi-View RAG for Italian Parliamentary Data

A Retrieval-Augmented Generation system that delivers **balanced, multi-view analysis** of Italian parliamentary debates — ensuring all political voices are represented in every response.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16+-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.15-4581C3?style=for-the-badge&logo=neo4j&logoColor=white)](https://neo4j.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[![Live Demo](https://img.shields.io/badge/Live_Demo-Railway-blueviolet?style=for-the-badge&logo=railway&logoColor=white)](https://truthful-amazement-production.up.railway.app/)

</div>

---

## Overview

ParliamentRAG is a research system built for a Master's thesis that combines **vector search** and **knowledge graph traversal** to analyze Italian parliamentary debates. It enforces balanced political representation by guaranteeing that all 10 parliamentary groups appear in every generated response.

The system features a 4-stage generation pipeline with **deterministic, offset-based citations** — zero fuzzy matching — ensuring full auditability and traceability of every quoted passage.

<div align="center">
  <a href="https://truthful-amazement-production.up.railway.app/">
    <img src="assets/neo4j_graph.png" alt="Neo4j Knowledge Graph" width="700"/>
  </a>
  <br/>
  <sub>Knowledge graph of Italian parliamentary data in Neo4j — <a href="https://truthful-amazement-production.up.railway.app/"><b>Try the live demo</b></a> · <a href="https://truthful-amazement-production.up.railway.app/explorer"><b>Interactive schema explorer</b></a></sub>
</div>

---

## Key Features

**Dual-Channel Retrieval** — Combines dense vector similarity search with structured graph traversal for comprehensive evidence gathering

**Query-Dependent Authority Scoring** — Ranks speakers by topic-specific credibility using profession, education, committee roles, legislative activity, and speech frequency — with coalition-aware temporal logic

**Ideological Compass** — Semi-supervised 2D positioning of parliamentary groups using PCA on text embeddings with configurable soft anchors

**4-Stage Generation Pipeline** — Analyst → Sectional Writer → Integrator → Citation Surgeon, each stage independently verifiable

**Deterministic Citations** — Offset-based extraction from raw text, no fuzzy matching. Every quote is verbatim and auditable

**Mandatory Multi-View Coverage** — All 10 parliamentary groups are represented in every response, preventing political bias

**Real-Time Streaming** — SSE-based streaming with visible pipeline progress across all 9 processing stages

---

## Architecture

```mermaid
flowchart TB
  subgraph Frontend["<b>Frontend</b> — Next.js 16 / React 19"]
    direction LR
    Chat["Chat"]
    Search["Search"]
    Explorer["Graph Explorer"]
    Survey["Survey"]
  end

  Frontend -->|"SSE / REST"| Backend

  subgraph Backend["<b>Backend</b> — FastAPI"]
    direction LR
    subgraph Retrieval["Retrieval"]
      Dense["Dense Channel"]
      Graph["Graph Channel"]
      Merger["Merger"]
    end
    subgraph Authority["Authority Scoring"]
      Prof["Profession & Education"]
      Comm["Committees & Acts"]
      Coal["Coalition Logic"]
    end
    subgraph Generation["4-Stage Pipeline"]
      S1["1 · Analyst"]
      S2["2 · Sectional Writer"]
      S3["3 · Integrator"]
      S4["4 · Citation Surgeon"]
      S1 --> S2 --> S3 --> S4
    end
    Compass["Ideological Compass<br/><i>PCA · KDE · Soft Anchors</i>"]
  end

  Retrieval --> Authority
  Authority --> Generation
  Authority --> Compass

  Backend -->|"Bolt"| DB

  subgraph DB["<b>Neo4j 5.15</b> — Docker"]
    direction LR
    GraphDB["Graph Database"]
    VectorIdx["Vector Index<br/><i>1536d embeddings</i>"]
    Plugins["APOC · GDS"]
  end

  style Frontend fill:#0f172a,stroke:#334155,color:#f8fafc
  style Backend fill:#1e1b4b,stroke:#4338ca,color:#f8fafc
  style DB fill:#042f2e,stroke:#0d9488,color:#f8fafc
  style Retrieval fill:#1e3a5f,stroke:#3b82f6,color:#e0f2fe
  style Authority fill:#3b1f5e,stroke:#8b5cf6,color:#ede9fe
  style Generation fill:#4a1d34,stroke:#ec4899,color:#fce7f3
  style Compass fill:#365314,stroke:#84cc16,color:#ecfccb
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| **Backend** | FastAPI, Python 3.10+, Pydantic 2, spaCy (Italian NLP) |
| **Database** | Neo4j 5.15 (Graph + Native Vector Index) |
| **LLM** | OpenAI GPT-4o (generation), GPT-4o-mini (analysis) |
| **Embeddings** | text-embedding-3-small (1536 dimensions) |
| **Infrastructure** | Docker, Docker Compose, Uvicorn |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose
- OpenAI API Key

### 1. Clone and configure

```bash
git clone https://github.com/Emeierkeio/thesis-ParliamentRAG.git
cd thesis-ParliamentRAG

# Set up environment variables
cp .env.example .env
# Edit .env with your OpenAI API key and Neo4j credentials
```

### 2. Start Neo4j

```bash
docker compose up -d neo4j
```

### 3. Start the Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate    # Windows: .\venv\Scripts\activate

pip install -r requirements.txt
python -m spacy download it_core_news_sm

uvicorn app.main:app --reload --port 8000
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Access the application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7475 |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Chat with SSE streaming |
| `/api/query` | POST | Alternative query endpoint |
| `/api/evidence/{id}` | GET | Full evidence details |
| `/api/config` | GET | System configuration |
| `/api/history` | GET/POST | Chat history |
| `/api/history/{id}` | GET/DELETE | Specific conversation |
| `/api/graph/schema` | GET | Neo4j graph schema |
| `/api/graph/stats` | GET | Database statistics |
| `/api/search/results` | GET | Parliamentary record search |
| `/api/search/deputies` | GET | Deputy list |
| `/api/search/groups` | GET | Parliamentary groups |
| `/api/evaluation` | POST | A/B evaluation submission |
| `/api/survey/create` | POST | User survey creation |

Full interactive documentation available at `/docs` when the backend is running.

---

## Configuration

All weights and thresholds are managed through YAML configuration in `config/default.yaml`:

```yaml
# Retrieval merger weights
retrieval:
  merger:
    diversity_weight: 0.2    # Penalizes speaker dominance
    coverage_weight: 0.3     # Favors party representation
    authority_weight: 0.3    # Query-dependent credibility
    relevance_weight: 0.2    # Semantic similarity

# Authority scoring components
authority:
  weights:
    profession: 0.10
    education: 0.10
    committee: 0.20
    acts: 0.25
    interventions: 0.30
    role: 0.05

# Generation model selection
generation:
  models:
    analyst: "gpt-4o-mini"   # Stage 1: query decomposition
    writer: "gpt-4o"         # Stage 2: per-party sections
    integrator: "gpt-4o"     # Stage 3: narrative coherence
    # Stage 4 is deterministic (no LLM)
```

---

## Database Schema

The Neo4j knowledge graph models Italian parliamentary data through the following entity-relationship structure:

```mermaid
graph LR
  Session([<b>Session</b>]):::session
  Debate([<b>Debate</b>]):::debate
  Phase([<b>Phase</b>]):::phase
  Speech([<b>Speech</b>]):::speech
  Chunk([<b>Chunk</b><br/><i>+ embedding</i>]):::chunk
  Deputy([<b>Deputy</b>]):::person
  GovMember([<b>GovernmentMember</b>]):::person
  Group([<b>ParliamentaryGroup</b>]):::group
  Committee([<b>Committee</b>]):::group
  Act([<b>ParliamentaryAct</b>]):::act

  Session -->|HAS_DEBATE| Debate
  Debate -->|HAS_PHASE| Phase
  Phase -->|CONTAINS_SPEECH| Speech
  Speech -->|HAS_CHUNK| Chunk
  Speech -->|SPOKEN_BY| Deputy
  Speech -->|SPOKEN_BY| GovMember
  Deputy -->|MEMBER_OF_GROUP| Group
  Deputy -->|MEMBER_OF_COMMITTEE| Committee
  Deputy -->|IS_PRESIDENT| Committee
  Deputy -->|IS_VICE_PRESIDENT| Committee
  Deputy -->|IS_SECRETARY| Committee
  Deputy -->|PRIMARY_SIGNATORY| Act
  Deputy -->|CO_SIGNATORY| Act

  classDef session fill:#4C8BF5,stroke:#2d6ae0,color:#fff,rx:12
  classDef debate fill:#7B61FF,stroke:#5a3fd6,color:#fff,rx:12
  classDef phase fill:#a855f7,stroke:#7e22ce,color:#fff,rx:12
  classDef speech fill:#F97316,stroke:#d4600e,color:#fff,rx:12
  classDef chunk fill:#EF4444,stroke:#c53030,color:#fff,rx:12
  classDef person fill:#10B981,stroke:#059669,color:#fff,rx:12
  classDef group fill:#06B6D4,stroke:#0891b2,color:#fff,rx:12
  classDef act fill:#F59E0B,stroke:#d48806,color:#fff,rx:12
```

> **Vector Index** — Each `Chunk` node stores a 1536-dimensional embedding (`text-embedding-3-small`) indexed via Neo4j's native vector search for dense retrieval.

---

## Testing

```bash
cd backend
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific critical tests
pytest tests/test_authority_coalition.py -v   # Coalition-aware temporal logic
pytest tests/test_citation_exact.py -v        # Offset-based citation extraction
```

---

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

| Document | Topic |
|----------|-------|
| [architecture.md](docs/architecture.md) | System design and component overview |
| [retrieval.md](docs/retrieval.md) | Dual-channel retrieval pipeline |
| [authority_score.md](docs/authority_score.md) | Query-dependent authority scoring |
| [ideological_compass.md](docs/ideological_compass.md) | Semi-supervised compass methodology |
| [citation_integrity.md](docs/citation_integrity.md) | Offset-based citation verification |
| [generation_pipeline.md](docs/generation_pipeline.md) | 4-stage generation pipeline |
| [design_choices.md](docs/design_choices.md) | Architectural decisions and rationale |
| [evaluation.md](docs/evaluation.md) | A/B testing methodology |

---

## Project Structure

```
ParliamentRAG/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings & config loader
│   │   ├── models/              # Pydantic data models
│   │   ├── routers/             # API endpoints (9 routers)
│   │   └── services/
│   │       ├── retrieval/       # Dense + Graph channels, Merger
│   │       ├── authority/       # Authority scoring, Coalition logic
│   │       ├── generation/      # 4-stage pipeline
│   │       ├── compass/         # Ideological compass (PCA, KDE)
│   │       └── citation/        # Sentence extraction
│   ├── config/                  # YAML configuration
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── app/                 # Next.js App Router pages
│       ├── components/          # React components
│       ├── hooks/               # Custom React hooks
│       └── types/               # TypeScript definitions
├── config/                      # Shared YAML configuration
├── docs/                        # Technical documentation
├── docker-compose.yml           # Neo4j container
├── .env.example                 # Environment template
└── LICENSE
```

---

## Author

**Mirko Tritella** — Master's Thesis Project

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
