import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
create table if not exists documents (
    id          text primary key,
    name        text not null,
    media_type  text not null,
    size_bytes  integer not null,
    page_count  integer not null default 0,
    chunk_count integer not null default 0,
    status      text not null check (status in ('processing', 'ready', 'failed')),
    error       text,
    created_at  text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

create table if not exists chunks (
    id          integer primary key,
    document_id text not null references documents(id) on delete cascade,
    page        integer not null,
    ordinal     integer not null,
    text        text not null,
    embedding   blob not null          -- float32 vector, L2-normalised
);
create index if not exists chunks_document_idx on chunks(document_id);

-- Full-text index for keyword (BM25) search, kept in sync with `chunks` by triggers.
create virtual table if not exists chunks_fts using fts5(
    text, content='chunks', content_rowid='id', tokenize='porter unicode61'
);
create trigger if not exists chunks_ai after insert on chunks begin
    insert into chunks_fts(rowid, text) values (new.id, new.text);
end;
create trigger if not exists chunks_ad after delete on chunks begin
    insert into chunks_fts(chunks_fts, rowid, text) values ('delete', old.id, old.text);
end;
"""


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    """A short-lived connection per unit of work. SQLite connections aren't shared across threads."""
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma journal_mode = wal")  # readers don't block the ingestion writer
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
