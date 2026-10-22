"""In-memory snapshot of the synced store. Rebuilt only after a sync, so screens read it for free."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from pulse import seed
from pulse.core import clock, db, store
from pulse.crm.model import Call, Company, Deal, Funnel, Lead, Stage, StageChange, Task, User
from pulse.erp.model import Counterparty, Payment, SaleDoc, StockItem, SupplierOrder
from pulse.modules.sales.quality import Assessment

SALES_DEPARTMENT = 3
DAY_START, DAY_END = time(9), time(19)


@dataclass
class Data:
    users: dict[int, User]
    funnels: list[Funnel]
    companies: dict[int, Company]
    deals: list[Deal]
    leads: list[Lead]
    calls: list[Call]
    tasks: list[Task]
    history: list[StageChange]
    assessments: dict[int, Assessment]
    sales: list[SaleDoc]
    payments: list[Payment]
    stock: list[StockItem]
    orders: list[SupplierOrder]
    counterparties: list[Counterparty]
    story: dict[str, Any]
    stages: dict[str, Stage] = field(init=False)
    team: list[User] = field(init=False)
    cache: dict[str, Any] = field(init=False, default_factory=dict)  # per-snapshot memo for derived facts

    def __post_init__(self) -> None:
        self.stages = {s.id: s for f in self.funnels for s in f.stages}
        active = {d.assigned_id for d in self.deals if (clock.now() - d.created).days < 120}
        self.team = [
            u for u in self.users.values() if SALES_DEPARTMENT in u.department_ids and u.id in active and u.active
        ]

    # -- time

    @property
    def now(self) -> datetime:
        return clock.now()

    @property
    def day(self) -> date:
        """The working day the dashboard is about: today, or the last working day on a weekend."""
        d = self.now.date()
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

    @property
    def day_progress(self) -> float:
        """Share of the working day (9:00–19:00) already gone; 1.0 for a past day."""
        if self.day != self.now.date():
            return 1.0
        start = datetime.combine(self.day, DAY_START, tzinfo=self.now.tzinfo)
        span = (datetime.combine(self.day, DAY_END) - datetime.combine(self.day, DAY_START)).total_seconds()
        return max(0.0, min(1.0, (self.now - start).total_seconds() / span))

    def workdays_before(self, d: date, n: int) -> list[date]:
        out: list[date] = []
        while len(out) < n:
            d -= timedelta(days=1)
            if d.weekday() < 5:
                out.append(d)
        return out

    # -- names

    def name(self, uid: int) -> str:
        u = self.users.get(uid)
        return u.name if u else f"Сотрудник {uid}"

    def client(self, company_id: int | None) -> str:
        c = self.companies.get(company_id or 0)
        return c.title if c else "Без компании"

    def funnel_name(self, fid: int) -> str:
        return next((f.name for f in self.funnels if f.id == fid), str(fid))

    def stage_name(self, stage_id: str) -> str:
        s = self.stages.get(stage_id)
        return s.name if s else stage_id


_cache: dict[str, Any] = {}


def load() -> Data:
    stamp = db.get_setting("last_sync")
    if _cache.get("stamp") == stamp and "data" in _cache:
        cached: Data = _cache["data"]
        return cached
    data = Data(
        users={u.id: u for u in store.load("user", User)},
        funnels=store.load("funnel", Funnel),
        companies={c.id: c for c in store.load("company", Company)},
        deals=store.load("deal", Deal),
        leads=store.load("lead", Lead),
        calls=sorted(store.load("call", Call), key=lambda c: c.started),
        tasks=store.load("task", Task),
        history=store.load("stage_change", StageChange),
        assessments={a.call_id: a for a in store.load("call_assessment", Assessment)},
        sales=store.load("erp_sale", SaleDoc),
        payments=store.load("erp_payment", Payment),
        stock=store.load("erp_stock", StockItem),
        orders=store.load("erp_order", SupplierOrder),
        counterparties=store.load("erp_counterparty", Counterparty),
        story=seed.story(),
    )
    _cache.update(stamp=stamp, data=data)
    return data
