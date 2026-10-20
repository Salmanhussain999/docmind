"""Embedding providers. Every provider returns L2-normalised float32 vectors, so cosine similarity is a dot product."""

import hashlib
import re
from typing import Protocol

import numpy as np

from .config import Settings


class Embedder(Protocol):
    name: str

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


def normalise(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


class HashEmbedder:
    """
    Feature hashing of words and word pairs into a fixed-size vector. It captures word overlap,
    not meaning, which makes it deterministic and offline: ideal for tests, not for real use.
    """

    name = "hash"

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _vector(self, text: str) -> np.ndarray:
        words = re.findall(r"[a-z0-9]+", text.lower())
        features = words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]
        vec = np.zeros(self.dim, dtype=np.float32)
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[index] += sign
        return vec

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return normalise(np.stack([self._vector(t) for t in texts]))

    def embed_query(self, text: str) -> np.ndarray:
        return normalise(self._vector(text))


class EmbeddingUnavailable(Exception):
    """The embedding model can't be used right now; the message is shown to the user."""


class LocalEmbedder:
    """
    Runs a small embedding model on the CPU with fastembed (ONNX). Free, and nothing leaves the
    machine. The model (~130 MB) downloads on first use, so loading is lazy: the server starts
    even when offline, and an upload explains what went wrong instead of crashing the app.
    """

    name = "local"

    def __init__(self, model: str):
        self.model_name = model
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:  # pragma: no cover - depends on optional extra
                raise EmbeddingUnavailable(
                    "Local embeddings need an extra package: pip install 'docmind[local]'."
                ) from exc
            try:
                self._model = TextEmbedding(model_name=self.model_name)
            except Exception as exc:  # pragma: no cover - network dependent
                raise EmbeddingUnavailable(
                    f"Couldn't download the embedding model {self.model_name}. Check the server's "
                    "internet connection, or set EMBEDDING_PROVIDER=openai."
                ) from exc
        return self._model

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return normalise(np.stack(list(self._load().passage_embed(texts))))

    def embed_query(self, text: str) -> np.ndarray:
        return normalise(next(iter(self._load().query_embed(text))))


class OpenAIEmbedder:
    """Any OpenAI-compatible /embeddings endpoint (OpenAI, Gemini, Ollama, ...)."""

    name = "openai"

    def __init__(self, model: str, base_url: str | None, api_key: str | None):
        from openai import OpenAI

        self.client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")
        self.model = model

    def _embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 64):
            response = self.client.embeddings.create(model=self.model, input=texts[start : start + 64])
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
        return normalise(np.array(vectors))

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([text])[0]


def create_embedder(settings: Settings) -> Embedder:
    match settings.embedding_provider:
        case "hash":
            return HashEmbedder()
        case "openai":
            return OpenAIEmbedder(
                settings.embedding_model, settings.embedding_base_url, settings.embedding_api_key
            )
        case _:
            return LocalEmbedder(settings.embedding_model)
