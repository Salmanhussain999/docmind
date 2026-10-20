"""Background pipeline: extract text, chunk it, embed it, store it."""

import logging
from pathlib import Path

import numpy as np

from .config import Settings
from .db import connect
from .embeddings import Embedder, EmbeddingUnavailable
from .ingest.chunking import chunk_pages
from .ingest.extract import ExtractionError, extract_pages
from .retrieval import VectorIndex

log = logging.getLogger("docmind.ingestion")


def ingest_document(
    document_id: str,
    file_path: Path,
    suffix: str,
    settings: Settings,
    embedder: Embedder,
    index: VectorIndex,
) -> None:
    try:
        pages = extract_pages(file_path.read_bytes(), suffix, settings.max_pages)
        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        vectors = embedder.embed_passages([c.text for c in chunks]).astype(np.float32)

        with connect(settings.db_path) as conn:
            exists = conn.execute("select 1 from documents where id = ?", (document_id,)).fetchone()
            if not exists:  # deleted while we were processing
                return
            conn.executemany(
                "insert into chunks (document_id, page, ordinal, text, embedding) values (?, ?, ?, ?, ?)",
                [
                    (document_id, c.page, c.ordinal, c.text, v.tobytes())
                    for c, v in zip(chunks, vectors, strict=True)
                ],
            )
            conn.execute(
                "update documents set status = 'ready', page_count = ?, chunk_count = ? where id = ?",
                (max(p.number for p in pages), len(chunks), document_id),
            )
        index.evict(document_id)
        log.info("Ingested %s: %d pages, %d chunks", document_id, len(pages), len(chunks))

    except (ExtractionError, EmbeddingUnavailable) as exc:
        _fail(settings, document_id, str(exc))
    except Exception:
        log.exception("Ingestion failed for %s", document_id)
        _fail(settings, document_id, "Something went wrong while reading this file. Try uploading it again.")


def _fail(settings: Settings, document_id: str, message: str) -> None:
    with connect(settings.db_path) as conn:
        conn.execute("update documents set status = 'failed', error = ? where id = ?", (message, document_id))
