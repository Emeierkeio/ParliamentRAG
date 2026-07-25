"""
Semantically anchored compass axes (IC-1 replacement).

Instead of discovering axes post-hoc with PCA (which captures the dominant
*lexical* variance, not political dimensions), the LLM generates two explicit
pole pairs for the query (e.g. "più spesa pubblica" vs "rigore di bilancio"),
each pole is embedded with the same model used for the chunk embeddings, and
the axis is the difference of the pole vectors. Evidence is then projected
onto axes that are readable *by construction*: the user sees the pole labels
before the points, and the same pole texts re-embedded later yield the same
axes — which makes positions comparable across time windows (timeline use).

The generator is deterministic-ish (temperature 0) and cached per query, so
repeated calls for the same query — including future per-window timeline
recomputation — reuse identical axes.
"""
import json
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ...config import get_config
from ...key_pool import make_client

logger = logging.getLogger(__name__)

# Poles more parallel than this are two phrasings of the same axis: the
# compass degrades gracefully (warning + orthogonalized second axis).
DEFAULT_MAX_AXIS_COS = 0.85

PROMPT = """Sei un analista politico italiano. Per la domanda di un utente su un tema \
di dibattito parlamentare, definisci DUE assi di disaccordo politico, specifici per il tema.

Regole:
- Ogni asse ha due poli OPPOSTI, formulati come posizioni sostantive (es. "più spesa pubblica" \
contro "rigore di bilancio"), MAI come "favorevoli/contrari" generici.
- I due assi devono essere dimensioni INDIPENDENTI del dibattito (non riformulazioni).
- Linguaggio neutrale: nessun nome di partito o persona, nessuna connotazione di merito.
- label: 2-5 parole. description: una frase che esprime la posizione tipica di quel polo, \
ricca dei termini con cui quella posizione viene argomentata in aula (serve per l'embedding).
- Rispondi SOLO con JSON valido:
{"axes": [
  {"name": "...", "positive": {"label": "...", "description": "..."},
   "negative": {"label": "...", "description": "..."}},
  {"name": "...", "positive": {"label": "...", "description": "..."},
   "negative": {"label": "...", "description": "..."}}
]}

Tema: {query}"""


@dataclass
class SemanticPole:
    label: str
    description: str


@dataclass
class SemanticAxis:
    name: str
    positive: SemanticPole
    negative: SemanticPole
    vector: np.ndarray = field(repr=False, default=None)


@dataclass
class SemanticAxes:
    axes: List[SemanticAxis]
    axis_cos: float  # |cos| between the two raw axis vectors, before orthogonalization
    correlated: bool

    def matrix(self) -> np.ndarray:
        """Axis vectors as a [2, D] array (rows are unit vectors)."""
        return np.array([a.vector for a in self.axes])


_cache: dict = {}
_cache_lock = threading.Lock()
_CACHE_MAX = 256


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


class SemanticAxisGenerator:
    """LLM pole generation + pole embedding -> anchored axis vectors."""

    def __init__(self, config: Optional[dict] = None):
        if config is None:
            config = get_config().load_config()
        sem_config = config.get("compass", {}).get("semantic_axes", {})
        self.model = sem_config.get("model", "gpt-4.1-mini")
        self.max_axis_cos = sem_config.get("max_axis_cos", DEFAULT_MAX_AXIS_COS)
        self.embedding_model = config.get("llm", {}).get(
            "embedding_model", "text-embedding-3-small")
        self.client = make_client()

    def generate(self, query: str) -> SemanticAxes:
        """Return anchored axes for the query (cached per normalized query)."""
        key = (_normalize_query(query), self.model)
        with _cache_lock:
            if key in _cache:
                return _cache[key]

        axes = self._build(query)

        with _cache_lock:
            if len(_cache) >= _CACHE_MAX:
                _cache.pop(next(iter(_cache)))
            _cache[key] = axes
        return axes

    def _build(self, query: str) -> SemanticAxes:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": PROMPT.replace("{query}", query)}],
            temperature=0.0,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        payload = json.loads(response.choices[0].message.content)
        raw_axes = payload["axes"][:2]
        if len(raw_axes) < 2:
            raise ValueError(f"LLM returned {len(raw_axes)} axes, need 2")

        axes = []
        for raw in raw_axes:
            axes.append(SemanticAxis(
                name=str(raw.get("name", "")),
                positive=SemanticPole(
                    label=str(raw["positive"]["label"]),
                    description=str(raw["positive"]["description"]),
                ),
                negative=SemanticPole(
                    label=str(raw["negative"]["label"]),
                    description=str(raw["negative"]["description"]),
                ),
            ))

        # One embeddings call for the 4 pole texts, same model as the chunks
        # so poles and evidence live in the same vector space.
        pole_texts = []
        for axis in axes:
            for pole in (axis.positive, axis.negative):
                pole_texts.append(f"{pole.label}. {pole.description}")
        emb_response = self.client.embeddings.create(
            input=pole_texts, model=self.embedding_model)
        vectors = [np.array(d.embedding) for d in emb_response.data]

        for i, axis in enumerate(axes):
            v = vectors[2 * i] - vectors[2 * i + 1]  # positive - negative
            norm = np.linalg.norm(v)
            if norm < 1e-8:
                raise ValueError(f"Degenerate axis '{axis.name}': identical poles")
            axis.vector = v / norm

        axis_cos = float(abs(np.dot(axes[0].vector, axes[1].vector)))
        correlated = axis_cos > self.max_axis_cos

        # Gram-Schmidt: make the second axis orthogonal to the first so the
        # 2D plot doesn't double-count the shared component. Labels stay as
        # generated — the residual is still "axis 2 minus what axis 1 covers".
        v2 = axes[1].vector - np.dot(axes[1].vector, axes[0].vector) * axes[0].vector
        v2_norm = np.linalg.norm(v2)
        if v2_norm > 1e-8:
            axes[1].vector = v2 / v2_norm

        logger.info(
            "Semantic axes for %r: [%s <-> %s] x [%s <-> %s], cos=%.2f%s",
            query[:60], axes[0].negative.label, axes[0].positive.label,
            axes[1].negative.label, axes[1].positive.label, axis_cos,
            " (CORRELATED)" if correlated else "",
        )
        return SemanticAxes(axes=axes, axis_cos=axis_cos, correlated=correlated)
