"""Tests for the Documents module: LangGraph state machine, 1C/CRM checks, and API routes."""

import pytest
from starlette.testclient import TestClient

from pulse import data, sync
from pulse.agents import tools
from pulse.core import db
from pulse.modules import docs


@pytest.fixture
async def snapshot() -> data.Data:
    db.init()
    await sync.reset()
    return data.load()


def test_classify_and_extract() -> None:
    text = (
        "Счёт на оплату № 582 от 21.10.2026\n"
        "Поставщик: ООО «ВентТехСнаб», ИНН 7814562019\n"
        "Покупатель: ООО «Норд Инжиниринг»\n"
        "Основание: Заказ поставщику № ЗП-0388\n"
        "Итого к оплате: 421 300,00 руб.\n"
        "В том числе НДС 20%: 70 216,67 руб."
    )

    kind, kind_label, conf = docs.extract.classify_text(text)
    assert kind == "invoice"
    assert kind_label == "Счёт"
    assert conf > 0.9

    parsed = docs.extract.parse_raw_document(text)
    assert parsed["kind"] == "invoice"
    assert "582" in parsed["number"]
    assert parsed["amount"] == 421300.0
    assert "ВентТехСнаб" in parsed["counterparty"]


def test_langgraph_pipeline_mismatch_and_confirm(snapshot: data.Data) -> None:
    # 1. Run pipeline on the planted mismatch seed invoice (421 300 vs 412 300 in 1C order ЗП-0388)
    initial = {
        "kind": "invoice",
        "kind_label": "Счёт",
        "number": "№ 2417",
        "date": "21.10.2026",
        "counterparty": "ООО «ВентТехСнаб»",
        "amount": 421_300.0,
        "confidence": 0.93,
        "fields": [
            {"key": "supplier", "label": "Поставщик", "value": "ООО «ВентТехСнаб»", "confidence": 0.99},
            {"key": "order", "label": "Основание", "value": "Заказ поставщику № ЗП-0388", "confidence": 0.91},
            {"key": "amount", "label": "Сумма с НДС", "value": "421 300,00 ₽", "confidence": 0.97},
        ],
        "raw_text": "Счёт № 2417 от ООО «ВентТехСнаб» на сумму 421 300 руб по заказу ЗП-0388",
    }

    res1 = docs.graph.run_pipeline(doc_id=999, initial=initial, approved=False)
    # Must detect mismatch and halt for human review
    assert res1["status"] == "mismatch"
    assert res1["needs_human"] is True

    # Validate step should have error status
    val_step = next(s for s in res1["steps"] if s["node"] == "validate")
    assert val_step["status"] == "error"

    # Amount check must be ok=False
    amt_check = next(c for c in res1["checks"] if "Сумма" in c["label"])
    assert amt_check["ok"] is False

    # Review step should be active (waiting for human)
    rev_step = next(s for s in res1["steps"] if s["node"] == "review")
    assert rev_step["status"] == "active"

    # 2. Human approval resumes thread to create draft and complete
    res2 = docs.graph.confirm_step(doc_id=999, current_state=res1)
    assert res2["status"] == "posted"
    draft_step = next(s for s in res2["steps"] if s["node"] == "draft")
    assert draft_step["status"] == "done"


def test_docs_store_and_tools(snapshot: data.Data) -> None:
    session = "test_store_session"
    items = docs.list_docs(session)
    assert len(items) >= 8

    doc1 = docs.get_doc(1, session)
    assert doc1 is not None
    assert doc1.status == "mismatch"
    assert doc1.number == "№ 2417"

    # Tools
    q = tools.run_tool("docs_queue", {})
    assert len(q) >= 1
    assert any(d["id"] == 1 for d in q)

    detail = tools.run_tool("review_doc", {"doc_id": 1})
    assert detail["number"] == "№ 2417"
    assert "steps" in detail


def test_api_docs_endpoints(snapshot: data.Data) -> None:
    from pulse.main import app

    with TestClient(app) as client:
        # 1. List
        r = client.get("/api/docs", headers={"x-visitor-id": "api_test_user"})
        assert r.status_code == 200
        docs_list = r.json()
        assert len(docs_list) >= 8
        assert docs_list[0]["id"] == 1

        # 2. Detail
        r_det = client.get("/api/docs/1", headers={"x-visitor-id": "api_test_user"})
        assert r_det.status_code == 200
        det = r_det.json()
        assert det["counterparty"] == "ООО «ВентТехСнаб»"
        assert len(det["steps"]) == 5

        # 3. Graph schema
        r_schema = client.get("/api/docs/graph/schema")
        assert r_schema.status_code == 200
        assert "flowchart" in r_schema.json()["mermaid"]

        # 4. Confirm document (Human-in-the-loop)
        r_conf = client.post("/api/docs/1/confirm", headers={"x-visitor-id": "api_test_user"})
        assert r_conf.status_code == 200
        conf_data = r_conf.json()
        assert conf_data["status"] == "posted"

        # 5. Upload document
        r_up = client.post(
            "/api/docs/upload",
            headers={"x-visitor-id": "api_test_user"},
        )
        assert r_up.status_code == 200
        up_data = r_up.json()
        assert up_data["id"] > 0
        assert len(up_data["steps"]) > 0


def test_upload_budget_limit(snapshot: data.Data) -> None:
    from pulse.main import app

    visitor = "limited_doc_user"
    with TestClient(app) as client:
        # Exhaust 3 documents limit
        for _ in range(3):
            r = client.post("/api/docs/upload", headers={"x-visitor-id": visitor})
            assert r.status_code == 200

        # 4th document must be rejected with 429
        r4 = client.post("/api/docs/upload", headers={"x-visitor-id": visitor})
        assert r4.status_code == 429
        assert "лимит" in r4.json()["detail"].lower()
