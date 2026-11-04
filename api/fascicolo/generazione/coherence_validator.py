"""Controlla che il testo che introduce una citazione dica la stessa cosa della citazione.

Due livelli: prima la similarità coseno tra embedding (OpenAI
text-embedding-3-small), in ripiego la sovrapposizione di parole di Jaccard
(senza chiamate). La scelta si appoggia a SummaC (Laban et al., TACL 2022: i
modelli NLI battono la sovrapposizione lessicale nel trovare incoerenze) e a
BERTScore (Zhang et al., ICLR 2020: gli embedding contestuali colgono le
parafrasi che Jaccard perde). Oltre alla similarità, un'introduzione positiva
("elogia", "sostiene") non deve introdurre una citazione negativa, e viceversa.
"""
import re
import logging
from typing import Dict, Any, List, Optional

from .contesto import scalare, vettori_piccoli
from .reported_speech import detect_reported_speech

logger = logging.getLogger(__name__)


class CoherenceValidator:
    """Controlla la coerenza di senso tra introduzione e citazione.

    Metodo principale: similarità coseno tra embedding (soglia
    min_coherence_score, 0.6 di base). Ripiego: sovrapposizione di parole di
    Jaccard (soglia fissa 0.2). validate_coherence restituisce un dict in cui
    "is_coherent" unisce il punteggio di similarità ai controlli su tono e
    posizione.
    """

    # parole vuote italiane da togliere (per il ripiego Jaccard)
    STOP_WORDS = {
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
        "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
        "e", "o", "ma", "che", "non", "anche", "come", "questo",
        "quello", "essere", "avere", "fare", "dire", "dovere",
        "potere", "volere", "sapere", "andare", "venire", "stare",
        "del", "della", "dei", "delle", "dello", "degli", "al",
        "alla", "ai", "alle", "allo", "agli", "dal", "dalla",
        "nel", "nella", "nei", "nelle", "nello", "negli", "sul",
        "sulla", "sui", "sulle", "sullo", "sugli", "col", "coi",
        "sono", "sia", "stato", "stata", "stati", "state", "hanno",
        "ha", "ho", "hai", "abbiamo", "avete", "era", "erano",
        "sarà", "saranno", "si", "ci", "vi", "ne", "mi", "ti",
        "loro", "lui", "lei", "noi", "voi", "se", "quando", "dove",
        "perché", "perche", "quindi", "però", "pero", "dunque",
        "così", "cosi", "poi", "già", "gia", "ancora", "sempre",
        "mai", "molto", "poco", "più", "piu", "meno", "tutto",
        "tutti", "tutte", "ogni", "qualche", "alcuni", "alcune",
        "altro", "altri", "altre", "quale", "quali", "quanto",
        "quanti", "quante", "chi", "cosa", "cui", "proprio"
    }

    # indicatori di tono positivo (lode, sostegno)
    POSITIVE_INDICATORS = {
        "sostiene", "difende", "elogia", "promuove", "appoggia",
        "approva", "plaude", "apprezza", "condivide", "supporta",
        "conferma", "ribadisce", "valorizza", "esalta", "celebra"
    }

    # indicatori di tono negativo (critica, opposizione)
    NEGATIVE_INDICATORS = {
        "critica", "denuncia", "contesta", "attacca", "respinge",
        "oppone", "condanna", "stigmatizza", "deplora", "lamenta",
        "controbatte", "rifiuta", "contrasta", "rigetta", "boccia"
    }

    def __init__(
        self,
        min_coherence_score: float = 0.6,
        method: str = "embedding"
    ):
        """Imposta il controllo.

        min_coherence_score è la soglia di similarità tra embedding (0.0-1.0);
        Jaccard non la usa, la sua soglia è fissa a 0.2. method è "embedding"
        (principale) o "jaccard".
        """
        self.min_coherence_score = min_coherence_score
        self.method = method
        self._embedding_available = None  # diventa False al primo errore dell'API

    def _embedding_similarity(self, text_a: str, text_b: str) -> Optional[float]:
        """Similarità coseno tra gli embedding di due testi.

        None se l'API degli embedding non risponde.
        """
        try:
            vec_a, vec_b = vettori_piccoli([text_a, text_b])
            return float(scalare(vec_a, vec_b))
        except Exception as exc:
            logger.warning(f"Embedding coherence check failed: {exc}")
            self._embedding_available = False
            return None

    def _jaccard_similarity(self, text_a: str, text_b: str) -> float:
        """Sovrapposizione di parole di Jaccard (il ripiego)."""
        tokens_a = set(self._tokenize(text_a))
        tokens_b = set(self._tokenize(text_b))

        if not tokens_a or not tokens_b:
            return 0.0

        overlap = tokens_a & tokens_b
        union_size = len(tokens_a | tokens_b)
        return len(overlap) / union_size if union_size > 0 else 0.0

    # schemi con cui l'introduzione presenta il gruppo come favorevole
    _INTRO_PRO_SIGNALS = re.compile(
        r'\b(?:si\s+esprime?\s+a\s+favore|sostien[ei]\s+la\s+necessità|è\s+favorevole|'
        r'appoggia|sostien[ei]|propone|auspica|chiede|ritiene\s+necessario|difende\s+la\s+proposta|'
        r'supporta|promuove|plaude|approva)\b',
        re.IGNORECASE,
    )

    # schemi con cui l'introduzione presenta il gruppo come contrario
    _INTRO_AGAINST_SIGNALS = re.compile(
        r'\b(?:si\s+oppone|è\s+contrario|contesta|critica|respinge|rifiuta|denuncia|'
        r'condanna|stigmatizza|boccia|rigetta|controbatte|contrasta)\b',
        re.IGNORECASE,
    )

    def _stance_alignment_check(
        self,
        intro_text: str,
        quote_text: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Controlla che la posizione attribuita dall'introduzione corrisponda al passo.

        Se il passo contiene discorso riportato (l'oratore cita un avversario),
        la similarità tra embedding resta alta (i due testi parlano dello
        stesso tema) ma la posizione può essere rovesciata.

        Il controllo toglie punti quando:
        1. l'introduzione attribuisce al gruppo una posizione favorevole, e
        2. il passo ha segnali forti di discorso riportato (le parole citate
           sono di un avversario, non dell'oratore).

        Restituisce un dict con:
        - has_stance_issue: bool
        - penalty: float da togliere al punteggio di coerenza
        - reason: str
        """
        result = {
            "has_stance_issue": False,
            "penalty": 0.0,
            "reason": "",
        }

        if not intro_text or not quote_text:
            return result

        # prima la segnatura già sul passo, altrimenti si controlla ora
        if evidence is not None:
            rs_info = evidence.get("reported_speech") or detect_reported_speech(quote_text)
        else:
            rs_info = detect_reported_speech(quote_text)

        if not rs_info.get("has_reported_speech"):
            return result

        intro_is_pro = bool(self._INTRO_PRO_SIGNALS.search(intro_text))
        intro_is_against = bool(self._INTRO_AGAINST_SIGNALS.search(intro_text))

        if intro_is_pro and not intro_is_against:
            # introduzione favorevole su discorso riportato: posizione forse rovesciata.
            # Le penalità 0.30/0.15 non hanno una taratura registrata
            penalty = 0.30 if rs_info.get("opening_is_reported") else 0.15
            result["has_stance_issue"] = True
            result["penalty"] = penalty
            result["reason"] = (
                f"Intro attributes PRO stance but evidence contains reported speech "
                f"(confidence={rs_info['confidence']:.2f}, "
                f"opening={rs_info['opening_is_reported']}). "
                f"Score penalty: -{penalty:.2f}"
            )
            logger.warning(
                f"[STANCE_CHECK] Possible stance inversion: intro=PRO but evidence "
                f"has reported speech (confidence={rs_info['confidence']:.2f}). "
                f"Penalty: -{penalty:.2f}. Intro: '{intro_text[:80]}'"
            )

        return result

    def validate_coherence(
        self,
        intro_text: str,
        quote_text: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Controlla la coerenza di senso tra introduzione e citazione.

        Usa la similarità coseno tra embedding e ripiega su Jaccard quando
        gli embedding non ci sono. evidence, se c'è, porta la segnatura
        reported_speech già calcolata per il controllo sulla posizione.

        Restituisce un dict con is_coherent (punteggio sopra soglia e tono
        concorde), score (0.0-1.0, dopo l'eventuale penalità), method,
        threshold, i campi su tono e posizione e un warning facoltativo.
        """
        if not intro_text or not quote_text:
            return {
                "is_coherent": True,
                "score": 0.0,
                "method": "none",
                "warning": "Empty text - cannot validate",
                "overlap_keywords": [],
                "sentiment_mismatch": False,
                "stance_issue": False,
            }

        intro_sentiment = self._detect_sentiment(intro_text)
        quote_sentiment = self._detect_sentiment(quote_text)
        sentiment_mismatch = (
            intro_sentiment is not None and
            quote_sentiment is not None and
            intro_sentiment != quote_sentiment
        )

        score = 0.0
        method_used = self.method
        overlap_keywords = []

        if self.method == "embedding" and self._embedding_available is not False:
            embedding_score = self._embedding_similarity(intro_text, quote_text)
            if embedding_score is not None:
                score = embedding_score
                method_used = "embedding"
            else:
                score = self._jaccard_similarity(intro_text, quote_text)
                method_used = "jaccard"
                overlap_keywords = list(
                    set(self._tokenize(intro_text)) &
                    set(self._tokenize(quote_text))
                )[:10]
        else:
            score = self._jaccard_similarity(intro_text, quote_text)
            method_used = "jaccard"
            overlap_keywords = list(
                set(self._tokenize(intro_text)) &
                set(self._tokenize(quote_text))
            )[:10]

        # controllo sulla posizione (penalità per discorso riportato), dopo la
        # similarità di base: così una citazione sullo stesso tema ma di verso
        # opposto perde punti anche se la similarità supera la soglia
        stance_result = self._stance_alignment_check(intro_text, quote_text, evidence)
        if stance_result["has_stance_issue"]:
            score = max(0.0, score - stance_result["penalty"])

        if method_used == "embedding":
            threshold = self.min_coherence_score
        else:
            threshold = 0.2  # origine non registrata

        is_coherent = score >= threshold and not sentiment_mismatch

        result = {
            "is_coherent": is_coherent,
            "score": round(score, 3),
            "method": method_used,
            "threshold": threshold,
            "overlap_keywords": overlap_keywords,
            "intro_sentiment": intro_sentiment,
            "quote_sentiment": quote_sentiment,
            "sentiment_mismatch": sentiment_mismatch,
            "stance_issue": stance_result["has_stance_issue"],
            "stance_penalty": stance_result["penalty"],
        }

        if stance_result["has_stance_issue"]:
            result["warning"] = stance_result["reason"]
        elif sentiment_mismatch:
            result["warning"] = (
                f"Sentiment mismatch: intro={intro_sentiment}, "
                f"quote={quote_sentiment}"
            )
            logger.warning(
                f"Coherence: Sentiment mismatch detected - "
                f"intro={intro_sentiment}, quote={quote_sentiment}"
            )
        elif not is_coherent:
            result["warning"] = (
                f"Low {method_used} score: {score:.2f} < {threshold}"
            )
            logger.warning(
                f"Coherence: Low {method_used} score {score:.2f} "
                f"(threshold {threshold})"
            )

        return result

    def _tokenize(self, text: str) -> List[str]:
        """Divide un testo italiano in parole utili (senza parole vuote)."""
        words = re.findall(r'\b[a-zA-ZàèéìòùÀÈÉÌÒÙ]{3,}\b', text.lower())
        return [w for w in words if w not in self.STOP_WORDS]

    def _detect_sentiment(self, text: str) -> Optional[str]:
        """Restituisce "positive", "negative", o None se il tono è misto o neutro."""
        text_lower = text.lower()

        has_positive = any(ind in text_lower for ind in self.POSITIVE_INDICATORS)
        has_negative = any(ind in text_lower for ind in self.NEGATIVE_INDICATORS)

        if has_positive and not has_negative:
            return "positive"
        elif has_negative and not has_positive:
            return "negative"
        else:
            return None

    def validate_all_citations(
        self,
        text_with_citations: str,
        evidence_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Controlla ogni citazione [CIT:id] del testo sui passi di evidence_map.

        Restituisce i conteggi (totali, coerenti, incoerenti), all_coherent,
        average_score e il dettaglio per citazione.
        """
        results = []

        # prende la frase che contiene ogni [CIT:id]. Le citazioni «...» nel
        # testo hanno punteggiatura di fine frase: uno schema ingenuo [^.!?]*
        # si fermava all'ultimo punto dentro la citazione e l'introduzione
        # diventava "»" (coerenza ~0.17 sistematica). I tratti «...» vanno presi interi
        pattern = r'((?:[^.!?«]|«[^»]*»)*\[CIT:([^\]]+)\])'
        matches = re.findall(pattern, text_with_citations)

        for full_match, evidence_id in matches:
            if evidence_id not in evidence_map:
                results.append({
                    "evidence_id": evidence_id,
                    "is_coherent": False,
                    "warning": "Evidence not found in map"
                })
                continue

            evidence = evidence_map[evidence_id]
            quote_text = evidence.get("quote_text") or evidence.get("chunk_text", "")

            # l'introduzione è il testo prima della « di apertura: la citazione
            # non va confrontata con se stessa
            parts = full_match.split(f"[CIT:{evidence_id}]")
            intro = parts[0].strip() if parts else ""
            if "«" in intro:
                before_quote = intro.split("«", 1)[0].strip()
                # se la citazione apre la frase, si tiene la frase senza citazioni
                intro = before_quote or re.sub(r'«[^»]*»', '', intro).strip()

            # il passo ha già la segnatura reported_speech messa da
            # annotate_evidence_with_reported_speech in write_sections: il
            # controllo sulla posizione non la ricalcola
            validation = self.validate_coherence(intro, quote_text, evidence=evidence)
            validation["evidence_id"] = evidence_id
            validation["intro_text"] = intro[:100] + "..." if len(intro) > 100 else intro
            validation["quote_preview"] = quote_text[:100] + "..." if len(quote_text) > 100 else quote_text

            results.append(validation)

        coherent_count = sum(1 for r in results if r.get("is_coherent", False))

        return {
            "total_citations": len(results),
            "coherent_citations": coherent_count,
            "incoherent_citations": len(results) - coherent_count,
            "all_coherent": coherent_count == len(results),
            "average_score": (
                sum(r.get("score", 0) for r in results) / len(results)
                if results else 0
            ),
            "details": results
        }

    def get_incoherent_citations(
        self,
        validation_report: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Dal rapporto del controllo, solo il dettaglio delle citazioni incoerenti."""
        return [
            detail for detail in validation_report.get("details", [])
            if not detail.get("is_coherent", True)
        ]
