"""Fase 4: chirurgo delle citazioni.

Inserisce le citazioni testuali e le controlla. Via principale: il formato
«inline» [CIT:id], con la frase verificata come sottostringa letterale della
fonte. Se il controllo fallisce, extract_best_sentences (per parole chiave).
Le frasi già scelte dal selettore (quote_vetted) si usano così come sono,
perché la citazione coincida con quella che il modello ha visto scrivendo
l'introduzione.
"""
import re
import logging
from typing import List, Dict, Any, Tuple, Optional

from .impostazioni import FORMATO_CITAZIONE
from .sentence_extractor import extract_best_sentences
from .verbatim import drop_parentheticals

logger = logging.getLogger(__name__)


class CitationSurgeon:
    """Trasforma i segnaposto di citazione in link alla frase, formattati e verificati.

    Fonti della frase, in ordine: il quote_text scelto dalla pipeline, il
    tratto (span) del testo completo dell'intervento, e chunk_text come
    ultima risorsa. Le frasi «» inline valgono solo se compaiono alla lettera
    nella fonte; altrimenti si estrae di nuovo per parole chiave. Le
    citazioni non risolte finiscono in failed_citations.
    """

    # forme delle citazioni, applicate in quest'ordine:
    # 1. «frase testuale» [CIT:id]  ← forma principale
    # 2. [CIT:id]                    ← segnaposto nudo (riserva)
    # 3. ["testo"](id)               ← vecchia forma markdown
    CITATION_PATTERN_INLINE = re.compile(r'«([^»]+)»\s*\[CIT:([^\]]+)\]')
    CITATION_PATTERN_CIT = re.compile(r'\[CIT:([^\]]+)\]')
    CITATION_PATTERN_MARKDOWN = re.compile(r'\["([^"]*)"\]\(([^)]+)\)')

    def __init__(self):
        self.citation_format = FORMATO_CITAZIONE

    def insert_citations(
        self,
        text: str,
        evidence_map: Dict[str, Dict[str, Any]],
        query: str = ""
    ) -> Dict[str, Any]:
        """Trasforma ogni forma di citazione del testo in link [«frase»](evidence_id).

        Gestisce «inline» [CIT:id] (principale), [CIT:id] nudo e il vecchio
        ["testo"](id). Quando una frase va estratta di nuovo, la domanda
        guida extract_best_sentences, che lavora per parole chiave.

        Restituisce testo finale, citations (dati delle citazioni usate),
        failed_citations, total_citations e failed_count.
        """
        self._current_query = query  # la legge _format_citation
        citations_used = []
        failed_citations = []
        seen_ids = set()

        def get_citation_data(evidence_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
            """Frase e dati dell'evidenza per un evidence_id."""
            if evidence_id not in evidence_map:
                logger.warning(f"Citation {evidence_id} not found in evidence map")
                failed_citations.append({
                    "evidence_id": evidence_id,
                    "reason": "not_found_in_evidence_map"
                })
                return None, None

            evidence = evidence_map[evidence_id]
            quote_text = evidence.get("quote_text", "")

            if not quote_text:
                text = evidence.get("text", "")
                span_start = evidence.get("span_start", 0)
                span_end = evidence.get("span_end", 0)
                if text and span_end > span_start:
                    quote_text = self._extract_quote(text, span_start, span_end)

            if not quote_text:
                quote_text = evidence.get("chunk_text", "")[:300]
                if not quote_text:
                    logger.warning(f"No quote_text available for {evidence_id}")
                    failed_citations.append({
                        "evidence_id": evidence_id,
                        "reason": "no_quote_text"
                    })
                    return None, None

            return quote_text, evidence

        def track_citation(evidence_id: str, quote_text: str, evidence: Dict[str, Any]):
            """Annota una citazione usata."""
            if evidence_id not in seen_ids:
                seen_ids.add(evidence_id)
                citations_used.append({
                    "evidence_id": evidence_id,
                    "quote_text": quote_text,
                    "speaker_name": evidence.get("speaker_name"),
                    "party": evidence.get("party"),
                    "date": str(evidence.get("date", "")),
                    "span_start": evidence.get("span_start"),
                    "span_end": evidence.get("span_end"),
                })

        # «frase testuale» [CIT:id]: lo scrittore ha copiato tra «» la frase
        # scelta dal selettore; vale solo se è una sottostringa letterale
        # della fonte
        def replace_inline_format(match):
            inline_quote = match.group(1)
            evidence_id = match.group(2)
            quote_text, evidence = get_citation_data(evidence_id)

            if quote_text is None:
                return f'«{inline_quote}» [Citazione non disponibile]'

            logger.debug(
                f"[CITATION_DEBUG] {evidence_id} | "
                f"chunk_start='{quote_text[:80]}...' | "
                f"llm_chose='{inline_quote[:80]}...'"
            )

            # maiuscola iniziale: il modello mette la prima lettera in minuscolo
            # quando la citazione segue un verbo (afferma che «citazione»);
            # si prova la variante maiuscola, così «noi non...» trova «Noi non...»
            if inline_quote and inline_quote[0].islower():
                capitalized = inline_quote[0].upper() + inline_quote[1:]
                if capitalized in quote_text:
                    inline_quote = capitalized

            # controllo testuale: inline_quote deve comparire alla lettera nella fonte
            if inline_quote in quote_text:
                # e si scarta se è una frase di terzi citata dentro l'intervento
                # (es. Peskov citato nell'intervento di Chiesa)
                if self._is_nested_quote(inline_quote, quote_text):
                    logger.warning(
                        f"Inline quote is a nested third-party citation for "
                        f"{evidence_id}, falling back. "
                        f"Starts with: '{inline_quote[:50]}'"
                    )
                    verified_quote = extract_best_sentences(
                        text=quote_text,
                        query=getattr(self, '_current_query', ''),
                        max_sentences=1,
                        max_chars=400
                    ) or quote_text[:400]
                else:
                    # si allarga a sinistra fino all'inizio della frase dentro il
                    # chunk (solo caso 1). Niente full_text/span_start: sp.text è
                    # testo preelaborato mentre span_start è uno scarto sul grezzo,
                    # e l'allargamento oltre il chunk (caso 2) duplicava il testo
                    # quando la frase parte da pos==0
                    verified_quote = self._expand_to_sentence_start(
                        inline_quote,
                        quote_text,
                    )
                    if verified_quote != inline_quote:
                        logger.debug(
                            f"[CITATION_DEBUG] Expanded mid-sentence quote for {evidence_id}: "
                            f"added {len(verified_quote) - len(inline_quote)} chars | "
                            f"result='{verified_quote[:100]}...'"
                        )
                    else:
                        logger.debug(f"Inline quote at sentence boundary for {evidence_id}")

                    # contro i frammenti: se anche dopo l'allargamento la frase è
                    # sotto i 60 caratteri (lo scrittore ha citato un pezzetto della
                    # frase obbligata), si usa tutto quote_text quando è già una
                    # frase scelta (≤450 caratteri, non un chunk intero)
                    if len(verified_quote) < 60 and 60 <= len(quote_text) <= 450:
                        logger.warning(
                            f"Fragment quote ({len(verified_quote)} chars) for "
                            f"{evidence_id}: using full vetted quote_text "
                            f"({len(quote_text)} chars)"
                        )
                        verified_quote = quote_text.strip()

                    # se la frase è una domanda retorica si aggiunge la risposta,
                    # perché fuori contesto non dica il contrario
                    if verified_quote.rstrip().endswith('?'):
                        expanded = self._expand_rhetorical_answer(verified_quote, quote_text)
                        if expanded != verified_quote:
                            logger.debug(
                                f"[CITATION_DEBUG] Expanded rhetorical question for {evidence_id}: "
                                f"result='{expanded[:120]}...'"
                            )
                            verified_quote = expanded
            else:
                # il modello ha parafrasato o ritoccato: si torna all'euristica
                logger.warning(
                    f"Inline quote not verbatim for {evidence_id}, falling back. "
                    f"Got: '{inline_quote[:60]}...'"
                )
                verified_quote = extract_best_sentences(
                    text=quote_text,
                    query=getattr(self, '_current_query', ''),
                    max_sentences=1,
                    max_chars=400
                ) or quote_text[:400]

            track_citation(evidence_id, verified_quote, evidence)

            return self._format_citation(
                quote=verified_quote,
                speaker=evidence.get("speaker_name", ""),
                party=evidence.get("party", ""),
                date=str(evidence.get("date", "")),
                evidence_id=evidence_id,
                pre_extracted=verified_quote,
                session_number=evidence.get("session_number")
            )

        # [CIT:id] nudo: riserva quando il modello omette le «»
        def replace_cit_format(match):
            evidence_id = match.group(1)
            quote_text, evidence = get_citation_data(evidence_id)

            if quote_text is None:
                return "[Citazione non disponibile]"

            track_citation(evidence_id, quote_text, evidence)

            # quote_vetted: quote_text è la frase scelta dal selettore (riportata
            # dalla pipeline) e si usa così com'è. Estrarla di nuovo per parole
            # chiave la riduce a frammenti (osservato il 24/07/2026: «israele del
            # diritto all'esistenza» da una frase scelta di 290 caratteri)
            return self._format_citation(
                quote=quote_text,
                speaker=evidence.get("speaker_name", ""),
                party=evidence.get("party", ""),
                date=str(evidence.get("date", "")),
                evidence_id=evidence_id,
                pre_extracted=(
                    quote_text if evidence.get("quote_vetted")
                    else evidence.get("pre_extracted_citation", "")
                ),
                session_number=evidence.get("session_number")
            )

        def replace_markdown_format(match):
            inline_text = match.group(1)
            evidence_id = match.group(2)

            quote_text, evidence = get_citation_data(evidence_id)

            if quote_text is None:
                return f'"{inline_text}" [Citazione non disponibile]'

            track_citation(evidence_id, quote_text, evidence)

            return self._format_citation(
                quote=quote_text,
                speaker=evidence.get("speaker_name", ""),
                party=evidence.get("party", ""),
                date=str(evidence.get("date", "")),
                evidence_id=evidence_id,
                pre_extracted=(
                    quote_text if evidence.get("quote_vetted")
                    else evidence.get("pre_extracted_citation", "")
                ),
                session_number=evidence.get("session_number")
            )

        # 1. prima la forma «inline» [CIT:id] (citazione già nel testo)
        final_text = self.CITATION_PATTERN_INLINE.sub(replace_inline_format, text)

        # 2. poi [CIT:id] nudo (riserva: il modello ha dimenticato le «»)
        final_text = self.CITATION_PATTERN_CIT.sub(replace_cit_format, final_text)

        # 3. infine la vecchia forma markdown ["testo"](id)
        final_text = self.CITATION_PATTERN_MARKDOWN.sub(replace_markdown_format, final_text)

        return {
            "text": final_text,
            "citations": citations_used,
            "failed_citations": failed_citations,
            "total_citations": len(citations_used),
            "failed_count": len(failed_citations),
        }

    def _extract_quote(
        self,
        text: str,
        span_start: int,
        span_end: int
    ) -> Optional[str]:
        """La frase esatta text[span_start:span_end].

        None se gli scarti non valgono per il testo dato.
        """
        if span_start < 0:
            logger.error(f"Invalid span_start: {span_start}")
            return None

        if span_end > len(text):
            logger.error(
                f"span_end ({span_end}) exceeds text length ({len(text)})"
            )
            return None

        if span_start >= span_end:
            logger.error(f"Invalid span: {span_start} >= {span_end}")
            return None

        return text[span_start:span_end]

    def _format_citation(
        self,
        quote: str,
        speaker: str,
        party: str,
        date: str,
        evidence_id: str,
        pre_extracted: str = "",
        session_number: Optional[int] = None
    ) -> str:
        """Formatta la citazione come link markdown cliccabile.

        Esce [«frase»](evidence_id). Se c'è pre_extracted (frase già scelta a
        monte) si usa quella, così testo introduttivo e citazione restano
        coerenti.
        """
        if pre_extracted:
            quote = pre_extracted
        else:
            # estrazione al volo. Il «or quote» serve perché extract_best_sentences
            # restituisce "" quando nessuna frase condivide parole con la domanda
            # (es. una frase sul popolo palestinese per una domanda su Israele:
            # pertinente ma senza parole chiave) e senza riserva usciva [«»](id)
            query = getattr(self, '_current_query', '')
            if query and len(quote) > 80:
                quote = extract_best_sentences(
                    text=quote,
                    query=query,
                    max_sentences=1,
                    max_chars=200
                ) or quote
        original_quote = quote

        # il filtro su frasi procedurali o retoriche sta a monte, nel
        # Chunk.citability_class salvato in indicizzazione; qui nessun filtro

        quote = " ".join(quote.split())

        # le parentesi (applausi, interruzioni) si tagliano e non si saltano:
        # la frase deve restare un tratto continuo dell'intervento
        quote = drop_parentheticals(quote).strip()

        # via la punteggiatura finale: le citazioni stanno sempre dentro il
        # racconto tra «», e un "." finale si leggerebbe così:
        # «dimezzare le tasse.» è quello che vuole il Governo (sbagliato)
        # «dimezzare le tasse» è quello che vuole il Governo (giusto)
        quote = quote.rstrip('.!?')
        quote = quote.rstrip()

        # via la punteggiatura rimasta in testa (virgola, punto e virgola)
        quote = quote.lstrip('.,;:')
        quote = quote.lstrip()

        # via la parentesi chiusa finale senza apertura (residuo della fonte,
        # es. "...due popoli due Stati)" con la "(" fuori dal tratto)
        if quote.endswith(')') and quote.count('(') < quote.count(')'):
            quote = quote[:quote.rfind(')')].rstrip()

        # via le parole sospese in coda che segnalano un taglio a metà: articoli,
        # preposizioni, congiunzioni, rimandi tronchi (es. "– n") e virgola più
        # frammento (es. "..., secondo")
        dangling = re.compile(
            r'(?:'
            r'\s+(?:'
            r'il|lo|la|i|gli|le|un|uno|una|l|dell|del|della|dello|dei|degli|delle|'
            r'nel|nella|nello|nei|negli|nelle|sul|sulla|sullo|sui|sugli|sulle|'
            r'al|alla|allo|ai|agli|alle|dal|dalla|dallo|dai|dagli|dalle|'
            r'di|a|da|in|con|su|per|tra|fra|'
            r'e|o|ma|che|né|se|'
            r'[–\-]\s*\w{0,2}'  # rimandi tronchi come "– n", "- 2"
            r')'
            r'|,\s+\w{1,6}'  # virgola finale più frammento corto
            r')$',
            re.IGNORECASE
        )
        # si ripete: togliere "il" può scoprire "che", e così via
        prev = None
        while quote != prev:
            prev = quote
            quote = dangling.sub('', quote)

        # ultima riserva: se la pulizia ha svuotato la frase (filtro e tagli
        # possono ridurla a ""), si torna all'originale ripulito, mai [«»](id)
        if len(quote) < 20:
            fallback = " ".join(original_quote.split())
            fallback = drop_parentheticals(fallback).strip()
            fallback = fallback[:300].rstrip('.!? ')
            if len(fallback) >= 20:
                logger.warning(
                    f"Empty/short quote after processing for {evidence_id}: "
                    f"using original ({len(fallback)} chars)"
                )
                quote = fallback
            else:
                logger.warning(
                    f"No usable quote for {evidence_id}: dropping citation link"
                )
                return ''

        # prima lettera minuscola (le citazioni seguono una frase che le introduce)
        if quote:
            quote = quote[0].lower() + quote[1:] if len(quote) > 1 else quote.lower()

        return f'[«{quote}»]({evidence_id})'

    @staticmethod
    def _expand_to_sentence_start(
        inline_quote: str,
        source_text: str,
        max_expansion: int = 320,
        full_text: str = "",
        span_start: int = 0,
    ) -> str:
        """Allarga a sinistra fino all'inizio della frase un inline_quote che parte a metà.

        Due casi:
        1. pos > 0: inline_quote parte a metà frase *dentro* source_text; si
           risale in source_text fino all'inizio della frase.
        2. pos == 0: è source_text a partire a metà (il confine del chunk taglia
           una frase); con full_text e span_start si premette il pezzo mancante
           preso dall'intervento prima del confine.

        Argomenti:
            inline_quote: il testo scelto dal modello, alla lettera.
            source_text: il quote_text dell'evidenza (può partire a metà frase).
            max_expansion: caratteri massimi da premettere (contro gli eccessi).
            full_text: testo completo dell'intervento (per il caso pos==0).
            span_start: scarto in full_text da cui parte source_text.

        Restituisce la frase, allargata se serve.
        """
        pos = source_text.find(inline_quote)
        if pos < 0:
            return inline_quote

        # caso 1: pos > 0, a metà frase dentro source_text
        if pos > 0:
            char_before = source_text[pos - 1]

            if char_before in '.!?\n»':
                return inline_quote
            if char_before == ' ' and pos >= 2 and source_text[pos - 2] in '.!?':
                return inline_quote

            sentence_start = pos
            while sentence_start > 0 and source_text[sentence_start - 1] not in '.!?\n':
                sentence_start -= 1

            # salta gli spazi dopo la punteggiatura di confine
            while sentence_start < pos and source_text[sentence_start] in ' \t':
                sentence_start += 1

            if sentence_start >= pos:
                return inline_quote

            expansion_len = pos - sentence_start
            if expansion_len > max_expansion:
                # tetto 320 (24/07/2026, prima 160): le frasi parlamentari sono
                # lunghe, «Israele del diritto all'esistenza» stava a ~160
                # caratteri dall'inizio frase e il vecchio tetto lasciava il
                # frammento rotto. I casi oltre 320 escono da questo avviso
                logger.warning(
                    f"Sentence-start expansion aborted: needs {expansion_len} chars "
                    f"(cap {max_expansion}) — keeping mid-sentence fragment "
                    f"'{inline_quote[:50]}'"
                )
                return inline_quote

            return source_text[sentence_start: pos + len(inline_quote)]

        # caso 2: pos == 0, il confine del chunk (span_start) può aver tagliato
        # la frase; si allarga con full_text. La frase parte da span_start
        if not full_text or span_start <= 0:
            return inline_quote

        abs_pos = span_start
        char_before_chunk = full_text[abs_pos - 1] if abs_pos > 0 else ''

        if char_before_chunk in '.!?\n»':
            return inline_quote
        if char_before_chunk == ' ' and abs_pos >= 2 and full_text[abs_pos - 2] in '.!?':
            return inline_quote

        sentence_start = abs_pos
        while sentence_start > 0 and full_text[sentence_start - 1] not in '.!?\n':
            sentence_start -= 1

        while sentence_start < abs_pos and full_text[sentence_start] in ' \t':
            sentence_start += 1

        if sentence_start >= abs_pos:
            return inline_quote

        expansion_len = abs_pos - sentence_start
        if expansion_len > max_expansion:
            return inline_quote

        prefix = full_text[sentence_start:abs_pos]
        return prefix + inline_quote

    @staticmethod
    def _expand_rhetorical_answer(quote: str, source_text: str, max_answer_chars: int = 120) -> str:
        """Aggiunge la risposta che segue una frase citata a domanda retorica.

        Evita che una domanda come «Possiamo sospendere gli aiuti?», citata
        senza la risposta «No, le armi sono indispensabili...», dica il contrario.

        Argomenti:
            quote: la frase verificata, che finisce con '?'.
            source_text: il testo del chunk in cui cercare la risposta.
            max_answer_chars: caratteri massimi da aggiungere dalla risposta.

        Restituisce la frase con la risposta, o l'originale se non la trova.
        """
        pos = source_text.find(quote)
        if pos < 0:
            return quote

        after_pos = pos + len(quote)
        remaining = source_text[after_pos:]

        stripped = remaining.lstrip()
        if not stripped:
            return quote

        # fine della risposta (primo . ! ? oppure max_answer_chars)
        end = 0
        for i, ch in enumerate(stripped):
            if ch in '.!?':
                end = i + 1
                break
        else:
            end = min(len(stripped), max_answer_chars)

        if end == 0:
            end = min(len(stripped), max_answer_chars)

        answer = stripped[:end].rstrip()
        if not answer:
            return quote

        # risposte sotto le 3 parole non vale la pena aggiungerle
        if len(answer.split()) < 3:
            return quote

        return quote + " " + answer

    @staticmethod
    def _is_nested_quote(inline_quote: str, source_text: str) -> bool:
        """Vero se inline_quote è una frase di terzi citata dentro source_text.

        Due casi:
        1. inline_quote comincia con un segno di citazione («, ", "): il modello
           ha copiato le virgolette interne, segno chiaro di citazione nella citazione.
        2. l'inizio di inline_quote in source_text cade dentro un blocco «...» o
           "..."/"..." non chiuso.
        """
        stripped = inline_quote.lstrip()
        if stripped.startswith(('«', '\u201c', '"')):
            return True

        pos = source_text.find(inline_quote)
        if pos == -1:
            return False

        text_before = source_text[:pos]
        # blocco «» aperto nel punto di estrazione
        if text_before.count('«') > text_before.count('»'):
            return True
        # blocco di virgolette doppie Unicode (" ") aperto
        if text_before.count('\u201c') > text_before.count('\u201d'):
            return True

        return False

    def extract_unsupported_claims(
        self,
        text: str
    ) -> List[str]:
        """Le frasi con un verbo di posizione (sostiene, afferma, ...) e senza citazione."""
        unsupported = []
        # gli ID nei link [«frase»](leg19_sed..._tit00070.sub00010...) hanno dei
        # punti: la divisione in frasi li spezzerebbe e la coda della frase
        # citata (senza più « né link) risulterebbe una posizione senza fonte.
        # Sostituire i link con «» tiene il segno della citazione
        text = re.sub(r'\[«[^\]]*»\]\([^)]+\)', '«»', text)
        text = self.CITATION_PATTERN_MARKDOWN.sub('«»', text)
        sentences = re.split(r'[.!?]', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            has_citation = (
                '«' in sentence or
                '[CIT:' in sentence or
                self.CITATION_PATTERN_MARKDOWN.search(sentence) is not None
            )

            if not has_citation:
                claim_patterns = [
                    r'\bsostiene\b',
                    r'\bafferma\b',
                    r'\bdichiara\b',
                    r'\bpropone\b',
                    r'\bcritica\b',
                    r'\bvuole\b',
                ]
                for pattern in claim_patterns:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        unsupported.append(sentence)
                        break

        return unsupported
