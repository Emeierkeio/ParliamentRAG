"""Estrae da un passo le frasi più attinenti alla domanda.

È il ripiego quando manca una best_quote già calcolata. Il peso politico non
si giudica qui: sta nei dati come citability_score / citability_class,
calcolati in indicizzazione dal backend precedente. Il punteggio conta solo
le parole in comune, senza chiamate.
"""
import re
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class SentenceExtractor:
    """Estrae le frasi più attinenti alla domanda, contando le parole in comune."""

    # parole vuote italiane ignorate nella divisione in parole
    STOP_WORDS = {
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
        "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
        "e", "o", "ma", "che", "chi", "cui", "quale", "quanto",
        "questo", "quello", "codesto", "stesso", "medesimo",
        "tale", "altro", "certo", "alcuno", "nessuno", "ogni",
        "ciascuno", "tutto", "tanto", "molto", "poco", "troppo",
        "parecchio", "alquanto", "altrettanto", "più", "meno",
        "come", "dove", "quando", "perché", "se", "non", "né",
        "anche", "pure", "inoltre", "dunque", "quindi", "però",
        "essere", "avere", "fare", "dire", "potere", "dovere",
        "volere", "sapere", "venire", "andare", "stare", "dare",
        "è", "sono", "ha", "hanno", "sia", "siano", "era", "erano",
        "stato", "stata", "stati", "state", "dell", "della", "dello",
        "dei", "degli", "delle", "nel", "nella", "nello", "nei",
        "negli", "nelle", "sul", "sulla", "sullo", "sui", "sugli",
        "sulle", "al", "alla", "allo", "ai", "agli", "alle",
        "dal", "dalla", "dallo", "dai", "dagli", "dalle",
        "col", "coi", "pel", "pei"
    }

    def __init__(self, max_sentences: int = 2, min_sentence_length: int = 30):
        self.max_sentences = max_sentences
        self.min_sentence_length = min_sentence_length

    def extract(
        self,
        text: str,
        query: str,
        max_total_chars: Optional[int] = 500
    ) -> str:
        """Estrae dal testo le frasi più attinenti alla domanda.

        Restituisce "" se nessuna frase è citabile, così chi chiama passa ad
        altri passi. max_total_chars è un limite morbido.
        """
        if not text or not query:
            return text[:max_total_chars] if text and max_total_chars else text

        sentences = self._split_sentences(text)

        if not sentences:
            return text[:max_total_chars] if max_total_chars else text

        scored = self._score_sentences(sentences, query)
        selected = self._select_best(scored, max_total_chars)

        if not selected:
            # nessuna frase ha parole della domanda: in questo passo non c'è niente da citare
            return ""

        result = " ".join(selected)
        return self._clean_result(result)

    def _clean_result(self, text: str) -> str:
        """Ripulisce il testo estratto per mostrarlo.

        Toglie i pezzi iniziali lasciati da una divisione sbagliata, come
        aggettivi o nomi che continuano la frase prima.
        """
        text = text.strip()

        # toglie connettivi e preposizioni iniziali lasciati da un taglio sbagliato
        leading_patterns = [
            r'^(e|o|ma|che|chi|cui|dove|quando|perché|se|però|quindi|dunque|inoltre|anche|pure)\s+',
            r'^(da|di|a|con|per|tra|fra|su|in)\s+(una?|il|lo|la|i|gli|le)\s+',
        ]
        for pattern in leading_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # toglie il pezzo iniziale fatto di parola minuscola e virgola, segno
        # che continua la frase prima (es. "internazionale, serve una
        # risposta" → "Serve una risposta")
        prev = None
        while text != prev:
            prev = text
            text = re.sub(
                r'^[a-zàèéìòù][a-zàèéìòù]*\s*,\s*',
                '', text
            )

        # toglie il pezzo iniziale minuscolo quando nelle prime parole non c'è
        # un verbo (es. "europeo e del Mediterraneo" è un frammento)
        if text and text[0].islower():
            first_words = text.split()[:4]
            first_words_lower = [w.lower().rstrip('.,;:') for w in first_words]
            has_early_verb = any(
                w in self._VERB_AUXILIARIES or
                self._VERB_ENDING_PATTERN.match(w)
                for w in first_words_lower
            )
            if not has_early_verb and len(first_words) > 2:
                # toglie le parole fino alla prima maiuscola, che di solito
                # segna l'inizio della frase vera
                words = text.split()
                for i, word in enumerate(words):
                    if i > 0 and word[:1].isupper():
                        text = " ".join(words[i:])
                        break

        if text and text[0].islower():
            text = text[0].upper() + text[1:]

        text = text.rstrip(',;:')
        text = text.rstrip()

        return text

    # forme verbali italiane comuni, per il controllo di completezza della frase
    _VERB_AUXILIARIES = {
        'è', 'ha', 'sono', 'hanno', 'sia', 'siano', 'abbiamo',
        'era', 'erano', 'sarà', 'saranno', 'può', 'deve', 'vuole',
        'dobbiamo', 'possiamo', 'vogliamo', 'devono', 'possono',
        'vogliono', 'viene', 'vengono', 'va', 'vanno', 'sta', 'stanno',
        'risulta', 'risultano', 'sembra', 'sembrano', 'rappresenta',
    }

    # desinenze verbali italiane comuni
    _VERB_ENDING_PATTERN = re.compile(
        r'\b\w+(?:amo|ano|ono|ato|uto|ito|ando|endo|isce|iamo'
        r'|ava|evano|iva|ivano|ò|ì|arono|irono|erà|irà|eranno|iranno'
        r'|asse|assero|esse|essero|isse|issero'
        r'|ata|uta|ita|ati|uti|iti|ate|ute|ite)\b',
        re.IGNORECASE
    )

    def _has_verb(self, text: str) -> bool:
        """Vero se il testo contiene almeno una forma verbale italiana."""
        words = set(re.findall(r'\b\w+\b', text.lower()))
        if words & self._VERB_AUXILIARIES:
            return True
        if self._VERB_ENDING_PATTERN.search(text):
            return True
        return False

    # righe che presentano l'oratore, es. "VANNIA GAVA, Vice Ministra
    # dell'Ambiente e della sicurezza energetica.": intestazioni, non parole citabili
    _SPEAKER_ID_PATTERN = re.compile(
        r'^[A-Z\s\'.]+,'  # nome in maiuscolo seguito da virgola
        r'\s*(?:Vice\s*)?'  # "Vice" facoltativo
        r'(?:Ministr[oa]|Sottosegretari[oa]|President[e]|Segretari[oa]'
        r'|Relator[e]|Deputat[oa]|Senatric[e]|Senator[e]'
        r'|Capogruppo|Questore|Commissari[oa])',
        re.IGNORECASE
    )

    # anche le righe brevi di sola presentazione (nome più gruppo o ruolo, senza contenuto)
    _SHORT_ID_PATTERN = re.compile(
        r'^[A-Z][a-zàèéìòù]+\s+[A-Z][a-zàèéìòù]+\s*'  # "Nome Cognome"
        r'[,(]\s*(?:Vice\s*)?(?:Ministr|Sottosegretari|President|Gruppo|Partito)',
        re.IGNORECASE
    )

    def _is_speaker_identification(self, sentence: str) -> bool:
        """Riconosce le intestazioni che presentano l'oratore.

        Sono righe come "VANNIA GAVA, Vice Ministra dell'Ambiente...": dicono
        chi parla ma non hanno niente da citare.
        """
        stripped = sentence.strip()
        if self._SPEAKER_ID_PATTERN.match(stripped):
            return True
        if self._SHORT_ID_PATTERN.match(stripped) and len(stripped) < 120:
            return True
        return False

    # congiunzioni subordinanti: segnalano un pezzo di frase dipendente
    _SUBORDINATING_CONJUNCTIONS = {
        'se', 'che', 'quando', 'dove', 'come', 'perché', 'poiché',
        'affinché', 'sebbene', 'benché', 'giacché', 'purché',
        'qualora', 'laddove', 'allorché', 'finché', 'ove',
    }

    # finali sospesi: la frase è stata tagliata a metà
    _DANGLING_ENDING_PATTERN = re.compile(
        r'\s+(?:per|di|a|da|in|con|su|il|lo|la|i|gli|le|un|uno|una|'
        r'al|alla|allo|del|della|dello|nel|nella|nello|'
        r'e|o|ma|che|né|se)$',
        re.IGNORECASE
    )

    def _syntactic_completeness_score(self, sentence: str) -> float:
        """Punteggio di completezza sintattica di una frase.

        1.0: ha un verbo, comincia con la maiuscola, non finisce sospesa
        0.7: come sopra ma finisce con una parola sospesa
        0.5: ha un verbo ma comincia a metà frase
        0.2: pezzo di subordinata (comincia con se/che/quando...)
        0.0: nessun verbo, o un'intestazione che presenta l'oratore
        """
        if not self._has_verb(sentence):
            return 0.0

        stripped = sentence.strip()

        if self._is_speaker_identification(stripped):
            return 0.0

        first_word = re.match(r'\b(\w+)\b', stripped.lower())
        has_dangling = bool(self._DANGLING_ENDING_PATTERN.search(stripped))

        if first_word and first_word.group(1) in self._SUBORDINATING_CONJUNCTIONS:
            return 0.2

        first_char = stripped[0] if stripped else ''
        if first_char.isupper() or first_char in '«"\'':
            return 0.7 if has_dangling else 1.0

        return 0.5

    def _split_sentences(self, text: str) -> List[str]:
        """Divide il testo in frasi o in proposizioni di senso compiuto.

        Pensato per la lingua parlamentare, che ha frasi molto lunghe con più
        subordinate.
        """
        text = " ".join(text.split())

        pattern = r'(?<=[.!?])\s+(?=[A-Z«])'
        raw_sentences = re.split(pattern, text)

        sentences = []
        for s in raw_sentences:
            s = s.strip()
            if len(s) >= self.min_sentence_length:
                # le frasi lunghe si dividono sul punto e virgola, un confine
                # forte, ma solo se restano almeno due parti con un verbo ciascuna
                if len(s) > 250:
                    sub_parts = re.split(r';', s)
                    if len(sub_parts) > 1:
                        valid_parts = [p.strip() for p in sub_parts
                                       if len(p.strip()) >= self.min_sentence_length
                                       and self._has_verb(p)]
                        if len(valid_parts) > 1:
                            sentences.extend(valid_parts)
                            continue

                sentences.append(s)

        if not sentences and len(text) >= self.min_sentence_length:
            sentences = [text]

        return sentences

    def _tokenize(self, text: str) -> List[str]:
        """Divide il testo in parole, senza le parole vuote."""
        words = re.findall(r'\b[a-zA-Zàèéìòù]{3,}\b', text.lower())
        return [w for w in words if w not in self.STOP_WORDS]

    def _score_sentences(
        self,
        sentences: List[str],
        query: str
    ) -> List[Tuple[str, float, int, bool]]:
        """Dà a ogni frase un punteggio di attinenza alla domanda.

        Restituisce tuple (frase, punteggio, indice originale, citabile).
        """
        query_tokens = set(self._tokenize(query))

        if not query_tokens:
            # la domanda non ha parole utili: niente filtro sulle parole in comune, tutto citabile
            return [(s, 1.0 / (i + 1), i, True) for i, s in enumerate(sentences)]

        scored = []
        for i, sentence in enumerate(sentences):
            sentence_tokens = self._tokenize(sentence)

            if not sentence_tokens:
                scored.append((sentence, 0.0, i, False))
                continue

            sentence_set = set(sentence_tokens)
            overlap = query_tokens & sentence_set

            overlap_score = len(overlap) / len(query_tokens)
            position_bonus = 0.1 * (1.0 / (i + 1))  # meglio le frasi che vengono prima
            density = len(overlap) / len(sentence_tokens) if sentence_tokens else 0

            completeness = self._syntactic_completeness_score(sentence)
            total_score = (overlap_score * 0.40 + completeness * 0.30
                           + density * 0.20 + position_bonus * 0.10)

            # filtro di citabilità: una frase è citabile solo se nomina il tema
            # della domanda. Il filtro sulla sostanza politica avviene prima,
            # con la citability_class salvata nei dati (classificata in
            # indicizzazione), quindi alla frase resta solo questo requisito
            citable = len(overlap) > 0
            scored.append((sentence, total_score, i, citable))

        return scored

    # punteggio totale minimo (attinenza + completezza + densità + posizione)
    # che serve a una frase quando ce ne sono altre citabili. Origine ignota
    MIN_QUALITY_SCORE = 0.15

    def _select_best(
        self,
        scored: List[Tuple[str, float, int, bool]],
        max_chars: Optional[int]
    ) -> List[str]:
        """Sceglie le frasi migliori entro il limite di caratteri.

        Meglio frasi intere che stanno nel limite che una frase più lunga
        tagliata. Salta le frasi sotto MIN_QUALITY_SCORE, a meno che non ne
        resti nessuna.

        Le frasi senza parole della domanda non si scelgono mai: se non ce
        n'è nessuna restituisce [], così chi chiama passa ad altri passi.
        """
        if not scored:
            return []

        citable = [s for s in scored if s[3]]
        if not citable:
            return []

        sorted_by_score = sorted(citable, key=lambda x: x[1], reverse=True)

        if len(sorted_by_score) > 1:
            sorted_by_score = [
                s for s in sorted_by_score
                if s[1] >= self.MIN_QUALITY_SCORE
            ] or sorted_by_score[:1]

        selected = []
        total_chars = 0

        for sentence, score, orig_idx, _citable in sorted_by_score:
            if len(selected) >= self.max_sentences:
                break

            if max_chars and total_chars + len(sentence) > max_chars:
                if not selected:
                    # la frase migliore non ci sta: se ne prende una più corta
                    # con almeno metà del punteggio migliore
                    best_score = sorted_by_score[0][1]
                    for alt_sentence, alt_score, alt_idx, _alt_citable in sorted_by_score[1:]:
                        if alt_score >= best_score * 0.5 and len(alt_sentence) <= max_chars:
                            selected.append((alt_sentence, alt_idx))
                            total_chars += len(alt_sentence) + 1
                            break
                    if not selected:
                        truncated = self._truncate_at_boundary(sentence, max_chars)
                        selected.append((truncated, orig_idx))
                break

            selected.append((sentence, orig_idx))
            total_chars += len(sentence) + 1  # lo spazio che unisce le frasi

        # riordina per posizione originale, per tenere l'ordine di lettura
        selected.sort(key=lambda x: x[1])

        return [s for s, _ in selected]

    def _truncate_at_boundary(self, text: str, max_chars: int) -> str:
        """Taglia il testo al confine naturale migliore prima di max_chars.

        In ordine: fine frase (.!?), punto e virgola o due punti, virgola,
        spazio; mai prima del primo terzo del limite.
        """
        if len(text) <= max_chars:
            return text

        truncated = text[:max_chars]
        min_pos = max_chars // 3

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


_extractor = None

def extract_best_sentences(
    text: str,
    query: str,
    max_sentences: int = 2,
    max_chars: int = 500
) -> str:
    """Estrae le frasi più attinenti alla domanda con un estrattore condiviso."""
    global _extractor
    if _extractor is None or _extractor.max_sentences != max_sentences:
        _extractor = SentenceExtractor(max_sentences=max_sentences)

    return _extractor.extract(text, query, max_chars)
