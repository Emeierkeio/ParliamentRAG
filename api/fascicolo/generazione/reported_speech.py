"""Riconosce il discorso riportato nei passi degli interventi.

Trova i passi in cui l'oratore riporta soprattutto le parole di un altro
(avversari, ministri, giornali) per smentirle, inquadrarle o rispondere.

Non sono dichiarazioni in prima persona: vanno trattate a parte, altrimenti
le parole citate finiscono attribuite all'oratore come sua posizione, un
errore frequente nell'estrazione delle citazioni.

Esempio di errore:
  Nisini (Lega) cita Gribaudo (PD): «per il centrodestra vengono prima i
  corrotti, vengono prima gli evasori». Non è la posizione della Lega sul
  salario minimo.
"""
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# schemi forti: discorso riportato molto probabile, soprattutto all'inizio
# del passo (opening_is_reported)
_STRONG_PATTERNS = [
    # "ieri/oggi la collega/il collega X ha dichiarato che..."
    re.compile(
        r'\b(?:ieri|oggi|l\'altro\s+ieri)\s+'
        r'(?:la\s+collega|il\s+collega|l\'onorevole|l\'on\.)\s+'
        r'\w+\s+ha\s+\w+\s+che\b',
        re.IGNORECASE,
    ),
    # "X ha dichiarato che per [partito/gruppo]..."
    re.compile(
        r'\b\w+\s+ha\s+(?:dichiarato|affermato|detto)\s+che\s+per\s+(?:il|la|i|lo)\b',
        re.IGNORECASE,
    ),
    # "il collega/la collega X ha [verbo] che..." (citazione parlamentare generica)
    re.compile(
        r'\b(?:la\s+collega|il\s+collega)\s+\w+\s+ha\s+\w+\s+che\b',
        re.IGNORECASE,
    ),
]

# schemi normali: confidenza media (0.60), da soli sotto la soglia di 0.75
_REGULAR_PATTERNS = [
    # "X ha dichiarato/affermato/detto/sostenuto che..."
    re.compile(
        r'\b(?:ha|hanno|aveva|avevano)\s+'
        r'(?:dichiarato|affermato|detto|sostenuto|asserito|proclamato|annunciato|comunicato|ribadito)\s+'
        r'che\b',
        re.IGNORECASE,
    ),
    # "come ha detto/dichiarato/affermato X"
    re.compile(
        r'\bcome\s+ha\s+(?:detto|dichiarato|affermato|sostenuto)\b',
        re.IGNORECASE,
    ),
    # "secondo X" / "stando a X" con X sintagma nominale
    re.compile(
        r'\b(?:secondo|stando\s+a)\s+(?:il|la|lo|i|gli|le|un|una|l\')\b',
        re.IGNORECASE,
    ),
    # "l'onorevole / l'on. X ha [verbo]"
    re.compile(
        r'\b(?:l\'onorevole|l\'on\.)\s+\w+\s+ha\s+\w+\b',
        re.IGNORECASE,
    ),
    # attribuzione subito prima delle caporali: "X ha detto: «" o "X: «"
    re.compile(r'\w+\s*:\s*«', re.IGNORECASE),
]

# attribuzione seguita da caporale (segnale molto forte)
_ATTRIBUTED_INLINE_QUOTE = re.compile(
    r'(?:\w+\s+){1,5}(?:ha\s+)?'
    r'(?:dichiarato|affermato|detto|sostenuto|scritto|twittato)\s+'
    r'(?:che\s+)?«',
    re.IGNORECASE,
)


def detect_reported_speech(text: str) -> Dict[str, Any]:
    """Dice se un passo contiene parole riportate di un'altra persona.

    text è il testo del passo (quote_text o chunk_text del passo).

    Restituisce un dict con:
    - has_reported_speech (bool)
    - confidence (float 0.0–1.0)
    - matched_patterns (list[str]): gli schemi trovati
    - opening_is_reported (bool): vero se uno schema forte compare nei primi
      300 caratteri o una citazione attribuita comincia nei primi 200, il
      segnale più forte
    """
    if not text or len(text) < 20:
        return {
            "has_reported_speech": False,
            "confidence": 0.0,
            "matched_patterns": [],
            "opening_is_reported": False,
        }

    matched: List[str] = []
    confidence = 0.0
    opening_is_reported = False
    opening_text = text[:300]

    # 1. schemi forti, cercati nell'apertura
    for pat in _STRONG_PATTERNS:
        if pat.search(opening_text):
            label = f"strong_opening:{pat.pattern[:60]}"
            matched.append(label)
            confidence = max(confidence, 0.90)
            opening_is_reported = True
            logger.debug(f"[REPORTED_SPEECH] Strong match: {label}")

    # 2. schemi normali, cercati in tutto il testo
    for pat in _REGULAR_PATTERNS:
        if pat.search(text):
            label = f"regular:{pat.pattern[:60]}"
            matched.append(label)
            confidence = max(confidence, 0.60)

    # 3. citazione attribuita nel testo (segnale forte)
    m = _ATTRIBUTED_INLINE_QUOTE.search(text)
    if m:
        matched.append("attributed_inline_quote")
        confidence = max(confidence, 0.85)
        if m.start() < 200:
            opening_is_reported = True
            confidence = max(confidence, 0.90)

    # soglia a 0.75: gli schemi normali (0.60) da soli davano troppi falsi
    # positivi su posizioni dirette in prima persona (segnalato «Noi chiediamo
    # il pieno riconoscimento…» di Schlein, osservato il 23/07/2026), proprio il
    # materiale di sostanza di PD e AVS. Da soli non bastano più: serve uno
    # schema forte (0.85-0.90) o una citazione attribuita (0.85+).
    has_reported = confidence >= 0.75

    return {
        "has_reported_speech": has_reported,
        "confidence": round(confidence, 2),
        "matched_patterns": matched,
        "opening_is_reported": opening_is_reported,
    }


def annotate_evidence_with_reported_speech(
    evidence_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Segna su ogni passo l'esito del controllo sul discorso riportato.

    Modifica i passi sul posto (chiave 'reported_speech') e restituisce la
    stessa lista. Per ogni passo segnalato scrive un warning, così nel log
    della pipeline si vede quali sono.
    """
    flagged = 0
    for e in evidence_list:
        text = e.get("quote_text", "") or e.get("chunk_text", "")
        result = detect_reported_speech(text)
        e["reported_speech"] = result
        if result["has_reported_speech"]:
            flagged += 1
            logger.warning(
                f"[REPORTED_SPEECH] Chunk {e.get('evidence_id', '?')} "
                f"({e.get('speaker_name', '?')}) flagged "
                f"(confidence={result['confidence']:.2f}, "
                f"opening={result['opening_is_reported']}): "
                f"{text[:120]!r}"
            )

    if flagged:
        logger.info(
            f"[REPORTED_SPEECH] {flagged}/{len(evidence_list)} chunks flagged as reported speech"
        )

    return evidence_list
