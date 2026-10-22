"""Documents module types. `to_dict` gives the exact shape the web app and the bot read."""

from dataclasses import dataclass, field
from typing import Any, Literal

DocKind = Literal["invoice", "upd", "act", "contract", "unknown"]
DocStatus = Literal["processing", "posted", "review", "mismatch", "rejected", "failed"]
StepStatus = Literal["done", "active", "waiting", "error", "skipped"]
KIND_LABEL: dict[str, str] = {
    "invoice": "Счёт",
    "upd": "УПД",
    "act": "Акт",
    "contract": "Договор",
    "unknown": "Документ",
}


@dataclass
class Field:
    key: str
    label: str
    value: str
    confidence: float
    expected: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "confidence": round(self.confidence, 2),
        }
        if self.expected:
            out["expected"] = self.expected
        return out


@dataclass
class Check:
    label: str
    ok: bool
    detail: str
    rule: str = ""  # the regulation section the check enforces, e.g. "Работа с первичными документами …, § 1.2"

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "ok": self.ok, "detail": self.detail, "rule": self.rule}


@dataclass
class Step:
    node: str
    label: str
    status: StepStatus
    ms: float | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"node": self.node, "label": self.label, "status": self.status, "note": self.note}
        if self.ms is not None:
            out["ms"] = round(self.ms, 1)
        return out


@dataclass
class Extracted:
    """What extraction produced: the document's kind and its fields, and how they were read."""

    kind: DocKind
    fields: list[Field]
    engine: Literal["rules", "model"]
    model: str = ""
    cost_usd: float = 0.0

    def get(self, key: str) -> str:
        return next((f.value for f in self.fields if f.key == key), "")


@dataclass
class Doc:
    id: int
    session: str
    source: Literal["demo", "upload"]
    filename: str
    text: str
    status: DocStatus = "processing"
    kind: DocKind = "unknown"
    fields: list[Field] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    engine: str = "rules"
    model: str = ""
    cost_usd: float = 0.0
    received: str = ""
    decision: str = ""

    def value(self, key: str) -> str:
        return next((f.value for f in self.fields if f.key == key), "")

    @property
    def amount(self) -> float:
        from pulse.modules.docs.read import money

        return money(self.value("total")) or 0.0

    @property
    def confidence(self) -> float:
        return min((f.confidence for f in self.fields), default=0.0)

    def to_dict(self) -> dict[str, Any]:
        number = self.value("number")
        return {
            "id": self.id,
            "kind": self.kind,
            "kindLabel": KIND_LABEL.get(self.kind, "Документ"),
            "number": f"№ {number}" if number else self.filename,
            "date": self.value("date"),
            "counterparty": self.value("counterparty") or "—",
            "amount": self.amount,
            "status": self.status,
            "confidence": round(self.confidence, 2),
            "receivedAgo": self.received,
            "source": self.source,
            "engine": self.engine,
            "model": self.model,
            "costUsd": round(self.cost_usd, 5),
            "decision": self.decision,
            "text": self.text[:4000],
            "steps": [s.to_dict() for s in self.steps],
            "fields": [f.to_dict() for f in self.fields],
            "checks": [c.to_dict() for c in self.checks],
        }
