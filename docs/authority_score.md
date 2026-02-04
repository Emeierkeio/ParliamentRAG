# Authority Score

## Definizione

L'Authority Score è una misura query-dependent della credibilità e competenza di uno speaker sul tema implicato dalla query.

```
AuthorityScore(speaker, query, date) ∈ [0, 1]
```

## Componenti

### 1. Professione (peso: 0.10)

Similarità semantica tra embedding della query e embedding della professione dello speaker.

```python
score = cosine_similarity(query_embedding, speaker.embedding_professione)
score = (score + 1) / 2  # Normalizza da [-1,1] a [0,1]
score = min(score, 0.8)  # Cap al 80%
```

**Razionale**: Gli esperti di dominio (es. avvocati su temi legali) dovrebbero avere peso maggiore.

### 2. Istruzione (peso: 0.10)

Analogo alla professione, usa `embedding_istruzione`.

### 3. Membership in Commissioni (peso: 0.20)

```python
score = Σ (temporal_validity × topic_relevance) / n_commissioni_attive
```

- **Validità temporale**: La membership deve essere attiva alla `reference_date`
- **Topic relevance**: Matching tra commissione e query via YAML mapping

### 4. Atti Parlamentari (peso: 0.25)

```python
score = log(1 + Σ time_decay(act.date)) / log(1 + max_expected)
```

**Time Decay Formula**:
```python
decay = exp(-λ × days_ago)
λ = ln(2) / half_life_days  # Default: 365 giorni
```

### 5. Interventi (peso: 0.30)

Analogo agli atti, con `half_life_days = 180`.

### 6. Ruolo Istituzionale (peso: 0.05)

Pesi predefiniti per ruoli:
- Presidente della Camera: 1.0
- Ministro: 0.9
- Vicepresidente Camera: 0.8
- Capogruppo: 0.6
- Deputato base: 0.3

## Logica Temporale Coalizioni

### Regola Fondamentale

Quando un deputato attraversa il confine MAGGIORANZA ↔ OPPOSIZIONE, l'autorità accumulata nella coalizione precedente viene invalidata.

### Implementazione

```python
def authority_carries_over(old_group: str, new_group: str) -> bool:
    old_coalition = get_coalition(old_group)  # "maggioranza" o "opposizione"
    new_coalition = get_coalition(new_group)
    return old_coalition == new_coalition
```

### Esempio

Deputato X passa da PD (opposizione) a FdI (maggioranza) il 2024-01-15.

Per una query con `reference_date = 2024-06-01`:
- Interventi **prima** del 2024-01-15: **ESCLUSI** (coalizione diversa)
- Interventi **dopo** il 2024-01-16: **INCLUSI** (stessa coalizione)

### Test Case Obbligatorio

```python
def test_coalition_crossing_invalidates_authority():
    logic = CoalitionLogic()

    # Opposizione → Maggioranza = NO carry-over
    assert logic.authority_carries_over(
        "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
        "FRATELLI D'ITALIA"
    ) == False

    # Stessa coalizione = carry-over
    assert logic.authority_carries_over(
        "FRATELLI D'ITALIA",
        "LEGA - SALVINI PREMIER"
    ) == True
```

## Normalizzazione

Normalizzazione percentile-based per prevenire il dominio di deputati iper-attivi.

```python
def normalize_percentile(scores: Dict[str, float]) -> Dict[str, float]:
    sorted_values = sorted(scores.values())
    return {
        speaker_id: sorted_values.index(score) / (len(sorted_values) - 1)
        for speaker_id, score in scores.items()
    }
```

## Limitazioni Note

1. **Dati mancanti**: `embedding_professione` ha ~14% di valori nulli
2. **Topic mapping manuale**: Le commissioni sono mappate manualmente a topic in YAML
3. **Confini coalizioni binari**: Non esistono sfumature per "opposizione costruttiva"

## Configurazione

```yaml
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
  max_component_contribution: 0.8
```
