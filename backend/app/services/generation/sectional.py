"""
Stage 2: Sectional Writer

Writes one section per party + government, using ONLY retrieved evidence.
All 10 parties must have sections.

CITATION-FIRST APPROACH:
Citations are pre-extracted BEFORE the LLM writes the text.
This ensures the introductory text matches the actual citation content.

SEMANTIC DEDUPLICATION (MMR-inspired):
Uses embedding cosine similarity instead of exact string match to detect
paraphrased duplicates across speakers. Based on MMR (Carbonell & Goldstein,
SIGIR 1998) and Sentence-BERT (Reimers & Gurevych, EMNLP 2019).
"""
import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator

import numpy as np
import openai

from ...config import get_config, get_settings
from ...key_pool import make_client, make_async_client
from ..citation import extract_best_sentences
from ..citation.sentence_extractor import compute_chunk_salience
from .position_brief import PositionBriefBuilder

logger = logging.getLogger(__name__)


# All 10 parliamentary groups (must all appear in output)
# Uses display names (title case) matching normalize_party_name() output
ALL_PARTIES = [
    "Fratelli d'Italia",
    "Partito Democratico - Italia Democratica e Progressista",
    "Lega - Salvini Premier",
    "Movimento 5 Stelle",
    "Forza Italia - Berlusconi Presidente - PPE",
    "Alleanza Verdi e Sinistra",
    "Azione - Popolari Europeisti Riformatori - Renew Europe",
    "Italia Viva - Il Centro - Renew Europe",
    "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare",
    "Misto",
]


