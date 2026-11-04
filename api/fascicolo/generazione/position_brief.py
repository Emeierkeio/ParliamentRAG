"""Scheda lessicale della posizione di un gruppo parlamentare, senza chiamate al modello.

La scheda dà a chi scrive le sezioni il quadro della posizione complessiva
del gruppo, perché le citazioni siano scelte e presentate bene. Evita due
errori:
1. scegliere una citazione che non è la più rappresentativa
2. scegliere una citazione che, letta da sola, dice il contrario della
   posizione vera del gruppo
"""
import re
import logging
from typing import List, Dict, Any, Tuple

from .impostazioni import SCHEDA_POSIZIONE
from .reported_speech import detect_reported_speech

logger = logging.getLogger(__name__)


# schemi per stimare l'orientamento: parole chiave, niente modello, veloce e deterministico

# schemi di contrarietà esplicita a una proposta o politica
_AGAINST_PATTERNS = [
    re.compile(r'\b(?:siamo contrari|ci opponiamo|votiamo contro|voteremo contro)\b', re.IGNORECASE),
    re.compile(r'\b(?:non condividiamo|non accettiamo|non possiamo accettare|respingiamo|rifiutiamo)\b', re.IGNORECASE),
    re.compile(r'\b(?:è sbagliato|sarebbe sbagliato|non è la soluzione|non è la strada)\b', re.IGNORECASE),
    re.compile(r'\b(?:è inutile|è dannoso|è controproducente|è rischioso|è pericoloso)\b', re.IGNORECASE),
    re.compile(r'\bnon (?:introdurre|introduciamo|introdurrebbe|introduce)\b', re.IGNORECASE),
    re.compile(r'\b(?:meglio la contrattazione|meglio i contratti collettivi|la contrattazione è sufficiente)\b', re.IGNORECASE),
    re.compile(r'\b(?:parere contrario|voto contrario)\b', re.IGNORECASE),
    re.compile(r'\b(?:non sono obbligati ad introdurre|non è rimesso alla legge)\b', re.IGNORECASE),
    # "contrattazione collettiva" presentata come alternativa al salario minimo
    # per legge: formula ricorrente di Lega e FdI che segnala contrarietà
    re.compile(r'\b(?:contrattazione\s+collettiva)\s+(?:è|resta|rimane|deve\s+restare)\s+(?:la\s+)?(?:strada|soluzione|via|strumento)\b', re.IGNORECASE),
    re.compile(r'\b(?:lasciare|lasciamo|affidare|affidiamo)\s+(?:alla\s+)?contrattazione\b', re.IGNORECASE),
    re.compile(r'\b(?:salario\s+minimo\s+(?:per\s+legge|legale))\s+(?:non\s+è|non\s+sarebbe|non\s+può\s+essere|non\s+serve|non\s+aiuta)\b', re.IGNORECASE),
    re.compile(r'\b(?:i\s+contratti\s+collettivi?|la\s+contrattazione\s+collettiva)\s+(?:già\s+)?(?:tutelano|tutela|garantiscono|garantisce|proteggono|protegge)\b', re.IGNORECASE),
    re.compile(r'\b(?:determinazione|fissazione)\s+(?:d(?:el|i\s+un|ei)\s+salari(?:o\s+\w+)*)\s+(?:\w+\s+){0,3}(?:trattata?|affidata?|rimessa?|demandata?)\s+(?:con\s+la\s+|alla\s+)?contrattazione\b', re.IGNORECASE),
    re.compile(r'\b(?:non\s+è\s+(?:con\s+)?(?:il\s+)?salario\s+minimo\s+(?:per\s+legge\s+)?che\s+(?:si\s+)?(?:tutelano|garantiscono|aiutano|difendono))\b', re.IGNORECASE),
    re.compile(r'\b(?:rischio\s+per\s+la\s+contrattazione|compromett(?:e|ere|erebbe)\s+(?:i\s+)?contratti\s+collettivi)\b', re.IGNORECASE),
]

# schemi di sostegno esplicito a una proposta o politica
_PRO_PATTERNS = [
    re.compile(r'\b(?:siamo favorevoli|siamo d\'accordo|sosteniamo|appoggiamo|approviamo)\b', re.IGNORECASE),
    re.compile(r'\b(?:votiamo a favore|voteremo a favore|voto favorevole)\b', re.IGNORECASE),
    re.compile(r'\b(?:è necessario introdurre|occorre introdurre|bisogna introdurre|serve introdurre)\b', re.IGNORECASE),
    re.compile(r'\b(?:proponiamo|chiediamo|auspichiamo)\s+(?:il|la|un|una|che)\b', re.IGNORECASE),
    re.compile(r'\b(?:è fondamentale|è indispensabile|è doveroso|è urgente)\b', re.IGNORECASE),
    re.compile(r'\b(?:un diritto|diritto fondamentale|diritto dei lavoratori)\b', re.IGNORECASE),
    re.compile(r'\b(?:soglia di dignità|salario dignitoso|retribuzione dignitosa|vita dignitosa)\b', re.IGNORECASE),
    re.compile(r'\b(?:parere favorevole|voto favorevole)\b', re.IGNORECASE),
    re.compile(r'\b(?:9 euro|nove euro)\b', re.IGNORECASE),
]

