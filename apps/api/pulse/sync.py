"""Pulls CRM and ERP data through the ports into the local store.

Full sync after start or a reset; afterwards a cheap delta every few minutes picks up new calls,
tasks and deal changes — in the demo that is how the day "happens" on the dashboard.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from pulse import crm as crm_factory
from pulse import erp as erp_factory
from pulse import seed
from pulse.core import clock, db, store
from pulse.core.config import get_settings
from pulse.crm.port import CrmPort
from pulse.erp.port import ErpPort
from pulse.modules.sales.quality import Assessment

log = logging.getLogger(__name__)
CALL_DAYS = 45
ERP_DAYS = 120
_lock = asyncio.Lock()


async def full(crm: CrmPort | None = None, erp: ErpPort | None = None) -> dict[str, int]:
    crm = crm or crm_factory.crm()
    erp = erp or erp_factory.erp()
    started = time.monotonic()
    now = clock.now()
    counts = {
        "users": store.save("user", await crm.users()),
        "funnels": store.save("funnel", await crm.funnels()),
        "companies": store.save("company", await crm.companies()),
        "deals": store.save("deal", await crm.deals(), at="modified"),
        "leads": store.save("lead", await crm.leads(), at="created"),
        "calls": store.save("call", await crm.calls(now - timedelta(days=CALL_DAYS * 1.5)), at="started"),
        "tasks": store.save("task", await crm.tasks(), at="created"),
        "stage_changes": store.save("stage_change", await crm.stage_history(now - timedelta(days=150)), at="at"),
    }
    if get_settings().crm_mode == "emulator":
        # In the demo the quality model's verdicts ship with the dataset instead of being computed on the fly.
        counts["assessments"] = store.save("call_assessment", [Assessment(**a) for a in seed.assessments()])
    since = now.date() - timedelta(days=ERP_DAYS)
    counts |= {
        "erp_counterparties": store.save("erp_counterparty", await erp.counterparties(), key="key"),
        "erp_stock": store.save("erp_stock", await erp.stock(), key="sku"),
        "erp_sales": store.save("erp_sale", await erp.sales(since), key="key", at="date"),
        "erp_payments": store.save("erp_payment", await erp.payments(since), key="key", at="date"),
        "erp_orders": store.save("erp_order", await erp.supplier_orders(since), key="key", at="date"),
    }
    db.set_setting("last_sync", now.isoformat())
    took = time.monotonic() - started
    db.log(
        "Битрикс24",
        "полный синк",
        f"{counts['deals']} сделок, {counts['calls']} звонков, {counts['tasks']} задач · {took:.1f} с",
    )
    db.log(
        "1С:ERP",
        "полный синк",
        f"{counts['erp_sales']} реализаций, {counts['erp_payments']} оплат, {counts['erp_stock']} позиций",
    )
    return counts


async def delta(crm: CrmPort | None = None) -> dict[str, int]:
    crm = crm or crm_factory.crm()
    now = clock.now()
    last = db.get_setting("last_sync")
    since = (datetime.fromisoformat(last) if last else now - timedelta(hours=1)) - timedelta(minutes=10)
    calls = await crm.calls(since)
    counts = {
        "calls": store.merge("call", calls, at="started"),
        "deals": store.save("deal", await crm.deals(), at="modified"),
        "tasks": store.save("task", await crm.tasks(), at="created"),
        "leads": store.save("lead", await crm.leads(), at="created"),
    }
    db.set_setting("last_sync", now.isoformat())
    if calls:
        db.log(
            "Битрикс24",
            "voximplant.statistic.get",
            f"дельта: {len(calls)} звонков, {sum(c.missed for c in calls)} пропущенных",
        )
    return counts


async def reset() -> dict[str, Any]:
    """Nightly reset: regenerate the demo company for today and resync from scratch."""
    async with _lock:
        story = seed.build()
        counts = await full()
        db.log("Система", "сброс демо-данных", f"компания пересоздана на {clock.today():%d.%m.%Y}", "info")
        return {"story": story, "counts": counts}


async def ensure_ready() -> None:
    db.init()
    settings = get_settings()
    if settings.crm_mode == "emulator" and not seed.is_fresh():
        await reset()
    elif db.count("deal") == 0:
        async with _lock:
            await full()


async def loop() -> None:
    """Background worker: delta sync every SYNC_INTERVAL_S, full reset when the demo day changes."""
    settings = get_settings()
    while True:
        await asyncio.sleep(settings.sync_interval_s)
        try:
            if settings.crm_mode == "emulator" and not seed.is_fresh():
                await reset()
            else:
                async with _lock:
                    await delta()
        except Exception:
            log.exception("sync failed")
            db.log("Система", "синк", "ошибка синхронизации, повтор в следующем цикле", "danger")
