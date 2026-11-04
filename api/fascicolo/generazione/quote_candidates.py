"""Estrazione deterministica dei pezzi candidati per la scelta della citazione.

Il testo finale della citazione non deve venire dal modello: il modello
ordina candidati già estratti e il testo scelto si prende tale e quale dalla
fonte. I candidati sono 1-2 frasi consecutive entro una fascia di lunghezza,
filtrati con criteri di struttura che prima stavano solo nelle regole del
prompt (connettivi in apertura, puntini dello stenografico, citazioni di
terzi annidate, annunci di procedura).
"""
import re
import logging
from typing import List, Optional

from .reported_speech import detect_reported_speech

logger = logging.getLogger(__name__)

MIN_CANDIDATE_CHARS = 80
MAX_CANDIDATE_CHARS = 350
MAX_CANDIDATES = 8

# connettivi e complementi orfani: la frase dipende da quella prima e non
# regge da sola come citazione
_LEADING_CONNECTIVE = re.compile(
    r'^(?:quindi|dunque|perciò|però|perché|che|e|ed|o|ma|infatti|inoltre|'
    r'tuttavia|infine|poi|allora|cioè|anzi|eppure|pertanto|comunque|'
    r'a\s+quest[aoie]|per\s+quest[aoie]|di\s+quest[aoie]|in\s+quest[aoie])\b',
    re.IGNORECASE,
)

# vocativi in apertura: nei resoconti aprono di continuo frasi di sostanza
# («Signor Presidente, onorevoli colleghi, come Fratelli d'Italia siamo…»).
# Scartare tutta la frase fa perdere le citazioni migliori (osservato il
# 19/09/2026 su "riforma sanitaria"): si toglie il vocativo e il resto, ancora
# un pezzo esatto della fonte, resta candidato
_VOCATIVE_PREFIX = re.compile(
    r'^(?:grazie,?\s+(?:signor[a]?\s+president[ea]|president[ea])[.,]?\s*|'
    r'grazie[.,]\s*|'
    r'signor[a]?\s+president[ea][.,]?\s*|'
    r'president[ea],\s*|'
    r'onorevol[ie]\s+collegh[ie](?:\s+e\s+collegh[ie])?[.,]?\s*)+',
    re.IGNORECASE,
)

# aperture di procedura: conduzione dell'aula, annunci di mozioni; mai la
# posizione del gruppo sul tema
_PROCEDURAL_OPENING = re.compile(
    r'^(?:ringrazio|'
    r'presentiamo\s+(?:una|la)\s+mozione|annuncio\s+il\s+voto|'
    r'dichiaro\s+(?:aperta|chiusa)|passiamo\s+(?:alla|al|all\')|'
    r'chiedo\s+di\s+(?:parlare|intervenire)|'
    r'l\'ordine\s+dei\s+lavori)',
    re.IGNORECASE,
)

_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')

# una citazione che annuncia quello che segue da sola non dice niente: «è “sì”
# e per due motivi» senza i motivi (Battilocchio, autonomia differenziata,
# 19/10/2026). Un elenco annunciato non si può verificare che ci stia, quindi
# si scarta; un annuncio singolo («vorrei dire una cosa:») prende la frase
# successiva della fonte
_ANNOUNCES_LIST = re.compile(
    r'\b(?:due|tre|quattro|cinque|sei|alcun[ie]|divers[ie]|vari[e]?|qualche)\s+'
    r'(?:motiv[oi]|ragion[ei]|punt[oi]|aspett[oi]|element[oi]|question[ei]|cose|'
    r'considerazion[ei]|osservazion[ei]|domande|obiettiv[oi]|pilastri|'
    r'priorità|proposte|richieste|criticità)\b[^.!?;]{0,60}[.:;!]?\s*$',
    re.IGNORECASE,
)
_ANNOUNCES_ONE = re.compile(
    r'(?::\s*$|\b(?:una\s+cosa|il\s+seguente|la\s+seguente|i\s+seguenti|'
    r'le\s+seguenti|quanto\s+segue|ecco\s+perché|ecco\s+cosa|'
    r'(?:il\s+motivo|la\s+ragione)\s+è\s+(?:semplice|presto\s+detta))\s*[.:!]?\s*$)',
    re.IGNORECASE,
)
EXTENDED_MAX_CHARS = 600


def _split_sentences(text: str) -> List[str]:
    """Divide in frasi senza spezzare dentro le citazioni «...»."""
    # protegge i tratti tra caporali: la punteggiatura dentro una citazione
    # non deve creare un taglio
    protected = []
    depth = 0
    chars = []
    for ch in text:
        if ch == '«':
            depth += 1
        elif ch == '»':
            depth = max(0, depth - 1)
        if depth > 0 and ch in '.!?':
            chars.append('\x00')
            protected.append(ch)
        else:
            chars.append(ch)
    masked = ''.join(chars)
    parts = _SENTENCE_END.split(masked)
    it = iter(protected)
    return [
        ''.join(next(it) if c == '\x00' else c for c in p).strip()
        for p in parts if p.strip()
    ]


