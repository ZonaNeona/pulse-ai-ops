"""The document pipeline as a LangGraph state machine.

    START → extract → validate ─┬─ all checks pass, confident ──────────→ post → END
                                └─ anything off → review ── interrupt() ─┬─ approve → post → END
                                                                         └─ reject → reject → END

`review` calls `interrupt()`: the run stops, its state is checkpointed in SQLite, and it resumes when a
person decides in the web app or in Telegram — minutes or days later, from any process. Step timings are
measured, not drawn.
"""

import time
from pathlib import Path
from typing import Any, Literal, TypedDict

import aiosqlite
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from pulse import data as data_mod
from pulse.core import llm
from pulse.core.config import get_settings
from pulse.modules.docs import checks, extract, store
from pulse.modules.docs.model import Doc, Step

STEPS = [
    ("extract", "Тип и реквизиты"),
    ("validate", "Сверка с 1С и CRM"),
    ("review", "Решение человека"),
    ("post", "Проводка"),
]


class State(TypedDict, total=False):
    doc: dict[str, Any]
    decision: str


def _doc(state: State) -> Doc:
    return store.from_dict(state["doc"])


def _step(doc: Doc, node: str, status: str, ms: float | None, note: str) -> None:
    label = dict(STEPS).get(node, node)
    doc.steps = [s for s in doc.steps if s.node != node] + [Step(node, label, status, ms, note)]  # type: ignore[arg-type]
    order = [n for n, _ in STEPS] + ["reject"]
    doc.steps.sort(key=lambda s: order.index(s.node) if s.node in order else 99)


async def node_extract(state: State, config: RunnableConfig) -> State:
    doc = _doc(state)
    opts = config.get("configurable", {})
    started = time.perf_counter()
    use_model = bool(opts.get("use_model")) and llm.available()
    result = None
    note = ""
    if use_model:
        try:
            result = await extract.by_model(
                text=doc.text or None, image=opts.get("image"), visitor=opts.get("quota", "demo")
            )
        except (llm.LlmUnavailable, ValueError) as exc:
            note = f"модель недоступна ({exc}); "
    if result is None:
        if not doc.text:
            doc.status = "failed"
            doc.decision = "Изображение можно прочитать только моделью, а она сейчас недоступна"
            _step(doc, "extract", "error", (time.perf_counter() - started) * 1000, "нужна vision-модель")
            return {"doc": store.to_dict(doc)}
        result = extract.by_rules(doc.text)
    doc.kind, doc.fields = result.kind, result.fields
    doc.engine, doc.model, doc.cost_usd = result.engine, result.model, doc.cost_usd + result.cost_usd
    how = f"модель {result.model.split('/')[-1]}" if result.engine == "model" else "правила"
    found = sum(1 for f in doc.fields if f.value != "не найдено")
    _step(doc, "extract", "done", (time.perf_counter() - started) * 1000, f"{note}{how}: {found} полей")
    return {"doc": store.to_dict(doc)}


async def node_validate(state: State, config: RunnableConfig) -> State:
    doc = _doc(state)
    if doc.status == "failed":
        return {"doc": store.to_dict(doc)}
    started = time.perf_counter()
    others = store.list_session(doc.session)
    doc.checks = checks.run(doc, data_mod.load(), others)
    failed = [c for c in doc.checks if not c.ok]
    ms = (time.perf_counter() - started) * 1000
    if failed:
        money_issue = any("Сумма" in c.label for c in failed)
        doc.status = "mismatch" if money_issue else "review"
        _step(doc, "validate", "error", ms, f"не пройдено: {len(failed)} из {len(doc.checks)}")
        _step(doc, "review", "active", None, "ждёт решения")
    elif doc.confidence < 0.9:
        doc.status = "review"
        _step(doc, "validate", "done", ms, "расхождений нет")
        _step(doc, "review", "active", None, f"реквизиты прочитаны неуверенно ({doc.confidence:.2f})")
    else:
        _step(doc, "validate", "done", ms, f"все {len(doc.checks)} проверок пройдены")
        _step(doc, "review", "skipped", None, "не нужно — всё сошлось")
    return {"doc": store.to_dict(doc)}


def after_validate(state: State) -> Literal["post", "review", "__end__"]:
    status = state["doc"]["status"]
    if status == "failed":
        return "__end__"
    return "review" if status in ("review", "mismatch") else "post"


def node_review(state: State) -> State:
    doc = state["doc"]
    decision = interrupt({"doc_id": doc["id"], "reason": [c["detail"] for c in doc["checks"] if not c["ok"]]})
    return {"decision": str(decision)}


def after_review(state: State) -> Literal["post", "reject"]:
    return "post" if state.get("decision") == "approve" else "reject"


def node_post(state: State) -> State:
    doc = _doc(state)
    by_person = state.get("decision") == "approve"
    doc.status = "posted"
    doc.decision = "Подтверждено человеком" if by_person else "Проведено автоматически: все проверки пройдены"
    if by_person:
        _step(doc, "review", "done", None, "подтверждено")
    _step(doc, "post", "done", None, "черновик проводки в 1С (в демо 1С только читается)")
    return {"doc": store.to_dict(doc)}


def node_reject(state: State) -> State:
    doc = _doc(state)
    doc.status = "rejected"
    doc.decision = "Возвращено: запрошен исправленный документ"
    _step(doc, "review", "done", None, "отклонено")
    _step(doc, "post", "skipped", None, "не проводится")
    return {"doc": store.to_dict(doc)}


def build(checkpointer: Any = None) -> Any:
    g = StateGraph(State)
    g.add_node("extract", node_extract)
    g.add_node("validate", node_validate)
    g.add_node("review", node_review)
    g.add_node("post", node_post)
    g.add_node("reject", node_reject)
    g.add_edge(START, "extract")
    g.add_edge("extract", "validate")
    g.add_conditional_edges("validate", after_validate)
    g.add_conditional_edges("review", after_review)
    g.add_edge("post", END)
    g.add_edge("reject", END)
    return g.compile(checkpointer=checkpointer)


def checkpoint_path() -> Path:
    return get_settings().pulse_data_dir / "langgraph.sqlite3"


async def _run(doc_id: int, payload: Any, opts: dict[str, Any]) -> Doc:
    checkpoint_path().parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(checkpoint_path()) as conn:
        saver = AsyncSqliteSaver(conn)
        app = build(saver)
        config: RunnableConfig = {"configurable": {"thread_id": f"doc-{doc_id}", **opts}}
        await app.ainvoke(payload, config)
        values = (await app.aget_state(config)).values
    doc = store.from_dict(values["doc"])
    store.save(doc)
    return doc


async def process(doc: Doc, *, image: str | None = None, quota: str = "demo", use_model: bool = True) -> Doc:
    return await _run(doc.id, {"doc": store.to_dict(doc)}, {"image": image, "quota": quota, "use_model": use_model})


async def decide(doc: Doc, approve: bool) -> Doc:
    """Resume a run paused in `review` with a person's decision."""
    return await _run(doc.id, Command(resume="approve" if approve else "reject"), {})


def mermaid() -> str:
    return str(build().get_graph().draw_mermaid())
