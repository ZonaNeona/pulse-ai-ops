"""Screens' business logic on the demo company at a fixed moment (Wednesday 16:40)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from pulse import data, sync
from pulse.core import db
from pulse.modules import integrations, overview
from pulse.modules.sales import calls, deals, pulse, quality, signals, team


@pytest.fixture
async def snapshot() -> data.Data:
    db.init()
    await sync.reset()
    return data.load()


async def test_signals_tell_the_planted_story(snapshot: data.Data) -> None:
    sigs = signals.build(snapshot)
    titles = " | ".join(s["title"] for s in sigs)
    assert "Клиника «Медиус»: 2 пропущенных звонка" in titles
    assert any(s["rule"] == "lead-no-action" and "3 000 м²" in s["title"] for s in sigs)
    assert any(s["rule"] == "stale-deal" and "2,4 млн ₽" in s["title"] for s in sigs)
    assert any(s["rule"] == "low-score" and s["manager"] == "Дмитрий Лебедев" for s in sigs)
    assert len(sigs) <= 25, "the feed must stay readable"
    ranks = [signals.SEVERITY_RANK[s["severity"]] for s in sigs]
    assert ranks == sorted(ranks)


async def test_kpis_compare_with_the_same_hour_of_previous_days(snapshot: data.Data) -> None:
    kpis = {k["key"]: k for k in pulse.kpis(snapshot)}
    assert kpis["calls"]["value"] > 100
    assert kpis["calls"]["delta"] is not None and abs(kpis["calls"]["delta"]) < 60
    assert kpis["noCallback"]["value"] >= 2
    assert len(pulse.series(snapshot)) == 14


async def test_team_flags_the_slumping_manager(snapshot: data.Data) -> None:
    rows = {m["name"]: m for m in team.team(snapshot)}
    assert rows["Дмитрий Лебедев"]["status"] == "danger"
    assert rows["Марина Соколова"]["quality"] > rows["Дмитрий Лебедев"]["quality"] + 25
    assert rows["Павел Орлов"]["role"] == "newbie"
    assert all(m["callsNorm"] > 0 for m in rows.values())


async def test_reconciliation_finds_the_four_gaps(snapshot: data.Data) -> None:
    rec = integrations.reconciliation(snapshot)
    issues = sorted(g["issue"].split(":")[0] for g in rec["gaps"])
    assert len(rec["gaps"]) == 4
    assert issues.count("Оплачено в CRM, реализации в 1С нет") == 2
    assert any(i.startswith("Сумма в 1С меньше на 40") for i in issues)
    assert rec["crmAmount"] - rec["erpAmount"] > 0


async def test_call_review_scores_add_up_and_quote_the_transcript(snapshot: data.Data) -> None:
    call_id = snapshot.story["calls"]["low_score"]
    review = calls.review(snapshot, call_id)
    assert review is not None
    assert review["call"]["score"] == 41
    assert sum(c["score"] for c in review["criteria"]) == 41
    assert all(c["score"] <= c["max"] for c in review["criteria"])
    lines = {line["text"] for line in review["transcript"]}
    assert all(c["quote"] in lines for c in review["criteria"] if "quote" in c)
    assert sum(w for _, _, w in quality.CRITERIA) == 100


async def test_board_and_feed(snapshot: data.Data) -> None:
    board = deals.board(snapshot)
    stages = {s["id"] for f in deals.funnels(snapshot) for s in f["stages"]}
    assert board and all(d["stage"] in stages for d in board)
    feed = calls.feed(snapshot)
    assert feed and all(not (c["direction"] == "out" and c["durationSec"] < 25) for c in feed)


async def test_overview_combines_modules(snapshot: data.Data) -> None:
    body = overview.overview(snapshot)
    assert [m["id"] for m in body["modules"]][:2] == ["sales", "integrations"]
    assert body["revenue"]["fact"] > 0 and body["revenue"]["plan"] > body["revenue"]["fact"]
    assert body["actions"] and body["kpis"][0]["unit"] == "rub"


@pytest.fixture
def client() -> Iterator[TestClient]:
    from pulse.main import app

    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize(
    "path",
    [
        "/api/overview",
        "/api/sales/pulse",
        "/api/sales/team",
        "/api/sales/funnels",
        "/api/sales/deals",
        "/api/sales/calls",
        "/api/integrations",
        "/api/integrations/log",
        "/api/integrations/reconciliation",
    ],
)
def test_screen_endpoints_answer(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200


def test_call_review_endpoint(client: TestClient) -> None:
    feed = client.get("/api/sales/calls").json()
    scored = next(c for c in feed if c["score"] is not None)
    assert client.get(f"/api/sales/calls/{scored['id']}").json()["call"]["id"] == scored["id"]
    assert client.get("/api/sales/calls/1").status_code == 404
