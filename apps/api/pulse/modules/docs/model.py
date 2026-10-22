"""Domain models for the Documents module (LangGraph pipeline + 1C/CRM verification)."""

from dataclasses import dataclass, field
from typing import Any, Literal

DocKind = Literal["invoice", "contract", "upd", "act"]
DocStatus = Literal["recognized", "mismatch", "review", "posted"]
StepStatus = Literal["done", "active", "waiting", "error", "skipped"]


@dataclass(slots=True)
class DocField:
    key: str
    label: str
    value: str
    confidence: float
    expected: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "confidence": round(self.confidence, 2),
        }
        if self.expected is not None:
            d["expected"] = self.expected
        return d


@dataclass(slots=True)
class GraphStep:
    node: str
    label: str
    status: StepStatus
    ms: int | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "node": self.node,
            "label": self.label,
            "status": self.status,
        }
        if self.ms is not None:
            d["ms"] = self.ms
        if self.note is not None:
            d["note"] = self.note
        return d


@dataclass(slots=True)
class DocCheck:
    label: str
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "ok": self.ok,
            "detail": self.detail,
        }


@dataclass(slots=True)
class DocItem:
    id: int
    kind: DocKind
    kind_label: str
    number: str
    date: str
    counterparty: str
    amount: float
    status: DocStatus
    confidence: float
    received_ago: str
    steps: list[GraphStep] = field(default_factory=list)
    fields: list[DocField] = field(default_factory=list)
    checks: list[DocCheck] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "kindLabel": self.kind_label,
            "number": self.number,
            "date": self.date,
            "counterparty": self.counterparty,
            "amount": self.amount,
            "status": self.status,
            "confidence": round(self.confidence, 2),
            "receivedAgo": self.received_ago,
            "steps": [s.to_dict() for s in self.steps],
            "fields": [f.to_dict() for f in self.fields],
            "checks": [c.to_dict() for c in self.checks],
        }
