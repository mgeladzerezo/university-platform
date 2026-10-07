import hashlib
import math
import re
import unicodedata
from typing import Protocol

EMBEDDING_DIMENSIONS = 384


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class E5Embedder:
    """multilingual-e5-small via sentence-transformers (the `embeddings` extra).

    E5 models expect "query: " / "passage: " prefixes and produce 384-dim vectors.
    """

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small"):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"passage: {text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([f"query: {text}"])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


# Compared after diacritics are stripped, hence "sie" and "sa".
_STOPWORDS = frozenset({
    "a", "i", "w", "z", "o", "na", "do", "sie", "jest", "to", "nie", "czy", "jak", "co", "za",
    "od", "po", "dla", "oraz", "lub", "ale", "ze", "sa", "byc", "ten", "ta", "te", "tym", "tego",
    "tej", "przez", "przy", "jakie", "jaki", "jaka", "kiedy", "gdzie", "ile", "mozna", "moge",
    "the", "of", "and", "in", "is", "are", "for", "on", "at", "by", "an", "be", "can", "does",
    "how", "what", "when", "where", "which", "who", "with", "it", "this", "that", "from", "as",
    "or", "my",
})  # fmt: skip


class HashingEmbedder:
    """Deterministic bag-of-words embedder for tests, local runs and the eval set.

    Each token (plus a 5-letter prefix, which roughly absorbs Polish and English
    inflection) is hashed into one of 384 buckets. It captures word overlap, not
    meaning, which is enough to exercise the retrieval pipeline without a model.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for feature in set(self._features(text)):
            digest = hashlib.sha1(feature.encode(), usedforsecurity=False).digest()
            vector[int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    @staticmethod
    def _features(text: str) -> list[str]:
        features = []
        for token in re.findall(r"[a-z0-9]+", _strip_diacritics(text.lower())):
            if token in _STOPWORDS or len(token) < 2:
                continue
            features.append(token)
            if len(token) > 5:
                features.append(f"{token[:5]}*")
        return features


def _strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.replace("ł", "l"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
