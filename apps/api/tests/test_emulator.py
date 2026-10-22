import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from pulse.core import clock
from pulse.crm.emulator import Bitrix24Emulator
from pulse.crm.rest import ReadOnlyViolation
from tests.conftest import NOW

SHAPES = json.loads((Path(__file__).parents[1] / "pulse/crm/fixtures/shapes.json").read_text(encoding="utf-8"))
# Fields the real portal returns but the snapshot portal had empty, so they are absent from the snapshot.
KNOWN_EXTRA = {"crm.company.list": {"PHONE"}, "tasks.task.list": {"ufCrmTask"}, "department.get": {"UF_HEAD"}}
COLLECTION = {
    "crm.deal.list": "deals",
    "crm.company.list": "companies",
    "crm.activity.list": "activities",
    "voximplant.statistic.get": "calls",
    "tasks.task.list": "tasks",
    "crm.stagehistory.list": "stagehistory",
    "user.get": "users",
    "crm.category.list": "categories",
    "crm.status.list": "statuses",
    "department.get": "departments",
}


@pytest.fixture
def emu(dataset: tuple[dict[str, Any], dict[str, Any]]) -> Bitrix24Emulator:
    return Bitrix24Emulator(dataset[0])


@pytest.mark.parametrize("method", sorted(COLLECTION))
def test_emulated_records_use_only_real_bitrix24_fields(dataset: tuple[dict[str, Any], Any], method: str) -> None:
    keys = set().union(*(set(r) for r in dataset[0][COLLECTION[method]]))
    invented = keys - set(SHAPES[method]) - KNOWN_EXTRA.get(method, set())
    assert not invented, f"{method}: fields that a real portal does not return: {sorted(invented)}"


async def test_list_pages_by_fifty_with_total_and_next(emu: Bitrix24Emulator) -> None:
    first = await emu.call("crm.deal.list", {"select": ["ID"]})
    assert len(first["result"]) == 50
    assert first["next"] == 50 and first["total"] > 50
    assert {"start", "finish", "duration", "date_start"} <= set(first["time"])
    last = await emu.call("crm.deal.list", {"select": ["ID"], "start": first["total"] - 1})
    assert len(last["result"]) == 1 and "next" not in last


async def test_filter_operators(emu: Bitrix24Emulator) -> None:
    won = await emu.call(
        "crm.deal.list",
        {
            "filter": {"STAGE_SEMANTIC_ID": "S", ">OPPORTUNITY": 1_000_000},
            "select": ["ID", "OPPORTUNITY", "STAGE_SEMANTIC_ID"],
        },
    )
    assert won["total"] > 0
    assert all(r["STAGE_SEMANTIC_ID"] == "S" and float(r["OPPORTUNITY"]) > 1_000_000 for r in won["result"])
    some = [r["ID"] for r in won["result"][:2]]
    picked = await emu.call("crm.deal.list", {"filter": {"@ID": some}, "select": ["ID"]})
    assert sorted(r["ID"] for r in picked["result"]) == sorted(some)
    rest = await emu.call("crm.deal.list", {"filter": {"!@ID": some}, "select": ["ID"]})
    assert rest["total"] == (await emu.call("crm.deal.list", {}))["total"] - len(some)
    like = await emu.call("crm.company.list", {"filter": {"%TITLE": "медиус"}})
    assert [r["TITLE"] for r in like["result"]] == ["Клиника «Медиус»"]


async def test_select_projects_fields_and_order_desc(emu: Bitrix24Emulator) -> None:
    res = await emu.call("crm.deal.list", {"select": ["TITLE"], "order": {"OPPORTUNITY": "DESC"}})
    assert set(res["result"][0]) == {"ID", "TITLE"}
    amounts = await emu.call("crm.deal.list", {"select": ["OPPORTUNITY"], "order": {"OPPORTUNITY": "DESC"}})
    values = [float(r["OPPORTUNITY"]) for r in amounts["result"]]
    assert values == sorted(values, reverse=True)


async def test_future_records_stay_hidden_until_their_time(emu: Bitrix24Emulator) -> None:
    flt = {"FILTER": {">=CALL_START_DATE": clock.b24(NOW.replace(hour=0, minute=0))}}
    before = (await emu.call("voximplant.statistic.get", flt))["total"]
    clock.freeze(NOW + timedelta(hours=2))
    emu._memo.clear()
    after = (await emu.call("voximplant.statistic.get", flt))["total"]
    assert after > before


async def test_tasks_accept_upper_case_filters_and_return_camel_case(emu: Bitrix24Emulator) -> None:
    res = await emu.call(
        "tasks.task.list", {"filter": {"RESPONSIBLE_ID": 15, "!REAL_STATUS": 5}, "select": ["ID", "TITLE", "DEADLINE"]}
    )
    tasks = res["result"]["tasks"]
    assert tasks and all(set(t) <= {"id", "title", "deadline"} for t in tasks)


@pytest.mark.parametrize(
    ("method", "params"),
    [("crm.deal.add", {"fields": {}}), ("crm.deal.list", {"fields": {}}), ("crm.deal.list", {"filter": "x"})],
)
async def test_same_read_only_allowlist_as_the_live_adapter(
    emu: Bitrix24Emulator, method: str, params: dict[str, Any]
) -> None:
    with pytest.raises(ReadOnlyViolation):
        await emu.call(method, params)
