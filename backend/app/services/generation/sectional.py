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
from .reported_speech import annotate_evidence_with_reported_speech

logger = logging.getLogger(__name__)


class SectionalWriter:
    """
    Stage 2 of the generation pipeline.

    Writes one section per party using ONLY the retrieved evidence.
    If no evidence exists for a party, writes the configured "no evidence" message.
    """

    SYSTEM_PROMPT = """Sei un redattore parlamentare italiano esperto.
Scrivi sezioni ANALITICHE (max 4-5 frasi per sezione).

⚠️ APPROCCIO CITATION-INTEGRATED:
Per ogni evidenza trovi un TESTO DISPONIBILE. Leggilo, scegli la parte più
incisiva e scrivila VERBATIM tra «». Metti [CIT:id] subito dopo la «» di chiusura.

REGOLE FONDAMENTALI — SOLO TESTO VERBATIM:
La frase tra «» DEVE apparire esattamente nel TESTO DISPONIBILE, parola per parola.
NON parafrasare. NON modificare nemmeno una parola.

REGOLA ANTI-DUPLICATI:
Ogni [CIT:id] deve comparire UNA SOLA VOLTA nel testo. Non riusare lo stesso ID.

REGOLA ANTI-ACCUMULAZIONE:
Mai due citazioni «» consecutive senza testo in mezzo.
Tra due citazioni ci deve essere ALMENO una frase di analisi.
SBAGLIATO: «prima citazione» [CIT:a]. «seconda citazione» [CIT:b].
GIUSTO:    «prima citazione» [CIT:a]. Aggiunge inoltre che «seconda» [CIT:b].

REGOLA DI COMPLETEZZA SINTATTICA:
La citazione tra «» deve essere una frase sintatticamente completa.
DEVE iniziare con: soggetto esplicito ("il Governo", "l'Italia", nome proprio)
                   OPPURE verbo principale ("non possiamo", "riteniamo", "serve").
NON iniziare con: connettori ("quindi", "però", "perché", "che", "e", "ma", "infatti")
                  preposizioni + dimostrativi ("a questa", "per queste", "per questo")
                  complementi orfani (parole che completano una frase precedente).
NON terminare in sospeso senza verbo principale o senza oggetto.

STRUTTURA SEZIONE (3-5 frasi):
1. TESTO INTRODUTTIVO (1-2 frasi): contestualizza il tema per questo gruppo e anticipa
   il contenuto della citazione che seguirà. Deve PREPARARE il terreno per la citazione.
2. CITAZIONE VERBATIM: «frase esatta dal testo» [CIT:id] — deve essere il passaggio più
   incisivo che DIMOSTRA e RAFFORZA quanto detto nell'introduzione.
   Formato obbligatorio: **Nome Cognome** [verbo] «citazione» [CIT:id].
3. POSIZIONAMENTO GENERALE (1-2 frasi): spiega la posizione complessiva del gruppo
   sul tema della domanda — strategia politica, visione d'insieme, implicazioni.
   La citazione del punto 2 deve essere coerente con e funzionale a questo posizionamento.

NON passare a un secondo deputato. La citazione riguarda UN SOLO deputato.

REGOLA NOMI:
Usa il nome di un deputato SOLO nella frase che contiene la sua citazione verbatim «».
Fuori da quella frase usa "il gruppo", "il partito", "la coalizione", mai un nome proprio.
SBAGLIATO: **Perego** evidenzia la complessità geopolitica. ← nessuna «» → NON mettere il nome!
GIUSTO: Il gruppo evidenzia la complessità geopolitica, citando le tensioni nel Mar Rosso.

ESEMPIO:
TESTO (Rossi): "la flat tax non riduce le tasse ai lavoratori dipendenti già soggetti ad aliquote proporzionali"
→ [INTRO] La discussione sulla riforma fiscale vede il partito schierarsi contro la flat tax, ritenuta iniqua per i redditi da lavoro dipendente.
  [CITAZIONE] **Rossi** chiarisce: «la flat tax non riduce le tasse ai lavoratori dipendenti già soggetti ad aliquote proporzionali» [CIT:abc].
  [POSIZIONAMENTO] Il gruppo sostiene una riforma fiscale progressiva che tuteli i redditi medio-bassi, in netta opposizione alla proposta governativa.

SBAGLIATO — citazione assente:
→ **Rossi** si è opposto alla flat tax [CIT:abc]. ← MANCA «»!

SBAGLIATO — citazione scollegata dall'intro:
→ Il partito discute di economia. **Rossi** dichiara «la flat tax...» [CIT:abc]. Il gruppo è preoccupato per l'ambiente. ← l'intro non prepara la citazione!

REGOLA ANTI-META-CITAZIONE (DISCORSO RIPORTATO):
Il TESTO DISPONIBILE può contenere frasi in cui il deputato RIPORTA le parole di
un ALTRO soggetto (avversari parlamentari, ministri, media, portavoce stranieri, ecc.)
per contestarle, confutarle o rispondervi.
Segnali tipici: "ieri/oggi la collega X ha dichiarato che...", "secondo X...",
"come ha detto Y...", "X ha affermato che...", "X sostiene che...".
⚠️ Le parole riportate SONO DELL'ALTRA PERSONA, non del deputato che parla.
NON usarle come citazione della posizione del gruppo.
Scegli SOLO frasi dette IN PRIMA PERSONA dal deputato — quelle FUORI dalle
virgolette di attribuzione nel testo, che esprimono la sua risposta/posizione.
ESEMPI:
✗ SBAGLIATO — TESTO: "ieri la collega Gribaudo ha dichiarato che per il centrodestra
  vengono prima i corrotti, vengono prima gli evasori e i lavoratori vengono per ultimi"
  → NON usare «vengono prima i corrotti» — sono parole di Gribaudo, non di Nisini!
  → Cerca invece la risposta di Nisini: "noi riteniamo che...", "non è così perché...", ecc.
✗ SBAGLIATO — TESTO contiene: «ha dichiarato Peskov: «l'espansione è necessaria»»
  → NON usare «l'espansione è necessaria» — è la voce del Cremlino, non del deputato.
⚠️ Se il TESTO DISPONIBILE è contrassegnato con "⚠️ DISCORSO RIPORTATO RILEVATO", presta
  attenzione massima: il rischio di inversione di posizione è elevato.

REGOLA DI PERTINENZA:
La citazione DEVE rispondere DIRETTAMENTE alla Domanda fornita.
Se il TESTO DISPONIBILE è un intervento lungo che tocca più argomenti, scegli
SOLO frasi che parlano dell'argomento specifico della Domanda. Ignora le frasi
su temi diversi, anche se retoricamente forti.
ESEMPIO: Domanda su "aiuti militari all'Ucraina" + testo che parla anche di Gaza/Medio Oriente
→ ignora le frasi su Gaza — scegli SOLO frasi sull'Ucraina.

REGOLA DI POSIZIONAMENTO ESPLICITO:
La citazione DEVE contenere un verbo o un'espressione che comunichi una posizione
ESPLICITA del gruppo (favorevole, contraria o condizionale) rispetto alla Domanda.
NON usare frasi che:
- Descrivono il problema senza prendere posizione ("il lavoro povero è aumentato")
- Introducono il tema senza valutarlo ("oggi parliamo di salario minimo")
- Riportano fatti o dati senza giudizio politico
- Sono premesse retoriche a una posizione non visibile nel testo
- Sono DOMANDE RETORICHE senza la risposta inclusa: una domanda come
  "possiamo permetterci di sospendere gli aiuti?" SEMBRA contraria al sostegno,
  ma è in realtà un'interrogativa retorica con risposta "No". Isolata, INVERTE
  il significato. Non usarla MAI da sola come citazione.
  → Se vuoi usare una domanda retorica, includi OBBLIGATORIAMENTE la risposta:
    «possiamo permetterci di sospendere gli aiuti? No, le armi sono indispensabili»
  → Oppure scegli un'affermazione diretta dallo stesso testo.
ESEMPI di citazioni VALIDE (contengono posizione esplicita):
✓ "non siamo obbligati ad introdurre un salario minimo legale" → posizione chiara CONTRO
✓ "serve una soglia di dignità di 9 euro lordi" → posizione chiara PRO
✓ "è indispensabile ma bisogna trovare risorse" → posizione CONDIZIONALE esplicita
✓ "possiamo sospendere gli aiuti? No, le armi sono indispensabili" → domanda + risposta
ESEMPI di citazioni NON VALIDE (nessuna posizione esplicita):
✗ "siamo qui oggi a parlare del salario minimo, cioè del livello minimo di retribuzione"
✗ "cooperative che sfruttano i lavoratori immigrati, che non vengono pagati"
✗ "in molti casi salari più alti di una ipotetica soglia" (frammento senza soggetto)
✗ "possiamo permetterci di sospendere gli aiuti militari?" (domanda retorica senza risposta)
Se il TESTO DISPONIBILE non contiene frasi con posizione esplicita, usa le evidenze
restanti per costruire il posizionamento con parole tue (senza «» né [CIT:]).

PROFONDITÀ MINIMA:
Ogni sezione deve avere ALMENO 2 frasi di analisi sostantiva.
Non liquidare nessun partito con una sola frase generica.
Usa 1 sola citazione verbatim per sezione; usa le evidenze restanti per costruire
analisi e contesto con parole tue.

DIVIETO DI FILLER:
NON scrivere "ha espresso la propria posizione" o "è intervenuto sul tema".
Ogni frase DEVE comunicare una posizione CONCRETA.

POSIZIONE DI GRUPPO:
Prima delle evidenze trovi la "POSIZIONE COMPLESSIVA DEL GRUPPO".
Usala per capire la direzione generale e verificare che la citazione scelta
sia coerente con essa. Se una citazione, letta isolatamente, trasmette il
CONTRARIO della posizione del gruppo, scegli un'altra evidenza.

STRUTTURA OUTPUT:
### [NOME PARTITO]
[1-2 frasi introduttive che preparano la citazione]
**Nome** [verbo] «citazione verbatim» [CIT:id].
[1-2 frasi sul posizionamento generale del gruppo sul tema]"""

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

        self.all_parties = self.config.get_all_parties()

        brief_config = gen_config.get("position_brief", {})
        self._context_chars = brief_config.get("context_chars", 500)

    @staticmethod
    def _anonymize_uncited_speakers(
        content: str,
        cited_speaker_names: set,
        all_speaker_names: list
    ) -> str:
        """
        Replace bold **Nome Cognome** references for non-cited speakers.

        The LLM may mention a secondary evidence speaker in bold format even
        without a verbatim citation. Since no citation verifies their words,
        replace the bold name with a generic group reference to avoid
        false attribution (e.g. "Perego evidenzia..." without any «»).

        Only bold names are targeted (**Name**) — plain text references
        are left untouched since they are less likely to imply direct quotes.
        """
        import re
        result = content
        for speaker in all_speaker_names:
            if not speaker or speaker in cited_speaker_names:
                continue
            bold_pattern = re.compile(r'\*\*' + re.escape(speaker) + r'\*\*')
            if bold_pattern.search(result):
                result = bold_pattern.sub('**Il gruppo**', result)
                logger.info(f"Anonymized uncited speaker bold reference: {speaker}")
        return result

    @staticmethod
    def _enforce_single_citation(content: str) -> str:
        """
        Code-level enforcement: keep only the first inline «...» [CIT:id] citation.

        Strips [CIT:id] markers from all subsequent inline citations while
        preserving the quoted text between «». This guarantees exactly one
        verifiable citation per section regardless of LLM behaviour.

        Example:
            Input:  **Rossi** dice «frase A» [CIT:x]. **Bianchi** aggiunge «frase B» [CIT:y].
            Output: **Rossi** dice «frase A» [CIT:x]. **Bianchi** aggiunge «frase B».
        """
        import re
        pattern = re.compile(r'«([^»]+)»\s*\[CIT:[^\]]+\]')
        matches = list(pattern.finditer(content))
        if len(matches) <= 1:
            return content
        # Remove [CIT:id] from all matches after the first (reverse order preserves positions)
        result = content
        for match in reversed(matches[1:]):
            result = result[:match.start()] + f'«{match.group(1)}»' + result[match.end():]
        return result

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

        # Annotate all evidence with reported-speech detection.
        # Must run AFTER dedup so that duplicate chunks already know their
        # status; the annotation is used by _build_evidence_context to add
        # visible warnings for the LLM.
        annotate_evidence_with_reported_speech(all_evidence)

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
        for party in self.all_parties:
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

        # Build evidence context (full quote_text shown to LLM for inline citation)
        # max_evidence=3: LLM cites 1 verbatim + uses 2 for analysis without citation
        evidence_context = self._build_evidence_context(evidence, query, max_evidence=3)

        # Build claims relevant to this party
        party_claims = [c for c in claims if c.get("party") == party or c.get("party") is None]

        user_prompt = f"""Domanda: {query}

Partito: {party}
{"(Sezione Governo/Esecutivo)" if is_government else ""}

Evidenze disponibili (ordinate per autorità, usa la PRIMA per la citazione verbatim; le altre per l'analisi):
{evidence_context}

⚠️ ISTRUZIONI CITATION-INTEGRATED:
1. LEGGI la POSIZIONE COMPLESSIVA DEL GRUPPO per capire la direzione generale
2. Scegli UNA SOLA evidenza per la citazione verbatim (la più autorevole/incisiva)
3. Scrivila VERBATIM tra «» seguita immediatamente da [CIT:ID_COMPLETO]
4. Usa le evidenze restanti SOLO per costruire analisi e contesto — senza «» né [CIT:]
5. Scegli il verbo introduttivo in base al TONO della citazione scelta
6. ⚠️ RILEVANZA + POSIZIONAMENTO OBBLIGATORI: la citazione deve (a) rispondere DIRETTAMENTE
   a "{query}" E (b) esprimere una posizione ESPLICITA del gruppo (favorevole/contraria/condizionale).
   NON usare frasi descrittive, introduttive o retoriche senza posizione.
   Se il testo tocca altri argomenti, scegli ESCLUSIVAMENTE frasi su "{query}".
   ⚠️ COERENZA CON L'ORIENTAMENTO: la citazione DEVE essere coerente con l'Orientamento
   stimato indicato nella POSIZIONE COMPLESSIVA DEL GRUPPO. Una citazione che sembra
   contraddire l'orientamento del gruppo è quasi sempre una premessa retorica, NON la posizione.

FORMATO OUTPUT (rispetta questo ordine):
1. [1-2 frasi introduttive — prepara il contesto e anticipa la citazione]
2. **Nome Cognome** [verbo], «frase verbatim dal testo» [CIT:id].
3. [1-2 frasi — posizionamento generale del gruppo sul tema della domanda]

✓ GIUSTO:
Il gruppo sostiene la necessità di una riforma fiscale equa, concentrandosi sull'impatto sui lavoratori dipendenti.
**Rossi** chiarisce che «la flat tax non riduce le tasse ai lavoratori dipendenti già soggetti ad aliquote proporzionali» [CIT:id].
Il partito propone un sistema progressivo che tuteli i redditi medio-bassi, distanziandosi nettamente dalla proposta governativa.

⚠️ SBAGLIATO: **Rossi** contesta la misura [CIT:id]. ← MANCANO LE «»!
⚠️ SBAGLIATO: Il gruppo discute di economia. **Rossi** «...» [CIT:id]. Il gruppo è preoccupato per l'ambiente. ← intro scollegata dalla citazione!
"""

        import re

        # Determine if there is citeable evidence before entering the retry loop.
        # A section with available, non-duplicate, substantive evidence MUST produce
        # a citation — if it doesn't, we retry once with an explicit reminder.
        has_citeable_evidence = any(
            not e.get("citation_duplicate_of")
            and compute_chunk_salience(e.get("quote_text", "") or e.get("chunk_text", "")) > 0.35
            for e in evidence[:3]
        )

        content = ""
        validated_ids: List[str] = []
        citations: List[Dict[str, Any]] = []

        for attempt in range(2):
            # On retry, prepend an explicit reminder that the previous output lacked «».
            if attempt == 0:
                attempt_prompt = user_prompt
            else:
                attempt_prompt = (
                    "⚠️ SECONDO TENTATIVO: il tuo output precedente NON conteneva nessuna "
                    "citazione verbatim «» con [CIT:id], nonostante le evidenze disponibili.\n"
                    "Devi OBBLIGATORIAMENTE includere:\n"
                    "  **Nome Cognome** [verbo] «frase esatta copiata dal TESTO DISPONIBILE» [CIT:ID_COMPLETO]\n"
                    "Scegli la frase più incisiva dalla prima evidenza e copiala parola per parola.\n\n"
                ) + user_prompt

            try:
                # Async call for true parallel execution
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": attempt_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=800
                )

                content = response.choices[0].message.content

                # Enforce single citation: strip extra [CIT:id] markers after the first.
                # This is code-level insurance — the prompt rule alone is not reliable.
                content = self._enforce_single_citation(content)

                # Extract citation IDs - primarily [CIT:id] format
                citation_ids = re.findall(r'\[CIT:([^\]]+)\]', content)

                # Also catch any legacy ["text"](id) format and extract just the ID
                legacy_ids = re.findall(r'\]\(([^)]+)\)', content)
                citation_ids.extend(legacy_ids)

                # Build valid evidence IDs set for validation
                valid_evidence_ids = {e.get("evidence_id") for e in evidence}

                # Build a map from evidence_id → party for cross-party guard
                evidence_party_map = {e.get("evidence_id"): e.get("party", "") for e in evidence}

                # Validate and filter citation IDs
                validated_ids = []
                invalid_ids = []
                for cit_id in citation_ids:
                    if cit_id not in valid_evidence_ids:
                        invalid_ids.append(cit_id)
                        logger.warning(f"Invalid citation ID '{cit_id}' not in evidence list for {party}")
                        continue
                    # Cross-party guard: reject evidence belonging to a different party
                    cited_party = evidence_party_map.get(cit_id, "")
                    if cited_party and cited_party != party and party != "GOVERNO":
                        logger.warning(
                            f"Cross-party citation rejected: '{cit_id}' belongs to "
                            f"'{cited_party}' but section is '{party}'"
                        )
                        invalid_ids.append(cit_id)
                        continue
                    validated_ids.append(cit_id)

                # Log if we found invalid citations (possible truncation)
                if invalid_ids:
                    logger.warning(f"Section {party}: {len(invalid_ids)} invalid citation IDs found: {invalid_ids[:5]}")
                    for invalid_id in invalid_ids:
                        # Try to salvage: find which valid evidence contains the verbatim quote
                        cit_pattern = re.compile(r'«([^»]+)»\s*\[CIT:' + re.escape(invalid_id) + r'\]')
                        match = cit_pattern.search(content)
                        salvaged = False
                        if match:
                            inline_quote = match.group(1)
                            # Normalize whitespace for robust matching (LLM may insert extra spaces/newlines)
                            inline_norm = " ".join(inline_quote.split())
                            for e in evidence:
                                qt = e.get("quote_text", "") or e.get("chunk_text", "")
                                qt_norm = " ".join(qt.split())
                                eid = e.get("evidence_id", "")
                                if eid in valid_evidence_ids and inline_norm in qt_norm:
                                    content = content.replace(f'[CIT:{invalid_id}]', f'[CIT:{eid}]')
                                    validated_ids.append(eid)
                                    logger.info(
                                        f"Salvaged citation: '{invalid_id}' → '{eid}' "
                                        f"(verbatim match found in evidence)"
                                    )
                                    salvaged = True
                                    break
                        if not salvaged:
                            # Strip the entire «quote» [CIT:id] pair to avoid leaving a bare «»
                            # that the pipeline would later have to clean up, causing attribution
                            # verbs ("afferma:", "propone che") to become orphaned sentences.
                            if match:
                                content = cit_pattern.sub('', content)
                            else:
                                content = content.replace(f'[CIT:{invalid_id}]', '')
                            logger.warning(f"Could not salvage citation '{invalid_id}', stripped from content")

                # Retry if no citation was produced but citeable evidence was available.
                if not validated_ids and has_citeable_evidence and attempt == 0:
                    logger.warning(
                        f"Section {party}: no citation on attempt 1 despite available evidence, retrying..."
                    )
                    continue

            except Exception as e:
                logger.error(f"Section writing failed for {party} (attempt {attempt + 1}): {e}")
                return {
                    "party": party,
                    "content": f"## {party}\n\n[Errore nella generazione della sezione]",
                    "citations": [],
                    "has_evidence": False,
                    "error": str(e),
                }

            # Citation produced (or last attempt exhausted) — exit the retry loop.
            break

        # Anonymize non-cited speaker bold names AFTER salvage, so that speakers
        # whose citation IDs were salvaged (invalid → valid) are correctly identified
        # as cited and keep their names.
        final_cit_ids = set(validated_ids)
        cited_names = {
            e.get("speaker_name", "")
            for e in evidence
            if e.get("evidence_id") in final_cit_ids and e.get("speaker_name")
        }
        all_names = [
            e.get("speaker_name", "")
            for e in evidence[:2]
            if e.get("speaker_name")
        ]
        content = self._anonymize_uncited_speakers(content, cited_names, all_names)

        # For government sections, replace generic "il gruppo/Il gruppo" with "il Governo/Il Governo"
        if is_government:
            content = re.sub(r'\bIl gruppo\b', 'Il Governo', content)
            content = re.sub(r'\bil gruppo\b', 'il Governo', content)
            content = re.sub(r'\bIl partito\b', 'Il Governo', content)
            content = re.sub(r'\bil partito\b', 'il Governo', content)

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

    def _build_evidence_context(
        self,
        evidence: List[Dict[str, Any]],
        query: str,
        max_evidence: int = 5
    ) -> str:
        """
        Build evidence context for the citation-integrated approach.

        CITATION-INTEGRATED: The sectional writer receives the full quote_text
        and is responsible for selecting and embedding verbatim text between «».
        The CitationSurgeon verifies the inline quote as a literal substring
        of the source before accepting it.

        POSITION-AWARE: Includes a brief of the group's overall position.
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
            lines.append("--- EVIDENZE DISPONIBILI ---")

        count = 0
        for e in evidence:
            if count >= max_evidence:
                break

            # Skip evidence marked as duplicate by cross-speaker dedup
            if e.get("citation_duplicate_of"):
                logger.info(f"Skipping duplicate citation {e.get('evidence_id')} (duplicate of {e['citation_duplicate_of']})")
                continue

            eid = e.get("evidence_id", "unknown")
            speaker = e.get("speaker_name", "")
            speaker_party = e.get("party", "")
            date = e.get("date", "")
            quote_text = e.get("quote_text", "") or e.get("chunk_text", "")

            if not quote_text:
                continue

            # Filter out procedural and low-substance chunks before exposing
            # them to the LLM. compute_chunk_salience returns the max salience
            # score across all sentences in the chunk, so a chunk with even one
            # good sentence will pass the gate.
            chunk_salience = compute_chunk_salience(quote_text)
            if chunk_salience <= 0.35:
                logger.info(
                    f"Skipping procedural chunk {eid} ({speaker}): "
                    f"salience={chunk_salience:.2f}"
                )
                continue

            # Nota cambio gruppo: visibile all'LLM per qualsiasi tipo di trasferimento
            party_changed = e.get("party_changed", False)
            current_party = e.get("current_party")
            group_change_note = ""
            if party_changed and current_party:
                group_change_note = f"\n⚠️ CAMBIO GRUPPO: al momento del discorso era in {speaker_party}, ora è in {current_party}. Aggiungi nel testo: «(allora in {speaker_party})» dopo il nome del deputato."

            # Reported-speech warning — injected directly into the evidence
            # block so the LLM sees it immediately before the text.
            rs_info = e.get("reported_speech", {})
            rs_warning = ""
            if rs_info.get("has_reported_speech"):
                if rs_info.get("opening_is_reported"):
                    rs_warning = (
                        "\n⚠️ DISCORSO RIPORTATO RILEVATO: questo testo INIZIA con il deputato "
                        "che cita le parole di un'ALTRA persona (avversario, collega, media). "
                        "NON usare le parole riportate come posizione del gruppo. "
                        "Cerca la risposta/posizione del deputato più avanti nel testo."
                    )
                else:
                    rs_warning = (
                        "\n⚠️ DISCORSO RIPORTATO RILEVATO: questo testo contiene citazioni "
                        "di ALTRI soggetti. Verifica che la frase scelta sia del deputato, "
                        "non di chi viene citato."
                    )

            similarity = e.get("similarity", 0.0)
            relevance_label = (
                " ← ALTA PERTINENZA — PREFERIRE per la citazione"
                if similarity >= 0.65 else
                " ← MEDIA PERTINENZA — usa solo se più pertinente delle altre"
                if similarity >= 0.45 else
                " ← BASSA PERTINENZA — usa solo per analisi, NON per la citazione"
            )
            lines.append(f"""
