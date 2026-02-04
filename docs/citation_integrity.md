# Citation Integrity

## Principio Fondamentale

Ogni citazione DEVE essere un'estrazione verbatim dal testo sorgente.

**NESSUNA parafrasi, NESSUN fuzzy matching, NESSUNA approssimazione.**

## Estrazione Offset-Based

### Motivazione

L'estrazione basata su offset è:
- **Deterministica**: Stesso input → stesso output
- **Verificabile**: Può essere riprodotta indipendentemente
- **Consistente**: Gestisce Unicode, whitespace, formattazione

### Implementazione

```python
def compute_quote_text(testo_raw: str, span_start: int, span_end: int) -> str:
    """
    Estrae citazione ESATTA usando offset da testo_raw.

    CRITICO: Questa è l'UNICA fonte valida per citazioni.
    NON usare chunk_text per verifica o confronto.
    """
    if span_start < 0:
        raise ValueError(f"span_start negativo: {span_start}")
    if span_end > len(testo_raw):
        raise ValueError(f"span_end ({span_end}) supera lunghezza testo ({len(testo_raw)})")
    if span_start >= span_end:
        raise ValueError(f"span non valido: {span_start} >= {span_end}")

    return testo_raw[span_start:span_end]
```

### Verifica

```python
def verify_citation_integrity(
    quote_text: str,
    testo_raw: str,
    span_start: int,
    span_end: int
) -> bool:
    """
    Verifica citazione tramite ri-estrazione dalla sorgente.

    NON confronta con chunk_text - sarebbe scorretto.
    Validità = offset validi + ri-estrazione identica.
    """
    try:
        re_extracted = testo_raw[span_start:span_end]
        return re_extracted == quote_text
    except (IndexError, ValueError):
        return False
```

## Perché NO Fuzzy Matching

### Problemi del Fuzzy Matching

1. **Ambiguità**: Potrebbero esistere più match vicini
2. **Soglia arbitraria**: 90% di similarità ammette 10% di errore
3. **Non-determinismo**: Risultati possono variare con l'algoritmo
4. **Auditabilità**: Impossibile riprodurre il processo esatto

### Problemi del Confronto con chunk_text

1. **Preprocessing**: `chunk_text` potrebbe essere stato pulito/normalizzato
2. **Divergenza**: `testo` vs `testo_raw` potrebbero differire
3. **Confusione sorgente**: La citazione deve riferire l'originale

## Schema Dati

### UnifiedEvidence

```python
class UnifiedEvidence(BaseModel):
    evidence_id: str           # chunk_id
    speech_id: str             # intervento_id

    # CAMPI TESTO - CHIARAMENTE DISTINTI
    chunk_text: str            # Per retrieval/preview SOLO
    quote_text: str            # VERBATIM da testo_raw[span_start:span_end]

    # Metadati offset per verifica
    span_start: int            # chunk.start_char_raw
    span_end: int              # chunk.end_char_raw
```

### Separazione chunk_text vs quote_text

| Campo | Uso | Fonte |
|-------|-----|-------|
| chunk_text | Preview retrieval | chunk.testo (potrebbe essere preprocessato) |
| quote_text | Citazione effettiva | intervento.testo_raw[start:end] |

## Tracciabilità Completa

### Catena di Evidenza

```
Query → Evidence ID → Chunk → Intervento → Seduta → Documento Sorgente
```

### Metadati Inclusi

- `evidence_id` (chunk_id)
- `speech_id` (intervento_id)
- `doc_id` (seduta_id)
- `speaker_id`, `speaker_name`, `party`, `coalition`
- `date`
- `span_start`, `span_end`
- `dibattito_titolo`

## Gestione Errori

| Situazione | Azione |
|------------|--------|
| Offset non validi | Log errore, escludi dai risultati |
| testo_raw mancante | Log errore, escludi dai risultati |
| Encoding issues | Normalizzazione UTF-8 |

## Audit Trail

Tutte le estrazioni di citazione sono loggabili con:
- Timestamp
- Query ID
- Evidence ID
- Successo/fallimento estrazione
- Eventuali messaggi di errore

## Test Obbligatori

