"""Retrieval backends: BM25 always, dense vectors optionally.

The default is lexical (BM25, implemented here in numpy) rather than dense
embeddings. That is a considered choice for this specific corpus, not a
shortcut:

* The corpus is a few hundred chunks of German tax and administrative guidance.
  The queries that matter contain the exact terms the documents use -
  "Kleinunternehmerregelung", "Fragebogen zur steuerlichen Erfassung",
  "Nebentaetigkeit". BM25 is extremely strong on precisely that shape, and a
  384-dimension general-purpose embedding is weaker at rare German compounds
  than at English prose.
* It needs no model download, no API key, no ONNX runtime and no network. The
  product's knowledge base therefore works on a fresh clone, in CI, and in a
  demo room with no wifi - which is when it is most likely to be needed.
* It is explainable. When retrieval returns the wrong passage, the term scores
  say why.

Dense retrieval is available and is the better choice as the corpus grows or
goes multilingual. Turning it on is one environment variable, and the store
runs both and fuses the rankings.
"""

from __future__ import annotations

import logging
import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from app.config import EmbeddingBackend, Settings, get_settings

logger = logging.getLogger(__name__)

#: BM25 parameters. k1 controls term-frequency saturation, b the length
#: normalisation. These are the standard values and there is no evidence in
#: this corpus for tuning them.
BM25_K1 = 1.5
BM25_B = 0.75

#: Compound expansion. Only terms this long are expanded - shorter ones appear
#: inside too many unrelated words to be evidence of anything.
COMPOUND_MIN_LENGTH = 6
COMPOUND_MAX_EXPANSIONS = 5
COMPOUND_WEIGHT = 0.6

_TOKEN = re.compile(r"[\wäöüßÄÖÜ]+", re.UNICODE)

#: German and English function words. Removing them stops "die" and "the"
#: dominating the length normalisation.
_STOPWORD_TEXT = (
    "der die das den dem des ein eine einer eines einem einen und oder aber "
    "ist sind war waren wird werden wurde kann koennen muss muessen soll "
    "fuer von mit bei aus auf in im an am zu zum zur nach ueber unter vor "
    "nicht auch nur noch wenn als wie dass sich es sie er ich du wir ihr "
    "the a an and or but is are was were be been being of for with by from "
    "to at in on this that these those it its as if not only also can may"
)

#: Interrogatives and generic verbs. Removed for the same reason as function
#: words, but worth naming separately: they are what a *question* is made of,
#: and leaving them in inflated the relevance signal in
#: :func:`app.services.tax_education.term_coverage` to the point where "how do I
#: bake sourdough bread" scored as 40% covered by a corpus of German tax law -
#: because "how" and "do" appear in it.
_QUESTION_WORD_TEXT = (
    "what which who whom whose where when why how do does did done have has had "
    "should would could must need needs needed get gets got make makes made "
    "want wants please tell explain about many much long there here "
    "my me mine your yours our ours their theirs his her hers "
    "mein meine meinem meinen ihr ihre sein seine unser unsere "
    "was wo wer wie wann warum welche welcher welches wieviel darf "
    "brauche brauchen habe haben bitte erklaeren"
)
_STOPWORDS = frozenset(_STOPWORD_TEXT.split()) | frozenset(_QUESTION_WORD_TEXT.split())


#: German text is written with umlauts and transliterated without them, often in
#: the same document - "Nebentätigkeit" in the prose, "Nebentaetigkeit" in a
#: filename or a user's question typed on a non-German keyboard. Folding one
#: into the other is standard practice for German retrieval, and without it a
#: question about Nebentaetigkeit misses a document that is entirely about it.
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def fold(text: str) -> str:
    return text.lower().translate(_UMLAUTS)


def tokenise(text: str) -> list[str]:
    return [
        token
        for token in (fold(m.group(0)) for m in _TOKEN.finditer(text))
        if token not in _STOPWORDS and len(token) > 1
    ]


# ------------------------------------------------------------------- lexical


