# Ideological Compass

## Scopo e Limiti

### Utilizzo Previsto

Il compass ideologico è utilizzato per:
- Garantire **copertura multi-view** nel retrieval
- Etichettare prospettive per la generazione
- Bilanciare la rappresentazione di diverse posizioni politiche

### NON Utilizzato Per

- Scoprire ideologia "da zero" (no unsupervised discovery)
- Classificare definitivamente posizioni politiche
- Analisi politologica rigorosa

## Filosofia di Design

### Perché Semi-Supervisionato?

**Approcci puramente unsupervised** (es. PCA su embedding) rischiano di:
- Scoprire assi non interpretabili
- Produrre risultati instabili tra query
- Mancare di ground truth per validazione

**Approcci puramente supervised** richiedono:
- Dati etichettati che potrebbero non esistere
- Assunzioni ideologiche potenzialmente contestate

**Approccio semi-supervisionato**:
- Usa membership nei gruppi parlamentari come ancore SOFT
- I gruppi forniscono supervisione debole per posizionamento L/C/R
- Configurabilità per posizioni contestate (es. M5S)

## Ancore Configurabili

### Struttura

```yaml
compass:
  anchors:
    left:
      groups:
        - "ALLEANZA VERDI E SINISTRA"
        - "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA"
      confidence: 0.8

    center:
      groups:
        - "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE"
        - "ITALIA VIVA-IL CENTRO-RENEW EUROPE"
        - "NOI MODERATI..."
      confidence: 0.6

    right:
      groups:
        - "FRATELLI D'ITALIA"
        - "LEGA - SALVINI PREMIER"
        - "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE"
      confidence: 0.8

  ambiguous:
    "MOVIMENTO 5 STELLE":
      default_position: "left"
      confidence: 0.5
      note: "Posizione contestata - configurabile"

  unclassified:
    - "MISTO"
```

### Interpretazione della Confidence

- **0.8 (alta)**: Posizione ampiamente accettata (es. FdI a destra)
- **0.6 (media)**: Posizione ragionevole ma con sfumature (es. centro)
- **0.5 (bassa)**: Posizione contestata o ambigua (es. M5S)
- **0.3 (molto bassa)**: Gruppo eterogeneo (es. Misto)

## Metodo di Calcolo

### 1. Posizionamento Basato su Gruppo

```python
def score_evidence(evidence: Dict) -> IdeologyScore:
    party = evidence.get("party", "MISTO")
    position, confidence = anchor_manager.get_position_for_group(party)

    # Conversione a numerico: left=-1, center=0, right=1
    numeric_position = position_to_numeric(position)

    # Calcolo score multi-view con softmax
    scores = compute_multi_view_scores(numeric_position, confidence)

    return IdeologyScore(
        left=scores["left"],
        center=scores["center"],
        right=scores["right"],
        confidence=confidence
    )
```

### 2. Calcolo Score Multi-View

```python
def compute_multi_view_scores(position: float, confidence: float) -> Dict:
    # Distanza da ogni posizione anchor
    left_dist = abs(position - (-1.0))
    center_dist = abs(position - 0.0)
    right_dist = abs(position - 1.0)

    # Softmax-style scoring
    temperature = 0.5
    left_score = exp(-left_dist / temperature)
    center_score = exp(-center_dist / temperature)
    right_score = exp(-right_dist / temperature)

    # Normalizzazione
    total = left_score + center_score + right_score
    left_score /= total
    center_score /= total
    right_score /= total

    # Aggiustamento per confidence (bassa confidence → più uniforme)
    uniform = 1/3
    return {
        "left": confidence * left_score + (1 - confidence) * uniform,
        "center": confidence * center_score + (1 - confidence) * uniform,
        "right": confidence * right_score + (1 - confidence) * uniform,
    }
```

## Clustering

### ≥3 Frammenti: KDE

Kernel Density Estimation per trovare il picco della distribuzione.

```python
kde = gaussian_kde(positions, bw_method="scott")
peak_position = x[argmax(kde(x))]
```

### 1-2 Frammenti: Mean + Ellipse

Media pesata con confidenza ridotta.

### 0 Frammenti: Insufficient Data

Ritorna score uniforme con confidence = 0.

## Metriche di Copertura

```python
def compute_coverage_metrics(evidence_list) -> Dict:
    # Conteggio per posizione
    position_counts = {"left": 0, "center": 0, "right": 0}
    for e in evidence_list:
        position = get_position_for_group(e["party"])
        position_counts[position] += 1

    # Balance score: 1.0 = perfettamente bilanciato
    ideal = total / 3
    deviations = [abs(count - ideal) for count in position_counts.values()]
    balance_score = 1.0 - sum(deviations) / (2 * ideal * 3)

    return {
        "position_coverage": position_counts,
        "balance_score": balance_score,
        "missing_positions": [p for p, c in position_counts.items() if c == 0]
    }
```

## Limitazioni Note

1. **Semplificazione binaria**: Il continuum sinistra-destra semplifica il panorama politico italiano
2. **Ancore a livello di gruppo**: Non riflettono posizioni individuali di deputati
3. **Evoluzione temporale**: L'evoluzione delle posizioni di gruppo non è modellata
4. **Dimensioni multiple**: Non distingue EU vs politica nazionale
