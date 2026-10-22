"""The planted story must hold every day: the screens and the copilot answers rely on it."""

from datetime import datetime, timedelta
from typing import Any

from pulse.erp import odata
from pulse.seed import erp
from tests.conftest import NOW

Data = tuple[dict[str, Any], dict[str, Any]]


def _calls_to(data: dict[str, Any], company_id: int) -> list[dict[str, Any]]:
    return [c for c in data["calls"] if int(c["CRM_ENTITY_ID"]) == company_id]


def test_generation_is_deterministic(dataset: Data) -> None:
    from pulse.seed import b24

    again, _ = b24.generate(NOW)
    assert again["deals"] == dataset[0]["deals"]
    assert len(again["calls"]) == len(dataset[0]["calls"])


def test_missed_calls_from_the_clinic_have_no_callback(dataset: Data) -> None:
    data, story = dataset
    clinic = story["company_ids"]["Клиника «Медиус»"]
    today = [c for c in _calls_to(data, clinic) if c["CALL_START_DATE"].startswith(NOW.date().isoformat())]
    assert [c["CALL_FAILED_CODE"] for c in today] == ["304", "304"]
    assert all(c["CALL_TYPE"] == "2" for c in today)


def test_stale_offer_has_no_contact_for_nine_days(dataset: Data) -> None:
    data, story = dataset
    deal = next(d for d in data["deals"] if int(d["ID"]) == story["deals"]["stale_offer"])
    assert deal["STAGE_ID"] == "PREPAYMENT_INVOICE" and float(deal["OPPORTUNITY"]) == 2_400_000
    last = datetime.fromisoformat(deal["LAST_ACTIVITY_TIME"])
    assert (NOW - last).days >= 9
    assert not [
        c for c in _calls_to(data, int(deal["COMPANY_ID"])) if datetime.fromisoformat(c["CALL_START_DATE"]) > last
    ]


def test_overdue_survey_task(dataset: Data) -> None:
    data, story = dataset
    task = next(t for t in data["tasks"] if int(t["id"]) == story["tasks"]["survey_overdue"])
    assert task["status"] != "5" and datetime.fromisoformat(task["deadline"]) < NOW


def test_slumping_manager_called_much_less_this_week(dataset: Data) -> None:
    data, _ = dataset
    week = NOW - timedelta(days=7)
    month = NOW - timedelta(days=35)
    mine = [
        datetime.fromisoformat(c["CALL_START_DATE"])
        for c in data["calls"]
        if c["PORTAL_USER_ID"] == "13" and c["CALL_TYPE"] == "1"
    ]
    recent = sum(1 for t in mine if week <= t <= NOW) / 5
    before = sum(1 for t in mine if month <= t < week) / 20
    assert recent < before * 0.6


def test_reconciliation_has_exactly_four_planted_gaps(dataset: Data) -> None:
    data, story = dataset
    sets = erp.generate(data, story, NOW.date())
    by_deal = {s["Комментарий"]: s for s in sets[odata.SALES]}
    deals = story["deals"]
    assert f"CRM:D_{deals['won_no_shipment']}" not in by_deal
    assert f"CRM:D_{deals['erp_missing']}" not in by_deal
    less = next(d for d in data["deals"] if int(d["ID"]) == deals["erp_less"])
    assert by_deal[f"CRM:D_{deals['erp_less']}"]["СуммаДокумента"] == float(less["OPPORTUNITY"]) - 40_000
    other = by_deal[f"CRM:D_{deals['erp_other_counterparty']}"]
    assert other["Контрагент_Key"] != erp.key(
        "cp", next(d["COMPANY_ID"] for d in data["deals"] if int(d["ID"]) == deals["erp_other_counterparty"])
    )
    won = [d for d in data["deals"] if d["STAGE_SEMANTIC_ID"] == "S"]
    assert len(sets[odata.SALES]) == len(won) - 2
    assert any(o["Number"] == "ЗП-0388" and o["СуммаДокумента"] == 412_300 for o in sets[odata.SUPPLIER_ORDERS])