class SectionalWriter:
    """
    Stage 2 of the generation pipeline.

    Writes one section per party using ONLY the retrieved evidence.
    If no evidence exists for a party, writes the configured "no evidence" message.
    """

    SYSTEM_PROMPT = """Sei un redattore parlamentare italiano esperto.
Scrivi sezioni BREVI e INCISIVE (max 3-4 frasi per sezione).

⚠️ APPROCCIO CITATION-FIRST:
Ogni evidenza contiene una ★ CITAZIONE DA USARE già selezionata.
DEVI costruire il testo introduttivo che PREPARI quella citazione.

⚠️⚠️ REGOLA CRITICA - NON COPIARE LA CITAZIONE:
Tu scrivi SOLO il testo introduttivo. Il sistema inserirà automaticamente la citazione.
NON scrivere MAI il contenuto della citazione tra virgolette «».
Scrivi SOLO fino a [CIT:id] e BASTA.

REGOLE FONDAMENTALI:
1. LEGGI la ★ CITAZIONE per capire il TEMA, ma NON copiarla
2. Scrivi un'intro che PREPARI quel contenuto, poi metti [CIT:id]
3. I nomi degli oratori in GRASSETTO: **Nome Cognome**
4. MASSIMO 1-2 citazioni per sezione

PROCESSO DI SCRITTURA:
1. Leggi la ★ CITAZIONE (es: «il conflitto in Ucraina ci riguarda tutti»)
2. Capisci il TEMA: parla di Ucraina e responsabilità collettiva
3. Scrivi intro che prepari quel tema: "ha sottolineato la rilevanza del conflitto per la comunità internazionale, affermando che [CIT:id]."
4. STOP - non aggiungere altro dopo [CIT:id]

ESEMPIO CORRETTO ✓:
★ CITAZIONE: «il sistema sanitario è in crisi per mancanza di fondi»
→ **Mario Rossi** denuncia le difficoltà del sistema sanitario, affermando che [CIT:id].

ESEMPIO SBAGLIATO ✗:
→ **Mario Rossi** denuncia che «il sistema è in crisi» [CIT:id]. ← HAI COPIATO LA CITAZIONE!

COSTRUZIONI CORRETTE (bridge verbale + soggetto) - VARIA il verbo in base al TONO:
- Propositivo: "...proponendo che [CIT:id]", "...auspicando che [CIT:id]"
- Critico: "...denunciando che [CIT:id]", "...contestando il fatto che [CIT:id]"
- Neutro: "...rilevando come [CIT:id]", "...osservando che [CIT:id]"
- Affermativo: "...affermando che [CIT:id]", "...dichiarando che [CIT:id]"

PROFONDITÀ MINIMA:
Ogni sezione deve avere ALMENO 2 frasi di analisi sostantiva.
Non liquidare nessun partito con una sola frase generica.
Se hai più evidenze, usa le prime 1-2 per citazioni e aggiungi contesto con le altre.

DIVIETO DI FILLER:
NON scrivere frasi vuote come "ha espresso la propria posizione" o "è intervenuto sul tema".
Ogni frase DEVE comunicare una posizione CONCRETA (a favore/contro cosa, quale proposta, quale critica).
Se l'evidenza non contiene una posizione chiara, riporta il fatto specifico citato dall'oratore.

DIVIETO DI CITAZIONI PROCEDURALI:
NON usare citazioni che contengono SOLO contenuto procedurale o formulaico, come:
- "il parere è favorevole/contrario"
- "annuncio il voto favorevole del gruppo"
- "dichiaro il voto favorevole/contrario"
- "l'emendamento è approvato/respinto"
- "ringrazio il Presidente"
Se la ★ CITAZIONE è procedurale, IGNORA quell'evidenza e usa le successive.

POSIZIONE DI GRUPPO:
Prima delle evidenze troverai una "POSIZIONE COMPLESSIVA DEL GRUPPO" con la sintesi
degli interventi più autorevoli. Usa questa sintesi per:
1. CAPIRE la direzione generale del gruppo (favorevole, contrario, critico, propositivo)
2. SCEGLIERE citazioni che siano COERENTI con la posizione complessiva
3. Se una citazione, letta da sola, potrebbe sembrare opposta alla posizione
   del gruppo, NON usarla - usa la citazione successiva

REGOLA ANTI-FRAINTENDIMENTO:
Prima di usare una ★ CITAZIONE, chiediti: "Letto senza contesto, questo frammento
esprime la stessa posizione del gruppo?" Se la risposta è no, scegli un'altra evidenza.

STRUTTURA OUTPUT:
### [NOME PARTITO]
[2-4 frasi, ogni citazione è SOLO [CIT:id] senza virgolette]"""

    def __init__(self):
        self.config = get_config()
        self.settings = get_settings()
        # Use AsyncOpenAI for true parallel execution with asyncio.gather()
        self.client = make_async_client()

        gen_config = self.config.load_config().get("generation", {})
        self.model = gen_config.get("models", {}).get("writer", "gpt-4o")
        self.no_evidence_message = gen_config.get(
            "no_evidence_message",
            "Nel corpus analizzato non risultano interventi rilevanti su questo tema."
        )
        self._position_brief_builder = PositionBriefBuilder()

        brief_config = gen_config.get("position_brief", {})
        self._context_chars = brief_config.get("context_chars", 500)

    @staticmethod
    def _truncate_at_boundary(text: str, max_chars: int) -> str:
        """Truncate text at a natural boundary, not mid-phrase."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        min_pos = max_chars // 3
        # Prefer sentence boundaries
        for punct in '.!?':
            pos = truncated.rfind(punct)
            if pos > min_pos:
                return truncated[:pos + 1].rstrip()
        for punct in ';:':
            pos = truncated.rfind(punct)
            if pos > min_pos:
                return truncated[:pos].rstrip()
        pos = truncated.rfind(',')
        if pos > min_pos:
            return truncated[:pos].rstrip()
        pos = truncated.rfind(' ')
        if pos > min_pos:
            return truncated[:pos].rstrip()
        return truncated.rstrip()

    def _get_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Get embeddings for a batch of texts using OpenAI API.

        Uses the same embedding model configured for retrieval.
        Returns normalized vectors for cosine similarity via dot product.
        """
        if not texts:
            return []

        try:
            sync_client = make_client()
            response = sync_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            embeddings = []
            for item in response.data:
                vec = np.array(item.embedding, dtype=np.float32)
                # Normalize for cosine similarity via dot product
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                embeddings.append(vec)
            return embeddings
        except Exception as exc:
            logger.warning(f"Embedding API failed for dedup, falling back to exact match: {exc}")
            return []

    def _deduplicate_citations_across_speakers(
        self,
        all_evidence: List[Dict[str, Any]],
        query: str
    ) -> None:
        """
        Mark duplicate citations across different speakers using
        semantic similarity (MMR-inspired, Carbonell & Goldstein 1998).

        Uses embedding cosine similarity instead of exact string match
        to detect paraphrased duplicates. Keeps the citation with higher
        authority_score when duplicates are found.

        Falls back to exact string match if embedding API is unavailable.

        Mutates evidence in-place by setting 'citation_duplicate_of' key.
        """
        # Phase 1: Extract citations for all evidence
        citations_with_evidence: List[tuple] = []  # (extracted_text, evidence_dict)

        for e in all_evidence:
            quote_text = e.get("quote_text", "") or e.get("chunk_text", "")
            if not quote_text or not query:
                continue

            extracted = extract_best_sentences(
                text=quote_text,
                query=query,
                max_sentences=1,
                max_chars=200
            )
            if not extracted:
                continue

            citations_with_evidence.append((extracted, e))

        if len(citations_with_evidence) < 2:
            return

        # Phase 2: Try embedding-based dedup
        texts = [c[0] for c in citations_with_evidence]
        embeddings = self._get_embeddings_batch(texts)

        if embeddings and len(embeddings) == len(texts):
            # Embedding-based semantic dedup
            config_data = self.config.load_config()
            threshold = config_data.get("citation", {}).get(
                "dedup_similarity_threshold", 0.85
            )

            for i in range(len(citations_with_evidence)):
                e_i = citations_with_evidence[i][1]
                if e_i.get("citation_duplicate_of"):
                    continue

                for j in range(i + 1, len(citations_with_evidence)):
                    e_j = citations_with_evidence[j][1]
                    if e_j.get("citation_duplicate_of"):
                        continue

                    similarity = float(np.dot(embeddings[i], embeddings[j]))

                    if similarity > threshold:
                        # Keep the one with higher authority score
                        score_i = e_i.get("authority_score", 0) or 0
                        score_j = e_j.get("authority_score", 0) or 0

                        if score_j > score_i:
                            e_i["citation_duplicate_of"] = e_j.get("evidence_id", "")
                        else:
                            e_j["citation_duplicate_of"] = e_i.get("evidence_id", "")

                        logger.info(
                            f"Semantic duplicate (sim={similarity:.2f}): "
                            f"'{texts[i][:60]}...' vs '{texts[j][:60]}...' "
                            f"({e_i.get('speaker_name', '?')} vs {e_j.get('speaker_name', '?')})"
                        )
        else:
            # Fallback: exact string match (original behavior)
            logger.info("Using exact-match dedup fallback")
            seen_citations: Dict[str, Dict[str, Any]] = {}

            for extracted, e in citations_with_evidence:
                normalized = " ".join(extracted.lower().split())

                if normalized in seen_citations:
                    existing = seen_citations[normalized]
                    existing_score = existing.get("authority_score", 0) or 0
                    current_score = e.get("authority_score", 0) or 0
                    if current_score > existing_score:
                        existing["citation_duplicate_of"] = e.get("evidence_id", "")
                        seen_citations[normalized] = e
                    else:
                        e["citation_duplicate_of"] = existing.get("evidence_id", "")
                    logger.info(
                        f"Exact duplicate: '{normalized[:60]}...' "
                        f"between {e.get('speaker_name', '?')} and {existing.get('speaker_name', '?')}"
                    )
                else:
                    seen_citations[normalized] = e

    async def write_sections(
        self,
        query: str,
        claims: List[Dict[str, Any]],
        evidence_by_party: Dict[str, List[Dict[str, Any]]],
        government_evidence: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Write sections for all parties IN PARALLEL.

        Yields section data as they are generated (for streaming).

        Args:
            query: Original user query
            claims: Claims from analyst stage
            evidence_by_party: Evidence grouped by party
            government_evidence: Evidence from government members

        Yields:
            Section dictionaries with party, content, citations
        """
        import asyncio

        # Deduplicate citations across all speakers before writing sections
        all_evidence = []
        if government_evidence:
            all_evidence.extend(government_evidence)
        for party_evidence in evidence_by_party.values():
            all_evidence.extend(party_evidence)
        self._deduplicate_citations_across_speakers(all_evidence, query)

        # Build all tasks for parallel execution
        tasks = []
        task_order = []  # Track order: government first, then parties

        # Government section task (if evidence exists)
        if government_evidence:
            tasks.append(self._write_section(
                query=query,
                party="GOVERNO",
                evidence=government_evidence,
                claims=claims,
                is_government=True
            ))
            task_order.append("GOVERNO")

        # Party section tasks
        for party in ALL_PARTIES:
            evidence = evidence_by_party.get(party, [])
            tasks.append(self._write_section(
                query=query,
                party=party,
                evidence=evidence,
                claims=claims,
                is_government=False
            ))
            task_order.append(party)

        # Execute ALL sections in parallel
        logger.info(f"Writing {len(tasks)} sections in parallel...")
        sections = await asyncio.gather(*tasks)

        # Yield results in order
        for section in sections:
            yield section

    async def _write_section(
        self,
        query: str,
        party: str,
        evidence: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        is_government: bool = False
    ) -> Dict[str, Any]:
        """Write a single section for a party or government."""

        if not evidence:
            # No evidence - return standard message
            return {
                "party": party,
                "content": f"## {party}\n\n{self.no_evidence_message}",
                "citations": [],
                "has_evidence": False,
            }

        # Build evidence context with pre-extracted citations
        evidence_context = self._build_evidence_context(evidence, query)

        # Build claims relevant to this party
        party_claims = [c for c in claims if c.get("party") == party or c.get("party") is None]

        user_prompt = f"""Domanda: {query}

Partito: {party}
{"(Sezione Governo/Esecutivo)" if is_government else ""}

Evidenze disponibili (ordinate per autorità, usa le PRIME 1-2):
{evidence_context}

⚠️ ISTRUZIONI CITATION-FIRST CON CONTESTO DI POSIZIONE:
1. LEGGI la POSIZIONE COMPLESSIVA DEL GRUPPO per capire la direzione generale
2. LEGGI la ★ CITAZIONE per capire il TEMA
3. VERIFICA che la citazione sia COERENTE con la posizione complessiva
4. Se la citazione, letta isolatamente, potrebbe trasmettere il CONTRARIO della
   posizione del gruppo, SALTA a un'altra evidenza
5. Scrivi SOLO l'introduzione che prepara quel tema
6. Metti [CIT:ID_COMPLETO] dove andrà la citazione
7. ⚠️ NON COPIARE MAI il testo della citazione tra «» - il sistema lo inserirà!

FORMATO OUTPUT:
**Nome Cognome** [contesto], affermando che [CIT:id].

⚠️ SBAGLIATO: **Rossi** dice che «testo citazione» [CIT:id]. ← NON FARE QUESTO!
✓ GIUSTO: **Rossi** interviene sul tema, affermando che [CIT:id].
"""

        try:
            # Async call for true parallel execution
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500  # Reduced for concise output
            )

            content = response.choices[0].message.content

            # Extract citation IDs - primarily [CIT:id] format
            import re
            citation_ids = re.findall(r'\[CIT:([^\]]+)\]', content)

            # Also catch any legacy ["text"](id) format and extract just the ID
            legacy_ids = re.findall(r'\]\(([^)]+)\)', content)
            citation_ids.extend(legacy_ids)

            # Build valid evidence IDs set for validation
            valid_evidence_ids = {e.get("evidence_id") for e in evidence}

            # Validate and filter citation IDs
            validated_ids = []
            invalid_ids = []
            for cit_id in citation_ids:
                if cit_id in valid_evidence_ids:
                    validated_ids.append(cit_id)
                else:
                    invalid_ids.append(cit_id)
                    logger.warning(f"Invalid citation ID '{cit_id}' not in evidence list for {party}")

            # Log if we found invalid citations (possible truncation)
            if invalid_ids:
                logger.warning(f"Section {party}: {len(invalid_ids)} invalid citation IDs found: {invalid_ids[:5]}")

            # Map validated IDs to actual evidence
            citations = []
            seen_ids = set()
            for cit_id in validated_ids:
                if cit_id in seen_ids:
                    continue
                seen_ids.add(cit_id)
                for e in evidence:
                    if e.get("evidence_id") == cit_id:
                        citations.append({
                            "citation_id": cit_id,
                            "evidence_id": e.get("evidence_id"),
                            "speaker_name": e.get("speaker_name"),
                            "party": e.get("party"),
                            "date": str(e.get("date", "")),
                        })
                        break

            return {
                "party": party,
                "content": content,
                "citations": citations,
                "has_evidence": True,
            }

        except Exception as e:
            logger.error(f"Section writing failed for {party}: {e}")
            return {
                "party": party,
                "content": f"## {party}\n\n[Errore nella generazione della sezione]",
                "citations": [],
                "has_evidence": False,
                "error": str(e),
            }

    def _build_evidence_context(
        self,
        evidence: List[Dict[str, Any]],
        query: str,
        max_evidence: int = 10
    ) -> str:
        """
        Build evidence context with PRE-EXTRACTED citations.

        CITATION-FIRST: Extract the exact citation BEFORE the LLM writes,
        so the LLM can construct text that matches the citation content.

        POSITION-AWARE: Include a brief of the group's overall position
        so citations are understood in proper context.
        """
        lines = []

        # Build and insert position brief at the top
        party = evidence[0].get("party", "") if evidence else ""
        position_brief = self._position_brief_builder.build_brief(
            evidence=evidence,
            party=party,
        )
        if position_brief:
            lines.append(position_brief)
            lines.append("")
            lines.append("--- EVIDENZE CON CITAZIONI PRE-ESTRATTE ---")

        for e in evidence[:max_evidence]:
            # Skip evidence marked as duplicate by cross-speaker dedup
            if e.get("citation_duplicate_of"):
                logger.info(f"Skipping duplicate citation {e.get('evidence_id')} (duplicate of {e['citation_duplicate_of']})")
                continue

            eid = e.get("evidence_id", "unknown")
            speaker = e.get("speaker_name", "")
            date = e.get("date", "")

            # Get the full quote text for extraction
            quote_text = e.get("quote_text", "") or e.get("chunk_text", "")

            # PRE-EXTRACT the citation that will actually be used
            # This is the KEY change: LLM sees the EXACT citation
            if quote_text and query:
                extracted_citation = extract_best_sentences(
                    text=quote_text,
                    query=query,
                    max_sentences=1,
                    max_chars=200
                )
                # Store pre-extracted citation in evidence for later use by Surgeon
                e["pre_extracted_citation"] = extracted_citation
            else:
                # Truncate at a natural boundary, not mid-phrase
                if quote_text and len(quote_text) > 200:
                    extracted_citation = self._truncate_at_boundary(quote_text, 200)
                else:
                    extracted_citation = quote_text or ""
                e["pre_extracted_citation"] = extracted_citation

            # Skip evidence whose citation extraction returned empty
            # (all sentences below quality threshold — no citable content)
            if not extracted_citation:
                logger.info(f"Skipping evidence {eid} ({speaker}): no sentence passed quality threshold")
                continue

            # Skip procedural citations (e.g. "il parere è favorevole",
            # "annuncio il voto favorevole del gruppo", "dichiaro aperta la seduta")
            # and low-substance meta-comments (e.g. "è un tema delicato").
            # Threshold 0.35 filters both procedural (0.2) and meta-comments (0.35).
            # See: FActScore (Min et al., EMNLP 2023) for atomic fact verification.
            citation_salience = compute_chunk_salience(extracted_citation)
            if citation_salience <= 0.35:
                logger.info(
                    f"Skipping procedural citation for {eid} ({speaker}): "
                    f"salience={citation_salience:.1f}, text='{extracted_citation[:80]}...'"
                )
                continue

            # Also provide context (truncated) for understanding
            context = e.get("chunk_text", "")[:self._context_chars]

            lines.append(f"""
[ID: {eid}]
Speaker: {speaker}
Date: {date}
★ CITAZIONE DA USARE (NON COPIARE NEL TESTO): [{extracted_citation}]
Contesto: {context}
---""")

        return "\n".join(lines)

    def write_sections_sync(
        self,
        query: str,
        claims: List[Dict[str, Any]],
        evidence_by_party: Dict[str, List[Dict[str, Any]]],
        government_evidence: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Synchronous version of write_sections.

        Returns all sections as a list.
        """
        import asyncio

        async def collect():
            sections = []
            async for section in self.write_sections(
                query, claims, evidence_by_party, government_evidence
            ):
                sections.append(section)
            return sections

        return asyncio.run(collect())