def settle_announcement(
    quote: str, text: str, max_chars: int = EXTENDED_MAX_CHARS
) -> Optional[str]:
    """La citazione come può stare: uguale se non annuncia quello che segue,
    allungata con la frase successiva di `text` se annuncia una cosa sola,
    None se annuncia un elenco o non si può allungare. Il risultato è sempre
    un pezzo esatto di `text`."""
    last = _split_sentences(quote)[-1] if quote.strip() else ""
    if _ANNOUNCES_LIST.search(last):
        return None
    if not _ANNOUNCES_ONE.search(last):
        return quote
    pos = text.find(quote)
    if pos < 0:
        return None
    rest = _split_sentences(text[pos + len(quote):])
    if not rest:
        return None
    end = text.find(rest[0], pos + len(quote))
    if end < 0:
        return None
    extended = text[pos:end + len(rest[0])]
    if len(extended) > max_chars or _ANNOUNCES_LIST.search(rest[0]) or _ANNOUNCES_ONE.search(rest[0]):
        return None
    return extended


def _inside_nested_quote(text: str, start_pos: int) -> bool:
    """Vero se start_pos cade dentro un «...» o "..." non chiuso."""
    before = text[:start_pos]
    if before.count('«') > before.count('»'):
        return True
    if before.count('“') > before.count('”'):
        return True
    return False


def _keyword_overlap(candidate: str, query_terms: set) -> int:
    if not query_terms:
        return 0
    words = set(re.findall(r'\b[a-zàèéìòù]{4,}\b', candidate.lower()))
    return len(words & query_terms)


def extract_quote_candidates(
    text: str,
    query: Optional[str] = None,
    min_chars: int = MIN_CANDIDATE_CHARS,
    max_chars: int = MAX_CANDIDATE_CHARS,
    max_candidates: int = MAX_CANDIDATES,
) -> List[str]:
    """Restituisce i pezzi candidati, ognuno un pezzo esatto di `text`.

    I candidati sono 1-2 frasi consecutive entro la fascia di lunghezza,
    ordinati per attinenza alla domanda (parole in comune, ordine stabile a
    parità). Restituisce [] se il testo non ha pezzi citabili: chi chiama
    torna alla vecchia scelta libera.
    """
    if not text or len(text) < min_chars:
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return []

    query_terms = (
        set(re.findall(r'\b[a-zàèéìòù]{4,}\b', query.lower())) if query else set()
    )

    candidates: List[str] = []
    seen: set = set()
    for i in range(len(sentences)):
        for span in (1, 2):
            if i + span > len(sentences):
                break
            candidate = ' '.join(sentences[i:i + span]).strip()
            # toglie i vocativi in apertura; il resto è ancora un tratto
            # continuo della fonte, quindi resta un pezzo esatto
            stripped = _VOCATIVE_PREFIX.sub('', candidate)
            vocative_cut = stripped != candidate
            candidate = stripped.strip()
            if not (min_chars <= len(candidate) <= max_chars):
                continue
            if candidate in seen:
                continue
            if '…' in candidate or '[...]' in candidate:
                continue
            # caporali dentro: o parole riportate di un altro, o un annidamento
            # che romperebbe la resa «candidato» più avanti
            if '«' in candidate or '»' in candidate:
                continue
            if detect_reported_speech(candidate)["has_reported_speech"]:
                continue
            if _LEADING_CONNECTIVE.match(candidate):
                continue
            if _PROCEDURAL_OPENING.match(candidate):
                continue
            # i pezzi che cominciano con la minuscola di solito dipendono da
            # una frase prima che la divisione non ha risolto, a meno che la
            # minuscola venga dal taglio del vocativo fatto qui
            first_alpha = next((c for c in candidate if c.isalpha()), '')
            if (
                not vocative_cut
                and first_alpha and first_alpha.islower()
                and not candidate.startswith(
                    ('è', 'noi', 'non', 'il', 'la', 'lo', 'serve', 'occorre', 'bisogna')
                )
            ):
                continue
            pos = text.find(candidate)
            if pos < 0:
                continue
            if _inside_nested_quote(text, pos):
                continue
            settled = settle_announcement(candidate, text)
            if settled is None or settled in seen:
                continue
            candidate = settled
            seen.add(candidate)
            candidates.append(candidate)

    if not candidates:
        return []

    candidates.sort(key=lambda c: _keyword_overlap(c, query_terms), reverse=True)
    return candidates[:max_candidates]
