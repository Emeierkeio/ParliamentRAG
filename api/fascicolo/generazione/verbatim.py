"""Cosa conta come citazione letterale.

Una citazione mostrata al lettore deve essere un tratto continuo del testo
dell'intervento. Sono ammesse tre differenze, tutte reversibili:

- più spazi o a capo di fila diventano uno spazio solo;
- la prima lettera può cambiare maiuscola, perché la citazione segue un verbo
  ("afferma che «noi…»");
- apostrofi tipografici e virgolette singole valgono come l'apostrofo dritto
  ': APOSTROPHES (U+2019, U+2018, U+201B, U+02BC, U+2032, U+0060, U+00B4),
  da entrambe le parti.

Nient'altro: niente puntini, niente parole saltate, niente punteggiatura
corretta, niente altre virgolette. Il verificatore pubblico del repo
(`api/strumenti/citazioni.py`) applica le stesse tre regole.
"""
import re

_PARENTHETICAL = re.compile(r'\([^)]*\)')


APOSTROPHES = "\u2019\u2018\u201b\u02bc\u2032\u0060\u00b4"
_STRAIGHT = str.maketrans({c: "'" for c in APOSTROPHES})


def straight_apostrophes(text: str) -> str:
    """Ogni apostrofo tipografico o virgoletta singola diventa '. La lunghezza non cambia."""
    return (text or "").translate(_STRAIGHT)


def _squash(text: str) -> str:
    return " ".join(straight_apostrophes(text).split())


def is_verbatim(quote: str, source: str) -> bool:
    """Vero se quote compare in source secondo le tre regole sopra."""
    q, s = _squash(quote), _squash(source)
    if not q or not s:
        return False
    if q in s:
        return True
    return q[0].swapcase() + q[1:] in s


def drop_parentheticals(quote: str, min_chars: int = 20) -> str:
    """Restituisce un pezzo continuo di quote senza parentesi.

    Togliere "(Applausi)" dal mezzo unirebbe due pezzi che nell'intervento non
    sono vicini, quindi la citazione si taglia: il primo pezzo se è lungo
    abbastanza, altrimenti il più lungo.
    """
    if "(" not in quote:
        return quote
    pieces = [p.strip() for p in _PARENTHETICAL.split(quote)]
    pieces = [p for p in pieces if p]
    if not pieces:
        return ""
    if len(pieces[0]) >= min_chars:
        return pieces[0]
    return max(pieces, key=len)
