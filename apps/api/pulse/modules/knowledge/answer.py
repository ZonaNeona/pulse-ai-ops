"""Answers from the regulations, with sources, or an honest "the regulations do not say".

Three outcomes, always labelled for the visitor:
- `model`: the language model wrote the answer from the retrieved sections only; citations it used are
  checked against what it was given, and the quotes are cut from the real text by code, never by the model;
- `extract`: no model available (no key, budget spent, provider down) — the answer is the most relevant
  sentences of the retrieved sections themselves;
- `refusal`: retrieval found nothing that covers the question.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pulse.core import llm
from pulse.modules.knowledge.index import stems
from pulse.modules.knowledge.search import Hit, search

Mode = Literal["model", "extract", "refusal"]
MIN_COVERAGE = 0.5  # the best section must contain at least half of the question's meaningful words
SENTENCE = re.compile(r"(?<=[.!?])\s+")
REFUSAL = "В регламентах компании нет ответа на этот вопрос. Уточните формулировку или спросите ответственного."


@dataclass
class Source:
    id: int
    title: str
    section: str
    quote: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "section": self.section, "quote": self.quote}


@dataclass
class Answer:
    question: str
    text: str
    mode: Mode
    sources: list[Source] = field(default_factory=list)
    model: str = ""
    cost_usd: float = 0.0
    note: str = ""

    @property
    def grounded(self) -> bool:
        return self.mode != "refusal" and bool(self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.text,
            "mode": self.mode,
            "grounded": self.grounded,
            "sources": [s.to_dict() for s in self.sources],
            "model": self.model,
            "costUsd": round(self.cost_usd, 5),
            "note": self.note,
        }


def relevant(question: str, k: int = 4) -> list[Hit]:
    """Sections worth answering from: the best one must cover the question, the rest must be close to it."""
    hits = search(question, k)
    if not hits or hits[0].coverage < MIN_COVERAGE:
        return []
    hits.sort(key=lambda h: (-h.coverage, -h.score))  # a section that answers more of the question wins ties in BM25
    best = hits[0]
    return [h for h in hits if h.coverage >= MIN_COVERAGE and h.score >= best.score * 0.6][:3]


def best_sentence(text: str, against: str) -> str:
    """The sentence of `text` sharing the most stems with `against` (the question or the model's answer)."""
    target = set(stems(against))
    sentences = [s for s in SENTENCE.split(text) if s.strip()]
    return max(sentences, key=lambda s: len(target & set(stems(s))), default=text)


def _sources(hits: list[Hit], against: str) -> list[Source]:
    return [
        Source(i, h.chunk.doc_title, h.chunk.section, best_sentence(h.chunk.text, against))
        for i, h in enumerate(hits, 1)
    ]


def extract(question: str, hits: list[Hit], note: str = "") -> Answer:
    sources = _sources(hits, question)
    text = " ".join(f"{s.quote} [{s.id}]" for s in sources)
    return Answer(question, text, "extract", sources, note=note)


PROMPT = """Ты отвечаешь сотрудникам компании «Норд Инжиниринг» строго по фрагментам регламентов ниже.
Правила:
- используй только факты из фрагментов, ничего не добавляй от себя;
- после каждого утверждения ставь номер фрагмента в квадратных скобках, например [2];
- если во фрагментах нет ответа, верни found=false;
- отвечай по-русски, коротко, 1–3 предложения.
Верни JSON: {"found": true|false, "answer": "текст с [n]", "used": [номера фрагментов]}.

Фрагменты:
"""


async def answer(question: str, visitor: str = "anonymous") -> Answer:
    question = question.strip()[:500]
    hits = relevant(question)
    if not hits:
        return Answer(question, REFUSAL, "refusal")
    if not llm.available():
        return extract(question, hits, "Модель не подключена — показаны выдержки из регламентов")
    passages = "\n".join(f"[{i}] {h.chunk.doc_title}, {h.chunk.section}: {h.chunk.text}" for i, h in enumerate(hits, 1))
    try:
        res = await llm.chat(
            [{"role": "system", "content": PROMPT + passages}, {"role": "user", "content": question}],
            visitor=visitor,
            json_mode=True,
        )
        data = llm.parse_json(res.text)
    except (llm.LlmUnavailable, ValueError) as exc:
        return extract(
            question, hits, str(exc) if isinstance(exc, llm.LlmUnavailable) else "Модель ответила не по формату"
        )
    if not data.get("found"):
        return Answer(question, REFUSAL, "refusal", model=res.model, cost_usd=res.cost_usd)
    used = sorted({int(n) for n in data.get("used") or [] if str(n).isdigit() and 1 <= int(n) <= len(hits)})
    text = str(data.get("answer") or "").strip()
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    if not text or not used or not cited or not cited <= set(used):
        # The model cited something it was not given, or nothing at all: do not show an unverifiable answer.
        return extract(question, hits, "Ответ модели не прошёл проверку источников — показаны выдержки")
    renumber = {old: new for new, old in enumerate(used, 1)}
    text = re.sub(r"\[(\d+)\]", lambda m: f"[{renumber.get(int(m.group(1)), int(m.group(1)))}]", text)
    sources = [
        Source(
            renumber[n],
            hits[n - 1].chunk.doc_title,
            hits[n - 1].chunk.section,
            best_sentence(hits[n - 1].chunk.text, text),
        )
        for n in used
    ]
    return Answer(question, text, "model", sources, model=res.model, cost_usd=res.cost_usd)
