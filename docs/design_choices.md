# Scelte di Design e Motivazioni

## Decisioni Architetturali Chiave

### Decisione 1: Neo4j vs PostgreSQL

**Scelta**: Neo4j graph database
**Alternativa**: PostgreSQL con pgvector

**Motivazione**:
- I dati parlamentari sono intrinsecamente relazionali (speaker-gruppo, speaker-commissione)
- Le relazioni temporali richiedono query di path efficienti
- Supporto nativo per vector index in Neo4j 5.x
- I dati esistenti erano già in Neo4j

**Trade-off**: Tecnologia meno diffusa, community più piccola

### Decisione 2: Dual-Channel Retrieval

**Scelta**: Canali paralleli dense + graph
**Alternativa**: Indice unificato singolo

**Motivazione**:
- Il retrieval dense cattura similarità semantica
- Il graph traversal sfrutta la struttura parlamentare
- La fusione permette di bilanciare i due aspetti

**Trade-off**: Complessità maggiore, richiede tuning

### Decisione 3: Citazioni Offset-Based

**Scelta**: Estrazione esatta da offset su testo_raw
**Alternativa**: Fuzzy string matching

**Motivazione**:
- Deterministico, verificabile
- Nessuna decisione di soglia
- Gestisce differenze di preprocessing

**Trade-off**: Richiede offset pre-calcolati nel DB

### Decisione 4: Compass Semi-Supervisionato

**Scelta**: Ancore soft basate su gruppi parlamentari
**Alternativa**: PCA unsupervised, labeling manuale

**Motivazione**:
- Fornisce dimensioni interpretabili
- Permette configurazione per gruppi contestati
- Evita necessità di dati etichettati

**Trade-off**: Potrebbe semplificare eccessivamente lo spettro politico

### Decisione 5: Pipeline 4-Stage

**Scelta**: Analyst → Writer → Integrator → Surgeon
**Alternativa**: Generazione single-pass

**Motivazione**:
- Verifica esplicita ad ogni stadio
- Debug e audit più semplici
- Previene hallucination delle citazioni

**Trade-off**: Latenza maggiore, più chiamate API

## Alternative Considerate e Rifiutate

### Rifiutato: BM25 come Retrieval Primario

**Motivazione del rifiuto**:
- Il retrieval dense gestisce meglio parafrasi e similarità semantica
- Il linguaggio parlamentare varia significativamente dal linguaggio delle query
- BM25 richiede match lessicali che potrebbero mancare

### Rifiutato: Calcolo Authority Real-Time

**Motivazione del rifiuto**:
- I componenti dell'authority score richiedono multiple query DB
- Preferita strategia di caching con invalidazione query-dependent
- Real-time introdurrebbe latenza inaccettabile

### Rifiutato: Claude come LLM Runtime

**Motivazione del rifiuto**:
- Il progetto usa già OpenAI per gli embedding
- Mescolare provider aumenta complessità e costi
- OpenAI gpt-4o fornisce qualità sufficiente

## Impatto sulle Proprietà del Sistema

### Mitigazione Bias

- Copertura multi-view via compass
- Tutti i partiti mostrati indipendentemente dall'evidenza disponibile
- Authority previene dominanza di singoli speaker

### Garanzie di Fedeltà

- Citazioni offset-based prevengono hallucination
- Statement espliciti "no evidence" quando appropriato
- Generazione staged con verifica

### Riproducibilità

- Estrazione citazioni deterministica
- Pesi e threshold configurabili
- Artefatti di valutazione loggati

## Compromessi Accettati

### Latenza vs Verificabilità

La pipeline 4-stage aumenta la latenza (~4x rispetto a single-pass) ma garantisce citazioni verificabili e copertura completa.

**Accettabile perché**: In un contesto accademico/giornalistico, la correttezza è più importante della velocità.

### Semplicità vs Flessibilità (Compass)

Il compass binario sinistra-destra semplifica la realtà politica italiana.

**Accettabile perché**: Lo scopo è garantire copertura multi-view, non analisi politologica rigorosa. La configurabilità permette raffinamenti futuri.

### Copertura vs Precisione (Retrieval)

Over-retrieval (top_k=200) seguito da filtering potrebbe includere risultati meno rilevanti.

**Accettabile perché**: Meglio rischiare qualche falso positivo che perdere prospettive importanti. Il merger con diversity weighting mitiga il rischio.

## Lessons Learned

1. **Schema DB come contratto**: Verificare sempre lo schema reale prima di implementare query
2. **Offset vs text matching**: Gli offset sono più robusti ma richiedono pre-computazione
3. **Multi-view by design**: È molto più difficile aggiungere bilanciamento a posteriori
4. **Config > code**: Tutti i parametri contestuali dovrebbero essere configurabili
