# Sistema di Retrieval

## Architettura Dual-Channel

Il sistema di retrieval implementa un approccio a doppio canale per bilanciare rilevanza semantica e sfruttamento dei metadati parlamentari.

## Dense Channel

### Implementazione

Ricerca vettoriale sull'indice `chunk_embedding_index` di Neo4j:

```cypher
CALL db.index.vector.queryNodes('chunk_embedding_index', $top_k, $query_embedding)
YIELD node AS c, score
MATCH (c)<-[:HAS_CHUNK]-(i:Speech)-[:SPOKEN_BY]->(speaker)
MATCH (i)<-[:CONTAINS_SPEECH]-(f:Phase)<-[:HAS_PHASE]-(d:Debate)<-[:HAS_DEBATE]-(s:Session)
RETURN c, i, speaker, s, score
```

**Nota critica**: La chiamata `db.index.vector.queryNodes` deve essere la prima operazione della query. Un `MATCH` preliminare invaliderebbe l'uso dell'indice vettoriale.

### Parametri

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| top_k | 200 | Numero di risultati |
| similarity_threshold | 0.3 | Soglia minima similarità |

### Punti di Forza

- Cattura similarità semantica
- Gestisce parafrasi e variazioni linguistiche
- Indipendente dalla lingua

### Limitazioni

- Non sfrutta direttamente i metadati strutturali
- Può recuperare contenuto semanticamente simile ma contestualmente irrilevante

## Graph Channel

### Strategia Ibrida Eurovoc

Il canale grafo implementa un matching ibrido (lessicale + semantico):

**Fase 1 - Matching Lessicale**:
```cypher
MATCH (a:ParliamentaryAct)
WHERE a.eurovoc CONTAINS $keyword
   OR toLower(a.title) CONTAINS toLower($keyword)
RETURN a
```

**Fase 2 - Rerank Semantico**:
Calcolo similarità coseno tra query embedding e `a.title_embedding`.

**Fase 3 - Traversal**:
```cypher
MATCH (d:Deputy)-[:PRIMARY_SIGNATORY|CO_SIGNATORY]->(a:ParliamentaryAct)
WHERE a.uri IN $relevant_act_uris
MATCH (i:Speech)-[:SPOKEN_BY]->(d)
MATCH (i)-[:HAS_CHUNK]->(c:Chunk)
RETURN c, i, d
```

### Motivazione dell'Approccio Ibrido

Non esiste un indice vettoriale su `ParliamentaryAct`. Creare un nuovo indice richiederebbe modifiche allo schema. L'approccio ibrido:
- Sfrutta i campi testuali esistenti (lexical)
- Utilizza embedding pre-calcolati per reranking (semantic)
- Non richiede modifiche al database

## Channel Merger

### Formula di Fusione

```
final_score = w_rel × relevance + w_div × diversity + w_cov × coverage + w_auth × authority
```

Pesi di default:
- relevance_weight: 0.2
- diversity_weight: 0.2
- coverage_weight: 0.3
- authority_weight: 0.3

### Deduplicazione

I risultati vengono deduplicati per `evidence_id`, mantenendo il punteggio più alto.

### Selezione Diversificata

Algoritmo greedy che bilancia score con diversità:
- Limite per speaker: `top_k / 10`
- Limite per partito: `top_k / 3` (soft - superabile con score > 0.8)

## Metriche di Valutazione

| Metrica | Descrizione |
|---------|-------------|
| Recall@k | Proporzione di documenti rilevanti nei top-k |
| nDCG@k | Qualità del ranking |
| Party Coverage | % di partiti con ≥1 chunk rilevante |
| Ideology Coverage | Bilanciamento L/C/R |

## Configurazione

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
```
