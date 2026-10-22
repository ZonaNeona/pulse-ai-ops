"""`CrmPort` over any `B24Transport` (emulator or live portal): paging plus field mapping."""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

from pulse.core import clock
from pulse.crm.model import Call, Company, Deal, Funnel, Lead, Semantics, Stage, StageChange, Task, User
from pulse.crm.port import B24Transport

SEMANTICS: dict[str, Semantics] = {"S": "success", "F": "failure", "success": "success", "failure": "failure"}
CALL_FIELDS = ["ID", "PORTAL_USER_ID", "PHONE_NUMBER", "CALL_START_DATE", "CALL_DURATION", "CALL_TYPE"]


def _dt(value: Any) -> datetime:
    parsed = clock.parse(value)
    if parsed is None:
        raise ValueError("Пустая дата в обязательном поле")
    return parsed


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "", "0", 0) else None
    except (TypeError, ValueError):
        return None


class B24Crm:
    def __init__(self, transport: B24Transport):
        self.transport = transport

    async def _all(
        self, method: str, params: dict[str, Any], wrapper: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        start = 0
        while True:
            res = await self.transport.call(method, {**params, "start": start})
            result: Any = res.get("result") or ([] if wrapper is None else {})
            for row in result[wrapper] if wrapper else result:
                yield row
            nxt = res.get("next")
            if nxt is None or int(nxt) <= start:
                return
            start = int(nxt)

    async def users(self) -> list[User]:
        return [
            User(
                id=int(u["ID"]),
                name=f"{u.get('NAME') or ''} {u.get('LAST_NAME') or ''}".strip(),
                position=u.get("WORK_POSITION") or "",
                department_ids=tuple(int(d) for d in u.get("UF_DEPARTMENT") or []),
                active=bool(u.get("ACTIVE")),
            )
            async for u in self._all("user.get", {"filter": {"ACTIVE": True}, "sort": "ID", "order": "ASC"})
        ]

    async def funnels(self) -> list[Funnel]:
        res = await self.transport.call("crm.category.list", {"entityTypeId": 2})
        categories = res["result"]["categories"]
        entity = {("DEAL_STAGE" if int(c["id"]) == 0 else f"DEAL_STAGE_{c['id']}"): int(c["id"]) for c in categories}
        stages: dict[int, list[Stage]] = {fid: [] for fid in entity.values()}
        async for s in self._all("crm.status.list", {"filter": {"ENTITY_ID": list(entity)}, "order": {"SORT": "ASC"}}):
            fid = entity.get(s["ENTITY_ID"])
            if fid is None:
                continue
            raw = (s.get("EXTRA") or {}).get("SEMANTICS") or s.get("SEMANTICS")
            stages[fid].append(
                Stage(
                    id=s["STATUS_ID"],
                    funnel_id=fid,
                    name=s["NAME"],
                    sort=int(s.get("SORT") or 0),
                    semantics=SEMANTICS.get(str(raw), "process"),
                )
            )
        return [Funnel(id=int(c["id"]), name=c["name"], stages=tuple(stages[int(c["id"])])) for c in categories]

    async def companies(self) -> list[Company]:
        select = ["ID", "TITLE", "ASSIGNED_BY_ID", "INDUSTRY", "DATE_CREATE", "PHONE"]
        return [
            Company(
                id=int(c["ID"]),
                title=c["TITLE"],
                assigned_id=int(c.get("ASSIGNED_BY_ID") or 0),
                industry=c.get("INDUSTRY") or "",
                phone=(c.get("PHONE") or [{}])[0].get("VALUE"),
                created=_dt(c["DATE_CREATE"]),
            )
            async for c in self._all("crm.company.list", {"select": select, "order": {"ID": "ASC"}})
        ]

    async def deals(self) -> list[Deal]:
        select = [
            "ID",
            "TITLE",
            "CATEGORY_ID",
            "STAGE_ID",
            "STAGE_SEMANTIC_ID",
            "OPPORTUNITY",
            "COMPANY_ID",
            "ASSIGNED_BY_ID",
            "DATE_CREATE",
            "DATE_MODIFY",
            "MOVED_TIME",
            "LAST_ACTIVITY_TIME",
            "CLOSEDATE",
        ]
        out = []
        async for d in self._all("crm.deal.list", {"select": select, "order": {"ID": "ASC"}}):
            close = clock.parse(d.get("CLOSEDATE"))
            out.append(
                Deal(
                    id=int(d["ID"]),
                    title=d["TITLE"],
                    funnel_id=int(d.get("CATEGORY_ID") or 0),
                    stage_id=d["STAGE_ID"],
                    semantics=SEMANTICS.get(d.get("STAGE_SEMANTIC_ID") or "", "process"),
                    amount=float(d.get("OPPORTUNITY") or 0),
                    company_id=_int(d.get("COMPANY_ID")),
                    assigned_id=int(d.get("ASSIGNED_BY_ID") or 0),
                    created=_dt(d["DATE_CREATE"]),
                    modified=_dt(d["DATE_MODIFY"]),
                    moved=clock.parse(d.get("MOVED_TIME")),
                    last_activity=clock.parse(d.get("LAST_ACTIVITY_TIME")),
                    close_date=close.date() if close else None,
                )
            )
        return out

    async def leads(self) -> list[Lead]:
        select = ["ID", "TITLE", "ASSIGNED_BY_ID", "STATUS_ID", "STATUS_SEMANTIC_ID", "DATE_CREATE", "COMPANY_TITLE"]
        return [
            Lead(
                id=int(x["ID"]),
                title=x["TITLE"],
                assigned_id=int(x.get("ASSIGNED_BY_ID") or 0),
                status_id=x.get("STATUS_ID") or "NEW",
                created=_dt(x["DATE_CREATE"]),
                company_title=x.get("COMPANY_TITLE") or "",
                in_progress=(x.get("STATUS_SEMANTIC_ID") or "P") == "P",
            )
            async for x in self._all("crm.lead.list", {"select": select, "order": {"ID": "ASC"}})
        ]

    async def calls(self, since: datetime) -> list[Call]:
        # Deal binding lives on the CRM activity; duration and the missed flag — in telephony statistics.
        owners: dict[int, int] = {}
        flt = {"TYPE_ID": 2, ">=START_TIME": clock.b24(since), "OWNER_TYPE_ID": 2}
        async for a in self._all(
            "crm.activity.list", {"filter": flt, "select": ["ID", "OWNER_ID"], "order": {"ID": "ASC"}}
        ):
            owners[int(a["ID"])] = int(a["OWNER_ID"])
        out = []
        params = {"FILTER": {">=CALL_START_DATE": clock.b24(since)}, "SORT": "CALL_START_DATE", "ORDER": "ASC"}
        async for c in self._all("voximplant.statistic.get", params):
            kind = str(c.get("CALL_TYPE"))
            inbound = kind in ("2", "3")
            activity = _int(c.get("CRM_ACTIVITY_ID"))
            out.append(
                Call(
                    id=int(c["ID"]),
                    user_id=int(c.get("PORTAL_USER_ID") or 0),
                    phone=c.get("PHONE_NUMBER") or "",
                    started=_dt(c["CALL_START_DATE"]),
                    duration_s=int(c.get("CALL_DURATION") or 0),
                    direction="in" if inbound else "out",
                    missed=inbound and str(c.get("CALL_FAILED_CODE")) == "304",
                    company_id=_int(c.get("CRM_ENTITY_ID")) if c.get("CRM_ENTITY_TYPE") == "COMPANY" else None,
                    deal_id=owners.get(activity) if activity else None,
                    activity_id=activity,
                    has_record=bool(c.get("RECORD_FILE_ID")),
                )
            )
        return out

    async def tasks(self) -> list[Task]:
        since = clock.b24(clock.now() - timedelta(days=120))
        select = ["ID", "TITLE", "RESPONSIBLE_ID", "CREATED_DATE", "DEADLINE", "CLOSED_DATE", "STATUS", "UF_CRM_TASK"]
        return [
            Task(
                id=int(t["id"]),
                title=t["title"],
                responsible_id=int(t.get("responsibleId") or 0),
                created=_dt(t["createdDate"]),
                deadline=clock.parse(t.get("deadline")),
                closed=clock.parse(t.get("closedDate")),
                status=int(t.get("status") or 2),
                crm=tuple(t.get("ufCrmTask") or ()),
            )
            async for t in self._all(
                "tasks.task.list", {"filter": {">=CREATED_DATE": since}, "select": select}, "tasks"
            )
        ]

    async def stage_history(self, since: datetime) -> list[StageChange]:
        params = {"entityTypeId": 2, "filter": {">=CREATED_TIME": clock.b24(since)}, "order": {"ID": "ASC"}}
        return [
            StageChange(
                id=int(h["ID"]),
                deal_id=int(h["OWNER_ID"]),
                funnel_id=int(h.get("CATEGORY_ID") or 0),
                stage_id=h["STAGE_ID"],
                at=_dt(h["CREATED_TIME"]),
            )
            async for h in self._all("crm.stagehistory.list", params, "items")
        ]
