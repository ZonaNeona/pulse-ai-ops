"""SQLite storage. Synced CRM/ERP records live in one typed key-value table per kind, so the schema
does not change when a module needs a new field; queries that must be fast get their own columns."""

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any

from pulse.core import clock
from pulse.core.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    kind TEXT NOT NULL,
    id TEXT NOT NULL,
    at TEXT,
    payload TEXT NOT NULL,
    PRIMARY KEY (kind, id)
);
CREATE INDEX IF NOT EXISTS records_kind_at ON records(kind, at);
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    source TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_usage (
    id TEXT PRIMARY KEY,
    day TEXT NOT NULL,
    hour INTEGER NOT NULL,
    visitor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    estimated_usd REAL NOT NULL,
    actual_usd REAL,
    status TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_usage_day ON ai_usage(day);
CREATE INDEX IF NOT EXISTS ai_usage_visitor ON ai_usage(day, visitor_id);
CREATE TABLE IF NOT EXISTS ai_traces (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    question TEXT NOT NULL,
    engine TEXT NOT NULL,
    model TEXT NOT NULL,
    total_ms INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    tokens INTEGER NOT NULL,
    steps_json TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    drafts_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_traces_created ON ai_traces(created_at);
CREATE TABLE IF NOT EXISTS ai_drafts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_drafts_session ON ai_drafts(session_id);

"""


def path() -> str:
    p = get_settings().db_path
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def replace_kind(kind: str, rows: Iterable[tuple[str, str | None, dict[str, Any]]]) -> int:
    """Atomically swap all records of one kind (a full sync of that kind)."""
    data = [(kind, rid, at, json.dumps(payload, ensure_ascii=False, default=str)) for rid, at, payload in rows]
    with connect() as conn:
        conn.execute("DELETE FROM records WHERE kind = ?", (kind,))
        conn.executemany("INSERT INTO records(kind, id, at, payload) VALUES (?, ?, ?, ?)", data)
    return len(data)


def upsert(kind: str, rows: Iterable[tuple[str, str | None, dict[str, Any]]]) -> int:
    """Insert or update records of one kind (a delta sync)."""
    data = [(kind, rid, at, json.dumps(payload, ensure_ascii=False, default=str)) for rid, at, payload in rows]
    with connect() as conn:
        conn.executemany(
            "INSERT INTO records(kind, id, at, payload) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(kind, id) DO UPDATE SET at = excluded.at, payload = excluded.payload",
            data,
        )
    return len(data)


def count(kind: str) -> int:
    with connect() as conn:
        return int(conn.execute("SELECT count(*) FROM records WHERE kind = ?", (kind,)).fetchone()[0])


def load(kind: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT payload FROM records WHERE kind = ? ORDER BY at, id", (kind,)).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def log(source: str, event: str, detail: str, status: str = "success") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO sync_log(at, source, event, detail, status) VALUES (?, ?, ?, ?, ?)",
            (clock.now().isoformat(), source, event, detail, status),
        )


def recent_log(limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM sync_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_setting(key: str, default: Any = None) -> Any:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )
