from datetime import timedelta

from fastapi.testclient import TestClient

from pulse import sync
from pulse.core import clock, db, store
from pulse.crm.model import Call, Deal, Funnel
from pulse.erp.model import SaleDoc, SupplierOrder
from tests.conftest import NOW


async def test_reset_builds_the_company_and_syncs_both_systems() -> None:
    db.init()
    result = await sync.reset()
    counts = result["counts"]
    assert counts["deals"] > 300 and counts["calls"] > 5000 and counts["erp_sales"] > 50
    funnels = store.load("funnel", Funnel)
    assert [f.name for f in funnels] == ["Поставка", "Монтаж", "Сервис"]
    assert funnels[0].stages[-2].semantics == "success"
    deal = store.load("deal", Deal)[0]
    assert deal.created.tzinfo is not None
    calls = store.load("call", Call)
    assert max(c.started for c in calls) <= NOW  # nothing from the future
    assert any(c.missed for c in calls) and any(c.deal_id for c in calls)
    orders = store.load("erp_order", SupplierOrder)
    assert any(o.number == "ЗП-0388" and o.lines for o in orders)
    assert store.load("erp_sale", SaleDoc)[0].deal_id is not None


async def test_delta_picks_up_calls_that_happened_since_the_last_sync() -> None:
    db.init()
    await sync.reset()
    before = db.count("call")
    clock.freeze(NOW + timedelta(hours=1, minutes=30))
    counts = await sync.delta()
    assert counts["calls"] > 0
    assert db.count("call") > before


def test_app_starts_with_a_fresh_seed_and_reports_the_store() -> None:
    with TestClient(__import__("pulse.main", fromlist=["app"]).app) as client:
        body = client.get("/api/data/summary").json()
        assert body["seed_fresh"] is True
        assert body["counts"]["deal"] > 300
        assert client.post("/api/admin/reset").status_code == 403
        assert client.post("/api/admin/reset", headers={"X-Admin-Key": "test-admin"}).status_code == 200
