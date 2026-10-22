"""SQLite persistence for documents (docs table)."""

import json
from typing import Any

from pulse.core import clock, db
from pulse.modules.docs import graph, seed
from pulse.modules.docs.model import DocCheck, DocField, DocItem, GraphStep


def _row_to_item(row: Any) -> DocItem:
    steps_data = json.loads(row["steps_json"])
    fields_data = json.loads(row["fields_json"])
    checks_data = json.loads(row["checks_json"])

    return DocItem(
        id=row["id"],
        kind=row["kind"],
        kind_label=row["kind_label"],
        number=row["number"],
        date=row["date"],
        counterparty=row["counterparty"],
        amount=row["amount"],
        status=row["status"],
        confidence=row["confidence"],
        received_ago=row["received_ago"],
        steps=[GraphStep(**s) for s in steps_data],
        fields=[DocField(**f) for f in fields_data],
        checks=[DocCheck(**c) for c in checks_data],
        raw_text=row["raw_text"] or "",
    )


def ensure_seeded(session_id: str = "default") -> None:
    """Populates the database with initial seed documents if empty."""
    with db.connect() as conn:
        count = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
        if count > 0:
            return

        now = clock.now().isoformat()
        for doc in seed.get_seed_docs():
            conn.execute(
                "INSERT INTO docs(id, session_id, kind, kind_label, number, date, counterparty, amount, "
                "status, confidence, received_ago, steps_json, fields_json, checks_json, raw_text, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc["id"],
                    "default",
                    doc["kind"],
                    doc["kind_label"],
                    doc["number"],
                    doc["date"],
                    doc["counterparty"],
                    doc["amount"],
                    doc["status"],
                    doc["confidence"],
                    doc["received_ago"],
                    json.dumps(doc["steps"], ensure_ascii=False),
                    json.dumps(doc["fields"], ensure_ascii=False),
                    json.dumps(doc["checks"], ensure_ascii=False),
                    "",
                    now,
                    now,
                ),
            )


def list_docs(session_id: str = "default") -> list[DocItem]:
    ensure_seeded(session_id)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM docs WHERE session_id = ? OR session_id = 'default' ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        seen = set()
        items = []
        for r in rows:
            if r["id"] not in seen:
                seen.add(r["id"])
                items.append(_row_to_item(r))
        return items


def get_doc(doc_id: int, session_id: str = "default") -> DocItem | None:
    ensure_seeded(session_id)
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM docs WHERE id = ? AND (session_id = ? OR session_id = 'default')",
            (doc_id, session_id),
        ).fetchone()
        if not row:
            return None
        return _row_to_item(row)


def create_doc(
    session_id: str,
    kind: str,
    kind_label: str,
    number: str,
    date: str,
    counterparty: str,
    amount: float,
    status: str,
    confidence: float,
    steps: list[dict[str, Any]],
    fields: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    raw_text: str = "",
) -> DocItem:
    now = clock.now().isoformat()
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO docs(session_id, kind, kind_label, number, date, counterparty, amount, "
            "status, confidence, received_ago, steps_json, fields_json, checks_json, raw_text, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                kind,
                kind_label,
                number,
                date,
                counterparty,
                amount,
                status,
                confidence,
                "только что",
                json.dumps(steps, ensure_ascii=False),
                json.dumps(fields, ensure_ascii=False),
                json.dumps(checks, ensure_ascii=False),
                raw_text,
                now,
                now,
            ),
        )
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM docs WHERE id = ?", (new_id,)).fetchone()
        return _row_to_item(row)


def confirm_doc(doc_id: int, session_id: str = "default") -> DocItem:
    doc = get_doc(doc_id, session_id)
    if not doc:
        raise ValueError(f"Document #{doc_id} not found")

    # Resume LangGraph thread to complete the draft step
    current_state = {
        "kind": doc.kind,
        "kind_label": doc.kind_label,
        "number": doc.number,
        "date": doc.date,
        "counterparty": doc.counterparty,
        "amount": doc.amount,
        "confidence": doc.confidence,
        "fields": [f.to_dict() for f in doc.fields],
        "checks": [c.to_dict() for c in doc.checks],
        "steps": [s.to_dict() for s in doc.steps],
    }

    result = graph.confirm_step(doc_id, current_state)

    updated_steps = result.get("steps", [s.to_dict() for s in doc.steps])
    updated_status = result.get("status", "posted")
    now = clock.now().isoformat()

    with db.connect() as conn:
        conn.execute(
            "UPDATE docs SET status = ?, steps_json = ?, updated_at = ? "
            "WHERE id = ? AND (session_id = ? OR session_id = 'default')",
            (
                updated_status,
                json.dumps(updated_steps, ensure_ascii=False),
                now,
                doc_id,
                session_id,
            ),
        )

    res = get_doc(doc_id, session_id)
    assert res is not None
    return res


def reject_doc(doc_id: int, session_id: str = "default", reason: str = "") -> DocItem:
    doc = get_doc(doc_id, session_id)
    if not doc:
        raise ValueError(f"Document #{doc_id} not found")

    steps = [s.to_dict() for s in doc.steps]
    for s in steps:
        if s.get("node") == "review":
            s["status"] = "error"
            s["note"] = reason or "отклонено человеком"

    checks = [c.to_dict() for c in doc.checks]
    checks.append(DocCheck("Запрос исправлений", False, reason or "Отправлен запрос поставщику").to_dict())

    now = clock.now().isoformat()
    with db.connect() as conn:
        conn.execute(
            "UPDATE docs SET status = 'review', steps_json = ?, checks_json = ?, updated_at = ? "
            "WHERE id = ? AND (session_id = ? OR session_id = 'default')",
            (
                json.dumps(steps, ensure_ascii=False),
                json.dumps(checks, ensure_ascii=False),
                now,
                doc_id,
                session_id,
            ),
        )

    res = get_doc(doc_id, session_id)
    assert res is not None
    return res
