# Multi-View RAG for Italian Parliamentary Data

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-blue.svg)](https://neo4j.com)

Sistema di Retrieval-Augmented Generation multi-view per l'analisi bilanciata dei dibattiti parlamentari italiani.

**Repository**: [github.com/Emeierkeio/thesis-ParliamentRAG](https://github.com/Emeierkeio/thesis-ParliamentRAG)

## Caratteristiche

- **Dual-Channel Retrieval**: Combina ricerca vettoriale densa e traversal di grafi per evidenze parlamentari
- **Authority Scoring**: Punteggi di autorevolezza query-dependent con logica temporale delle coalizioni
- **Ideological Compass**: Sistema semi-supervisionato per garantire copertura multi-view
- **4-Stage Generation Pipeline**: Analyst → Sectional Writer → Integrator → Citation Surgeon
- **Citazioni Esatte**: Estrazione offset-based, ZERO fuzzy matching

## Architettura

```
tesi_2/
├── backend/
│   ├── app/
│   │   ├── models/          # Schema dati
│   │   ├── services/        # Business logic
│   │   │   ├── retrieval/   # Dual-channel retrieval
│   │   │   ├── authority/   # Authority scoring
│   │   │   ├── compass/     # Ideological compass
│   │   │   └── generation/  # 4-stage pipeline
│   │   └── routers/         # API endpoints
│   └── tests/
├── frontend/                 # Next.js frontend
├── config/                   # YAML configuration
└── docs/                     # Thesis documentation
```

## Setup

### 1. Prerequisiti

- Python 3.10+
- Node.js 18+
- Docker (per Neo4j)
- OpenAI API Key

### 2. Database Neo4j

```bash
# Avvia Neo4j (già configurato in docker-compose.yml)
docker-compose up -d neo4j

# Verifica connessione
# Browser: http://localhost:7475
# Bolt: bolt://localhost:7689
```

### 3. Backend

```bash
cd backend

# Crea virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows

# Installa dipendenze
pip install -r requirements.txt

# Configura ambiente
cp ../.env.example ../.env
# Modifica .env con le tue credenziali

# Avvia server
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend

# Installa dipendenze
npm install

# Avvia development server
npm run dev
```

### 5. Accesso

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7475

## API Endpoints

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/chat` | POST | Chat con streaming SSE |
| `/api/query` | POST | Query alternativa |
| `/api/evidence/{id}` | GET | Dettagli evidenza |
| `/api/config` | GET | Configurazione sistema |
| `/api/history` | GET/POST | Cronologia chat |
| `/api/history/{id}` | GET/DELETE | Dettagli/eliminazione chat |
| `/api/graph/schema` | GET | Schema del grafo Neo4j |
| `/api/graph/stats` | GET | Statistiche database |
| `/api/search/results` | GET | Ricerca atti parlamentari |
| `/api/search/deputies` | GET | Lista deputati |
| `/api/search/groups` | GET | Lista gruppi parlamentari |

## Configurazione

Tutti i pesi e threshold sono configurabili in `config/default.yaml`:

```yaml
retrieval:
  merger:
    diversity_weight: 0.2
    coverage_weight: 0.3
    authority_weight: 0.3
    relevance_weight: 0.2

authority:
  weights:
    profession: 0.10
    education: 0.10
    committee: 0.20
    acts: 0.25
    interventions: 0.30
    role: 0.05
```

## Tests

```bash
cd backend
pytest tests/ -v
```

### Test Critici

- `test_authority_coalition.py`: Verifica logica temporale coalizioni
- `test_citation_exact.py`: Verifica estrazione citazioni offset-based

## Regole Fondamentali

1. **NO fuzzy matching per citazioni** - Solo estrazione offset-based
2. **Logica temporale coalizioni** - Cambio maggioranza↔opposizione invalida autorità precedente
3. **Copertura multi-view** - Tutti i 10 partiti devono apparire nella risposta
4. **Configurazione > codice** - Tutti i parametri in YAML

## Compass Ideologico 2D

Il sistema include un compass ideologico basato su **PCA (Principal Component Analysis)** degli embedding testuali:

- Le posizioni dei gruppi parlamentari sono derivate esclusivamente dal **contenuto semantico** dei testi analizzati
- **Non** basato su classificazioni a priori dei partiti
- Gli assi emergono dai dati stessi tramite riduzione dimensionale
- Visualizza la distribuzione delle posizioni politiche nello spazio semantico

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | FastAPI, Python 3.10+ |
| Frontend | Next.js 14, React, TypeScript |
| Database | Neo4j 5.x (Graph + Vector) |
| LLM | OpenAI GPT-4o |
| Embeddings | text-embedding-3-small (1536 dim) |
| UI Components | shadcn/ui, Tailwind CSS |

## Struttura Database

Il sistema utilizza un grafo Neo4j con le seguenti entità principali:

- **Seduta**: Sessioni parlamentari
- **Dibattito**: Discussioni su specifici temi
- **Intervento**: Discorsi dei parlamentari
- **Chunk**: Frammenti di testo con embedding vettoriali
- **Deputato**: Membri del parlamento
- **MembroGoverno**: Membri del governo
- **GruppoParlamentare**: Gruppi politici
- **AttoParlamentare**: Atti e proposte legislative
- **Commissione**: Commissioni parlamentari

## Autore

Progetto di tesi magistrale in Informatica.

## Licenza

MIT License - Vedi [LICENSE](LICENSE) per dettagli.
