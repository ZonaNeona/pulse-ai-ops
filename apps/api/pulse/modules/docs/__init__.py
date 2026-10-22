"""Incoming documents: read → extract → check against 1С/CRM → post, or stop for a person (LangGraph)."""

from typing import Any

from pulse import data
from pulse.core import llm
from pulse.modules.docs import demo, graph, read, store
from pulse.modules.docs.model import Doc


class NotAllowed(ValueError):
    """The action cannot be done on this document; the message is shown as is."""


async def queue(session: str) -> list[dict[str, Any]]:
    await demo.ensure_queue(session, data.load())
    return demo.to_list(store.list_session(session))


async def get(session: str, doc_id: int) -> Doc | None:
    await demo.ensure_queue(session, data.load())
    return store.get(doc_id, session)


async def upload(session: str, quota: str, filename: str, content: bytes) -> Doc:
    text = read.text_of(filename, content)  # raises read.Unreadable with a visitor-facing reason
    image = read.data_url(filename, content) if text is None else None
    if image and not llm.available():
        raise read.Unreadable(
            "Фото и сканы читает vision-модель, а она на стенде сейчас не подключена — загрузите PDF или TXT"
        )
    await demo.ensure_queue(session, data.load())
    doc = store.create(session, "upload", filename, text or "")
    return await graph.process(doc, image=image, quota=quota, use_model=True)


async def decide(session: str, doc_id: int, approve: bool) -> Doc:
    doc = store.get(doc_id, session)
    if doc is None:
        raise NotAllowed("Документ не найден")
    if doc.status not in ("review", "mismatch"):
        raise NotAllowed("Документ не ждёт решения")
    return await graph.decide(doc, approve)


def pending(session: str) -> list[Doc]:
    return [d for d in store.list_session(session) if d.status in ("review", "mismatch")]


__all__ = ["Doc", "NotAllowed", "decide", "get", "graph", "pending", "queue", "read", "store", "upload"]
