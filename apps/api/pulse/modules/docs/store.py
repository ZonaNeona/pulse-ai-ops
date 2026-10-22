"""Documents per visitor session. Each visitor gets their own copy of the demo queue, so one person's
"approve" never changes what the next person sees."""

import json
from datetime import datetime
from typing import Any

from pulse.core import clock, db, fmt
from pulse.modules.docs.model import Check, Doc, Field, Step

SCHEMA = """
CREATE TABLE IF NOT EXISTS doc_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS doc_items_session ON doc_items(session);
"""


def init() -> None:
    with db.connect() as conn:
        conn.executescript(SCHEMA)


def to_dict(doc: Doc) -> dict[str, Any]:
    return {
        "id": doc.id,
        "session": doc.session,
        "source": doc.source,
        "filename": doc.filename,
        "text": doc.text,
        "status": doc.status,
        "kind": doc.kind,
        "engine": doc.engine,
        "model": doc.model,
        "cost_usd": doc.cost_usd,
        "decision": doc.decision,
        "fields": [vars(f) for f in doc.fields],
        "checks": [vars(c) for c in doc.checks],
        "steps": [vars(s) for s in doc.steps],
    }


def from_dict(d: dict[str, Any]) -> Doc:
    return Doc(
        id=d["id"],
        session=d["session"],
        source=d["source"],
        filename=d["filename"],
        text=d["text"],
        status=d["status"],
        kind=d["kind"],
        engine=d.get("engine", "rules"),
        model=d.get("model", ""),
        cost_usd=d.get("cost_usd", 0.0),
        decision=d.get("decision", ""),
        fields=[Field(**f) for f in d.get("fields", [])],
        checks=[Check(**c) for c in d.get("checks", [])],
        steps=[Step(**s) for s in d.get("steps", [])],
    )


def create(session: str, source: str, filename: str, text: str, created: datetime | None = None) -> Doc:
    init()
    at = (created or clock.now()).isoformat()
    with db.connect() as conn:
        cur = conn.execute("INSERT INTO doc_items(session, created_at, payload) VALUES (?, ?, '{}')", (session, at))
        doc_id = int(cur.lastrowid or 0)
    doc = Doc(id=doc_id, session=session, source=source, filename=filename, text=text)  # type: ignore[arg-type]
    save(doc)
    return doc


def save(doc: Doc) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE doc_items SET payload = ? WHERE id = ?", (json.dumps(to_dict(doc), ensure_ascii=False), doc.id)
        )


def _load(row: Any) -> Doc:
    doc = from_dict(json.loads(row["payload"]))
    doc.received = fmt.ago((clock.now() - datetime.fromisoformat(row["created_at"])).total_seconds() / 60)
    return doc


def list_session(session: str) -> list[Doc]:
    init()
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM doc_items WHERE session = ? ORDER BY created_at DESC", (session,)).fetchall()
    return [_load(r) for r in rows if r["payload"] != "{}"]


def get(doc_id: int, session: str) -> Doc | None:
    init()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM doc_items WHERE id = ? AND session = ?", (doc_id, session)).fetchone()
    return _load(row) if row and row["payload"] != "{}" else None


def has_session(session: str) -> bool:
    init()
    with db.connect() as conn:
        return conn.execute("SELECT 1 FROM doc_items WHERE session = ? LIMIT 1", (session,)).fetchone() is not None


def clear() -> None:
    """Nightly reset: the demo queue is rebuilt from the new day's data."""
    init()
    with db.connect() as conn:
        conn.execute("DELETE FROM doc_items")