[ID: {eid} | Pertinenza query: {similarity:.2f}{relevance_label}]
Speaker: {speaker} ({speaker_party}){group_change_note}{rs_warning}
Date: {date}
TESTO DISPONIBILE (scegli la parte più incisiva, copiala VERBATIM tra «»):
{quote_text[:1000]}
---""")
            count += 1

        return "\n".join(lines)

    async def write_section_without_citation(
        self,
        query: str,
        party: str,
        evidence: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
    ) -> str:
        """
        Rewrite a party paragraph without any verbatim citation.

        Called when a citation is hard-removed with score < REWRITE_THRESHOLD
        (extreme semantic mismatch). The original section was generated around
        a citation that no longer exists, leaving disconnected intro/positioning
        sentences. This method produces a self-contained 2-3 sentence paragraph
        based on the available evidence.

        Returns the paragraph body (plain text, no ## header, no «» citations).
        """
        evidence_context = self._build_evidence_context(evidence, query, max_evidence=2)

        system_prompt = (
            "Sei un redattore parlamentare italiano esperto.\n"
            "Scrivi una sezione analitica di 2-3 frasi che riassume la posizione del partito.\n\n"
            "REGOLE:\n"
            "- NON usare citazioni verbatim «» né marcatori [CIT:id].\n"
            "- NON mettere nomi propri in grassetto.\n"
            "- INIZIA con 'il gruppo' o 'il partito' (minuscolo, nessun header ### o ##).\n"
            "- Ogni frase deve comunicare una posizione CONCRETA: angolo specifico, proposta, critica.\n"
            "- Usa le evidenze come base per costruire l'analisi con parole tue.\n"
            "DIVIETO DI FILLER: NON scrivere 'ha espresso la propria posizione' o simili."
        )

        user_prompt = (
            f"Domanda: {query}\n\n"
            f"Partito: {party}\n\n"
            f"Evidenze disponibili:\n{evidence_context}\n\n"
            "Scrivi 2-3 frasi che descrivono la posizione concreta del partito. "
            "NON includere citazioni verbatim."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=300,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"write_section_without_citation failed for {party}: {e}")
            return ""

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
