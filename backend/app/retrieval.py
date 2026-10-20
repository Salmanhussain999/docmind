"""
Hybrid retrieval: keyword search (SQLite FTS5, BM25) and vector search (cosine similarity),
merged with Reciprocal Rank Fusion.

Why both? Vector search finds passages that mean the same thing in different words; keyword
search nails exact terms (names, error codes, clause numbers) that embeddings tend to blur.
RRF combines the two ranked lists without having to calibrate their very different scores.
"""

import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .db import connect
from .embeddings import Embedder

RRF_K = 60  # standard constant from the original RRF paper; dampens the weight of top ranks


@dataclass
class Passage:
    chunk_id: int
    document_id: str
    document_name: str
    page: int
    text: str
    score: float


class VectorIndex:
    """Keeps each document's embedding matrix in memory so a query is a single matrix multiply."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._lock = threading.Lock()

    def _load(self, document_id: str) -> tuple[np.ndarray, np.ndarray]:
        with self._lock:
            cached = self._cache.get(document_id)
        if cached is not None:
            return cached
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "select id, embedding from chunks where document_id = ? order by id", (document_id,)
            ).fetchall()
        ids = np.array([r["id"] for r in rows], dtype=np.int64)
        matrix = (
            np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
            if rows
            else np.zeros((0, 0), dtype=np.float32)
        )
        with self._lock:
            self._cache[document_id] = (ids, matrix)
        return ids, matrix

    def evict(self, document_id: str) -> None:
        with self._lock:
            self._cache.pop(document_id, None)

    def search(
        self, query_vector: np.ndarray, document_ids: list[str], limit: int
    ) -> list[tuple[int, float]]:
        all_ids, all_scores = [], []
        for document_id in document_ids:
            ids, matrix = self._load(document_id)
            if len(ids) == 0 or matrix.shape[1] != query_vector.shape[0]:
                continue
            all_ids.append(ids)
            all_scores.append(matrix @ query_vector)
        if not all_ids:
            return []
        ids = np.concatenate(all_ids)
        scores = np.concatenate(all_scores)
        top = np.argsort(-scores)[:limit]
        return [(int(ids[i]), float(scores[i])) for i in top]


def fts_query(question: str) -> str | None:
    """Turns free text into a safe FTS5 query: each word quoted (so punctuation can't break the syntax), ORed."""
    words = [w for w in re.findall(r"\w+", question.lower()) if len(w) > 1]
    if not words:
        return None
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words))


def keyword_search(conn: sqlite3.Connection, question: str, document_ids: list[str], limit: int) -> list[int]:
    query = fts_query(question)
    if not query or not document_ids:
        return []
    placeholders = ",".join("?" * len(document_ids))
    rows = conn.execute(
        f"""
        select c.id
        from chunks_fts f
        join chunks c on c.id = f.rowid
        where chunks_fts match ? and c.document_id in ({placeholders})
        order by bm25(chunks_fts)
        limit ?
        """,
        (query, *document_ids, limit),
    ).fetchall()
    return [r["id"] for r in rows]


def reciprocal_rank_fusion(*rankings: list[int], k: int = RRF_K) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


class Retriever:
    def __init__(self, db_path: Path, embedder: Embedder, index: VectorIndex):
        self.db_path = db_path
        self.embedder = embedder
        self.index = index

    def search(self, question: str, document_ids: list[str], top_k: int) -> list[Passage]:
        candidates = top_k * 4
        vector_hits = self.index.search(self.embedder.embed_query(question), document_ids, candidates)

        with connect(self.db_path) as conn:
            keyword_hits = keyword_search(conn, question, document_ids, candidates)
            fused = reciprocal_rank_fusion([cid for cid, _ in vector_hits], keyword_hits)
            best = sorted(fused, key=fused.__getitem__, reverse=True)[:top_k]
            if not best:
                return []
            placeholders = ",".join("?" * len(best))
            rows = conn.execute(
                f"""
                select c.id, c.document_id, d.name, c.page, c.text
                from chunks c join documents d on d.id = c.document_id
                where c.id in ({placeholders})
                """,
                best,
            ).fetchall()

        by_id = {r["id"]: r for r in rows}
        return [
            Passage(
                chunk_id=cid,
                document_id=by_id[cid]["document_id"],
                document_name=by_id[cid]["name"],
                page=by_id[cid]["page"],
                text=by_id[cid]["text"],
                score=round(fused[cid], 5),
            )
            for cid in best
            if cid in by_id
        ]
