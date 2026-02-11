# ParliamentRAG: Un Sistema RAG Avanzato per l'Analisi Equilibrata dei Dibattiti Parlamentari Italiani

## Tesi di Laurea Magistrale in Data Science

---

## Indice

1. [Introduzione](#1-introduzione)
2. [Background e Stato dell'Arte](#2-background-e-stato-dellarte)
3. [Architettura del Sistema](#3-architettura-del-sistema)
4. [Metodologia](#4-metodologia)
5. [Implementazione](#5-implementazione)
6. [Valutazione](#6-valutazione)
7. [Risultati e Discussione](#7-risultati-e-discussione)
8. [Conclusioni e Lavori Futuri](#8-conclusioni-e-lavori-futuri)
9. [Bibliografia](#9-bibliografia)
10. [Appendici](#appendici)

---

## 1. Introduzione

### 1.1 Motivazione

L'accesso trasparente e imparziale all'informazione parlamentare rappresenta un pilastro fondamentale delle democrazie moderne. Tuttavia, il volume crescente di atti parlamentari, dibattiti e interventi rende sempre più complesso per cittadini, giornalisti e ricercatori ottenere una visione equilibrata e completa delle posizioni politiche su specifici temi.

I sistemi tradizionali di ricerca parlamentare soffrono di diverse limitazioni:
- **Bias di selezione**: tendenza a mostrare risultati provenienti prevalentemente da una parte politica
- **Mancanza di contestualizzazione**: citazioni decontestualizzate che possono distorcere il significato originale
- **Assenza di verifica**: impossibilità di tracciare le fonti fino al documento originale
- **Sovraccarico informativo**: difficoltà nel sintetizzare centinaia di interventi su un singolo tema

### 1.2 Obiettivi della Tesi

Questa tesi presenta **ParliamentRAG**, un sistema di Retrieval-Augmented Generation (RAG) progettato per affrontare queste sfide attraverso:

1. **Bilanciamento Multi-Vista**: garantire rappresentazione equilibrata di maggioranza e opposizione
2. **Integrità delle Citazioni**: citazioni verificabili con tracciabilità completa fino al documento sorgente
3. **Authority Scoring Query-Dependent**: identificare gli esperti più rilevanti per ogni specifica query
4. **Compass Ideologico**: mappare e visualizzare la distribuzione delle posizioni politiche

### 1.3 Contributi Originali

I principali contributi di questa tesi sono:

1. **Dual-Channel Retrieval Architecture**: combinazione innovativa di ricerca vettoriale densa e traversal su knowledge graph per massimizzare recall e precisione
2. **Coalition-Aware Authority Scoring**: sistema di scoring che considera la dinamica temporale delle coalizioni politiche italiane
3. **Offset-Based Citation Integrity**: metodo deterministico per l'estrazione e verifica delle citazioni che elimina completamente il fuzzy matching
4. **Four-Stage Generation Pipeline**: architettura a pipeline verificabile che garantisce trasparenza ad ogni stadio della generazione

### 1.4 Struttura della Tesi

Il resto della tesi è organizzato come segue: il Capitolo 2 presenta il background teorico e lo stato dell'arte; il Capitolo 3 descrive l'architettura complessiva del sistema; il Capitolo 4 dettaglia la metodologia di ogni componente; il Capitolo 5 illustra i dettagli implementativi; il Capitolo 6 presenta il framework di valutazione; il Capitolo 7 discute i risultati; il Capitolo 8 conclude con limitazioni e lavori futuri.

---

## 2. Background e Stato dell'Arte

### 2.1 Retrieval-Augmented Generation (RAG)

I sistemi RAG, introdotti da Lewis et al. (2020), combinano la capacità generativa dei Large Language Models (LLM) con un meccanismo di retrieval che fornisce contesto fattuale. Questo paradigma ha dimostrato significativi miglioramenti nella riduzione delle "allucinazioni" e nell'accuracy fattuale.

L'architettura RAG standard comprende:
1. **Retriever**: recupera documenti rilevanti da un corpus
2. **Generator**: produce la risposta condizionata sui documenti recuperati

#### 2.1.1 Dense Retrieval

I metodi di dense retrieval (Karpukhin et al., 2020) utilizzano embedding vettoriali per rappresentare query e documenti in uno spazio latente condiviso. La similarity viene calcolata mediante prodotto scalare o cosine similarity:

$$sim(q, d) = \frac{E_q(q) \cdot E_d(d)}{||E_q(q)|| \cdot ||E_d(d)||}$$

dove $E_q$ e $E_d$ sono gli encoder per query e documenti.

#### 2.1.2 Graph-Based Retrieval

I knowledge graph permettono di catturare relazioni strutturate tra entità. Sistemi come GraphRAG (Microsoft, 2024) hanno dimostrato che la combinazione di retrieval vettoriale e traversal su grafi migliora significativamente la qualità delle risposte per query complesse.

### 2.2 Analisi del Dibattito Politico

#### 2.2.1 Sistemi Esistenti

- **OpenParlamento** (Italia): aggregazione dati parlamentari con ricerca keyword-based
- **They Vote For You** (UK): tracking votazioni con analisi posizioni
- **GovTrack** (USA): monitoraggio legislativo con focus su bills e voting records

Questi sistemi, pur fornendo accesso ai dati grezzi, non offrono:
- Sintesi equilibrate multi-partito
- Citazioni verificabili con context completo
- Scoring di autorevolezza query-dependent

#### 2.2.2 Bias nei Sistemi di Ricerca

La letteratura ha ampiamente documentato i bias presenti nei sistemi di information retrieval (Baeza-Yates, 2018). Nel contesto politico, questi bias possono:
- Amplificare posizioni mainstream
- Marginalizzare voci minoritarie
- Creare "filter bubbles" informative

### 2.3 Large Language Models per Testi Politici

L'applicazione di LLM a testi politici presenta sfide uniche:
- **Neutralità**: evitare l'introduzione di bias ideologici
- **Fidelity**: mantenere accuratezza rispetto alle fonti
- **Attribution**: garantire tracciabilità delle affermazioni

Studi recenti (Santurkar et al., 2023) hanno evidenziato bias sistematici nei LLM verso posizioni moderate-liberali. Il nostro sistema affronta questo problema attraverso vincoli espliciti di bilanciamento nella pipeline di generazione.

### 2.4 Embedding e Rappresentazioni Semantiche

#### 2.4.1 Text Embedding Models

I modelli di embedding recenti (OpenAI text-embedding-3, Cohere embed-v3) raggiungono performance state-of-the-art su benchmark di semantic similarity. In questo lavoro utilizziamo:

- **text-embedding-3-small** (OpenAI): 1536 dimensioni, ottimizzato per retrieval
- Performance su MTEB benchmark: 62.3% (retrieval tasks)

#### 2.4.2 Thesaurus Eurovoc

EUROVOC è il thesaurus multilingue dell'Unione Europea, utilizzato per l'indicizzazione dei documenti parlamentari. Comprende:
- ~7000 descrittori
- 21 domini tematici
- 127 micro-thesauri

Nel nostro sistema, EUROVOC viene utilizzato per il matching semantico degli atti parlamentari.

---

## 3. Architettura del Sistema

### 3.1 Overview Architetturale

ParliamentRAG segue un'architettura a microservizi composta da quattro componenti principali:

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │   Chat   │  │ Explorer │  │  Search  │  │ Settings │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │ SSE
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    API Layer (Routers)                   │   │
│  │  /chat  /query  /evidence  /search  /graph  /config     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Service Layer                         │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐  │   │
│  │  │ Retrieval │ │ Authority │ │  Compass  │ │Generation│  │   │
│  │  │  Engine   │ │  Scorer   │ │  Pipeline │ │ Pipeline │  │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (Neo4j)                         │
│  ┌──────────────────┐  ┌──────────────────────────────────┐    │
│  │  Vector Index    │  │      Knowledge Graph              │    │
│  │  (chunk_embedding│  │  Seduta→Dibattito→Intervento→    │    │
│  │   _index)        │  │  Chunk, Deputato, Atto, etc.     │    │
│  └──────────────────┘  └──────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Model

Il knowledge graph parlamentare modella le seguenti entità e relazioni:

#### 3.2.1 Entità Principali

| Entità | Descrizione | Proprietà Chiave |
|--------|-------------|------------------|
| **Seduta** | Sessione parlamentare | data, numero, legislatura |
| **Dibattito** | Discussione tematica | titolo, tipo |
| **Fase** | Fase del dibattito | tipo, ordine |
| **Intervento** | Discorso singolo | testo_raw, data_ora |
| **Chunk** | Frammento di testo | text, embedding, span_start, span_end |
| **Deputato** | Membro parlamento | nome, cognome, professione, istruzione |
| **MembroGoverno** | Membro esecutivo | nome, cognome, carica |
| **GruppoParlamentare** | Gruppo politico | nome, coalizione |
| **AttoParlamentare** | Atto legislativo | titolo, eurovoc, embedding_titolo |
| **Commissione** | Commissione parlamentare | nome, tipo |

#### 3.2.2 Relazioni

```
(Seduta)-[:HA_DIBATTITO]->(Dibattito)
(Dibattito)-[:HA_FASE]->(Fase)
(Fase)-[:CONTIENE_INTERVENTO]->(Intervento)
(Intervento)-[:HA_CHUNK]->(Chunk)
(Intervento)-[:PRONUNCIATO_DA]->(Deputato|MembroGoverno)
(Deputato)-[:MEMBRO_GRUPPO {dataInizio, dataFine}]->(GruppoParlamentare)
(Deputato)-[:FIRMATARIO]->(AttoParlamentare)
(Deputato)-[:MEMBRO_COMMISSIONE {dataInizio, dataFine}]->(Commissione)
```

### 3.3 Stack Tecnologico

| Componente | Tecnologia | Versione | Motivazione |
|------------|------------|----------|-------------|
| Backend | FastAPI | ≥0.109 | Performance async, OpenAPI auto-docs |
| Frontend | Next.js | 16.1 | SSR, App Router, React 19 |
| Database | Neo4j | 5.15 | Native graph + vector index |
| LLM | OpenAI GPT-4o | - | State-of-the-art reasoning |
| Embedding | text-embedding-3-small | - | Ottimo rapporto qualità/costo |
| Styling | Tailwind CSS | 4.0 | Utility-first, customizable |
| UI Components | shadcn/ui + Radix | - | Accessible, composable |

### 3.4 Flusso Dati End-to-End

```
Query Utente: "Qual è la posizione dei partiti sulla riforma fiscale?"
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. QUERY EMBEDDING                                              │
│    OpenAI text-embedding-3-small → [1536 dim vector]            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. DUAL-CHANNEL RETRIEVAL                                       │
│    ┌─────────────────────┐    ┌─────────────────────┐          │
│    │   Dense Channel     │    │   Graph Channel     │          │
│    │   (Vector Search)   │    │   (Eurovoc + KG)    │          │
│    │   top_k=200         │    │   hybrid matching   │          │
│    └─────────────────────┘    └─────────────────────┘          │
│                    └──────────┬──────────┘                      │
│                               ▼                                 │
│                    Channel Merger (weighted fusion)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. AUTHORITY SCORING                                            │
│    Per ogni speaker: profession + education + committee +       │
│                      acts + interventions + role                │
│    Con time decay e coalition logic                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. IDEOLOGICAL COMPASS                                          │
│    IC-1: Axis Discovery (Weighted PCA)                          │
│    IC-2: Projection (Z-score normalization)                     │
│    IC-3: Group Clustering (KDE)                                 │
│    IC-4: Dispersion Analysis                                    │
│    IC-5: Evidence Binding                                       │
│    IC-6: Interpretability (TF-IDF labeling)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. GENERATION PIPELINE (4-Stage)                                │
│    Stage 1: Analyst      → Claim decomposition                  │
│    Stage 2: Sectional    → Per-party sections (10 parties)      │
│    Stage 3: Integrator   → Narrative coherence                  │
│    Stage 4: Surgeon      → Citation resolution (offset-based)   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. SSE STREAMING RESPONSE                                       │
│    Events: progress, evidence, citation, expert, compass,       │
│            response                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Metodologia

### 4.1 Dual-Channel Retrieval

Il sistema di retrieval combina due canali complementari per massimizzare recall e precisione.

#### 4.1.1 Dense Channel

Il canale denso utilizza la ricerca vettoriale su Neo4j Vector Index.

**Algoritmo:**
```
Input: query, top_k=200, threshold=0.3
Output: List[ChunkWithMetadata]

1. query_embedding = embed(query)  // text-embedding-3-small
2. results = neo4j.vector_query(
     index="chunk_embedding_index",
     vector=query_embedding,
     top_k=top_k
   )
3. filtered = [r for r in results if r.similarity >= threshold]
4. enriched = join_metadata(filtered)  // speaker, seduta, dibattito
5. return enriched
```

**Query Cypher:**
```cypher
CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
YIELD node AS c, score
WHERE score >= $threshold
MATCH (c)<-[:HA_CHUNK]-(i:Intervento)-[:PRONUNCIATO_DA]->(speaker)
MATCH (i)<-[:CONTIENE_INTERVENTO]-(f:Fase)<-[:HA_FASE]-(d:Dibattito)
      <-[:HA_DIBATTITO]-(s:Seduta)
OPTIONAL MATCH (speaker)-[mg:MEMBRO_GRUPPO]->(g:GruppoParlamentare)
WHERE mg.dataInizio <= s.data AND (mg.dataFine IS NULL OR mg.dataFine >= s.data)
RETURN c, i, speaker, g, s, d, score
```

#### 4.1.2 Graph Channel

Il canale graph sfrutta la struttura del knowledge graph per un retrieval più mirato.

**Strategia Ibrida Eurovoc:**

1. **Fase Lessicale**: matching diretto sui termini EUROVOC degli atti parlamentari
2. **Fase Semantica**: reranking mediante similarity sull'embedding del titolo
3. **Fase Traversal**: navigazione dal firmatario agli interventi correlati

**Algoritmo:**
```
Input: query, max_acts=100
Output: List[ChunkWithMetadata]

1. keywords = extract_keywords(query)
2. acts_lexical = match_eurovoc_lexical(keywords)
3. query_emb = embed(query)
4. acts_semantic = rerank_by_title_similarity(acts_lexical, query_emb)
5. acts_filtered = acts_semantic[:max_acts]
6. chunks = traverse_signatories_to_chunks(acts_filtered)
7. return chunks
```

#### 4.1.3 Channel Merger

La fusione dei due canali avviene attraverso una formula pesata:

$$score_{final} = w_r \cdot relevance + w_d \cdot diversity + w_c \cdot coverage + w_a \cdot authority$$

Con pesi di default: $w_r = 0.2$, $w_d = 0.2$, $w_c = 0.3$, $w_a = 0.3$

**Componenti:**

- **Relevance**: similarity score normalizzato dal retrieval
- **Diversity**: penalizza dominanza di un singolo speaker (limite: top_k/10 per speaker)
- **Coverage**: bilancia rappresentazione partiti (soft limit: top_k/3 per partito)
- **Authority**: authority score query-dependent

### 4.2 Authority Scoring

Il sistema di authority scoring valuta la credibilità di ogni speaker rispetto alla specifica query.

#### 4.2.1 Componenti dello Score

Lo score finale è la somma pesata di sei componenti:

$$authority = \sum_{i=1}^{6} w_i \cdot component_i$$

| Componente | Peso | Descrizione |
|------------|------|-------------|
| Professione | 0.10 | Cosine similarity tra query embedding e embedding_professione |
| Istruzione | 0.10 | Cosine similarity tra query embedding e embedding_istruzione |
| Commissioni | 0.20 | Rilevanza delle commissioni di appartenenza per il topic |
| Atti | 0.25 | Numero di atti firmati sul tema (con time decay) |
| Interventi | 0.30 | Numero di interventi sul tema (con time decay) |
| Ruolo | 0.05 | Peso predefinito per ruolo istituzionale |

#### 4.2.2 Time Decay

Per atti e interventi si applica un decadimento temporale esponenziale:

$$decayed\_count = \sum_{i} e^{-\lambda \cdot days\_old_i}$$

Con half-life configurabili:
- Atti: 365 giorni
- Interventi: 180 giorni

#### 4.2.3 Coalition Logic

**Regola Fondamentale**: Quando un deputato attraversa il confine MAGGIORANZA ↔ OPPOSIZIONE, l'autorità accumulata nella coalizione precedente viene invalidata.

```python
def authority_carries_over(old_group: str, new_group: str) -> bool:
    old_coalition = get_coalition(old_group)
    new_coalition = get_coalition(new_group)
    return old_coalition == new_coalition
```

Questa scelta riflette la realtà politica italiana dove il cambio di schieramento rappresenta una discontinuità significativa.

#### 4.2.4 Normalizzazione

Lo score finale viene normalizzato usando un approccio percentile-based che garantisce una distribuzione uniforme tra [0, 1].

### 4.3 Ideological Compass

Il compass ideologico fornisce una visualizzazione bidimensionale delle posizioni politiche sul tema della query.

#### 4.3.1 Design Philosophy

A differenza dei sistemi di political scaling tradizionali (es. DW-NOMINATE), il nostro compass:
- È **query-dependent**: gli assi cambiano in base al tema
- Funziona in modalità **unsupervised** (default) o con **soft anchors opzionali**
- Ha scopo di **multi-view coverage**, non di scoperta ideologica

#### 4.3.2 Pipeline IC-1 to IC-6

**IC-1: Axis Discovery**
```
Input: fragments with embeddings
Output: principal components (PC1, PC2)

1. W = compute_weights(fragments)  // authority-weighted
2. X = stack_embeddings(fragments)
3. X_weighted = X * sqrt(W)
4. PC1, PC2 = weighted_PCA(X_weighted, n_components=2)
```

**IC-2: Projection**
```
Input: fragments, PC1, PC2
Output: projected positions with confidence

1. positions = project(fragments, [PC1, PC2])
2. confidences = compute_SCR_confidence(positions)
3. positions_normalized = z_score_normalize(positions, clip=4.0)
```

**IC-3: Group Clustering**
```
Input: projected positions grouped by party
Output: party centroid positions

1. for each party:
     if n_samples >= min_for_kde:
       centroid = KDE_mode(positions)
       ellipse = KDE_contour(positions, level=0.68)
     else:
       centroid = mean(positions)
       ellipse = covariance_ellipse(positions)
```

**IC-4: Dispersion Analysis**
```
Input: party positions with ellipses
Output: dispersion metrics

1. within_party_variance = mean(ellipse_areas)
2. between_party_distance = mean(pairwise_centroid_distances)
3. separation_ratio = between / within
```

**IC-5: Evidence Binding**
```
Input: projected fragments
Output: extreme evidence per pole

1. for each axis:
     positive_extreme = top_k_by_projection(axis, k=3)
     negative_extreme = bottom_k_by_projection(axis, k=3)
2. bind evidence to axis poles
```

**IC-6: Interpretability**
```
Input: fragments per pole
Output: axis labels

1. for each pole:
     texts = [f.text for f in pole_fragments]
     tfidf_scores = compute_tfidf(texts, corpus=all_texts)
     label = top_k_terms(tfidf_scores, k=3)
```

#### 4.3.3 Soft Anchors (Opzionali)

Il sistema supporta soft anchors configurabili esternamente in YAML, **disabilitate di default** per un approccio completamente unsupervised:

```yaml
compass:
  anchors:
    enabled: false  # Default: unsupervised mode
    left:
      groups: ["ALLEANZA VERDI E SINISTRA", "PD-IDP"]
      confidence: 0.8
    center:
      groups: ["AZIONE-POPOLARI", "ITALIA VIVA"]
      confidence: 0.6
    right:
      groups: ["FRATELLI D'ITALIA", "LEGA", "FORZA ITALIA"]
      confidence: 0.8
```

Quando `enabled: false`, il compass utilizza esclusivamente PCA sugli embedding dei frammenti, senza orientamento predefinito degli assi. Questo approccio è più "data-driven" ma può produrre assi con orientamento arbitrario tra query diverse.

### 4.4 Generation Pipeline

La pipeline di generazione segue un pattern a 4 stadi ispirato al "surgeon pattern" per massimizzare verificabilità e tracciabilità.

#### 4.4.1 Stage 1: Analyst (ClaimAnalyst)

**Input:** Query + Retrieved Evidence
**Output:** Structured claim analysis

```json
{
  "claims": [
    {
      "claim_id": "C1",
      "claim_text": "La riforma fiscale ridurrà le tasse",
      "evidence_requirements": ["supporting", "opposing", "neutral"],
      "parties_expected": ["FDI", "PD", "M5S", ...]
    }
  ]
}
```

**Prompt System:**
```
Sei un analista politico. Decomponi la query in claim atomici
e identifica quali evidenze sono necessarie per ogni claim.
Assicurati di considerare tutti i 10 gruppi parlamentari.
```

#### 4.4.2 Stage 2: Sectional Writer

**Input:** Claims + Evidence grouped by party
**Output:** Per-party text sections with citation placeholders

**Regola Fondamentale:** Una sezione DEVE essere generata per ogni partito (10 sezioni obbligatorie). Se non c'è evidence per un partito:

```
"Nel corpus analizzato non risultano interventi rilevanti
del [PARTITO] su questo tema."
```

**Citation Placeholders:**
```
Il deputato ha affermato che [CIT:chunk_abc123] la riforma
porterà benefici significativi.
```

#### 4.4.3 Stage 3: Narrative Integrator

**Input:** 10 sezioni per-party
**Output:** Testo coerente con transizioni

**Regole:**
- PROIBITO fondere posizioni di partiti diversi
- PERMESSO: frasi di transizione, correzioni grammaticali
- PERMESSO: riordino sezioni per migliorare flusso narrativo
- OBBLIGATORIO: mantenere tutti i placeholder [CIT:*]
- OBBLIGATORIO: variare i bridge verbali — ogni verbo introduttivo usabile **una sola volta** nell'intero documento. Il sistema fornisce un repertorio di ~25 verbi categorizzati per tono (propositivo, critico, neutro, affermativo, interrogativo) e il prompt include esempi espliciti di output errato (verbi ripetuti) vs. corretto (verbi tutti diversi)

**Introduzione con Dati Reali:**
L'Integrator riceve statistiche computate dalle evidenze recuperate: titolo del provvedimento/dibattito principale (campo `debate_title`, estratto come titolo più frequente tra le evidenze), numero di interventi analizzati, numero di parlamentari coinvolti, periodo temporale (data primo e ultimo intervento). Questi dati vengono inseriti nell'introduzione per fornire contesto fattuale concreto, nominando specificamente il provvedimento in discussione ed evitando introduzioni generiche.

#### 4.4.4 Stage 4: Citation Surgeon

**Input:** Testo con placeholders [CIT:id]
**Output:** Testo con citazioni formattate

**Algoritmo Deterministico:**
```
Input: text, evidence_map
Output: text_with_citations

1. for each placeholder [CIT:id] in text:
     evidence = evidence_map[id]
     quote = evidence.testo_raw[span_start:span_end]  // EXACT
     citation = format_citation(quote, evidence)
     text = replace(placeholder, citation)
2. return text
```

**Formato Citazione:**
```
«{quote_verbatim}» [{speaker}, {party}, {date}, ID:{id}]
```

**CRITICO: Zero Fuzzy Matching**

La citazione è estratta deterministicamente usando gli offset pre-calcolati durante il chunking:
- `span_start`: offset iniziale in `testo_raw`
- `span_end`: offset finale in `testo_raw`
- `quote_text = testo_raw[span_start:span_end]`

Questo garantisce che ogni citazione sia esattamente verificabile nel documento sorgente.

#### 4.4.5 Deduplicazione Citazioni Cross-Speaker

Per evitare che la stessa citazione verbatim appaia in sezioni di speaker diversi (es. quando un deputato riporta le parole di un ministro o cita lo stesso decreto), il sistema implementa una deduplicazione a livello di testo normalizzato prima della generazione delle sezioni. Per ogni coppia di citazioni identiche, viene mantenuta quella associata allo speaker con `authority_score` più elevato, mentre l'altra viene marcata e esclusa dal contesto evidenze.

### 4.5 Sistema di Integrità Citazioni a 5 Livelli

Per garantire l'integrità assoluta delle citazioni nel testo generato, il sistema implementa un'architettura a 5 livelli complementari.

#### 4.5.1 Citation Registry (Livello 1)

Il Citation Registry traccia ogni citazione attraverso l'intera pipeline di generazione:

```python
class CitationRegistry:
    """Registro centrale per il tracciamento delle citazioni."""

    def register_evidence(self, evidence_list)      # Registra evidenze disponibili
    def bind_citation(self, eid, party, intro)      # Lega citazione a sezione
    def verify_placeholders_in_text(self, text)     # Verifica placeholder
    def mark_resolved(self, eid, success, error)    # Marca risoluzione
    def get_final_report(self)                      # Report integrità finale
```

**Stati delle citazioni:**
- `REGISTERED`: Evidenza disponibile nel sistema
- `BOUND`: Assegnata a una sezione di testo
- `IN_TEXT`: Placeholder `[CIT:id]` trovato nel testo integrato
- `RESOLVED`: Citazione formattata con successo dal Surgeon
- `FAILED`: Impossibile risolvere (errore offset, evidence mancante)
- `ORPHANED`: Placeholder perso durante l'integrazione

#### 4.5.2 Citation-First Writer (Livello 2)

L'architettura **Citation-First** risolve il problema fondamentale della coerenza tra testo introduttivo e citazione:

```
PROBLEMA (Text-First):
1. LLM scrive: "**Rossi** denuncia la crisi, affermando che"
2. [CIT:xxx] ← placeholder cieco (LLM non conosce la citazione esatta)
3. Surgeon inserisce: "il decreto è insufficiente"
4. RISULTATO: Intro parla di "crisi", citazione di "decreto" ❌

SOLUZIONE (Citation-First):
1. PRE-ESTRAI citazione: "il sistema sanitario è in crisi"
2. LLM riceve la FRASE ESATTA nel prompt
3. LLM scrive ATTORNO a quella frase: "denuncia la crisi del sistema"
4. RISULTATO: Testo costruito sulla citazione reale ✅
```

**Implementazione:**

Nel `SectionalWriter._build_evidence_context()`:
```python
# PRE-EXTRACT the citation BEFORE the LLM writes
extracted_citation = extract_best_sentences(
    text=quote_text,
    query=query,
    max_sentences=1,
    max_chars=200
)
# Store for later use by Surgeon
evidence["pre_extracted_citation"] = extracted_citation
```

**Prompt all'LLM:**
```
[ID: leg19_xxx]
Speaker: Marco Rossi
★ CITAZIONE DA USARE (NON COPIARE NEL TESTO): [il sistema sanitario è in crisi per mancanza di fondi]
Contesto: [testo completo per capire il tema]

ISTRUZIONE: Scrivi il testo introduttivo che si colleghi A QUELLA FRASE ESATTA.
```

Questo garantisce coerenza semantica **by construction**: il LLM conosce la citazione prima di scrivere.

#### 4.5.2.1 Completezza Sintattica delle Citazioni

Per garantire che le citazioni estratte siano frasi sintatticamente complete e comprensibili, il Sentence Extractor integra uno scoring di completezza sintattica che verifica la presenza di forme verbali italiane. La formula di scoring è:

$$score = 0.45 \times overlap + 0.25 \times completeness + 0.2 \times density + 0.1 \times position$$

dove $completeness \in \{0, 0.2, 0.5, 0.7, 1.0\}$ implementa una scala granulare di qualità sintattica:

- **1.0**: frase completa con verbo, inizio maiuscolo, nessuna troncatura
- **0.7**: frase completa ma con terminazione sospesa (preposizione/articolo finale)
- **0.5**: contiene verbo ma inizia a metà clausola
- **0.2**: frammento di clausola subordinata (inizia con *se*, *che*, *quando*, *dove*, *perché*, ecc.) — sintatticamente dipendente e incomprensibile senza il contesto della clausola principale
- **0.0**: nessun verbo rilevato (frammento nominale), oppure **intestazione di identificazione oratore**

Il punteggio 0.0 viene assegnato anche alle righe di identificazione dell'oratore presenti nei resoconti parlamentari (es. "VANNIA GAVA, Vice Ministra dell'Ambiente e della sicurezza energetica"), che rappresentano intestazioni protocollari e non contenuto citabile. Il rilevamento avviene tramite pattern matching su nomi in maiuscolo seguiti da ruoli istituzionali (Ministro, Sottosegretario, Presidente, Relatore, ecc.).

Il sistema applica inoltre una **soglia minima di qualità** (`MIN_QUALITY_SCORE = 0.15`): le frasi con punteggio inferiore vengono scartate in favore di alternative sintatticamente complete. Quando **nessuna** frase di un'evidenza supera la soglia (es. il chunk contiene solo l'intestazione protocollare dell'oratore senza contenuto sostanziale), l'estrattore restituisce stringa vuota e l'evidenza viene esclusa interamente dal contesto fornito al LLM. In questo modo la sezione non conterrà una citazione inutilizzabile, ma solo citazioni di qualità verificata.

#### 4.5.3 Integrator Guard (Livello 3)

Verifica pre/post integrazione per prevenire perdita di citazioni:

```python
def integrate_with_guard(query, sections, registry):
    # Pre: raccoglie [CIT:id] attesi
    expected = extract_all_citations(sections)

    # Integrazione standard
    result = integrate(query, sections)

    # Post: verifica preservazione
    found = extract_all_citations(result.text)
    missing = expected - found

    # Riparazione automatica
    if missing:
        repair_text = append_missing_sentences(missing, sections)
        result.text += repair_text

    return result
```

#### 4.5.4 Coherence Validator (Livello 4)

Valida la coerenza semantica tra testo introduttivo e citazione senza chiamate API:

**Metriche:**
- **Keyword Overlap Score**: Jaccard similarity sui token significativi
- **Sentiment Detection**: Rileva contraddizioni positivo/negativo

```python
result = validator.validate_coherence(
    intro="Il deputato critica la gestione sanitaria",
    quote="il sistema sanitario è in crisi per mancanza di fondi"
)
# → is_coherent=True, score=0.35, sentiment_mismatch=False
```

**Indicatori positivi**: sostiene, difende, elogia, approva
**Indicatori negativi**: critica, denuncia, contesta, respinge

Una citazione con intro positivo ma contenuto negativo (o viceversa) è marcata come incoerente.

#### 4.5.5 Final Completeness Check (Livello 5)

Verifica finale prima di restituire la risposta:

1. **Placeholder non risolti**: Cerca `[CIT:id]` rimasti nel testo finale
2. **Claim non supportati**: Usa `extract_unsupported_claims()` per trovare affermazioni senza citazione
3. **Report integrità**: Genera statistiche complete

#### 4.5.6 Report di Integrità

Ogni risposta include un report completo:

```json
{
  "citation_integrity": {
    "is_complete": true,
    "success_rate": 1.0,
    "coherence_verified": true,
    "unsupported_claims_count": 0,
    "unresolved_placeholders": []
  },
  "metadata": {
    "citation_integrity": {
      "coherence": {
        "all_coherent": true,
        "average_score": 0.35
      },
      "final": {
        "resolved": 12,
        "failed": 0,
        "orphaned": 0
      }
    }
  }
}
```

---

## 5. Implementazione

### 5.1 Backend (FastAPI)

#### 5.1.1 Struttura del Progetto

```
backend/
├── app/
│   ├── main.py              # Entry point, middleware, routers
│   ├── config.py            # Settings (env) + ConfigLoader (YAML)
│   ├── models/
│   │   ├── evidence.py      # UnifiedEvidence, IdeologyScore
│   │   ├── authority.py     # Authority components
│   │   ├── compass.py       # Compass models
│   │   └── query.py         # Request/Response
│   ├── services/
│   │   ├── neo4j_client.py  # Database singleton
│   │   ├── retrieval/
│   │   │   ├── engine.py    # Retrieval orchestrator
│   │   │   ├── dense_channel.py
│   │   │   ├── graph_channel.py
│   │   │   ├── merger.py
│   │   │   └── commission_matcher.py
│   │   ├── authority/
│   │   │   ├── scorer.py    # Authority orchestrator
│   │   │   ├── components.py
│   │   │   └── coalition_logic.py
│   │   ├── compass/
│   │   │   ├── pipeline.py  # IC-1 to IC-6
│   │   │   ├── anchors.py
│   │   │   ├── clustering.py
│   │   │   └── axis_labeling.py
│   │   ├── generation/
│   │   │   ├── pipeline.py  # 4-stage orchestrator
│   │   │   ├── analyst.py
│   │   │   ├── sectional.py
│   │   │   ├── integrator.py
│   │   │   └── surgeon.py
│   │   └── citation/
│   │       └── sentence_extractor.py
│   └── routers/
│       ├── chat.py          # SSE streaming
│       ├── query.py
│       ├── evidence.py
│       ├── search.py
│       ├── graph.py
│       └── config.py
├── tests/                   # pytest test suite
├── requirements.txt
└── venv/
```

#### 5.1.2 Configurazione Esterna

Tutti i parametri sono configurati esternamente in YAML per facilitare tuning e esperimenti:

**config/default.yaml:**
```yaml
retrieval:
  dense_channel:
    top_k: 200
    similarity_threshold: 0.3
    index_name: "chunk_embedding_index"
  graph_channel:
    lexical_keywords_min_match: 1
    semantic_similarity_threshold: 0.4
    max_acts_per_query: 100
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
  time_decay:
    acts_half_life_days: 365
    speeches_half_life_days: 180
  normalization: "percentile"

generation:
  models:
    analyst: "gpt-4o"
    writer: "gpt-4o"
    integrator: "gpt-4o"
  parameters:
    max_tokens: 4000
    temperature: 0.3
  require_all_parties: true

coalitions:
  maggioranza: ["FRATELLI D'ITALIA", "LEGA", "FORZA ITALIA", ...]
  opposizione: ["PD", "M5S", "AVS", ...]
```

#### 5.1.3 Streaming SSE

La comunicazione con il frontend avviene via Server-Sent Events per feedback real-time:

```python
@router.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    async def generate():
        # Progress events
        yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'label': 'Retrieval'})}\n\n"

        # Evidence events
        for evidence in retrieved:
            yield f"data: {json.dumps({'type': 'evidence', 'data': evidence.dict()})}\n\n"

        # Generation streaming
        async for chunk in pipeline.generate_stream():
            yield f"data: {json.dumps({'type': 'response', 'content': chunk})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 5.2 Frontend (Next.js)

#### 5.2.1 Struttura del Progetto

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx       # Root layout
│   │   ├── page.tsx         # Home (chat)
│   │   ├── explorer/        # Graph explorer
│   │   └── search/          # Search page
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatArea.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── CitationCard.tsx
│   │   │   ├── ExpertCard.tsx
│   │   │   └── CompassCard.tsx
│   │   ├── layout/
│   │   │   └── Sidebar.tsx
│   │   └── ui/              # shadcn/ui components
│   ├── hooks/
│   │   ├── use-chat.ts
│   │   └── use-sidebar.ts
│   └── types/
│       ├── chat.ts
│       └── api.ts
├── package.json
└── tailwind.config.ts
```

#### 5.2.2 State Management (useChat Hook)

```typescript
export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = async (query: string) => {
    setIsLoading(true);
    abortControllerRef.current = new AbortController();

    const response = await fetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ query }),
      signal: abortControllerRef.current.signal
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const events = decoder.decode(value).split('\n\n');
      for (const event of events) {
        if (event.startsWith('data: ')) {
          const data = JSON.parse(event.slice(6));
          handleEvent(data);
        }
      }
    }

    setIsLoading(false);
  };

  return { messages, isLoading, progress, sendMessage, cancelRequest, loadChat };
}
```

#### 5.2.3 Balance Metrics

Il frontend calcola e visualizza metriche di bilanciamento:

```typescript
interface BalanceMetrics {
  maggioranzaPercentage: number;  // % citazioni da maggioranza
  opposizionePercentage: number;  // % citazioni da opposizione
  biasScore: number;              // -1 (opp) to +1 (mag), 0 = balanced
}
```

### 5.3 Database (Neo4j)

#### 5.3.1 Configurazione Docker

```yaml
services:
  neo4j:
    image: neo4j:5.15.0
    ports:
      - "7475:7474"  # HTTP
      - "7689:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/thesis2026
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
      NEO4J_dbms_security_procedures_unrestricted: apoc.*,gds.*
    volumes:
      - ./neo4j/neo4j_data:/data
      - ./neo4j/neo4j_plugins:/plugins
```

#### 5.3.2 Vector Index

```cypher
CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}}
```

---

## 6. Valutazione

### 6.1 Framework di Valutazione

Il sistema viene valutato su quattro dimensioni principali:

1. **Retrieval Quality**: precisione e recall del sistema di retrieval
2. **Balance Metrics**: equità nella rappresentazione delle parti politiche
3. **Citation Integrity**: accuratezza e verificabilità delle citazioni
4. **Generation Quality**: qualità e coerenza delle risposte generate

### 6.2 Metriche di Retrieval

#### 6.2.1 Precision@k

$$Precision@k = \frac{|relevant \cap retrieved@k|}{k}$$

Valutata su un set di query annotate manualmente con documenti rilevanti.

#### 6.2.2 Recall@k

$$Recall@k = \frac{|relevant \cap retrieved@k|}{|relevant|}$$

#### 6.2.3 Mean Reciprocal Rank (MRR)

$$MRR = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{rank_i}$$

dove $rank_i$ è la posizione del primo documento rilevante per la query $i$.

#### 6.2.4 Normalized Discounted Cumulative Gain (nDCG)

$$nDCG@k = \frac{DCG@k}{IDCG@k}$$

dove:
$$DCG@k = \sum_{i=1}^{k} \frac{rel_i}{\log_2(i+1)}$$

### 6.3 Metriche di Bilanciamento

#### 6.3.1 Coalition Balance Ratio

$$CBR = \frac{|citations_{maggioranza}|}{|citations_{totali}|}$$

Target: $CBR \approx 0.5$ (bilanciamento perfetto)

#### 6.3.2 Party Coverage

$$Coverage = \frac{|parties\_cited|}{|parties\_total|}$$

Target: $Coverage = 1.0$ (tutti i 10 partiti rappresentati)

#### 6.3.3 Gini Coefficient per Citazioni

$$G = \frac{\sum_{i=1}^{n} \sum_{j=1}^{n} |c_i - c_j|}{2n \sum_{i=1}^{n} c_i}$$

dove $c_i$ è il numero di citazioni del partito $i$.

Target: $G \approx 0$ (distribuzione uniforme)

### 6.4 Metriche di Integrità Citazioni

#### 6.4.1 Exact Match Rate

$$EMR = \frac{|citations_{exact\_match}|}{|citations_{total}|}$$

Verifica che ogni citazione corrisponda esattamente al testo sorgente.

Target: $EMR = 1.0$ (100% exact match)

#### 6.4.2 Offset Verification Rate

Per ogni citazione, verifica che:
```python
testo_raw[span_start:span_end] == quote_text
```

Target: 100% di successo

#### 6.4.3 Source Traceability

Verifica che ogni citazione sia tracciabile fino a:
- Intervento originale
- Seduta parlamentare
- Data esatta
- Speaker identificato

### 6.5 Metriche di Qualità Generazione

#### 6.5.1 Faithfulness (Human Evaluation)

Valutazione umana su scala 1-5:
- 5: Perfettamente fedele alle fonti
- 4: Fedele con minime imprecisioni
- 3: Sostanzialmente corretto ma con omissioni
- 2: Parzialmente accurato
- 1: Significativamente inaccurato

#### 6.5.2 Coherence (Human Evaluation)

Valutazione della coerenza narrativa su scala 1-5.

#### 6.5.3 Completeness (Human Evaluation)

Valutazione della completezza rispetto alle evidenze disponibili.

#### 6.5.4 ROUGE-L (Automatic)

Per confronto con risposte di riferimento:
$$ROUGE-L = \frac{LCS(candidate, reference)}{|reference|}$$

### 6.6 Protocollo di Valutazione

#### 6.6.1 Dataset di Test

- **Dimensione**: 100 query su temi parlamentari diversificati
- **Copertura**: economia, sanità, ambiente, giustizia, immigrazione, etc.
- **Annotazioni**: documenti rilevanti, bilancio atteso, citazioni ground truth

#### 6.6.2 Valutazione Automatica

1. Eseguire tutte le query sul sistema
2. Calcolare metriche automatiche (retrieval, balance, citation integrity)
3. Confrontare con baseline (BM25, standard RAG senza bilanciamento)

#### 6.6.3 Valutazione Umana

- **Annotatori**: 3 valutatori esperti in politica italiana
- **Inter-annotator agreement**: Cohen's kappa ≥ 0.7
- **Metriche**: faithfulness, coherence, completeness

### 6.7 Baseline di Confronto

1. **BM25**: retrieval lessicale tradizionale
2. **Dense-only RAG**: solo canale vettoriale
3. **Unbalanced RAG**: senza vincoli di bilanciamento
4. **No-Authority RAG**: senza authority scoring

#### 6.7.1 Architettura della Baseline Interna

Per la valutazione A/B cieca, il sistema genera internamente una risposta baseline ad ogni query. La baseline utilizza le stesse evidenze recuperate dal retrieval ma con le seguenti differenze rispetto al sistema completo:

| Aspetto | Sistema Completo | Baseline |
|---------|-----------------|----------|
| Authority Scores | Variabili (0-1) | Uniformi (0.5) |
| Stage 1: Analyst | Sincrono | Asincrono con retry |
| Stage 2: Sectional Writer | Parallelo (`asyncio.gather`) | **Sequenziale** |
| Stage 3: Integrator | Con guard e repair | Semplice (senza guard) |
| Stage 4: Citation Surgeon | Risoluzione completa | **Omesso** |
| Topic Statistics | Passate all'integrator | Passate all'integrator |
| Citazioni finali | Citazioni verbatim risolte | Placeholder rimossi |

**Gestione dei Rate Limit**: La pipeline principale consuma circa 13 chiamate API OpenAI (1 Analyst + ~11 Sectional Writer in parallelo + 1 Integrator). Per evitare il superamento del rate limit di 60 RPM, la baseline adotta due strategie:

1. **Delay inter-pipeline**: un ritardo di 3 secondi tra la fine della generazione principale e l'inizio della baseline
2. **Sezioni sequenziali**: le 11 sezioni della baseline vengono generate una alla volta, anziché in parallelo, distribuendo le chiamate API nel tempo

**Retry con Backoff Esponenziale**: L'Analyst della baseline utilizza `AsyncOpenAI` con retry automatico (max 3 tentativi, backoff esponenziale con base 2s) per gestire errori transitori di rate limit (`RateLimitError`) e timeout (`APITimeoutError`).

**Pulizia del Testo**: Dopo la rimozione dei placeholder `[CIT:id]`, il testo viene ripulito da artefatti residui (spazi doppi, spazi prima della punteggiatura, righe vuote consecutive).

### 6.8 Test di Stress

#### 6.8.1 Query Adversariali

Query progettate per testare la robustezza:
- Query su temi controversiali (es. immigrazione)
- Query con bias implicito
- Query su temi con scarsa copertura

#### 6.8.2 Edge Cases

- Partiti con pochi interventi
- Argomenti nuovi (ultima legislatura)
- Query ambigue

---

## 7. Risultati e Discussione

*Questa sezione sarà completata dopo l'esecuzione degli esperimenti.*

### 7.1 Risultati Quantitativi

#### 7.1.1 Retrieval Performance

| Metrica | ParliamentRAG | Dense-only | BM25 |
|---------|---------------|------------|------|
| P@10    | TBD           | TBD        | TBD  |
| R@100   | TBD           | TBD        | TBD  |
| MRR     | TBD           | TBD        | TBD  |
| nDCG@10 | TBD           | TBD        | TBD  |

#### 7.1.2 Balance Metrics

| Metrica | ParliamentRAG | Unbalanced |
|---------|---------------|------------|
| CBR     | TBD           | TBD        |
| Coverage| TBD           | TBD        |
| Gini    | TBD           | TBD        |

#### 7.1.3 Citation Integrity

| Metrica | ParliamentRAG |
|---------|---------------|
| EMR     | 100% (by design) |
| OVR     | 100% (by design) |

### 7.2 Risultati Qualitativi

*Esempi di risposte generate con analisi qualitativa.*

### 7.3 Discussione

#### 7.3.1 Punti di Forza

- Garanzia di bilanciamento multi-vista
- Citazioni 100% verificabili
- Authority scoring query-dependent
- Configurabilità completa

#### 7.3.2 Limitazioni

- Dipendenza da API OpenAI (costi, latenza)
- Copertura limitata a legislature recenti
- Bias intrinseci nei modelli di embedding
- Complessità computazionale del compass

---

## 8. Conclusioni e Lavori Futuri

### 8.1 Contributi

Questa tesi ha presentato ParliamentRAG, un sistema RAG avanzato per l'analisi equilibrata dei dibattiti parlamentari italiani. I principali contributi sono:

1. **Architettura Dual-Channel**: combinazione innovativa di dense retrieval e graph traversal
2. **Authority Scoring Query-Dependent**: valutazione dinamica della credibilità degli speaker
3. **Offset-Based Citation Integrity**: garanzia di verificabilità al 100%
4. **Four-Stage Generation Pipeline**: trasparenza completa nel processo generativo
5. **Multi-View Balance Guarantee**: rappresentazione equilibrata di tutte le parti politiche

### 8.2 Limitazioni

1. **Scalabilità**: il sistema è ottimizzato per il parlamento italiano; l'estensione ad altri parlamenti richiederebbe adattamenti
2. **Copertura Temporale**: focus su legislature recenti; dati storici potrebbero richiedere preprocessing aggiuntivo
3. **Costi Computazionali**: l'uso di GPT-4o per la generazione comporta costi significativi
4. **Bias dei Modelli**: i modelli di embedding e generazione hanno bias intrinseci difficili da eliminare completamente

### 8.3 Lavori Futuri

#### 8.3.1 Estensioni Immediate

- Supporto multilingue (Parlamento Europeo)
- Integrazione con dati di voto
- Timeline tracking delle posizioni nel tempo

#### 8.3.2 Ricerca Futura

- Fine-tuning di modelli embedding domain-specific
- Sviluppo di metriche di bias più sofisticate
- Integrazione di fact-checking automatico
- Sistemi di spiegabilità per l'authority scoring

### 8.4 Impatto

ParliamentRAG rappresenta un passo verso una democrazia più informata, fornendo ai cittadini strumenti per accedere in modo equilibrato e verificabile all'informazione parlamentare.

---

## 9. Bibliografia

### Sistemi RAG e LLM

- Lewis, P., et al. (2020). "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." NeurIPS.
  [https://arxiv.org/abs/2005.11401](https://arxiv.org/abs/2005.11401)

- Karpukhin, V., et al. (2020). "Dense Passage Retrieval for Open-Domain Question Answering." EMNLP.
  [https://arxiv.org/abs/2004.04906](https://arxiv.org/abs/2004.04906)

- Gao, L., et al. (2023). "RARR: Researching and Revising What Language Models Say, Using Language Models." ACL.
  [https://arxiv.org/abs/2210.08726](https://arxiv.org/abs/2210.08726)

- Microsoft Research (2024). "GraphRAG: Graph-Based Retrieval-Augmented Generation."
  [https://arxiv.org/abs/2404.16130](https://arxiv.org/abs/2404.16130)

### Political Text Analysis

- Laver, M., Benoit, K., & Garry, J. (2003). "Extracting Policy Positions from Political Texts." APSR.

- Poole, K. T., & Rosenthal, H. (2007). "Ideology and Congress." Transaction Publishers.

- Rheault, L., & Cochrane, C. (2020). "Word Embeddings for the Analysis of Ideological Placement." Political Analysis.

### Information Retrieval e Bias

- Baeza-Yates, R. (2018). "Bias on the Web." Communications of the ACM.

- Shah, C., & Bender, E. M. (2022). "Situating Search." CHI.

### LLM e Bias Politico

- Santurkar, S., et al. (2023). "Whose Opinions Do Language Models Reflect?"
  [https://arxiv.org/abs/2303.17548](https://arxiv.org/abs/2303.17548)

- Feng, S., et al. (2023). "From Pretraining Data to Language Models to Downstream Tasks." ACL.
  [https://arxiv.org/abs/2305.08283](https://arxiv.org/abs/2305.08283)

### Embedding e Semantic Similarity

- Neelakantan, A., et al. (2022). "Text and Code Embeddings by Contrastive Pre-Training."
  [https://arxiv.org/abs/2201.10005](https://arxiv.org/abs/2201.10005)

- Muennighoff, N., et al. (2022). "MTEB: Massive Text Embedding Benchmark."
  [https://arxiv.org/abs/2210.07316](https://arxiv.org/abs/2210.07316)

### Thesaurus e Knowledge Organization

- EUROVOC Thesaurus. Publications Office of the European Union.
  [https://op.europa.eu/en/web/eu-vocabularies/th-dataset/-/resource/dataset/eurovoc](https://op.europa.eu/en/web/eu-vocabularies/th-dataset/-/resource/dataset/eurovoc)

- Gruber, T. R. (1993). "A Translation Approach to Portable Ontology Specifications." Knowledge Acquisition.

---

## Appendici

### Appendice A: Schema Completo Neo4j

```cypher
// Entità
(:Seduta {id, data, numero, legislatura})
(:Dibattito {id, titolo, tipo})
(:Fase {id, tipo, ordine})
(:Intervento {id, testo_raw, data_ora})
(:Chunk {id, text, embedding, span_start, span_end})
(:Deputato {id, nome, cognome, professione, istruzione,
            embedding_professione, embedding_istruzione})
(:MembroGoverno {id, nome, cognome, carica})
(:GruppoParlamentare {id, nome})
(:AttoParlamentare {id, titolo, eurovoc, embedding_titolo})
(:Commissione {id, nome, tipo})

// Relazioni
(Seduta)-[:HA_DIBATTITO]->(Dibattito)
(Dibattito)-[:HA_FASE]->(Fase)
(Fase)-[:CONTIENE_INTERVENTO]->(Intervento)
(Intervento)-[:HA_CHUNK]->(Chunk)
(Intervento)-[:PRONUNCIATO_DA]->(Deputato|MembroGoverno)
(Deputato)-[:MEMBRO_GRUPPO {dataInizio, dataFine}]->(GruppoParlamentare)
(Deputato)-[:FIRMATARIO]->(AttoParlamentare)
(Deputato)-[:MEMBRO_COMMISSIONE {dataInizio, dataFine}]->(Commissione)
```

### Appendice B: Configurazione Completa

Vedere file `config/default.yaml` per la configurazione completa del sistema.

### Appendice C: API Reference

#### POST /api/chat

```typescript
// Request
{
  "query": string,      // 3-4000 caratteri
  "mode": "standard" | "high_quality"
}

// Response (SSE stream)
// Event types: progress, evidence, citation, expert, compass, response
```

#### GET /api/evidence/{id}

```typescript
// Response
{
  "evidence_id": string,
  "doc_id": string,
  "speech_id": string,
  "speaker_id": string,
  "speaker_name": string,
  "speaker_role": "Deputato" | "MembroGoverno",
  "party": string,
  "coalition": "maggioranza" | "opposizione",
  "date": string,
  "chunk_text": string,
  "quote_text": string,
  "span_start": number,
  "span_end": number,
  "dibattito_titolo": string,
  "seduta_numero": number,
  "similarity": number,
  "authority_score": number,
  "ideology": {
    "left": number,
    "center": number,
    "right": number,
    "confidence": number,
    "method": "kde" | "mean_ellipse" | "insufficient_data"
  }
}
```

### Appendice D: Query di Test

Esempi di query utilizzate per la valutazione:

1. "Qual è la posizione dei partiti sulla riforma fiscale?"
2. "Come si sono espressi i deputati riguardo al salario minimo?"
3. "Quali interventi ci sono stati sul tema dell'autonomia differenziata?"
4. "Cosa pensano i vari gruppi parlamentari del PNRR?"
5. "Come è stato discusso il tema dell'immigrazione in parlamento?"

---

*Documento generato il: 2026-02-04*
*Versione: 1.0*
