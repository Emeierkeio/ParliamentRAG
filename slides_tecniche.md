---
marp: true
theme: default
paginate: true
backgroundColor: #fff
math: mathjax
style: |
  section { font-family: 'Segoe UI', sans-serif; font-size: 24px; }
  h1 { color: #1a365d; font-size: 36px; }
  h2 { color: #2c5282; font-size: 28px; }
  h3 { color: #4a5568; font-size: 22px; }
  table { font-size: 18px; }
  pre { font-size: 14px; }
  code { font-size: 14px; }
  .columns { display: flex; gap: 20px; }
  .column { flex: 1; }
---

# ParliamentRAG

### Sistema RAG Multi-Vista per l'Analisi Equilibrata dei Dibattiti Parlamentari

**Tesi di Laurea Magistrale in Data Science**

Candidato: Mirko Tritella
Relatore: [Nome Relatore]

---

# Agenda

1. **Problema e Obiettivi** - Gap nei sistemi esistenti
2. **Architettura del Sistema** - Componenti e flusso dati
3. **Dual-Channel Retrieval** - Dense + Graph retrieval
4. **Authority Scoring** - Valutazione competenza query-dependent
5. **Generation Pipeline** - Architettura Citation-First a 4 stadi
6. **Sistema di Integrità** - 5 livelli di verifica citazioni
7. **Stack Tecnologico** - Scelte implementative
8. **Valutazione e Metriche** - Framework sperimentale
9. **Conclusioni** - Contributi e limitazioni

---

# 1. Problema: Bias nei Sistemi di Ricerca Parlamentare

## Limitazioni dei sistemi esistenti

| Sistema | Retrieval | Bilanciamento | Citazioni Verificabili |
|---------|-----------|---------------|------------------------|
| OpenParlamento | Keyword (BM25) | Nessuno | No |
| They Vote For You | Voting records | Parziale | N/A |
| GovTrack | Full-text search | Nessuno | No |
| **ParliamentRAG** | **Dual-channel** | **Multi-vista** | **100% by design** |

## Obiettivi formali

1. **Multi-View Coverage**: $\forall p \in Parties : \exists c \in Citations : party(c) = p$
2. **Citation Integrity**: $\forall c \in Citations : c.text = source[c.start:c.end]$
3. **Authority-Weighted Ranking**: $score(d) = f(relevance, authority_{query})$

---

# 2. Architettura: Overview

```
                          Query: "Posizione partiti su sanità"
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │   Embedding  │   │    Dense     │   │    Graph     │
            │  Generation  │   │   Channel    │   │   Channel    │
            │ (1536-dim)   │   │  (Vector)    │   │  (Eurovoc)   │
            └──────────────┘   └──────────────┘   └──────────────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        ▼
                              ┌──────────────────┐
                              │  Channel Merger  │
                              │  + Authority     │
                              │  Scoring         │
                              └──────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │   Analyst    │   │  Sectional   │   │  Integrator  │
            │   (Stage 1)  │──▶│  (Stage 2)   │──▶│  (Stage 3)   │
            └──────────────┘   └──────────────┘   └──────────────┘
                                                          │
                                                          ▼
                                                 ┌──────────────┐
                                                 │   Surgeon    │
                                                 │  (Stage 4)   │
                                                 └──────────────┘
```

---

# 3. Data Model: Knowledge Graph Parlamentare

## Schema Neo4j

```cypher
(:Seduta {data, numero, legislatura})
  -[:HA_DIBATTITO]-> (:Dibattito {titolo, tipo})
    -[:HA_FASE]-> (:Fase {tipo, ordine})
      -[:CONTIENE_INTERVENTO]-> (:Intervento {testo_raw, data_ora})
        -[:HA_CHUNK]-> (:Chunk {text, embedding[1536], span_start, span_end})

(:Intervento)-[:PRONUNCIATO_DA]->(:Deputato {professione, istruzione,
                                              embedding_professione[1536]})
(:Deputato)-[:MEMBRO_GRUPPO {dataInizio, dataFine}]->(:GruppoParlamentare)
(:Deputato)-[:FIRMATARIO]->(:AttoParlamentare {eurovoc[], embedding_titolo[1536]})
(:Deputato)-[:MEMBRO_COMMISSIONE {dataInizio, dataFine}]->(:Commissione)
```

## Indice Vettoriale

```cypher
CREATE VECTOR INDEX chunk_embedding_index
FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
```

---

# 4. Dual-Channel Retrieval

## Dense Channel (Semantic Similarity)

$$sim(q, c) = \frac{E(q) \cdot E(c)}{||E(q)|| \cdot ||E(c)||}$$

dove $E(\cdot)$ = `text-embedding-3-small` (OpenAI, 1536 dim)

**Query Cypher:**
```cypher
CALL db.index.vector.queryNodes('chunk_embedding_index', 200, $query_emb)
YIELD node AS c, score
WHERE score >= 0.3
MATCH (c)<-[:HA_CHUNK]-(i:Intervento)-[:PRONUNCIATO_DA]->(speaker)
OPTIONAL MATCH (speaker)-[mg:MEMBRO_GRUPPO]->(g:GruppoParlamentare)
WHERE mg.dataInizio <= s.data AND (mg.dataFine IS NULL OR mg.dataFine >= s.data)
RETURN c, speaker, g, score
```

---

# 4. Dual-Channel Retrieval (cont.)

## Graph Channel (Structural Retrieval)

**Strategia ibrida Eurovoc:**

1. **Matching lessicale**: keyword → atti parlamentari (campo `eurovoc[]`)
2. **Reranking semantico**: $sim(query_{emb}, atto_{emb})$ su `embedding_titolo`
3. **Graph traversal**: atto → firmatari → interventi recenti

```
Query: "riforma fiscale"
   │
   ▼
Atti con eurovoc ∈ {fiscalità, tasse, imposte, ...}
   │
   ▼
Firmatari (Deputati)
   │
   ▼
Interventi degli ultimi 2 anni
   │
   ▼
Chunks con similarity ≥ threshold
```

---

# 5. Channel Merger: Fusione Multi-Obiettivo

## Formula di scoring

$$score_{final}(c) = w_r \cdot relevance(c) + w_d \cdot diversity(c) + w_c \cdot coverage(c) + w_a \cdot authority(c)$$

| Componente | Peso | Descrizione |
|------------|------|-------------|
| $relevance$ | 0.2 | Cosine similarity normalizzata |
| $diversity$ | 0.2 | Penalità se speaker già rappresentato ($>\frac{top\_k}{10}$) |
| $coverage$ | 0.3 | Bonus se partito sotto-rappresentato ($<\frac{top\_k}{30}$) |
| $authority$ | 0.3 | Authority score query-dependent |

## Vincoli hard

- **Max per speaker**: $|citations_{speaker}| \leq 20$
- **Max per partito**: $\frac{|citations_{party}|}{|citations_{total}|} \leq 0.33$

---

# 6. Authority Scoring: Competenza Query-Dependent

## Componenti dello score

$$authority(s, q) = \sum_{i=1}^{6} w_i \cdot component_i(s, q)$$

| Componente | Peso | Calcolo |
|------------|------|---------|
| Professione | 0.10 | $cos(E_{query}, E_{professione})$ |
| Istruzione | 0.10 | $cos(E_{query}, E_{istruzione})$ |
| Commissioni | 0.20 | $\mathbb{1}[commissione \in topic\_match(query)]$ |
| Atti firmati | 0.25 | $\sum_a e^{-\lambda_{acts} \cdot days\_old(a)}$ |
| Interventi | 0.30 | $\sum_i e^{-\lambda_{speeches} \cdot days\_old(i)}$ |
| Ruolo | 0.05 | $role\_weight(presidente > ministro > deputato)$ |

## Time decay

$$\lambda_{acts} = \frac{\ln(2)}{365}, \quad \lambda_{speeches} = \frac{\ln(2)}{180}$$

---

# 6. Authority Scoring: Coalition Logic

## Regola del cambio schieramento

> Quando un deputato attraversa il confine **MAGGIORANZA ↔ OPPOSIZIONE**, l'autorità accumulata viene invalidata.

```python
def authority_carries_over(old_group: str, new_group: str) -> bool:
    old_coalition = COALITIONS[old_group]  # "maggioranza" | "opposizione"
    new_coalition = COALITIONS[new_group]
    return old_coalition == new_coalition  # True solo se stesso schieramento
```

## Razionale

Un deputato che passa da opposizione a maggioranza non può portare con sé la "credibilità" accumulata criticando il governo.

**Esempio**: Italia Viva → FdI = reset authority

---

# 7. Generation Pipeline: Architettura a 4 Stadi

## Design Principles

1. **Separation of Concerns**: ogni stadio ha responsabilità specifiche
2. **Verificabilità**: output intermedi ispezionabili
3. **Determinismo Stage 4**: citazioni estratte per offset (zero fuzzy matching)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Stage 1   │     │   Stage 2   │     │   Stage 3   │     │   Stage 4   │
│   Analyst   │────▶│  Sectional  │────▶│ Integrator  │────▶│   Surgeon   │
│   (LLM)     │     │   (LLM)     │     │   (LLM)     │     │   (Code)    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
     │                    │                   │                    │
     ▼                    ▼                   ▼                    ▼
  Claims            10 sezioni          Testo integrato      Citazioni
  decomposition     per-party           con [CIT:id]         formattate
```

---

# 7.1 Stage 1: Claim Analyst

## Input/Output

- **Input**: Query + Evidence list
- **Output**: Structured claim decomposition (JSON)

```json
{
  "claims": [
    {"id": "C1", "text": "Finanziamento SSN", "parties_expected": ["FDI", "PD", ...]},
    {"id": "C2", "text": "Liste d'attesa", "parties_expected": ["M5S", "LEGA", ...]}
  ],
  "query_type": "policy",
  "requires_government": true
}
```

## Prompt engineering

- Temperature: 0.3 (bassa variabilità)
- Explicit instruction: considerare tutti i 10 gruppi parlamentari

---

# 7.2 Stage 2: Sectional Writer (Citation-First)

## Problema del Text-First approach

```
PROBLEMA:
1. LLM scrive: "Rossi denuncia la crisi, affermando che [CIT:xxx]"
2. Surgeon inserisce: "il decreto è insufficiente"
3. RISULTATO: Intro parla di "crisi", citazione di "decreto" ❌
```

## Soluzione: Citation-First

```python
def _build_evidence_context(self, evidence, query):
    for e in evidence:
        # PRE-EXTRACT citation BEFORE LLM writes
        extracted = extract_best_sentences(
            text=e["quote_text"],
            query=query,
            max_sentences=1,
            max_chars=150
        )
        e["pre_extracted_citation"] = extracted

        # LLM sees the EXACT citation
        context += f"★ CITAZIONE DA USARE: «{extracted}»\n"
```

**Coerenza by construction**: LLM conosce la citazione prima di scrivere.

---

# 7.2 Stage 2: Prompt Structure

## Evidence context (per l'LLM)

```
[ID: leg19_sed531_int00190_chunk_4]
Speaker: Marco Rossi
Date: 2024-01-15
★ CITAZIONE DA USARE: «il sistema sanitario nazionale sta attraversando una crisi profonda»
Contesto: Signor Presidente, il sistema sanitario nazionale sta attraversando...
---
```

## Istruzione

```
⚠️ ISTRUZIONI CITATION-FIRST:
1. LEGGI la ★ CITAZIONE DA USARE per ogni evidenza
2. Scrivi il testo introduttivo che si colleghi A QUELLA FRASE ESATTA
3. Usa [CIT:ID_COMPLETO] dove inserire la citazione
4. Bridge verbale obbligatorio: "affermando che", "sottolineando come"
```

---

# 7.3 Stage 3: Narrative Integrator

## Responsabilità

| Permesso | Proibito |
|----------|----------|
| Frasi di transizione | Fondere posizioni di partiti diversi |
| Correzioni grammaticali | Eliminare placeholder [CIT:...] |
| Riordino sezioni | Inventare contenuti |
| Raggruppamento per coalizione | Modificare citazioni |

## Guard mechanism

```python
def integrate_with_guard(query, sections, registry):
    expected = extract_all_citations(sections)  # Pre-integration
    result = integrate(query, sections)
    found = extract_all_citations(result.text)  # Post-integration

    missing = expected - found
    if missing:
        result = retry_with_stricter_prompt(missing, sections)

    return result
```

---

# 7.4 Stage 4: Citation Surgeon

## Algoritmo deterministico

```python
def insert_citations(text, evidence_map, query):
    for match in re.findall(r'\[CIT:([^\]]+)\]', text):
        evidence = evidence_map[match]

        # CITATION-FIRST: use pre-extracted citation if available
        if "pre_extracted_citation" in evidence:
            quote = evidence["pre_extracted_citation"]
        else:
            # Fallback: extract from testo_raw using offsets
            quote = evidence["testo_raw"][evidence["span_start"]:evidence["span_end"]]

        formatted = f'[«{quote}»]({match})'
        text = text.replace(f'[CIT:{match}]', formatted)

    return text
```

## Garanzia di integrità

$quote = testo\_raw[span\_start:span\_end]$ → **Zero fuzzy matching**

---

# 8. Sistema di Integrità: 5 Livelli

```
┌─────────────────────────────────────────────────────────────────┐
│ Livello 1: Citation Registry                                    │
│ Traccia stati: REGISTERED → BOUND → IN_TEXT → RESOLVED/FAILED  │
├─────────────────────────────────────────────────────────────────┤
│ Livello 2: Citation-First Writer                                │
│ LLM vede citazione PRIMA di scrivere → coerenza by design      │
├─────────────────────────────────────────────────────────────────┤
│ Livello 3: Integrator Guard                                     │
│ Verifica pre/post: expected - found = missing → retry           │
├─────────────────────────────────────────────────────────────────┤
│ Livello 4: Coherence Validator                                  │
│ Keyword overlap + sentiment detection (no API calls)            │
├─────────────────────────────────────────────────────────────────┤
│ Livello 5: Final Completeness Check                             │
│ Placeholder non risolti + unsupported claims detection          │
└─────────────────────────────────────────────────────────────────┘
```

---

# 8.1 Citation Registry

## Stati delle citazioni

```python
class CitationState(Enum):
    REGISTERED = "registered"    # Evidenza disponibile
    BOUND = "bound"              # Assegnata a sezione
    IN_TEXT = "in_text"          # Placeholder trovato nel testo
    RESOLVED = "resolved"        # Formattata con successo
    FAILED = "failed"            # Errore risoluzione
    ORPHANED = "orphaned"        # Persa durante integrazione
```

## Report finale

```json
{
  "citation_integrity": {
    "is_complete": true,
    "success_rate": 1.0,
    "resolved": 12, "failed": 0, "orphaned": 0
  }
}
```

---

# 8.2 Coherence Validator

## Validazione senza API calls

```python
def validate_coherence(intro: str, quote: str) -> CoherenceResult:
    # Keyword overlap
    intro_tokens = tokenize(intro) - STOP_WORDS
    quote_tokens = tokenize(quote) - STOP_WORDS
    overlap = len(intro_tokens & quote_tokens) / len(intro_tokens)

    # Sentiment detection
    positive = {"sostiene", "difende", "elogia", "approva", ...}
    negative = {"critica", "denuncia", "contesta", "respinge", ...}

    intro_sentiment = detect_sentiment(intro, positive, negative)
    quote_sentiment = detect_sentiment(quote, positive, negative)

    mismatch = (intro_sentiment == "positive" and quote_sentiment == "negative") or \
               (intro_sentiment == "negative" and quote_sentiment == "positive")

    return CoherenceResult(score=overlap, mismatch=mismatch)
```

---

# 9. Sentence Extractor

## Algoritmo di estrazione semantica

**Obiettivo**: selezionare la frase più rilevante per la query (max 150 char)

```python
def extract_best_sentences(text, query, max_sentences=1, max_chars=150):
    sentences = split_sentences(text)  # Gestisce frasi lunghe parlamentari
    query_tokens = tokenize(query) - STOP_WORDS

    scored = []
    for i, sent in enumerate(sentences):
        sent_tokens = tokenize(sent) - STOP_WORDS
        overlap = len(query_tokens & set(sent_tokens))

        overlap_score = overlap / len(query_tokens)
        position_bonus = 0.1 / (i + 1)  # Frasi iniziali preferite
        density = overlap / len(sent_tokens) if sent_tokens else 0

        total = overlap_score * 0.6 + density * 0.3 + position_bonus * 0.1
        scored.append((sent, total, i))

    # Select top by score, maintain original order
    selected = sorted(scored, key=lambda x: x[1], reverse=True)[:max_sentences]
    return " ".join(s for s, _, _ in sorted(selected, key=lambda x: x[2]))
```

---

# 10. Stack Tecnologico

## Backend

| Componente | Tecnologia | Motivazione |
|------------|------------|-------------|
| Framework | FastAPI 0.109+ | Async native, auto OpenAPI docs |
| LLM | OpenAI GPT-4o | SOTA reasoning, function calling |
| Embedding | text-embedding-3-small | 1536 dim, MTEB 62.3% |
| Database | Neo4j 5.15 | Native graph + vector index |

## Frontend

| Componente | Tecnologia | Motivazione |
|------------|------------|-------------|
| Framework | Next.js 16.1 | App Router, React 19, SSR |
| Styling | Tailwind CSS 4.0 | Utility-first |
| Components | shadcn/ui + Radix | Accessible, composable |
| Streaming | SSE (Server-Sent Events) | Real-time feedback |

---

# 11. Metriche di Valutazione

## Retrieval Quality

| Metrica | Formula | Target |
|---------|---------|--------|
| Precision@k | $\frac{\|relevant \cap retrieved@k\|}{k}$ | ≥ 0.7 |
| Recall@k | $\frac{\|relevant \cap retrieved@k\|}{\|relevant\|}$ | ≥ 0.8 |
| nDCG@k | $\frac{DCG@k}{IDCG@k}$ | ≥ 0.75 |

## Balance Metrics

| Metrica | Formula | Target |
|---------|---------|--------|
| Coalition Balance | $\frac{\|cit_{maggioranza}\|}{\|cit_{total}\|}$ | ≈ 0.5 |
| Party Coverage | $\frac{\|parties\_cited\|}{10}$ | = 1.0 |
| Gini Coefficient | $\frac{\sum\sum\|c_i - c_j\|}{2n\sum c_i}$ | ≈ 0 |

## Citation Integrity

| Metrica | Target |
|---------|--------|
| Exact Match Rate | **100%** (by design) |
| Coherence Score | ≥ 0.2 |

---

# 12. Baseline di Confronto

## Ablation Study Design

| Configurazione | Dense | Graph | Authority | Balance | Citation-First |
|----------------|-------|-------|-----------|---------|----------------|
| BM25 | ✗ | ✗ | ✗ | ✗ | ✗ |
| Dense-only | ✓ | ✗ | ✗ | ✗ | ✗ |
| Dual-channel | ✓ | ✓ | ✗ | ✗ | ✗ |
| + Authority | ✓ | ✓ | ✓ | ✗ | ✗ |
| + Balance | ✓ | ✓ | ✓ | ✓ | ✗ |
| **ParliamentRAG** | ✓ | ✓ | ✓ | ✓ | ✓ |

## Metriche per ablation

Per ogni configurazione misurare:
- Retrieval: P@10, R@100, nDCG@10
- Balance: CBR, Coverage, Gini
- Generation: Faithfulness (human), Coherence (human)

---

# 13. Limitazioni

| Limitazione | Impatto | Mitigazione |
|-------------|---------|-------------|
| Solo parlamento IT | Non generalizzabile | Design modulare |
| 14% deputati senza professione | Authority incompleto | Fallback a media |
| Costi API (~€0.10/query) | Sostenibilità | Cache, batching |
| Latenza 4 LLM calls (~10s) | UX | Streaming SSE |
| Coalizioni semplificate | Perde sfumature | Configurabile |

## Bias intrinseci

- **Embedding bias**: text-embedding-3 ha bias documentati
- **Generation bias**: GPT-4o tende a posizioni moderate
- **Mitigazione**: vincoli espliciti di bilanciamento nella pipeline

---

# 14. Contributi Originali

1. **Dual-Channel Retrieval Architecture**
   - Combinazione dense + graph per massimizzare recall su dati strutturati

2. **Coalition-Aware Authority Scoring**
   - Time decay + reset al cambio coalizione

3. **Citation-First Generation**
   - Pre-estrazione citazione → LLM scrive attorno → coerenza by design

4. **Offset-Based Citation Integrity**
   - $quote = text[start:end]$ → 100% exact match garantito

5. **5-Level Integrity System**
   - Registry + Citation-First + Guard + Validator + Final Check

---

# 15. Conclusioni

## Risultati chiave

- **Multi-View Coverage**: tutti i 10 partiti rappresentati
- **Citation Integrity**: 100% verificabile by design
- **Authority Scoring**: esperti emergono automaticamente
- **Trasparenza**: ogni stadio ispezionabile

## Impatto

Sistema che permette accesso **equilibrato** e **verificabile** all'informazione parlamentare per cittadini, giornalisti e ricercatori.

## Lavori futuri

- Supporto multilingue (Parlamento Europeo)
- Fine-tuning embedding domain-specific
- Timeline tracking posizioni nel tempo

---

# Grazie

## Domande?

**Repository**: github.com/Emeierkeio/thesis-ParliamentRAG

### Riferimenti chiave

- Lewis et al. (2020) - *Retrieval-Augmented Generation* [arXiv:2005.11401]
- Karpukhin et al. (2020) - *Dense Passage Retrieval* [arXiv:2004.04906]
- Microsoft (2024) - *GraphRAG* [arXiv:2404.16130]
- Gao et al. (2023) - *RARR: Retrofit Attribution* [arXiv:2210.08726]

