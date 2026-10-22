"""Tests for Knowledge & RAG module (FTS5 search, citation attribution, refusals and eval suite)."""

from fastapi.testclient import TestClient

from pulse.agents import tools
from pulse.main import app
from pulse.modules import knowledge as kb_mod


def test_search_chunks_fts() -> None:
    """Tests FTS5 full-text indexing and Russian prefix matching."""
    kb_mod.ensure_seeded()

    chunks = kb_mod.search_chunks("скидка дилерам", limit=3)
    assert len(chunks) > 0
    assert any("Ценовая политика" in c["title"] for c in chunks)

    chunks_pressure = kb_mod.search_chunks("опрессовка давление", limit=3)
    assert len(chunks_pressure) > 0
    assert any("Стандарт монтажа" in c["title"] for c in chunks_pressure)


def test_rag_answer_with_citations() -> None:
    """Tests grounded answer synthesis with [1], [2] citations and source references."""
    kb_mod.ensure_seeded()

    res = kb_mod.answer_question("Какая скидка допустима для дилера без согласования с директором?")
    assert res.grounded is True
    assert "[1]" in res.answer
    assert len(res.sources) >= 1
    assert any("Ценовая политика" in s.title for s in res.sources)
    assert res.sources[0].quote != ""


def test_rag_refusal_on_unknown_topics() -> None:
    """Tests that out-of-scope questions result in a clean and honest refusal without fake citations."""
    kb_mod.ensure_seeded()

    trap_res = kb_mod.answer_question("Какая марка кофе закупается на кухню офиса?")
    assert trap_res.grounded is False
    assert len(trap_res.sources) == 0
    assert "нет информации" in trap_res.answer.lower()

    autocad_res = kb_mod.answer_question("Где скачать взломанную версию AutoCAD?")
    assert autocad_res.grounded is False
    assert len(autocad_res.sources) == 0


def test_eval_benchmark_suite() -> None:
    """Runs the 20 golden benchmark cases and checks high pass rate and 100% correct refusals."""
    kb_mod.ensure_seeded()

    report = kb_mod.run_eval()
    assert report["total"] == 20
    assert report["passed"] >= 18
    assert report["passRate"] >= 90.0
    assert report["refusalsTotal"] == 5
    assert report["refusalsCorrect"] == 5


def test_kb_api_endpoints() -> None:
    """Tests /api/kb/stats, /api/kb/answer, /api/kb/ask, /api/kb/documents and /api/kb/eval."""
    client = TestClient(app)

    # 1. Stats
    resp = client.get("/api/kb/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["documents"] >= 24
    assert stats["chunks"] >= 318
    assert stats["grounded"] >= 90
    assert stats["evalTotal"] == 20
    assert stats["refusalsCorrect"] == 5

    # 2. Answer via GET
    resp = client.get("/api/kb/answer?q=Какой+срок+гарантии+на+монтажные+работы?")
    assert resp.status_code == 200
    ans = resp.json()
    assert ans["grounded"] is True
    assert "[1]" in ans["answer"]
    assert len(ans["sources"]) >= 1

    # 3. Ask via POST
    resp = client.post("/api/kb/ask", json={"question": "Какая скидка дилеру?"})
    assert resp.status_code == 200
    ans_post = resp.json()
    assert ans_post["grounded"] is True

    # 4. Documents list
    resp = client.get("/api/kb/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) >= 10
    assert any("Ценовая политика" in d["title"] for d in docs)

    # 5. Eval report
    resp = client.get("/api/kb/eval")
    assert resp.status_code == 200
    ev = resp.json()
    assert ev["total"] == 20


def test_tool_knowledge_search() -> None:
    """Tests knowledge_search tool execution through agent registry."""
    res = tools.run_tool("knowledge_search", {"query": "скидка дилерам", "limit": 2})
    assert isinstance(res, dict)
    assert res["grounded"] is True
    assert len(res["sources"]) > 0
    assert len(res["chunks"]) > 0