@dataclass
class BM25Index:
    """An in-memory BM25 index. Rebuilt from the database on startup.

    In-memory is right at this scale: the whole corpus is well under a
    megabyte, and an exhaustive scan takes microseconds. It is stated here so
    the limit is visible - at a hundred thousand chunks this would need to move
    into Postgres full-text search.
    """

    documents: list[list[str]] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    _df: Counter[str] = field(default_factory=Counter)
    _lengths: np.ndarray = field(default_factory=lambda: np.zeros(0))
    _avg_length: float = 0.0

    def build(self, chunks: list[tuple[str, str]]) -> None:
        """``chunks`` is a list of ``(chunk_id, text)``."""
        self.ids = [chunk_id for chunk_id, _ in chunks]
        self.documents = [tokenise(text) for _, text in chunks]
        self._df = Counter()
        for tokens in self.documents:
            self._df.update(set(tokens))
        self._lengths = np.array([len(d) for d in self.documents], dtype=float)
        self._avg_length = float(self._lengths.mean()) if len(self._lengths) else 0.0

    def expand(self, term: str) -> list[tuple[str, float]]:
        """A query term plus its compound relatives, each with a weight.

        German forms compounds freely, and BM25 matches tokens exactly. Without
        this, a question about "Nebentaetigkeit" retrieves *nothing* from a
        document whose every paragraph is about "Nebentaetigkeitsklausel" - the
        retriever is not wrong, the vocabulary simply does not line up.

        Exact matches keep full weight. Compound relatives are discounted,
        because "Umsatzsteuer" appearing inside "Umsatzsteuer-Identifikations-
        nummer" is weaker evidence than the word itself.
        """
        if term in self._df:
            return [(term, 1.0)]
        if len(term) < COMPOUND_MIN_LENGTH:
            return []
        related = [
            word
            for word in self._df
            if len(word) >= COMPOUND_MIN_LENGTH and (term in word or word in term)
        ]
        related.sort(key=len)
        return [(word, COMPOUND_WEIGHT) for word in related[:COMPOUND_MAX_EXPANSIONS]]

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        if not self.documents:
            return []
        query_terms = tokenise(query)
        if not query_terms:
            return []
        total = len(self.documents)
        scores = np.zeros(total, dtype=float)

        # Expand first, then de-duplicate: two query terms may expand onto the
        # same corpus token, and it should not be counted twice.
        weighted: dict[str, float] = {}
        for term in set(query_terms):
            for match, weight in self.expand(term):
                weighted[match] = max(weighted.get(match, 0.0), weight)

        for term, weight in weighted.items():
            df = self._df.get(term, 0)
            if df == 0:
                continue
            # Standard BM25 IDF with the +0.5 smoothing, floored at zero so a
            # term appearing in almost every document cannot subtract score.
            idf = max(0.0, math.log(1 + (total - df + 0.5) / (df + 0.5)))
            for index, tokens in enumerate(self.documents):
                tf = tokens.count(term)
                if tf == 0:
                    continue
                norm = 1 - BM25_B + BM25_B * (self._lengths[index] / (self._avg_length or 1))
                scores[index] += weight * idf * (tf * (BM25_K1 + 1)) / (tf + BM25_K1 * norm)

        order = np.argsort(-scores)[:top_k]
        return [(self.ids[i], float(scores[i])) for i in order if scores[i] > 0]

    @property
    def size(self) -> int:
        return len(self.documents)


# --------------------------------------------------------------------- dense


class Embedder(ABC):
    name: str = "abstract"
    dimension: int = 0

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def available(self) -> bool:
        return True


class NullEmbedder(Embedder):
    """No dense embeddings. The default, and not an error."""

    name = "none"
    dimension = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        return []

    @property
    def available(self) -> bool:
        return False


class LocalEmbedder(Embedder):
    """On-device via fastembed (ONNX, no torch). Requires the ``local-embed`` extra.

    The first call downloads about 130 MB and caches it, so it needs network
    access once. After that it is free and offline - which is why it is the
    recommended upgrade over a hosted endpoint for a corpus that does not move.
    """

    name = "local"
    dimension = 384

    def __init__(self, model_name: str) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as error:  # pragma: no cover - depends on install extras
            raise RuntimeError(
                "Local embeddings need the 'local-embed' extra: uv sync --extra local-embed"
            ) from error
        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, vector)) for vector in self._model.embed(texts)]


class OpenAIEmbedder(Embedder):
    """Hosted embeddings. Bills per call; used only when explicitly configured."""

    name = "openai"
    dimension = 1536

    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        self._key = api_key
        self._model = model
        self._timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            json={"input": texts, "model": self._model},
            headers={"Authorization": f"Bearer {self._key}"},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return [item["embedding"] for item in payload["data"]]


def build_embedder(settings: Settings | None = None) -> Embedder:
    settings = settings or get_settings()
    match settings.embedding_backend:
        case EmbeddingBackend.LOCAL:
            try:
                return LocalEmbedder(settings.local_embedding_model)
            except RuntimeError:
                logger.warning("local embeddings unavailable; falling back to lexical retrieval")
                return NullEmbedder()
        case EmbeddingBackend.OPENAI:
            key = settings.openai_api_key.get_secret_value()
            if not key:
                logger.warning("no OpenAI key; falling back to lexical retrieval")
                return NullEmbedder()
            return OpenAIEmbedder(key, settings.openai_embedding_model)
        case _:
            return NullEmbedder()


def cosine_similarity(query: list[float], matrix: np.ndarray) -> np.ndarray:
    vector = np.asarray(query, dtype=float)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return np.zeros(matrix.shape[0])
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    scores: np.ndarray = (matrix @ vector) / (norms * norm)
    return scores


def reciprocal_rank_fusion(
    rankings: list[list[tuple[str, float]]], *, k: int = 60
) -> list[tuple[str, float]]:
    """Combine several rankings by rank rather than by score.

    Chosen over score-weighted fusion because BM25 scores and cosine
    similarities are not on comparable scales, and normalising them introduces
    a tuning parameter that would need data this product does not yet have.
    """
    fused: dict[str, float] = {}
    for ranking in rankings:
        for position, (identifier, _) in enumerate(ranking):
            fused[identifier] = fused.get(identifier, 0.0) + 1.0 / (k + position + 1)
    return sorted(fused.items(), key=lambda item: item[1], reverse=True)