```python
def test_basic_extraction(sample_testo_raw):
    quote = compute_quote_text(sample_testo_raw, 22, 36)
    assert quote == "Questo governo"

def test_verification_fails_on_mismatch(sample_testo_raw):
    wrong_quote = "Questo Governo"  # G maiuscola
    assert verify_citation_integrity(
        wrong_quote, sample_testo_raw, 22, 36
    ) == False

def test_invalid_span_raises_error(sample_testo_raw):
    with pytest.raises(ValueError):
        compute_quote_text(sample_testo_raw, -1, 10)
```

---

## Sistema di Integrità Citazioni a 5 Livelli

A partire dalla versione corrente, il sistema implementa un'architettura a **5 livelli** per garantire l'integrità assoluta delle citazioni.

### Livello 1: Citation Registry

Traccia ogni citazione attraverso tutta la pipeline di generazione.

```python
from backend.app.services.generation import CitationRegistry

registry = CitationRegistry()
registry.register_evidence(evidence_list)  # Registra tutte le evidenze

# Durante la scrittura sezionale
registry.bind_citation("evidence_id", "PARTITO", "Testo introduttivo...")

# Dopo l'integrazione
report = registry.verify_placeholders_in_text(integrated_text)

# Dopo il surgeon
registry.mark_resolved("evidence_id", success=True)

# Report finale
final = registry.get_final_report()
```

**Stati delle citazioni:**
- `REGISTERED`: Evidenza disponibile
- `BOUND`: Assegnata a una sezione di testo
- `IN_TEXT`: Placeholder trovato nel testo
- `RESOLVED`: Citazione formattata con successo
- `FAILED`: Impossibile risolvere
- `ORPHANED`: Placeholder perso durante l'integrazione

### Livello 2: Evidence-First Writer

Approccio alternativo che costruisce il testo **ATTORNO** alle citazioni.

```python
from backend.app.services.generation import EvidenceFirstWriter

writer = EvidenceFirstWriter()
section = await writer.write_section_evidence_first(
    query="Domanda utente",
    party="PARTITO",
    evidence=evidence_list
)
```

**Processo:**
1. Seleziona le evidenze migliori
2. Estrae la citazione esatta
3. Chiede al LLM di scrivere SOLO il testo introduttivo
4. Assembla: intro + `[CIT:id]`

**Garanzia:** La coerenza semantica è garantita *by construction*.

### Livello 3: Integrator Guard

Verifica pre/post integrazione per prevenire la perdita di citazioni.

```python
integrated = integrator.integrate_with_guard(query, sections, registry)

# Risultato include verifica
print(integrated["citation_verification"])
# {
#   "expected": 10,
#   "found": 10,
#   "missing_before_repair": [],
#   "repaired": 0
# }
```

Se l'integrator corrompe placeholder, il guard tenta la **riparazione automatica** appendendo le frasi contenenti le citazioni mancanti.

### Livello 4: Coherence Validator

Verifica la coerenza semantica tra testo introduttivo e citazione.

```python
from backend.app.services.generation import CoherenceValidator

validator = CoherenceValidator(min_coherence_score=0.2)

result = validator.validate_coherence(
    intro_text="Il deputato critica la gestione sanitaria",
    quote_text="il sistema sanitario è in crisi per mancanza di fondi"
)

print(result)
# {
#   "is_coherent": True,
#   "score": 0.35,
#   "overlap_keywords": ["sistema", "sanitario", "crisi"],
#   "sentiment_mismatch": False
# }
```

**Verifiche:**
- Overlap di keyword (Jaccard score)
- Rilevamento contraddizioni di sentiment (positivo vs negativo)
- Nessuna chiamata API (basato su keyword)

### Livello 5: Final Completeness Check

Verifica finale prima di restituire la risposta.

```python
# Nella pipeline
remaining_placeholders = re.findall(r'\[CIT:([^\]]+)\]', final_text)
if remaining_placeholders:
    # Errore critico: citazioni non risolte
    logger.error(f"UNRESOLVED: {remaining_placeholders}")

# Usa metodo esistente
unsupported_claims = surgeon.extract_unsupported_claims(final_text)
```

### Report di Integrità

Ogni risposta include un report completo:

```json
{
  "citation_integrity": {
    "is_complete": true,
    "success_rate": 1.0,
    "coherence_verified": true,
    "unsupported_claims_count": 0,
    "unresolved_placeholders": []
  }
}
```

### Configurazione

```yaml
citation:
  integrity:
    enable_registry: true
    min_coherence_score: 0.2
    integrator_guard: true
    strict_resolution: true
    include_report: true
    evidence_first_mode: false  # Modalità sperimentale
```