# schemi di posizione condizionata o sfumata
_CONDITIONAL_PATTERNS = [
    re.compile(r'\b(?:a condizione che|purché|a patto che|subordinatamente)\b', re.IGNORECASE),
    re.compile(r'\b(?:ci asterremo|ci asteniamo|astensione)\b', re.IGNORECASE),
    re.compile(r'\b(?:ma bisogna|tuttavia|però occorre|pur riconoscendo)\b', re.IGNORECASE),
    re.compile(r'\b(?:non sufficiente da sola|non basta|non è sufficiente)\b', re.IGNORECASE),
]


def _detect_direction(texts: List[str]) -> Tuple[str, int, int, int]:
    """Conta i segnali a favore, contro e condizionati in tutti i passi.

    Restituisce (label, pro_hits, against_hits, conditional_hits); label è
    "FAVOREVOLE", "CONTRARIO", "CONDIZIONALE" o "NON DETERMINATO".
    """
    pro_hits = 0
    against_hits = 0
    cond_hits = 0

    for text in texts:
        for p in _PRO_PATTERNS:
            if p.search(text):
                pro_hits += 1
        for p in _AGAINST_PATTERNS:
            if p.search(text):
                against_hits += 1
        for p in _CONDITIONAL_PATTERNS:
            if p.search(text):
                cond_hits += 1

    if against_hits == 0 and pro_hits == 0 and cond_hits == 0:
        return "NON DETERMINATO", pro_hits, against_hits, cond_hits

    # condizionale vince solo se favore e contro distano al massimo uno
    if cond_hits > 0 and abs(pro_hits - against_hits) <= 1:
        return "CONDIZIONALE", pro_hits, against_hits, cond_hits

    if against_hits > pro_hits:
        return "CONTRARIO", pro_hits, against_hits, cond_hits
    if pro_hits > against_hits:
        return "FAVOREVOLE", pro_hits, against_hits, cond_hits

    # non si arriva qui con cond_hits > 0: la parità favore/contro è presa sopra
    if cond_hits > 0:
        return "CONDIZIONALE", pro_hits, against_hits, cond_hits

    return "NON DETERMINATO", pro_hits, against_hits, cond_hits


