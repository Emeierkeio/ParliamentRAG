"""
LLM stance classification for the semantic compass.

Embedding projection onto pole-difference vectors measures LEXICAL similarity
to the pole descriptions, not the speaker's position: a speech rebutting a
pole quotes its vocabulary and lands on that pole, and off-topic fragments get
amplified noise (empirically ~1% of variance lies along the anchored axes).

This module replaces the projection step: each fragment is scored by an LLM
against the two generated axes, per axis in [-1, +1] (+1 = positive pole) or
null when the fragment takes no position. Rebuttals are handled explicitly in
the prompt. Batched + parallel calls keep latency at one request wave.
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from ...config import get_config
from ...key_pool import make_client

logger = logging.getLogger(__name__)

StanceScore = Tuple[Optional[float], Optional[float]]

PROMPT_HEADER = """Sei un analista del dibattito parlamentare italiano. Per ogni intervento \
numerato, valuta la POSIZIONE SOSTENUTA DALL'ORATORE rispetto a due assi di disaccordo.

Asse 1 — {axis1_name}:
  polo positivo (+1): {axis1_pos_label} — {axis1_pos_desc}
  polo negativo (-1): {axis1_neg_label} — {axis1_neg_desc}
Asse 2 — {axis2_name}:
  polo positivo (+1): {axis2_pos_label} — {axis2_pos_desc}
  polo negativo (-1): {axis2_neg_label} — {axis2_neg_desc}

Regole:
- Per ogni asse un punteggio in [-1, 1]: +1 pieno sostegno al polo positivo, -1 pieno \
sostegno al polo negativo, valori intermedi per posizioni sfumate o parziali.
- null se l'intervento NON prende posizione su quell'asse (procedura, cronaca, altro tema).
- ATTENZIONE alle confutazioni: chi NEGA o critica la tesi di un polo sta dal lato OPPOSTO. \
"Non è vero che X" conta come opposizione al polo che sostiene X, anche se ne usa le parole.
- Giudica solo ciò che l'oratore afferma o chiede, non il partito di appartenenza.
- Rispondi SOLO con JSON valido: {{"scores": [{{"i": <numero>, "a1": <num|null>, "a2": <num|null>}}, ...]}} \
con esattamente una voce per ogni intervento.

Interventi:
"""


class StanceClassifier:
    """Batch LLM stance scoring of fragments against two semantic axes."""

    def __init__(self, config: Optional[dict] = None):
        if config is None:
            config = get_config().load_config()
        stance_config = config.get("compass", {}).get("stance", {})
        self.model = stance_config.get("model", "gpt-4.1-mini")
        self.batch_size = stance_config.get("batch_size", 25)
        self.max_workers = stance_config.get("max_workers", 8)
        self.max_fragments = stance_config.get("max_fragments", 200)
        self.text_clip = stance_config.get("text_clip", 700)
        self.client = make_client()

    def classify(self, fragments: List, semantic_axes) -> Dict[str, StanceScore]:
        """
        Score fragments against the two axes.

        Returns {fragment_id: (a1, a2)} for every fragment that was classified;
        each score is in [-1, 1] or None (no position on that axis). Fragments
        beyond max_fragments or in failed batches are absent from the result.

        Raises if every batch fails (caller falls back to embedding projection).
        """
        targets = fragments[: self.max_fragments]
        if len(fragments) > self.max_fragments:
            logger.info(
                f"Stance: classifying first {self.max_fragments} of "
                f"{len(fragments)} fragments (retrieval order)")

        header = self._build_header(semantic_axes)
        batches = [
            targets[i:i + self.batch_size]
            for i in range(0, len(targets), self.batch_size)
        ]

        results: Dict[str, StanceScore] = {}
        failed = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for batch, scores in zip(
                batches, pool.map(lambda b: self._classify_batch(header, b), batches)
            ):
                if scores is None:
                    failed += 1
                    continue
                results.update(scores)

        if failed == len(batches):
            raise RuntimeError(f"All {failed} stance batches failed")
        if failed:
            logger.warning(f"Stance: {failed}/{len(batches)} batches failed, partial result")

        n_stance = sum(1 for s in results.values() if s[0] is not None or s[1] is not None)
        logger.info(
            f"Stance: classified {len(results)} fragments, "
            f"{n_stance} take a position on at least one axis")
        return results

    def _build_header(self, semantic_axes) -> str:
        a1, a2 = semantic_axes.axes[0], semantic_axes.axes[1]
        return PROMPT_HEADER.format(
            axis1_name=a1.name or "asse 1",
            axis1_pos_label=a1.positive.label, axis1_pos_desc=a1.positive.description,
            axis1_neg_label=a1.negative.label, axis1_neg_desc=a1.negative.description,
            axis2_name=a2.name or "asse 2",
            axis2_pos_label=a2.positive.label, axis2_pos_desc=a2.positive.description,
            axis2_neg_label=a2.negative.label, axis2_neg_desc=a2.negative.description,
        )

    def _classify_batch(self, header: str, batch: List) -> Optional[Dict[str, StanceScore]]:
        """Classify one batch; returns None on failure (batch dropped)."""
        lines = [
            f"[{i + 1}] {(f.text or '')[: self.text_clip]}"
            for i, f in enumerate(batch)
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": header + "\n".join(lines)}],
                temperature=0.0,
                max_tokens=40 * len(batch) + 100,
                response_format={"type": "json_object"},
            )
            payload = json.loads(response.choices[0].message.content)
            by_index = {}
            for entry in payload.get("scores", []):
                idx = int(entry.get("i", 0)) - 1
                if 0 <= idx < len(batch):
                    by_index[idx] = (
                        self._clamp(entry.get("a1")),
                        self._clamp(entry.get("a2")),
                    )
            return {
                f.id: by_index.get(i, (None, None))
                for i, f in enumerate(batch)
            }
        except Exception as e:
            logger.warning(f"Stance batch of {len(batch)} failed: {e}")
            return None

    @staticmethod
    def _clamp(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return max(-1.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return None
