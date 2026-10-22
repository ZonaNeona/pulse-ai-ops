"""Documents: the LangGraph pipeline over the day's demo queue and uploaded files, human-in-the-loop."""

import json

import pytest

from pulse.modules import docs
from pulse.modules.docs import read
from tests.conftest import Script, reply

INVOICE = (
    "Счёт на оплату № 55 от 20.10.2026\n"
    "Поставщик: ООО «Неизвестный поставщик», ИНН 7800000001\n"
    "Всего к оплате: 100 000,00 руб.\n"
    "В том числе НДС 20%: 16 666,67"
)


def by_number(items: list[dict], number: str) -> dict:  # type: ignore[type-arg]
    return next(d for d in items if any(f["key"] == "number" and f["value"] == number for f in d["fields"]))


def failed(doc: dict) -> list[str]:  # type: ignore[type-arg]
    return [c["label"] for c in doc["checks"] if not c["ok"]]


async def test_demo_queue_goes_through_the_graph_with_every_outcome(ready: None) -> None:
    items = await docs.queue("s1")
    statuses = sorted(d["status"] for d in items)
    assert statuses.count("posted") == 2 and statuses.count("mismatch") == 1 and statuses.count("review") == 3

    planted = by_number(items, "2417")
    assert planted["status"] == "mismatch"
    assert "Сумма совпадает с заказом" in failed(planted)
    total = next(f for f in planted["fields"] if f["key"] == "total")
    assert total["expected"] and "+9 000" in next(c["detail"] for c in planted["checks"] if not c["ok"])
    assert [s["node"] for s in planted["steps"]][:3] == ["extract", "validate", "review"]

    assert "НДС посчитан верно" in failed(by_number(items, "342"))
    assert "Контрагент есть в 1С" in failed(by_number(items, "77"))
    assert "Неустойка в пределах политики" in failed(by_number(items, "М-77/10"))
    for number in ("1182", "904"):
        doc = by_number(items, number)
        assert doc["status"] == "posted" and not failed(doc)


async def test_a_person_resumes_the_stopped_graph(ready: None) -> None:
    items = await docs.queue("s1")
    planted = by_number(items, "2417")
    approved = await docs.decide("s1", planted["id"], approve=True)
    assert approved.status == "posted" and approved.decision == "Подтверждено человеком"
    assert any(s.node == "post" and s.status == "done" for s in approved.steps)
    with pytest.raises(docs.NotAllowed):
        await docs.decide("s1", planted["id"], approve=False)

    stranger = by_number(items, "77")
    rejected = await docs.decide("s1", stranger["id"], approve=False)
    assert rejected.status == "rejected"


async def test_visitors_do_not_see_each_others_documents(ready: None) -> None:
    first = await docs.queue("s1")
    planted = by_number(first, "2417")
    await docs.decide("s1", planted["id"], approve=True)
    second = await docs.queue("s2")
    assert by_number(second, "2417")["status"] == "mismatch"
    assert await docs.get("s2", planted["id"]) is None
    with pytest.raises(docs.NotAllowed):
        await docs.decide("s2", planted["id"], approve=False)


async def test_uploaded_text_is_read_by_rules_without_a_model(ready: None) -> None:
    doc = await docs.upload("s1", "q1", "schet.txt", INVOICE.encode())
    assert doc.engine == "rules" and doc.value("number") == "55"
    assert doc.status == "review" and "Контрагент есть в 1С" in [c.label for c in doc.checks if not c.ok]


async def test_uploaded_image_needs_the_vision_model(ready: None) -> None:
    with pytest.raises(read.Unreadable, match="vision"):
        await docs.upload("s1", "q1", "scan.png", b"\x89PNG fake")


async def test_uploaded_document_is_read_by_the_model_when_connected(ready: None, model: Script) -> None:
    fields = {
        "kind": "invoice",
        "fields": {
            "number": {"value": "55", "confidence": 0.98},
            "date": {"value": "20.10.2026", "confidence": 0.95},
            "counterparty": {"value": "ООО «Неизвестный поставщик»", "confidence": 0.9},
            "inn": {"value": "7800000001", "confidence": 0.9},
            "total": {"value": "100000", "confidence": 0.97},
        },
    }
    model.append(reply(json.dumps(fields, ensure_ascii=False), cost=0.0021))
    doc = await docs.upload("s1", "q1", "schet.txt", INVOICE.encode())
    assert doc.engine == "model" and doc.cost_usd == 0.0021
    assert doc.value("total") == "100 000,00 ₽"
    assert model.requests[0]["response_format"] == {"type": "json_object"}


def test_unreadable_files_are_refused_with_a_reason() -> None:
    with pytest.raises(read.Unreadable):
        read.text_of("big.txt", b"x" * (read.MAX_BYTES + 1))
    with pytest.raises(read.Unreadable):
        read.text_of("table.xlsx", b"PK")


def test_the_graph_is_drawn_by_langgraph_itself() -> None:
    chart = docs.graph.mermaid()
    for node in ("extract", "validate", "review", "post", "reject"):
        assert node in chart
