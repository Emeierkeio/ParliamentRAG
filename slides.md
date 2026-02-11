---
marp: true
theme: default
paginate: true
backgroundColor: #fff
math: mathjax
style: |
  section {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 21px;
    color: #1e293b;
    padding: 30px 60px;
    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
    letter-spacing: -0.01em;
    line-height: 1.5;
  }
  h1 {
    color: #0f172a;
    font-size: 38px;
    border-bottom: 3px solid #3b82f6;
    padding-bottom: 8px;
    margin-bottom: 25px;
    width: 100%;
  }
  h2 { color: #1e40af; font-size: 28px; margin-top: 15px; margin-bottom: 10px; }
  h3 { color: #334155; font-size: 22px; font-weight: 600; margin-bottom: 15px; }

  .columns { display: flex; gap: 40px; width: 100%; justify-content: space-between; align-items: stretch; }
  .column { flex: 1; }
  .card {
    background: white;
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    border: 1px solid #eef2f6;
  }

  table { width: 100% !important; display: table; font-size: 17px; margin: 15px 0; border-collapse: collapse; }
  th { background-color: #1e3a8a; color: white; padding: 10px; text-align: left; }
  td { padding: 8px 10px; border-bottom: 1px solid #f1f5f9; }

  pre { padding: 15px; border-radius: 8px; font-size: 13px !important; }
  code { font-size: inherit; }

  .badge { background: #dbeafe; color: #1e40af; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 700; margin-bottom: 8px; display: inline-block; }
  .highlight-box { border-left: 4px solid #3b82f6; background: #f0f7ff; padding: 15px 20px; border-radius: 0 8px 8px 0; margin-top: 15px; }

  /* Diagram Styles - Optimized for vertical space */
  .flow-container { display: flex; flex-direction: column; align-items: center; gap: 8px; margin-top: 5px; }
  .node { 
    background: white; border: 1px solid #e2e8f0; padding: 8px 15px; border-radius: 8px; 
    box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; min-width: 160px;
    font-size: 0.75em;
    line-height: 1.2;
  }
  .node.primary { border-left: 4px solid #3b82f6; background: #f8fafc; }
  .node.split { display: flex; gap: 20px; justify-content: center; width: 100%; border: none; box-shadow: none; background: transparent; padding: 0; }
  .arrow { color: #94a3b8; font-size: 16px; line-height: 1; margin: -2px 0; }
  .horizontal-line { height: 1px; background: #cbd5e1; flex-grow: 1; margin: 0 5px; align-self: center; }
---

<!-- _class: invert -->

# Who speaks matters: Topic-Aware Speaker Authority for Multi-View Parliamentary RAG

<div style="display: flex; justify-content: space-between; align-items: center; height: 60%;">
  <div style="flex: 1.5;">
    <h3>(Titolo da confermare insieme)</h3>
    <br>
    <p><strong>Tesi di Laurea Magistrale in Data Science A.A. 2025/2026</strong></p>
    <p>Studente: <strong>Mirko Tritella</strong><br>Relatore: Prof. Matteo <strong>Palmonari</strong><br>Corelatore: Dott. Riccardo <strong>Pozzi</strong></p>
  </div>
  <div class="card" style="flex: 1; text-align: center; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);">
    <p style="font-size: 16px; color: #fff;">Repository (per ora è privata)</p>
    <a href="https://github.com/Emeierkeio/thesis-ParliamentRAG" target="_blank" style="font-size: 14px; color: #3b82f6; text-decoration: none;">
     https://github.com/Emeierkeio/thesis-ParliamentRAG
    </a>
  </div>
</div>

---

# Agenda

<div class="columns">
  <div class="column card">
    <div class="badge">I. Fondamenta</div>
    <ol style="line-height: 1.4;">
      <li><strong>Stato dell'Arte</strong></li>
      <li><strong>Problema</strong></li>
      <li><strong>Architettura</strong></li>
    </ol>
  </div>
  <div class="column card">
    <div class="badge">II. Sistema</div>
    <ol start="4" style="line-height: 1.4;">
      <li><strong>Componenti del Sistema</strong>
        <ul style="font-size: 0.7em; padding-left: 20px; color: #64748b; line-height: 1.1; margin-top: 5px;">
          <li>4.1 Knowledge Graph</li>
          <li>4.2 Dual-Channel Retrieval</li>
          <li>4.3 Authority Scoring</li>
          <li>4.4 Generation Pipeline</li>
          <li>4.5 Sistema di Integrità</li>
          <li>4.6 Ideological Compass</li>
        </ul>
      </li>
    </ol>
  </div>
  <div class="column card">
    <div class="badge">III. Validazione</div>
    <ol start="5" style="line-height: 1.4;">
      <li><strong>Stack Tecnologico</strong></li>
      <li><strong>Protocollo di Valutazione</strong></li>
      <li><strong>Conclusioni</strong></li>
    </ol>
  </div>
</div>

---

# 1. Stato dell'Arte: NLP Parlamentare

<div class="columns">
  <div class="column">
    <div class="badge">Dataset & Corpora</div>
    <table style="font-size: 0.75em;">
      <tr><th>Corpus</th><th>Focus</th><th>Dimensione</th></tr>
      <tr><td><a href="https://www.clarin.si/repository/xmlui/handle/11356/1432"><strong>ParlaMint</strong></a></td><td>EU/29 Paesi</td><td>1B+ parole</td></tr>
      <tr><td><a href="https://aclanthology.org/2024.lrec-main.1394/"><strong>IPSA</strong></a></td><td>Italia (1848+)</td><td>175 anni</td></tr>
      <tr><td><a href="https://www.statmt.org/europarl/"><strong>Europarl</strong></a></td><td>EU Multilingue</td><td>60M parole</td></tr>
      <tr><td><a href="https://link.springer.com/article/10.1007/s10579-018-9411-5"><strong>Talk of Norway</strong></a></td><td>Metadata spk</td><td>1M interventi</td></tr>
    </table>
  </div>
  <div class="column">
    <div class="badge">Task ricorrenti</div>
    <ul style="font-size: 0.85em; margin-top: 10px;">
      <li><strong>Sentiment Analysis</strong>: Polarità dei dibattiti.</li>
      <li><strong>Stance Detection</strong>: Posizionamento vs Target.</li>
      <li><strong>Topic Modeling</strong>: BERTopic per fasi legislative.</li>
      <li><strong>Argumentation Mining</strong>: Struttura dei claim.</li>
    </ul>
    <div class="highlight-box" style="font-size: 0.8em; margin-top: 15px;">
      <strong>Research Gap</strong>: Manca utilizzo QA generativo.
    </div>
  </div>
</div>

---

# 1.1 Differenziazione Strategica

<div class="columns">
  <div class="column">
    <div class="badge">ParliamentRAG vs Approccio attuale</div>
    <table style="font-size: 0.73em;">
      <tr><th><strong>Feature</strong></th><th>Approccio</th><th>ParliamentRAG</th></tr>
      <tr><td><strong>Task</strong></td><td>Classification</td><td>Generative QA</td></tr>
      <tr><td><strong>Viewpoint</strong></td><td>Single/N.D.</td><td>Multi-view Balanced</td></tr>
      <tr><td><strong>Trust</strong></td><td>Heuristic</td><td>Verifiable</td></tr>
      <tr><td><strong>Authority</strong></td><td>Static</td><td>Query-Dependent</td></tr>
    </table>
  </div>
  <div class="column">
    <div class="badge">Related Works</div>
    <ul style="list-style: none; padding-left: 0; font-size: 0.8em; margin-top: 10px;">
      <li style="margin-bottom: 12px;">📄 Erjavec (2022) - <a href="https://link.springer.com/article/10.1007/s10579-021-09574-0"><em>ParlaMint</em></a>: Gold standard per i corpora XML.</li>
      <li style="margin-bottom: 12px;">📄 Ferrara (2024) - <a href="https://aclanthology.org/2024.lrec-main.1394/"><em>IPSA</em></a>: Analisi ideologica di lungo periodo.</li>
      <li style="margin-bottom: 12px;">📄 Basile (2025) - <a href="https://arxiv.org/abs/2506.20209"><em>Perspectives</em></a>: Ruolo dei "vari" punti di vista.</li>
    </ul>
  </div>
</div>

---

# 2. Problema: Accesso ai Dati

<div class="columns">
  <div class="column card">
    <div class="badge" style="background: #f1f5f9; color: #475569;">Sistemi Esistenti (IR)</div>
    <ul style="font-size: 0.8em; margin-top: 10px;">
      <li>Keyword matching (OpenParlamento)</li>
      <li>Lista di documenti "piatti" (Stenografici Camera dei Deputati)</li>
      <li>Sintesi multi-partitica assente</li>
    </ul>
  </div>
  <div class="column card" style="border: 2px solid #3b82f6;">
    <div class="badge">Focus ParliamentRAG</div>
    <ul style="font-size: 0.8em; margin-top: 10px;">
      <li><strong>Coverage</strong>: Rappresentazione di tutti i Gruppi parlamentari</li>
      <li><strong>Integrità della citazione</strong>
      <li><strong>Authority-based Relevance</strong>: sim × authority</li>
    </ul>
  </div>
</div>

---

# 3. Architettura: Overview

<div class="flow-container">
  <div class="badge">Input</div>
  <div class="node">Query: <em>"Posizione partiti su sanità"</em></div>
  <div class="arrow">▼</div>
  <div class="node primary"><strong>Embedding Generation</strong><br><small>text-embedding-3-small (1536-dim)</small></div>
  <div class="arrow">▼</div>
  <div class="node split">
    <div class="node"><strong>Dense Channel</strong><br>Vector Similarity</div>
    <div class="node"><strong>Graph Channel</strong><br>Eurovoc / Structural</div>
  </div>
  <div class="arrow">▼</div>
  <div class="node primary"><strong>Channel Merger + Authority Scoring</strong><br><small>Optimization via Gini Coefficient</small></div>
  <div class="arrow">▼</div>
  <div class="node split">
    <div class="column">
      <div class="node"><strong>Generation Pipeline</strong><br>Multi-LLM Pipeline</div>
      <div class="arrow" style="margin-bottom: 2px;">▼</div>
      <div style="font-size: 0.65em; color: #3b82f6; font-weight: bold;">Risposta con Citazioni</div>
    </div>
    <div class="column">
      <div class="node"><strong>Ideological Compass</strong><br>Weighted PCA</div>
      <div class="arrow" style="margin-bottom: 2px;">▼</div>
      <div style="font-size: 0.65em; color: #3b82f6; font-weight: bold;">Mappa Ideologica</div>
    </div>
  </div>
</div>

---

# 4. Componenti del Sistema

<div class="columns">
  <div class="column card">
    <div class="badge">A. Retrieval Layer</div>
    <ul style="font-size: 0.85em;">
      <li><strong>Knowledge Graph</strong>: Neo4j 5.15</li>
      <li><strong>Dual-Channel Retrieval</strong>: Dense + Graph</li>
      <li><strong>Authority Scorer</strong>: Query-Dependent</li>
    </ul>
  </div>
  <div class="column card" style="border-right: 4px solid #3b82f6;">
    <div class="badge" style="background: #eff6ff;">B. Generation & Analysis</div>
    <ul style="font-size: 0.85em;">
      <li><strong>Pipeline</strong>: 4-Stage Multi-LLM</li>
      <li><strong>Integrity</strong>: 5-Level Guard</li>
      <li><strong>Compass</strong>: Weighted PCA (XAI)</li>
    </ul>
  </div>
</div>


---

# 4.1 Data Model & Knowledge Graph

<div class="columns">
  <div style="flex: 1.2;">
    <div class="badge">Neo4j Schema</div>
    <pre style="font-size: 11px;">
(:Seduta)-[:HA_DIBATTITO]->(:Dibattito)-[:HA_FASE]->(:Fase)
  -[:CONTIENE_INTERVENTO]->(:Intervento)-[:HA_CHUNK]->(:Chunk)
(:Intervento)-[:PRONUNCIATO_DA]->(:Deputato)
(:Deputato)-[:FIRMATARIO]->(:AttoParlamentare)
(:Deputato)-[:MEMBRO_GRUPPO]->(:GruppoParlamentare)
    </pre>
    <div class="highlight-box" style="font-size: 0.7em;">
      <strong>Indice Vettoriale</strong>: OpenAI 3-small (1536 dim) su nodi <em>Chunk</em> e <em>Atto</em>.
    </div>
  </div>
  <div class="card" style="flex: 1;">
    <img src="assets/neo4j_graph.png" width="100%" style="border-radius: 8px;">
    <p style="font-size: 0.7em; color: #64748b; margin-top: 10px;">Visualizzazione centrata sul <strong>Deputato</strong> (viola) come hub di atti (rosso) e interventi.</p>
  </div>
</div>

---

# 4.2 Dual-Channel Retrieval

## Dense Channel (Semantic Similarity)

$$\text{sim}(q, c) = \frac{E(q) \cdot E(c)}{\|E(q)\| \cdot \|E(c)\|}$$

dove $E(\cdot)$ = `text-embedding-3-small` (OpenAI, 1536 dim)

**Query Cypher (con distinzione MembroGoverno):**

```cypher
CALL db.index.vector.queryNodes('chunk_embedding_index', 200, $query_emb)
YIELD node AS c, score
WHERE score >= 0.3
MATCH (c)<-[:HA_CHUNK]-(i:Intervento)-[:PRONUNCIATO_DA]->(speaker)
OPTIONAL MATCH (speaker)-[mg:MEMBRO_GRUPPO]->(g:GruppoParlamentare)
RETURN c, speaker, g, score,
       CASE WHEN 'MembroGoverno' IN labels(speaker)
            THEN 'MembroGoverno' ELSE 'Deputato' END AS speaker_type
-- speaker_type usato per separare Governo da Maggioranza
```

---

# 4.2.1 Graph Channel

<div class="highlight-box" style="font-size: 0.8em; margin-bottom: 15px;">
  <strong>Intuizione</strong>: Chi ha firmato una legge sul tema è probabilmente esperto, anche se usa termini diversi nei suoi interventi.
</div>
<br>

<div class="columns">
  <div class="column card" style="flex: 1;">
    <div class="badge">1. Keyword Extraction</div>
    <pre style="font-size: 0.6em; margin: 8px 0; background: #f8fafc; padding: 10px; border-radius: 6px;">
"Posizione partiti sulla sanità"
      ↓ tokenizza + stopwords
        → ["sanità"]</pre>
  </div>
  <div class="column card" style="flex: 1.3;">
    <div class="badge">2. Trova Atti Parlamentari</div>
    <pre style="font-size: 0.55em; margin: 8px 0; background: #f8fafc; padding: 10px; border-radius: 6px;">
MATCH (a:AttoParlamentare)
WHERE a.eurovoc CONTAINS $kw
   OR a.titolo CONTAINS $kw
RETURN a.uri, a.titolo</pre>
  </div>
  <div class="column card" style="flex: 1;">
    <div class="badge">3-4. Nel Graph</div>
    <p style="font-size: 0.7em; margin: 8px 0;">
      Percorso: <br>Atto → <strong>Firmatari</strong> → Interventi → <strong>Chunks</strong>
    </p>
  </div>
</div>

---

# 4.2.2 Channel Merger: Fusione Strategica

<div class="columns">
  <div style="flex: 1.4;">

$$\forall c \in \text{Chunk}: \text{score}_c = \sum w_i \cdot \text{component}_i$$

<table style="font-size: 0.60em; margin-top: 10px;">
  <thead>
    <tr><th>Peso</th><th>Componente</th><th>Formula</th></tr>
  </thead>
  <tbody>
    <tr><td>0.20</td><td><strong>Relevance</strong></td><td><code>similarity</code> (cosine dal vector index)</td></tr>
    <tr><td>0.20</td><td><strong>Diversity</strong></td><td><code>1 - 0.5 × (count_spk / max_spk)</code></td></tr>
    <tr><td>0.30</td><td><strong>Coverage</strong></td><td><code>1 - 0.5 × (count_party / max_party)</code></td></tr>
    <tr><td>0.30</td><td><strong>Authority</strong></td><td>Pre-computed (6 componenti)</td></tr>
  </tbody>
</table>
<p style="font-size: 0.55em; color: #64748b; margin-top: 8px; line-height: 1.4;">
  <code>count_spk</code> = chunk dello speaker nel result set<br>
  <code>max_spk</code> = massimo tra tutti gli speaker<br>
  <code>count_party</code> = chunk del partito nel result set<br>
  <code>max_party</code> = massimo tra tutti i partiti
</p>

  </div>
  <div class="column" style="flex: 1;">
    <div class="badge">Vincoli Hard di Integrità</div>
    <div class="highlight-box" style="font-size: 0.7em;">
      <ul style="margin: 5px 0; padding-left: 15px;">
        <li><strong>Max Speaker</strong>: max 20 citazioni per speaker</li>
        <li><strong>Max Partito</strong>: max 33% citazioni per partito</li>
        <li><strong>Threshold</strong>: similarità minima ≥ 0.35</li>
      </ul>
    </div>
    <br>
    <p style="font-size: 0.65em; color: #64748b; margin-top: 10px;"><strong>Logica</strong>: Speaker frequenti → diversity bassa (penalità). Partiti rari → coverage alta (bonus).</p>
  </div>
</div>

---

# 4.3 Authority Scoring: Competenza Dinamica

<div class="columns">
  <div style="flex: 1.6;">

$$\text{authority}(s, q) = \sum w_i \cdot \text{component}_i(s, q)$$

<table style="font-size: 0.6em; margin-top: 5px;">
  <tr><th>Componente</th><th>Peso</th><th>Dinamica temporale / Regole</th></tr>
  <tr><td><strong>Professione & Istruzione</strong></td><td>0.20</td><td>Statico (Semantic match query-CV)</td></tr>
  <tr><td><strong>Commissioni</strong></td><td>0.20</td><td>Match tematico Legislatura in corso</td></tr>
  <tr><td><strong>Atti Firmati</strong></td><td>0.25</td><td><strong>Time Decay</strong> (Half-life: 1 anno)</td></tr>
  <tr><td><strong>Interventi (Speech)</strong></td><td>0.30</td><td><strong>Time Decay</strong> (Half-life: 6 mesi)</td></tr>
  <tr><td><strong>Ruoli Istituzionali</strong></td><td>0.05</td><td>Bonus (Ministri, Presidenti)</td></tr>
</table>
  </div>
  <div class="column" style="flex: 1;">
    <div class="badge">Reset Policy</div>
    <div class="highlight-box" style="font-size: 0.7em;">
      <strong>Confine Politico</strong>: L'autorità accumulata viene resettata se il deputato scambia schieramento (Maggioranza ↔ Opposizione).
    </div>
    <p style="font-size: 0.65em; color: #64748b; margin-top: 10px;">Decadimento: <code>decay(t) = 2^(-t/λ)</code><br>dove λ = half-life (365gg atti, 180gg speech)</p>
  </div>
</div>

---

# 4.3.1 Perché Authority DOPO il Retrieval?

<div class="columns">
  <div class="column card">
    <div class="badge">Approccio Alternativo (Scartato)</div>
    <p style="font-size: 0.75em;"><strong>Authority-First</strong>: Calcola authority → Cerca chunk solo degli esperti</p>
    <div class="highlight-box" style="font-size: 0.7em; background: #fef2f2; border-color: #ef4444;">
      <strong>Problemi</strong>:
      <ul style="margin: 5px 0; padding-left: 15px;">
        <li>~400 deputati × authority per query = costoso</li>
        <li>Esclude partiti senza "esperti certificati"</li>
        <li>Perde contenuti rilevanti da non-esperti</li>
      </ul>
    </div>
  </div>
  <div class="column card" style="border: 2px solid #3b82f6;">
    <div class="badge">Approccio Scelto</div>
    <p style="font-size: 0.75em;"><strong>Retrieval-First</strong>: Cerca chunk rilevanti → Calcola authority solo per speaker trovati</p>
    <div class="highlight-box" style="font-size: 0.7em;">
      <strong>Vantaggi</strong>:
      <ul style="margin: 5px 0; padding-left: 15px;">
        <li>Authority calcolata solo per ~50 speaker</li>
        <li>Garantisce coverage di tutti i partiti</li>
        <li>Authority come <em>boost</em>, non filtro</li>
      </ul>
    </div>
  </div>
</div>

<div class="highlight-box" style="font-size: 0.75em; margin-top: 15px; text-align: center;">
  <strong>Intuizione</strong>: Prima "Cosa è stato detto?" → poi "Chi tra questi è esperto?"<br>
  <span style="font-size: 0.85em; color: #64748b;">Evita che esperti senza interventi in Aula (es. Presidente Commissione) escludano partiti dalla coverage.</span>
</div>

---

# 4.4 Generation Pipeline: 4 Stadi

<div class="columns" style="gap: 8px;">
  <div class="column card" style="flex: 1.3;">
    <div class="badge">1. Analyst</div>
    <p style="font-size: 0.6em; color: #3b82f6;"><strong>IN</strong>: Query + Evidence list (dal retrieval)</p>
    <p style="font-size: 0.6em; color: #22c55e;"><strong>OUT</strong>: JSON con claims atomici per partito</p>
    <pre style="font-size: 0.45em; background: #f8fafc; padding: 4px; margin: 3px 0;">{"claims": [
  {"claim": "FdI difende riforma", "party": "FDI"},
{"claim": "PD critica tagli", "party": "PD"}
], "query_type": "policy"}</pre>
    <p style="font-size: 0.5em; color: #64748b; margin: 2px 0;">LLM legge le evidence → genera claims verificabili</p>
  </div>
  <div class="column card">
    <div class="badge">2. Sectional</div>
    <p style="font-size: 0.6em; color: #3b82f6;"><strong>IN</strong>: Claims (da 1) + Evidence raggruppate per partito</p>
    <p style="font-size: 0.6em; color: #22c55e;"><strong>OUT</strong>: 10 sezioni (1 per partito)</p>
    <pre style="font-size: 0.45em; background: #f8fafc; padding: 4px; margin: 3px 0;">**Foti** difende la riforma,
affermando che [CIT:chunk_42]</pre>
    <p style="font-size: 0.5em; color: #64748b; margin: 2px 0;">Citation-First: LLM vede citazione → scrive intro</p>
  </div>
</div>
<br>
<div class="columns" style="gap: 8px; margin-top: 8px;">
  <div class="column card">
    <div class="badge">3. Integrator</div>
    <p style="font-size: 0.6em; color: #3b82f6;"><strong>IN</strong>: 10 sezioni separate</p>
    <p style="font-size: 0.6em; color: #22c55e;"><strong>OUT</strong>: <code>## Intro (provvedimento + N interventi + date) ... ## Governo... ## Maggioranza... ## Opposizione...</code></p>
    <p style="font-size: 0.55em; color: #a78bfa;">Bridge verbs: zero ripetizioni (~25 verbi per tono)</p>
  </div>
  <div class="column card" style="border: 2px solid #22c55e;">
    <div class="badge" style="background: #dcfce7;">4. Surgeon</div>
    <p style="font-size: 0.6em; color: #3b82f6;"><strong>IN</strong>: <code>[CIT:chunk_42]</code></p>
    <p style="font-size: 0.6em; color: #22c55e;"><strong>OUT</strong>: <code>«il SSN va potenziato» [Foti, FdI, 12/03/24]</code></p>
  </div>
</div>

---

# 4.4.4 Stage 4: Citation Surgeon

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

$quote = testo\_raw[span\_start:span\_end]$ → **No fuzzy matching**

**Contributo Originale**: Mentre i sistemi RAG standard rigenerano le citazioni (rischio di allucinazioni/parafrasi), il _Citation Surgeon_ estrae la fonte originale direttamente tramite offset nel testo nel database, garantendo integrità.

---

# 4.5 Sistema di Integrità: Multi-Level Guard

<div class="badge">Obiettivo: Garantire che ogni citazione sia tracciabile, coerente e verificabile</div>

<table style="font-size: 0.62em; margin-top: 10px;">
  <tr><th style="width: 18%;">Livello</th><th style="width: 42%;">Cosa fa</th><th style="width: 40%;">Come opera</th></tr>
  <tr>
    <td><strong>L1: Citation Registry</strong></td>
    <td>Traccia lo <strong>stato</strong> di ogni citazione lungo tutta la pipeline</td>
    <td>State machine: <code>REGISTERED → BOUND → IN_TEXT → RESOLVED</code><br>Ogni evidence ha un binding con speaker, party, quote_preview</td>
  </tr>
  <tr>
    <td><strong>L2: Citation-First</strong></td>
    <td>Garantisce <strong>coerenza intro↔citazione</strong></td>
    <td>Il Sectional vede la citazione PRIMA di scrivere l'intro → "afferma che [CIT:id]" invece di intro scollegato</td>
  </tr>
  <tr>
    <td><strong>L3: Integrator Guard</strong></td>
    <td>Verifica che l'LLM non <strong>perda</strong> citazioni durante l'integrazione</td>
    <td><code>expected = {CIT nelle sezioni}</code><br><code>found = {CIT nel testo integrato}</code><br>Se <code>expected - found ≠ ∅</code> → <strong>RETRY</strong> con prompt mirato</td>
  </tr>
  <tr>
    <td><strong>L4: Coherence Validator</strong></td>
    <td>Verifica che intro e quote siano <strong>semanticamente allineati</strong></td>
    <td>Keyword overlap (Jaccard) + Sentiment check<br>"elogia" + citazione negativa = ❌ mismatch</td>
  </tr>
  <tr>
    <td><strong>L5: Final Check</strong></td>
    <td>Pulizia finale e <strong>report</strong></td>
    <td>Rimuove placeholder <code>[CIT:...]</code> orfani, genera <code>success_rate</code></td>
  </tr>
  <tr>
    <td><strong>L6: Cross-Speaker Dedup</strong></td>
    <td>Previene <strong>citazioni duplicate</strong> tra speaker diversi</td>
    <td>Normalizza testo citazioni, mantiene quella con <code>authority_score</code> più alto</td>
  </tr>
</table>

<div class="highlight-box" style="font-size: 0.65em; margin-top: 10px; padding: 8px 12px;">
  <strong>Sentence Extractor</strong>: Seleziona la frase più rilevante dal chunk (max 200 char) con score = <code>0.45×overlap + 0.25×completeness + 0.2×density + 0.1×position</code> dove <em>completeness</em> ∈ {0, 0.2, 0.5, 0.7, 1.0} — penalizza clausole subordinate orfane (0.2), terminazioni sospese (0.7), e filtra intestazioni oratore (0.0, es. "GAVA, Vice Ministra..."). Soglia minima: se nessuna frase supera <code>MIN_QUALITY_SCORE</code>, evidenza esclusa (nessuna citazione)
</div>

---

# 4.6 Ideological Compass: Pipeline IC-1 → IC-6

<div class="badge">Obiettivo: Visualizzare le posizioni ideologiche dei partiti sugli assi semantici scoperti dai dati</div>

<table style="font-size: 0.58em; margin-top: 8px;">
  <tr><th style="width: 12%;">Stage</th><th style="width: 25%;">Nome</th><th style="width: 63%;">Operazione</th></tr>
  <tr>
    <td><strong>IC-1</strong></td>
    <td>Axis Discovery</td>
    <td><strong>Weighted PCA</strong>: peso = <code>1/(count_party × n_parties)</code> → partiti con più frammenti pesano meno<br>SVD su embeddings pesati → estrae PC1, PC2</td>
  </tr>
  <tr>
    <td><strong>IC-2</strong></td>
    <td>Projection</td>
    <td>Proietta frammenti su assi. Calcola <strong>SCR</strong> (Subspace Contribution Ratio) = <code>‖proj‖² / ‖x‖²</code><br>Z-score normalization + soft clipping con tanh. Outlier se SCR < 0.15</td>
  </tr>
  <tr>
    <td><strong>IC-3</strong></td>
    <td>Group Clustering</td>
    <td><strong>KDE</strong> (Kernel Density Estimation) per trovare centroide di ogni partito se ≥3 frammenti, altrimenti media</td>
  </tr>
  <tr>
    <td><strong>IC-4</strong></td>
    <td>Dispersion</td>
    <td><strong>Ellissi</strong> via eigendecomposition della covarianza pesata (Chi² al 50%)</td>
  </tr>
  <tr>
    <td><strong>IC-5</strong></td>
    <td>Evidence Binding</td>
    <td>Associa i frammenti estremi a ciascun polo: <code>n = min(50, max(3, 10%))</code></td>
  </tr>
  <tr>
    <td><strong>IC-6</strong></td>
    <td>Interpretability</td>
    <td><strong>TF-IDF contrastivo</strong>: score = <code>tf × log(freq_polo / freq_opposto)</code><br>Estrae lemmi NOUN/ADJ via spaCy → genera label per ogni polo</td>
  </tr>
</table>

<div class="highlight-box" style="font-size: 0.6em; margin-top: 8px; padding: 8px 12px;">
  <strong>White-Box XAI</strong>: Gli assi NON sono predefiniti (es. "destra/sinistra") ma <em>scoperti dai dati</em>. IC-6 li rende interpretabili mostrando le keyword discriminanti e i frammenti rappresentativi per ogni polo.
</div>

---

# 5. Stack Tecnologico

<div class="columns">
  <div class="column card">
    <div class="badge">Backend</div>
    <table style="font-size: 0.65em;">
      <tr><th>Componente</th><th>Tecnologia</th></tr>
      <tr><td>Framework</td><td>FastAPI 0.109+</td></tr>
      <tr><td>LLM</td><td>OpenAI GPT-4o</td></tr>
      <tr><td>Embedding</td><td>text-3-small</td></tr>
      <tr><td>Database</td><td>Neo4j 5.15</td></tr>
    </table>
  </div>
  <div class="column card">
    <div class="badge">Frontend</div>
    <table style="font-size: 0.65em;">
      <tr><th>Componente</th><th>Tecnologia</th></tr>
      <tr><td>Framework</td><td>Next.js 16.1</td></tr>
      <tr><td>Styling</td><td>Tailwind 4.0</td></tr>
      <tr><td>Components</td><td>shadcn/ui</td></tr>
      <tr><td>Streaming</td><td>SSE (Events)</td></tr>
    </table>
  </div>
</div>

---

# 6. Protocollo di Valutazione Sperimentale

<div class="columns" style="gap: 25px;">
  <div class="column card" style="flex: 1.5;">
    <div class="badge">Ground Truth: Pagella Politica</div>
    <p style="font-size: 0.7em; margin: 5px 0;">10 articoli di fact-checking</p>
    <ul style="font-size: 0.6em; margin: 5px 0; padding-left: 15px; columns: 2; column-gap: 20px;">
      <li>Referendum cittadinanza</li>
      <li>Ius Scholae</li>
      <li>Guerra Israele-Hamas</li>
      <li>Armi Ucraina</li>
      <li>Tassa extraprofitti banche</li>
      <li>Maternità surrogata</li>
      <li>Sanzioni Russia</li>
      <li>Mercato tutelato energia</li>
      <li>Referendum 2022</li>
      <li>Referendum giugno</li>
    </ul>
  </div>
  <div style="flex: 1;">
    <div class="badge">Metriche Automatiche</div>
    <table style="font-size: 0.6em;">
      <tr><th>Metrica</th><th>Formula</th></tr>
      <tr><td><strong>Position Accuracy</strong></td><td>pos_RAG == pos_Pagella</td></tr>
      <tr><td><strong>Coverage</strong></td><td>partiti_menzionati / partiti_totali</td></tr>
      <tr><td><strong>Citation Integrity</strong></td><td>% CIT risolte correttamente</td></tr>
      <tr><td><strong>Hallucination Rate</strong></td><td>posizioni non in Pagella</td></tr>
    </table>
    <p style="font-size: 0.55em; color: #64748b; margin-top: 5px;">+ RAGAS (Faithfulness) per verificare citazioni.</p>
    <div class="highlight-box" style="font-size: 0.6em; padding: 8px; margin-top: 8px;">
      <strong>Vantaggio</strong>: No annotazione manuale → confronto automatico.
    </div>
  </div>
</div>

---

# Related Works: Metodi di Valutazione

<div class="columns" style="gap: 20px;">
  <div class="column card" style="padding: 12px;">
    <div class="badge">Multi-Perspective Coverage</div>
    <table style="font-size: 0.5em; margin-top: 5px;">
      <tr><th>Metrica</th><th>Come funziona</th><th>Ref</th></tr>
      <tr>
        <td><strong>JSD</strong></td>
        <td>Jensen-Shannon Divergence tra distribuzioni di label: misura quanto due viewpoint divergono statisticamente</td>
        <td><a href="https://arxiv.org/abs/2506.20209">Muscato '25</a></td>
      </tr>
      <tr>
        <td><strong>Mauve</strong></td>
        <td>Confronta distribuzioni di embedding tra testi generati e riferimento → misura copertura semantica</td>
        <td><a href="https://arxiv.org/abs/2102.01454">Pillutla '21</a></td>
      </tr>
      <tr>
        <td><strong>Jaccard</strong></td>
        <td><code>|A∩B| / |A∪B|</code> su keyword set → misura overlap lessicale tra prospettive</td>
        <td>Standard IR</td>
      </tr>
    </table>
  </div>
  <div class="column card" style="padding: 12px;">
    <div class="badge">Faithfulness & Citation</div>
    <table style="font-size: 0.5em; margin-top: 5px;">
      <tr><th>Metrica</th><th>Come funziona</th><th>Ref</th></tr>
      <tr>
        <td><strong>RAGAS</strong></td>
        <td>LLM-as-judge: verifica se ogni frase della risposta è supportata dal context recuperato</td>
        <td><a href="https://arxiv.org/abs/2309.15217">Es '23</a></td>
      </tr>
      <tr>
        <td><strong>Cit. Precision</strong></td>
        <td><code>citazioni_corrette / citazioni_totali</code> → citazioni che supportano effettivamente il claim</td>
        <td><a href="https://arxiv.org/abs/2210.08726">Gao '23</a></td>
      </tr>
      <tr>
        <td><strong>Cit. Recall</strong></td>
        <td><code>claim_supportati / claim_totali</code> → claim con almeno una citazione valida</td>
        <td><a href="https://arxiv.org/abs/2210.08726">Gao '23</a></td>
      </tr>
    </table>
  </div>
</div>

---

# 7. Conclusioni & Futuro

<div class="columns" style="font-size: 0.75em;">
  <div class="column card">
    <div class="badge">Risultati Chiave</div>
    <ul style="padding-left: 20px;">
      <li><strong>Multi-View</strong>: Tutti i Gruppi rappresentati.</li>
      <li><strong>Integrità citazioni</strong>: 100% verificabile.</li>
      <li><strong>Authority</strong>: Esperti emergenti e query-based.</li>
    </ul>
  </div>
  <div class="column card">
    <div class="badge">Impatto</div>
    <ul style="padding-left: 20px;">
      <li><strong>Democrazia Digitale</strong>: Accesso facilitato.</li>
      <li><strong>Fact-checking</strong>: Verifica real-time.</li>
      <li><strong>Trasparenza</strong>: Riduzione bias algoritmici.</li>
    </ul>
  </div>
  <div class="column card">
    <div class="badge">Lavori Futuri</div>
    <ul style="padding-left: 20px;">
      <li>Integrazione vecchie legislature.</li>
      <li>Collegamento Parlamento EU.</li>
      <li>Analisi storica dei voti.</li>
      <li>Domain-specific embeddings.</li>
    </ul>
  </div>
</div>

---

# Bibliografia Selezione

<div class="columns" style="font-size: 13px; line-height: 1.3;">
  <div class="column">
    <div class="badge">RAG & Knowledge Graphs</div>
    <ul style="list-style-type: none; padding-left: 0;">
      <li>📄 <strong>Lewis et al. (2020)</strong> - <a href="https://arxiv.org/abs/2005.11401"><em>Retrieval-Augmented Generation</em></a></li>
      <li>📄 <strong>Karpukhin et al. (2020)</strong> - <a href="https://arxiv.org/abs/2004.04906"><em>Dense Passage Retrieval</em></a></li>
      <li>📄 <strong>Gao et al. (2024)</strong> - <a href="https://arxiv.org/abs/2312.10997"><em>RAG Survey</em></a></li>
      <li>📄 <strong>Edge et al. (2024)</strong> - <a href="https://arxiv.org/abs/2404.16130"><em>Microsoft GraphRAG</em></a></li>
      <li>📄 <strong>Peng et al. (2024)</strong> - <a href="https://arxiv.org/abs/2408.08921"><em>Graph RAG Survey</em></a></li>
    </ul>
    <div class="badge" style="margin-top: 10px;">Citation & Faithfulness</div>
    <ul style="list-style-type: none; padding-left: 0;">
      <li>📄 <strong>Gao et al. (2023)</strong> - <a href="https://arxiv.org/abs/2210.08726"><em>RARR: Researching and Revising</em></a></li>
      <li>📄 <strong>Wallat et al. (2024)</strong> - <a href="https://arxiv.org/abs/2412.18004"><em>Correctness ≠ Faithfulness</em></a></li>
      <li>📄 <strong>VeriCite (2025)</strong> - <a href="https://arxiv.org/abs/2510.11394"><em>VeriCite: Reliable Citations</em></a></li>
    </ul>
  </div>
  <div class="column">
    <div class="badge">Fairness & Multi-Perspective</div>
    <ul style="list-style-type: none; padding-left: 0;">
      <li>📄 <strong>Kim & Diaz (2024)</strong> - <a href="https://arxiv.org/abs/2409.11598"><em>Towards Fair RAG</em></a></li>
      <li>📄 <strong>Stammbach et al. (2024)</strong> - <a href="https://arxiv.org/abs/2406.14155"><em>Aligning LLMs with Viewpoints</em></a></li>
      <li>📄 <strong>Muscato et al. (2025)</strong> - <a href="https://arxiv.org/abs/2506.20209"><em>Perspectives in Play</em></a></li>
    </ul>
    <div class="badge" style="margin-top: 10px;">Parliamentary NLP</div>
    <ul style="list-style-type: none; padding-left: 0;">
      <li>📄 <strong>Erjavec et al. (2022)</strong> - <a href="https://link.springer.com/article/10.1007/s10579-021-09574-0"><em>ParlaMint Corpora</em></a></li>
      <li>📄 <strong>Abercrombie et al. (2020)</strong> - <a href="https://aclanthology.org/2020.lrec-1.624/"><em>ParlVote: Sentiment Analysis</em></a></li>
      <li>📄 <strong>Koniaris et al. (2025)</strong> - <a href="https://arxiv.org/abs/2511.08247"><em>ParliaBench</em></a></li>
      <li>📄 <strong>Çöltekin et al. (2024)</strong> - <a href="https://arxiv.org/abs/2405.07363"><em>Multilingual Power & Ideology</em></a></li>
    </ul>
  </div>
</div>

<div class="highlight-box" style="font-size: 11px; margin-top: 10px;">
  Nota: I riferimenti includono i paper più recenti (2025/2026) in ambito Multi-Perspective RAG e Evaluation.
</div>
