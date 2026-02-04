# Architettura del Sistema

## Panoramica

Il sistema Multi-View RAG per dati parlamentari italiani è progettato per fornire risposte bilanciate che rappresentano tutte le prospettive politiche presenti nel corpus parlamentare. L'architettura si basa su quattro componenti principali che operano in pipeline.

## Componenti del Sistema

### 1. Retrieval Engine (Dual-Channel)

Il motore di retrieval implementa un approccio a doppio canale:

- **Dense Channel**: Ricerca vettoriale su embedding pre-calcolati dei chunk di intervento
- **Graph Channel**: Traversal del grafo Neo4j per sfruttare metadati parlamentari (atti, commissioni, firmatari)

La fusione dei due canali avviene tramite un merger che bilancia:
- Rilevanza semantica
- Diversità (penalizzazione di speaker dominanti)
- Copertura partitica
- Autorevolezza

### 2. Authority Scorer

Calcolo query-dependent dell'autorevolezza di ogni speaker:

```
Authority(speaker, query, date) = Σ wi × component_i
```

Componenti:
- Professione/formazione (similarità semantica)
- Membership in commissioni (temporale + topic relevance)
- Atti parlamentari (count + time decay)
- Interventi (count + time decay)
- Ruolo istituzionale

**Logica Temporale Coalizioni**: Il passaggio maggioranza↔opposizione invalida l'autorità accumulata nella coalizione precedente.

### 3. Ideological Compass

Sistema semi-supervisionato per garantire copertura multi-view:

- Ancore SOFT basate sui gruppi parlamentari (configurabili)
- Proiezione frammenti in spazio Left/Center/Right
- Metriche di bilanciamento per verificare la copertura

### 4. Generation Pipeline (4-Stage)

Pipeline a 4 stadi per generazione fedele:

1. **Analyst**: Decomposizione query in claim atomici
2. **Sectional Writer**: Scrittura sezioni per partito
3. **Integrator**: Integrazione narrativa (senza fusione posizioni)
4. **Citation Surgeon**: Inserimento citazioni verbatim via offset

## Flusso Dati

```
Query → Embedding → [Dense Channel + Graph Channel] → Merge →
Authority Scoring → Compass Analysis → 4-Stage Generation → Response
```

## Stack Tecnologico

| Componente | Tecnologia | Motivazione |
|------------|------------|-------------|
| Database | Neo4j 5.15 | Grafo nativo per dati parlamentari, vector index integrato |
| Backend | FastAPI | Async nativo, SSE streaming, OpenAPI |
| Frontend | Next.js | SSR, TypeScript, componenti React |
| LLM | OpenAI GPT-4o | API stabile, structured output |
| Embeddings | text-embedding-3-small | 1536 dimensioni, costo contenuto |

## Scelte Architetturali

### Perché Neo4j?

I dati parlamentari sono intrinsecamente relazionali:
- Deputato → Gruppo (temporale)
- Deputato → Commissione (temporale)
- Intervento → Dibattito → Seduta
- Atto → Firmatari

PostgreSQL con pgvector avrebbe richiesto JOIN complessi per navigare queste relazioni.

### Perché 4-Stage Generation?

Un singolo passaggio LLM rischia:
- Hallucination delle citazioni
- Fusione indesiderata delle posizioni partitiche
- Omissione di partiti meno rappresentati

La pipeline a 4 stadi garantisce verificabilità ad ogni passaggio.

### Perché Offset-Based Citations?

Il fuzzy matching introduce ambiguità:
- Soglie arbitrarie
- Non-determinismo
- Difficoltà di audit

L'estrazione offset-based è deterministica e verificabile.
