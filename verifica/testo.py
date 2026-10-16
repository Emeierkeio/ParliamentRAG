"""Regole sul testo: quando una citazione è letterale, quando sono parole di terzi.

Funzioni pure, senza dipendenze. Vengono da Fascicoli
(backend/app/services/citation/verbatim.py, generation/surgeon.py
`_is_nested_quote`, generation/reported_speech.py) e applicano la stessa
regola, congelata nella versione 1 del formato.

Citazione letterale: un tratto contiguo del testo dell'intervento. Sono
ammesse tre sole differenze:

- gli spazi multipli (spazi, a capo, tabulazioni) contano come uno;
- la prima lettera può cambiare maiuscola («afferma che «noi…»»);
- apostrofi e virgolette singole tipografiche valgono come l'apostrofo
  dritto ': ’ ‘ ‛ ʼ ′ ` ´ (APOSTROFI). Si applica a entrambi i testi.

Tutto il resto conta come modifica: punteggiatura corretta, virgolette doppie
diverse, parole saltate, puntini di sospensione, traduzioni.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Regole ammesse, nell'ordine in cui il rapporto le elenca
NORMALIZZAZIONI = ("whitespace", "first_letter_case", "typographic_apostrophe")

# U+2019 ’, U+2018 ‘, U+201B ‛, U+02BC ʼ, U+2032 ′, U+0060 `, U+00B4 ´ -> U+0027 '
APOSTROFI = "\u2019\u2018\u201b\u02bc\u2032\u0060\u00b4"
_A_DRITTO = str.maketrans({c: "'" for c in APOSTROFI})


def comprimi_spazi(testo: str) -> str:
    return " ".join((testo or "").split())


def apostrofi_dritti(testo: str) -> str:
    """Ogni apostrofo o virgoletta singola tipografica diventa '. Non cambia la lunghezza."""
    return (testo or "").translate(_A_DRITTO)


@dataclass(frozen=True)
class Riscontro:
    """Dove la citazione compare nel testo, e con quale regola."""
    letterale: bool          # sottostringa esatta, senza normalizzare nulla
    regole: tuple            # normalizzazioni servite (vuota se letterale)
    inizio: int              # posizione nel testo compresso


def trova(citazione: str, testo: str) -> Optional[Riscontro]:
    """Cerca la citazione nel testo con le tre sole differenze ammesse.

    Restituisce None se la citazione non compare. `regole` elenca le
    normalizzazioni servite davvero: si prova prima senza, poi con il minimo
    indispensabile. La posizione è sul testo con gli spazi compressi, che è
    quello su cui si leggono le parole di terzi.
    """
    if not citazione or not citazione.strip() or not testo:
        return None
    if citazione in testo:
        return Riscontro(True, (), comprimi_spazi(testo).find(comprimi_spazi(citazione)))
    for regole in _COMBINAZIONI:
        q, t = citazione, testo
        if "whitespace" in regole:
            q, t = comprimi_spazi(q), comprimi_spazi(t)
        if "typographic_apostrophe" in regole:
            q, t = apostrofi_dritti(q), apostrofi_dritti(t)
        if "first_letter_case" in regole:
            q = q[:1].swapcase() + q[1:]
        if q and q in t:
            # Posizione sul testo compresso (gli apostrofi non cambiano lunghezza)
            qq = apostrofi_dritti(comprimi_spazi(q))
            return Riscontro(False, regole, apostrofi_dritti(comprimi_spazi(testo)).find(qq))
    return None


# Dalla combinazione più piccola alla più grande, nell'ordine di NORMALIZZAZIONI
_COMBINAZIONI = [
    tuple(r for r in NORMALIZZAZIONI if r in scelta)
    for scelta in (
        {"whitespace"}, {"first_letter_case"}, {"typographic_apostrophe"},
        {"whitespace", "first_letter_case"}, {"whitespace", "typographic_apostrophe"},
        {"first_letter_case", "typographic_apostrophe"},
        {"whitespace", "first_letter_case", "typographic_apostrophe"},
    )
]


# ---------------------------------------------------------------------------
# Parole di terzi
# ---------------------------------------------------------------------------

_APRE = ("«", "“", '"')

# Attribuzione a un'altra persona subito prima della citazione, nella stessa
# frase. Sono i modelli di reported_speech.py, ancorati alla fine del testo che
# precede la citazione: lì dicono che quello che segue sono parole di altri.
_ATTRIBUZIONE = [
    # "ieri la collega X ha dichiarato che"
    re.compile(r"\b(?:ieri|oggi|l'altro\s+ieri)\s+(?:la\s+collega|il\s+collega|l'onorevole|l'on\.)\s+\w+\s+ha\s+\w+\s+che\s*$", re.I),
    # "X ha dichiarato che per il"
    re.compile(r"\b\w+\s+ha\s+(?:dichiarato|affermato|detto)\s+che\s*$", re.I),
    # "il collega X ha detto che"
    re.compile(r"\b(?:la\s+collega|il\s+collega)\s+\w+\s+ha\s+\w+\s+che\s*$", re.I),
    # "ha/hanno dichiarato, affermato, … che"
    re.compile(r"\b(?:ha|hanno|aveva|avevano)\s+(?:dichiarato|affermato|detto|sostenuto|asserito|proclamato|"
               r"annunciato|comunicato|ribadito|scritto|twittato)\s*(?:che|:)?\s*$", re.I),
    # "come ha detto X," / "come ha detto,"
    re.compile(r"\bcome\s+ha\s+(?:detto|dichiarato|affermato|sostenuto)\b[^.!?;]{0,60}?[,:]?\s*$", re.I),
    # "l'onorevole X ha detto:"
    re.compile(r"\b(?:l'onorevole|l'on\.)\s+\w+\s+ha\s+\w+\s*(?:che|:)?\s*$", re.I),
]

_FINE_FRASE = re.compile(r"[.!?;]\s")


def _blocco_aperto(prima: str) -> bool:
    """Il testo che precede lascia aperte delle virgolette?

    Conta l'ultima virgoletta prima della citazione, non il saldo di tutto
    l'intervento: un resoconto con una sola virgoletta mai chiusa all'inizio
    (capita negli elenchi di ordini del giorno riformulati) altrimenti
    renderebbe «di terzi» tutto quello che segue. Fascicoli
    (_is_nested_quote) conta il saldo; qui la regola è più stretta.
    """
    for apre, chiude in (("«", "»"), ("“", "”")):
        if prima.rfind(apre) > prima.rfind(chiude):
            return True
    # Virgolette dritte: aperte se dispari nella frase corrente
    frase = _FINE_FRASE.split(prima)[-1]
    return frase.count('"') % 2 == 1


def parole_di_terzi(citazione: str, testo: str, inizio: int) -> Optional[str]:
    """Perché la citazione sono parole di altri riportate dall'oratore, o None.

    `inizio` è la posizione della citazione nel testo con gli spazi compressi
    (Riscontro.inizio). Tre segnali, tutti letterali:

    1. la citazione stessa si apre con delle virgolette;
    2. nel resoconto cade dentro un blocco «…» o “…” aperto prima;
    3. nella stessa frase, subito prima, l'oratore attribuisce le parole a
       un altro («il collega X ha detto che …»).
    """
    if comprimi_spazi(citazione).startswith(_APRE):
        return "opens_with_quotation_marks"
    prima = comprimi_spazi(testo)[:inizio]
    if _blocco_aperto(prima):
        return "inside_quotation_marks"
    frase = _FINE_FRASE.split(prima)[-1]
    for modello in _ATTRIBUZIONE:
        if modello.search(frase):
            return "attributed_to_someone_else"
    return None
