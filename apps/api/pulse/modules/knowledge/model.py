"""Data models for Knowledge & RAG module."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class KbSource:
    id: int
    title: str
    section: str
    quote: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KbAnswer:
    question: str
    answer: str
    sources: list[KbSource]
    grounded: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "sources": [s.to_dict() for s in self.sources],
            "grounded": self.grounded,
        }


@dataclass
class KbStats:
    documents: int
    chunks: int
    grounded: int
    eval_passed: int
    eval_total: int
    refusals_correct: int
    refusals_total: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "documents": self.documents,
            "chunks": self.chunks,
            "grounded": self.grounded,
            "evalPassed": self.eval_passed,
            "evalTotal": self.eval_total,
            "refusalsCorrect": self.refusals_correct,
            "refusalsTotal": self.refusals_total,
        }


@dataclass
class KbDocInfo:
    id: int
    title: str
    category: str
    chunk_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "chunkCount": self.chunk_count,
        }


@dataclass
class EvalCase:
    id: int
    question: str
    expected_facts: list[str]
    is_refusal: bool
    required_sources: list[str]


@dataclass
class EvalResult:
    case_id: int
    question: str
    passed: bool
    is_refusal: bool
    answer: str
    latency_ms: int
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