class PositionBriefBuilder:
    """Scheda della posizione di un gruppo parlamentare, dai suoi passi.

    La scheda contiene:
    1. orientamento stimato (complessivo, per anno, in evoluzione o in conflitto)
    2. oratori principali del gruppo
    3. estratti dei primi max_chunks passi, nell'ordine di chi chiama
    4. avvisi sul discorso riportato

    Entra nel prompt di chi scrive le sezioni, così il modello conosce la
    posizione complessiva del gruppo prima di scegliere le citazioni.
    """

    def __init__(self):
        brief_config = SCHEDA_POSIZIONE

        self.enabled = brief_config.get("enabled", True)
        self.max_chunks = brief_config.get("max_chunks", 5)
        self.chars_per_chunk = brief_config.get("chars_per_chunk", 200)

    @staticmethod
    def _truncate_at_boundary(text: str, max_chars: int) -> str:
        """Taglia il testo alla fine di una frase o di un inciso."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        min_pos = max_chars // 3
        for punct in '.;!?':
            pos = truncated.rfind(punct)
            if pos > min_pos:
                return truncated[:pos + 1].rstrip()
        pos = truncated.rfind(',')
        if pos > min_pos:
            return truncated[:pos].rstrip()
        pos = truncated.rfind(' ')
        if pos > min_pos:
            return truncated[:pos].rstrip()
        return truncated.rstrip()

    @staticmethod
    def _direction_by_period(evidence_texts: List[tuple]) -> Dict[str, str]:
        """Stima l'orientamento anno per anno.

        evidence_texts è una lista di tuple (anno o None, testo). Restituisce
        {anno: orientamento} per gli anni con almeno un testo datato.
        """
        by_year: Dict[str, List[str]] = {}
        for year, text in evidence_texts:
            if year:
                by_year.setdefault(year, []).append(text)

        directions = {}
        for year, texts in sorted(by_year.items()):
            label, _, _, _ = _detect_direction(texts)
            directions[year] = label
        return directions

    def build_brief(
        self,
        evidence: List[Dict[str, Any]],
        party: str,
    ) -> str:
        """Scrive la scheda di posizione dai passi del gruppo.

        La scheda è un'ipotesi ricavata da schemi lessicali, non un fatto: il
        testo chiede al modello di verificare sui passi le contraddizioni
        apparenti invece di scartarle.

        evidence è la lista dei passi in ordine di priorità (l'alternanza per
        oratore della pipeline) e se ne usano i primi max_chunks; party è il
        nome del gruppo. Restituisce la scheda in italiano, o "" se è spenta
        o non ci sono passi.
        """
        if not self.enabled or not evidence:
            return ""

        top_evidence = evidence[:self.max_chunks]

        speakers = []
        seen_speakers: set = set()
        for e in top_evidence:
            name = e.get("speaker_name", "")
            if name and name not in seen_speakers:
                speakers.append(name)
                seen_speakers.add(name)

        key_passages = []
        full_texts = []  # testo intero, non tagliato, per stimare l'orientamento
        dated_texts = []  # (anno, testo) per l'orientamento per periodo
        reported_speech_count = 0
        reported_speech_opening_count = 0
        for e in top_evidence:
            text = e.get("quote_text", "") or e.get("chunk_text", "")
            if not text:
                continue
            full_texts.append(text)
            year = str(e.get("date", ""))[:4] or None
            dated_texts.append((year if year and year.isdigit() else None, text))
            passage = self._truncate_at_boundary(text, self.chars_per_chunk)
            if passage:
                key_passages.append(passage)

            # prima la segnatura di write_sections, altrimenti si controlla ora
            rs_info = e.get("reported_speech") or detect_reported_speech(text)
            if rs_info.get("has_reported_speech"):
                reported_speech_count += 1
                if rs_info.get("opening_is_reported"):
                    reported_speech_opening_count += 1

        if not key_passages:
            return ""

        # orientamento dai testi interi, complessivo e per periodo
        direction, pro_hits, against_hits, cond_hits = _detect_direction(full_texts)
        period_directions = self._direction_by_period(dated_texts)
        determined_periods = {
            y: d for y, d in period_directions.items()
            if d in ("FAVOREVOLE", "CONTRARIO", "CONDIZIONALE")
        }
        evolving = len(set(determined_periods.values())) > 1

        # segnali opposti nello stesso periodo senza una maggioranza chiara:
        # posizione in conflitto, non si fa la media
        conflicting = (
            not evolving
            and pro_hits > 0 and against_hits > 0
            and abs(pro_hits - against_hits) <= 1
        )

        logger.info(
            f"[POSITION_BRIEF] {party}: direction={direction} "
            f"(pro={pro_hits}, contro={against_hits}, cond={cond_hits}, "
            f"periods={period_directions}, evolving={evolving})"
        )

        if evolving:
            timeline = "; ".join(
                f"{y}: {d}" for y, d in sorted(determined_periods.items())
            )
            direction_label = (
                f"IN EVOLUZIONE nel tempo ({timeline}) — NON fondere i periodi "
                f"in una posizione media, racconta l'evoluzione ancorata alle date"
            )
        elif conflicting:
            direction_label = (
                "CONFLITTUALE (segnali contrastanti nello stesso periodo) — "
                "NON forzare una sintesi unica, riporta la tensione interna"
            )
        elif direction == "CONTRARIO":
            direction_label = "CONTRARIO alla proposta/politica"
        elif direction == "FAVOREVOLE":
            direction_label = "FAVOREVOLE alla proposta/politica"
        elif direction == "CONDIZIONALE":
            direction_label = "CONDIZIONALE / SFUMATO (né puramente pro né puramente contro)"
        else:
            direction_label = "NON DETERMINATO dai testi disponibili"

        brief_lines = [
            f"IPOTESI DI POSIZIONE DEL GRUPPO ({party}) — stima preliminare "
            f"derivata da pattern lessicali, NON un fatto verificato:",
            f"Orientamento stimato: {direction_label}",
            "Usa questa ipotesi come contesto, non come vincolo: se la citazione",
            "   selezionata sembra contraddire l'orientamento stimato, verifica nel",
            "   testo se è la posizione reale (critica e sostegno sono entrambe",
            "   evidenze valide) o una premessa retorica/discorso riportato.",
            f"Principali oratori: {', '.join(speakers[:3])}",
        ]

        if reported_speech_count > 0:
            warning_level = "ALTA PRIORITÀ" if reported_speech_opening_count > 0 else "ATTENZIONE"
            brief_lines.append(
                f"{warning_level} — DISCORSO RIPORTATO: {reported_speech_count} dei "
                f"{len(top_evidence)} testi analizzati contengono citazioni di ALTRI soggetti "
                f"(avversari, colleghi, media) riportate dal deputato per confutarle o rispondervi."
            )
            if reported_speech_opening_count > 0:
                brief_lines.append(
                    f"   MASSIMA ATTENZIONE: {reported_speech_opening_count} testo/i INIZIANO con discorso riportato: "
                    f"massimo rischio di inversione di posizione. "
                    f"La posizione VERA del gruppo è nella RISPOSTA del deputato, "
                    f"NON nelle parole altrui che vengono citate."
                )

        brief_lines.append(f"Sintesi dei {len(key_passages)} interventi più autorevoli:")

        for i, passage in enumerate(key_passages, 1):
            brief_lines.append(f"  {i}. «{passage}»")

        return "\n".join(brief_lines)
