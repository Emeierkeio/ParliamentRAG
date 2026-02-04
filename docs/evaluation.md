# Framework di Valutazione

## Metriche di Retrieval

### Recall@k

Proporzione di documenti rilevanti recuperati nei top-k risultati.

```
Recall@k = |Relevant ∩ Retrieved_k| / |Relevant|
```

Valori di k: 10, 50, 100

**Requisito**: Giudizi di rilevanza (annotazione manuale o proxy).

### nDCG@k (Normalized Discounted Cumulative Gain)

Tiene conto della qualità del ranking, non solo della presenza.

```
DCG@k = Σ (2^rel_i - 1) / log2(i + 1)
nDCG@k = DCG@k / IDCG@k
```

### MRR (Mean Reciprocal Rank)

Posizione del primo risultato rilevante.

```
MRR = (1/|Q|) × Σ (1/rank_i)
```

### Party Coverage

Percentuale di gruppi parlamentari con ≥1 chunk rilevante nei risultati.

**Target**: 100% (tutti i 10 gruppi rappresentati quando esiste evidenza)

### Ideology Coverage

Bilanciamento delle prospettive left/center/right nei risultati.

## Metriche di Attribuzione

### Quote Exactness

Verifica che la citazione estratta corrisponda esattamente alla sorgente.

```python
def quote_exactness(evidence: Evidence, testo_raw: str) -> bool:
    extracted = testo_raw[evidence.span_start:evidence.span_end]
    return extracted == evidence.quote_text
```

**Target**: 100% (requisito obbligatorio)

### Claim Support Rate

Percentuale di claim generati supportati da evidenza valida.

```
CSR = |Claims with Valid Evidence| / |Total Claims|
```

### Citation Precision

Percentuale di citazioni che supportano correttamente i claim associati.

## Studio di Ablazione Authority

### Configurazioni

1. **Baseline**: Solo retrieval (no authority weighting)
2. **+Authority**: Retrieval con ranking pesato per authority
3. **+Authority+Compass**: Sistema completo con copertura ideologica

### Metriche per Configurazione

| Configurazione | Retrieval (Recall, nDCG) | Generation (Faithfulness) | Coverage |
|----------------|--------------------------|---------------------------|----------|
| Baseline | ✓ | ✓ | ✗ |
| +Authority | ✓ | ✓ | Parziale |
| +Authority+Compass | ✓ | ✓ | ✓ |

### Ipotesi

- +Authority migliora la qualità delle citazioni (speaker più autorevoli)
- +Compass migliora la copertura multi-view

## Metriche di Generazione

### Per-Party Completeness

Tutti i 10 gruppi hanno una sezione (anche se con messaggio "no evidence").

**Verifica**:
```python
def check_completeness(response: str, all_parties: List[str]) -> bool:
    return all(party in response for party in all_parties)
```

### Faithfulness

Nessun claim senza evidenza di supporto.

**Implementazione**: Cross-reference claim con bundle evidenze.

## Riproducibilità

### Requisiti

1. **Seed fissi**: Per componenti stocastici
2. **Retrieval deterministico**: Stessa query → stessi risultati
3. **Configurazioni loggate**: Versioning dei parametri
4. **Dataset versionati**: Checkpoint del corpus

### Artefatti

```
results/
├── retrieval_metrics.json
├── attribution_metrics.json
├── ablation_study.json
└── plots/
    ├── recall_by_k.png
    ├── party_coverage.png
    └── authority_ablation.png
```

## Procedura di Valutazione

### 1. Preparazione Dataset

```python
evaluation_queries = [
    {"query": "immigrazione", "expected_parties": ["FDI", "PD", "LEGA", ...]},
    {"query": "manovra economica", "expected_parties": [...]},
    # ...
]
```

### 2. Esecuzione

```bash
python scripts/run_evaluation.py \
    --queries evaluation_queries.json \
    --output results/ \
    --configurations baseline,authority,full
```

### 3. Analisi

- Confronto metriche tra configurazioni
- Analisi errori (citazioni fallite, partiti mancanti)
- Visualizzazioni per documentazione tesi

## Limitazioni

1. **Ground truth**: I giudizi di rilevanza potrebbero essere soggettivi
2. **Copertura temporale**: Il corpus copre un periodo specifico
3. **Bias di selezione**: Le query di test potrebbero non essere rappresentative
4. **Scalabilità**: Valutazione manuale non scala a grandi volumi
