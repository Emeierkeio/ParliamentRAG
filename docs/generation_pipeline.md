# Generation Pipeline

## Pattern "Surgeon" a 4 Stadi

### Motivazione

La generazione RAG tradizionale presenta rischi:
- **Hallucination delle citazioni**: Il modello può "inventare" citazioni
- **Fusione delle posizioni**: Diverse prospettive vengono sintetizzate
- **Copertura incompleta**: Alcuni partiti vengono omessi
- **Parafrasi non fedeli**: Le citazioni vengono riformulate

Il pattern "Surgeon" affronta questi rischi attraverso stadi separati con verifica esplicita.

## Stage 1: Analyst

### Obiettivo

Decomporre la query in claim atomici con requisiti di evidenza.

### Input

- Query utente
- Evidenze recuperate

### Output

```json
{
  "claims": [
    {
      "claim_id": "c1",
      "claim": "Affermazione specifica...",
      "evidence_needed": true,
      "party": "FRATELLI D'ITALIA",
      "priority": "high"
    }
  ],
  "query_type": "policy|event|comparison|general",
  "requires_government_view": true
}
```

### Implementazione

Prompt engineering con structured output JSON.

## Stage 2: Sectional Writer

### Obiettivo

Scrivere una sezione per OGNI partito usando SOLO le evidenze recuperate.

### Regola di Copertura

**TUTTI i 10 gruppi parlamentari devono avere una sezione.**

Se non esiste evidenza per un partito:
```
"Nel corpus analizzato non risultano interventi rilevanti su questo tema."
```

### Formato Output

```markdown
## FRATELLI D'ITALIA
[Contenuto con citazioni nel formato [CIT:evidence_id]]
```

### Citation Placeholders

Le citazioni sono inserite come placeholder `[CIT:id]` che verranno risolti nello Stage 4.

## Stage 3: Narrative Integrator

### Obiettivo

Garantire coerenza narrativa SENZA fondere le posizioni.

### Regola Critica

**MAI sintetizzare o fondere posizioni di partiti diversi.**

Ogni prospettiva deve rimanere distinta e attribuibile.

### Operazioni Consentite

- Aggiungere frasi di transizione
- Correggere errori grammaticali
- Migliorare leggibilità

### Operazioni Proibite

- Modificare contenuto sostanziale
- Fondere posizioni
- Rimuovere sezioni

## Stage 4: Citation Surgeon

### Obiettivo

Inserire citazioni VERBATIM con verifica.

### Regole Inviolabili

1. **Estrazione SOLO via offset**: `testo_raw[span_start:span_end]`
2. **MAI confrontare con chunk_text**: Usare SOLO testo_raw
3. **Validità = offset validi + estrazione riuscita**
4. **NO fuzzy matching**

### Implementazione

```python
def insert_citations(text: str, evidence_map: Dict) -> Dict:
    def replace_citation(match):
        evidence_id = match.group(1)
        evidence = evidence_map.get(evidence_id)

        # Estrai quote via offset
        quote = evidence["testo_raw"][evidence["span_start"]:evidence["span_end"]]

        # Verifica integrità
        if quote != evidence["quote_text"]:
            return "[Citazione non verificabile]"

        # Formatta
        return f'«{quote}» [{speaker}, {party}, {date}, ID:{evidence_id}]'

    return CITATION_PATTERN.sub(replace_citation, text)
```

### Gestione Errori

| Situazione | Azione |
|------------|--------|
| evidence_id non trovato | `[Citazione non disponibile]` |
| Offset non validi | `[Citazione non verificabile]` |
| Quote non corrisponde | `[Citazione non verificabile]` |

## Flusso Completo

```
Query
  ↓
[Stage 1: Analyst]
  ↓
Claims + Evidence Requirements
  ↓
[Stage 2: Sectional Writer] (loop su tutti i partiti)
  ↓
Sezioni con [CIT:id] placeholders
  ↓
[Stage 3: Integrator]
  ↓
Testo integrato con placeholders
  ↓
[Stage 4: Surgeon]
  ↓
Testo finale con citazioni verbatim
```

## Trade-off

### Pro

- Auditabilità ad ogni stadio
- Prevenzione hallucination citazioni
- Garanzia copertura tutti i partiti
- Citazioni verificabili

### Contro

- Latenza maggiore (4 chiamate LLM invece di 1)
- Costo API più alto
- Complessità implementativa

## Configurazione

```yaml
generation:
  models:
    analyst: "gpt-4o"
    writer: "gpt-4o"
    integrator: "gpt-4o"
    # Stage 4 è deterministico, non usa LLM

  parameters:
    max_tokens: 4000
    temperature: 0.3

  require_all_parties: true
  no_evidence_message: "Nel corpus analizzato non risultano interventi rilevanti su questo tema."
```

---

## Sistema di Integrità Citazioni

La pipeline include un sistema a **5 livelli** per garantire l'integrità assoluta delle citazioni.

### Architettura

```
Query
  ↓
[Stage 1: Analyst]
  ↓
Claims + Evidence Requirements
  ↓
[Stage 2: Sectional Writer] ←── Citation Registry: bind citations
  ↓
Sezioni con [CIT:id] placeholders
  ↓
[Stage 3: Integrator] ←── Integrator Guard: verify + repair
  ↓
Testo integrato con placeholders
  ↓
[Coherence Validator] ←── Semantic coherence check
  ↓
[Stage 4: Surgeon] ←── Citation Registry: mark resolved
  ↓
[Final Completeness Check] ←── Verify no unresolved [CIT:id]
  ↓
Testo finale con citazioni verbatim + Integrity Report
```

### Componenti

#### Citation Registry

Traccia ogni citazione attraverso la pipeline:

```python
from backend.app.services.generation import CitationRegistry

registry = CitationRegistry()
registry.register_evidence(evidence_list)

# Track binding
registry.bind_citation(evidence_id, party, intro_text)

# Verify after integration
registry.verify_placeholders_in_text(integrated_text)

# Track resolution
registry.mark_resolved(evidence_id, success=True)

# Final report
report = registry.get_final_report()
```

#### Coherence Validator

Verifica coerenza semantica (keyword overlap + sentiment detection):

```python
from backend.app.services.generation import CoherenceValidator

validator = CoherenceValidator(min_coherence_score=0.2)
result = validator.validate_coherence(intro_text, quote_text)
```

#### Integrator Guard

Verifica pre/post integrazione con riparazione automatica:

```python
integrated = integrator.integrate_with_guard(query, sections, registry)
# Repara automaticamente citazioni perse durante l'integrazione
```

#### Evidence-First Writer (Alternativo)

Costruisce testo attorno alle citazioni per coerenza garantita:

```python
from backend.app.services.generation import EvidenceFirstWriter

writer = EvidenceFirstWriter()
section = await writer.write_section_evidence_first(query, party, evidence)
```

### Output con Report di Integrità

```json
{
  "text": "...",
  "citations": [...],
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
        "total_registered": 50,
        "total_expected": 12,
        "resolved": 12,
        "failed": 0,
        "orphaned": 0,
        "success_rate": 1.0,
        "is_complete": true
      }
    }
  }
}
```

### Configurazione Integrità

```yaml
citation:
  integrity:
    enable_registry: true           # Tracciamento citazioni
    min_coherence_score: 0.2        # Soglia coerenza semantica
    integrator_guard: true          # Guard con riparazione
    strict_resolution: true         # Fallire se citazioni non risolte
    include_report: true            # Includere report nella risposta
    evidence_first_mode: false      # Modalità evidence-first
```
