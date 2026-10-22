"""Generates the demo company's Bitrix24 data in native REST format.

Background activity is random but seeded; on top of it a few situations are planted on purpose
(the "story"), so every screen has something worth showing whatever the day.
Dates are relative to `now`: the nightly reset regenerates everything and "today" is always today.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from pulse.core.clock import b24
from pulse.seed import names

CALL_DAYS = 45
DEAL_DAYS = 120
CYCLE = {0: 22, 1: 48, 2: 8}  # typical days from creation to close per funnel
FUNNEL_SHARE = [(0, 0.55), (1, 0.25), (2, 0.20)]


@dataclass
class Gen:
    now: datetime
    rng: random.Random
    data: dict[str, Any] = field(default_factory=dict)
    story: dict[str, Any] = field(default_factory=dict)
    seq: dict[str, int] = field(default_factory=dict)

    def next_id(self, kind: str, start: int) -> int:
        self.seq[kind] = self.seq.get(kind, start) + self.rng.randint(1, 3)
        return self.seq[kind]

    @property
    def today(self) -> date:
        return self.now.date()

    def at(self, day: date, hh: int, mm: int = 0, ss: int = 0) -> datetime:
        return datetime.combine(day, time(hh, mm, ss), tzinfo=self.now.tzinfo)

    def workdays(self, n: int) -> list[date]:
        """The last `n` working days including today, oldest first."""
        out: list[date] = []
        d = self.today
        while len(out) < n:
            if d.weekday() < 5:
                out.append(d)
            d -= timedelta(days=1)
        return out[::-1]

    def day_time(self, day: date) -> datetime:
        # Two peaks: late morning and mid-afternoon, nothing before 9 or after 19.
        hour = self.rng.choice([9, 10, 10, 11, 11, 11, 12, 13, 14, 14, 15, 15, 16, 16, 17, 18])
        return self.at(day, hour, self.rng.randint(0, 59), self.rng.randint(0, 59))


def short(company: str) -> str:
    return company.split("«", 1)[1].rstrip("»") if "«" in company else company


def phone(rng: random.Random) -> str:
    return f"+7{rng.choice(['812', '495', '921', '911', '981'])}{rng.randint(1000000, 9999999)}"


def amount(rng: random.Random, low: int, high: int) -> int:
    return int(math.exp(rng.uniform(math.log(low), math.log(high))) / 1000) * 1000


def generate(now: datetime, seed: int = 2026) -> tuple[dict[str, Any], dict[str, Any]]:
    g = Gen(now=now, rng=random.Random(seed))
    _reference(g)
    _companies(g)
    _deals(g)
    _calls(g)
    _tasks(g)
    _leads(g)
    _last_activity(g)
    return g.data, g.story


# ---------------------------------------------------------------- reference data


def _reference(g: Gen) -> None:
    g.data["departments"] = names.DEPARTMENTS
    g.data["users"] = [
        {
            "ID": str(uid),
            "ACTIVE": True,
            "NAME": first,
            "LAST_NAME": last,
            "EMAIL": f"user{uid}@{names.COMPANY['domain']}",
            "WORK_POSITION": pos,
            "UF_DEPARTMENT": [dep],
            "USER_TYPE": "employee",
            "TIME_ZONE": "Europe/Moscow",
            "DATE_REGISTER": b24(g.now - timedelta(days=names.NEWBIE_START_DAYS if role == "newbie" else 700)),
            "IS_ONLINE": "Y" if role != "staff" else "N",
        }
        for uid, first, last, pos, dep, role, *_ in names.PEOPLE
    ]
    g.data["categories"] = [
        {"id": fid, "name": name, "sort": (fid + 1) * 100, "entityTypeId": 2, "isDefault": "Y" if fid == 0 else "N"}
        for fid, name, _ in names.FUNNELS
    ]
    statuses: list[dict[str, Any]] = []
    sid = 100
    for fid, _, stages in names.FUNNELS:
        for sort, (stage, title, sem) in enumerate(stages, start=1):
            sid += 1
            statuses.append(
                {
                    "ID": str(sid),
                    "ENTITY_ID": "DEAL_STAGE" if fid == 0 else f"DEAL_STAGE_{fid}",
                    "STATUS_ID": stage,
                    "NAME": title,
                    "NAME_INIT": title,
                    "SORT": str(sort * 10),
                    "SYSTEM": "Y" if sem != "P" else "N",
                    "COLOR": names.STATUS_COLORS[sem],
                    "SEMANTICS": sem if sem != "P" else None,
                    "CATEGORY_ID": str(fid),
                    "EXTRA": {
                        "SEMANTICS": {"P": "process", "S": "success", "F": "failure"}[sem],
                        "COLOR": names.STATUS_COLORS[sem],
                    },
                }
            )
    for sort, (stage, title, lead_sem) in enumerate(
        [
            ("NEW", "Не обработан", None),
            ("IN_PROCESS", "В работе", None),
            ("CONVERTED", "Качественный лид", "S"),
            ("JUNK", "Некачественный лид", "F"),
        ],
        1,
    ):
        sid += 1
        statuses.append(
            {
                "ID": str(sid),
                "ENTITY_ID": "STATUS",
                "STATUS_ID": stage,
                "NAME": title,
                "SORT": str(sort * 10),
                "SEMANTICS": lead_sem,
                "CATEGORY_ID": "0",
                "EXTRA": {"SEMANTICS": "process" if not lead_sem else ("success" if lead_sem == "S" else "failure")},
            }
        )
    g.data["statuses"] = statuses
    g.data["deal_fields"] = {
        k: {"type": t, "isRequired": k == "TITLE", "isReadOnly": k == "ID", "title": k}
        for k, t in [
            ("ID", "integer"),
            ("TITLE", "string"),
            ("CATEGORY_ID", "crm_category"),
            ("STAGE_ID", "crm_status"),
            ("OPPORTUNITY", "double"),
            ("COMPANY_ID", "crm_company"),
            ("ASSIGNED_BY_ID", "user"),
            ("DATE_CREATE", "datetime"),
            ("CLOSEDATE", "date"),
        ]
    }


# ---------------------------------------------------------------- companies


def _companies(g: Gen) -> None:
    rng = g.rng
    titles = list(names.FEATURED)
    seen = set(titles)
    reserved = {short(t) for t in names.FEATURED}  # «Медиус» must stay a single, unambiguous client
    while len(titles) < 140:
        name = rng.choice(names.CLIENT_NAMES)
        t = f"{rng.choice(names.CLIENT_PREFIX)} «{name}»"
        if name not in reserved and t not in seen:
            seen.add(t)
            titles.append(t)
    owners = {
        "Клиника «Медиус»": 13,
        "Завод «Термаль»": 14,
        "БЦ «Невский 38»": 15,
        "Логистик-Центр «Восток»": 11,
        "ЖК «Зелёный квартал»": 13,
        "ГК «СтройМонолит»": 12,
        "ТехПарк «Северный»": 11,
        "ООО «Аквалайн»": 11,
        "ТЦ «Галерея Парк»": 15,
        "Гостиница «Онега»": 16,
    }
    farmers = [p[0] for p in names.PEOPLE if p[5] == "farmer"]
    hunters = [p[0] for p in names.PEOPLE if p[5] in ("hunter", "newbie")]
    rows: list[dict[str, Any]] = []
    for i, title in enumerate(titles):
        cid = 20 + i * 2
        owner = owners.get(title) or (rng.choice(farmers) if rng.random() < 0.62 else rng.choice(hunters))
        age = rng.randint(40, 1100) if owner in farmers else rng.randint(5, 200)
        if owner == 15:
            age = min(age, names.NEWBIE_START_DAYS)
        created = g.now - timedelta(days=age, hours=rng.randint(0, 9))
        rows.append(
            {
                "ID": str(cid),
                "COMPANY_TYPE": "CUSTOMER",
                "TITLE": title,
                "ASSIGNED_BY_ID": str(owner),
                "CREATED_BY_ID": str(owner),
                "INDUSTRY": rng.choice(names.INDUSTRIES),
                "CURRENCY_ID": "RUB",
                "OPENED": "Y",
                "HAS_PHONE": "Y",
                "HAS_EMAIL": "N",
                "PHONE": [{"ID": str(cid * 10), "VALUE_TYPE": "WORK", "VALUE": phone(rng), "TYPE_ID": "PHONE"}],
                "DATE_CREATE": b24(created),
                "DATE_MODIFY": b24(created),
                "IS_MY_COMPANY": "N",
            }
        )
    g.data["companies"] = rows
    g.data["contacts"] = []
    g.story["company_ids"] = {r["TITLE"]: int(r["ID"]) for r in rows if r["TITLE"] in names.FEATURED}


def _company(g: Gen, title: str) -> dict[str, Any]:
    return next(c for c in g.data["companies"] if c["TITLE"] == title)


# ---------------------------------------------------------------- deals and stage history


def _stage_path(fid: int) -> tuple[list[str], str, str]:
    stages = next(s for f, _, s in names.FUNNELS if f == fid)
    process = [s for s, _, sem in stages if sem == "P"]
    won = next(s for s, _, sem in stages if sem == "S")
    lost = next(s for s, _, sem in stages if sem == "F")
    return process, won, lost


def _add_deal(
    g: Gen,
    *,
    fid: int,
    title: str,
    company: dict[str, Any],
    owner: int,
    value: int,
    created: datetime,
    stage_index: int | None,
    outcome: str | None,
    moved: datetime,
) -> dict[str, Any]:
    """Creates a deal plus its stage history. `outcome` is 'won'/'lost' for closed deals."""
    process, won, lost = _stage_path(fid)
    path = process[: (stage_index or 0) + 1] if outcome is None else process[: g.rng.randint(1, len(process))]
    final = won if outcome == "won" else lost if outcome == "lost" else path[-1]
    steps = path + ([final] if outcome else [])
    deal_id = g.next_id("deal", 1000)
    span = max(1.0, (moved - created).total_seconds())
    for i, stage in enumerate(steps):
        at = created + timedelta(seconds=span * (i / max(1, len(steps) - 1))) if len(steps) > 1 else created
        sem = "S" if stage == won else "F" if stage == lost else "P"
        g.data["stagehistory"].append(
            {
                "ID": g.next_id("hist", 5000),
                "TYPE_ID": 1 if i == 0 else 2,
                "OWNER_ID": deal_id,
                "CREATED_TIME": b24(at),
                "CATEGORY_ID": fid,
                "STAGE_SEMANTIC_ID": sem,
                "STAGE_ID": stage,
            }
        )
    sem = "S" if outcome == "won" else "F" if outcome == "lost" else "P"
    close = moved if outcome else created + timedelta(days=CYCLE[fid])
    deal = {
        "ID": str(deal_id),
        "TITLE": title,
        "TYPE_ID": "SALE",
        "CATEGORY_ID": str(fid),
        "STAGE_ID": final,
        "STAGE_SEMANTIC_ID": sem,
        "CURRENCY_ID": "RUB",
        "OPPORTUNITY": f"{value:.2f}",
        "IS_MANUAL_OPPORTUNITY": "Y",
        "COMPANY_ID": company["ID"],
        "CONTACT_ID": "0",
        "ASSIGNED_BY_ID": str(owner),
        "CREATED_BY_ID": str(owner),
        "MODIFY_BY_ID": str(owner),
        "MOVED_BY_ID": str(owner),
        "DATE_CREATE": b24(created),
        "DATE_MODIFY": b24(moved),
        "MOVED_TIME": b24(moved),
        "BEGINDATE": b24(created),
        "CLOSEDATE": b24(close),
        "OPENED": "Y",
        "CLOSED": "Y" if outcome else "N",
        "SOURCE_ID": g.rng.choice(["CALL", "WEB", "EMAIL", "RECOMMENDATION", "REPEAT_SALE"]),
        "IS_RETURN_CUSTOMER": "Y" if owner in (12, 14, 16) else "N",
        "LAST_ACTIVITY_TIME": b24(moved),
        "LAST_ACTIVITY_BY": str(owner),
        "COMMENTS": names.LOSS_REASONS[deal_id % 4] if outcome == "lost" else "",
    }
    g.data["deals"].append(deal)
    return deal


def _deals(g: Gen) -> None:
    rng = g.rng
    g.data["deals"], g.data["stagehistory"] = [], []
    by_owner: dict[int, list[dict[str, Any]]] = {}
    for c in g.data["companies"]:
        by_owner.setdefault(int(c["ASSIGNED_BY_ID"]), []).append(c)
    volume = {11: 70, 12: 72, 13: 64, 14: 66, 15: 16, 16: 78}
    people = {p[0]: p for p in names.PEOPLE}
    for owner, count in volume.items():
        win = people[owner][8]
        horizon = names.NEWBIE_START_DAYS if owner == 15 else DEAL_DAYS
        for _ in range(count):
            fid = rng.choices([f for f, _ in FUNNEL_SHARE], [w for _, w in FUNNEL_SHARE])[0]
            item, low, high = rng.choice(names.DEAL_ITEMS[fid])
            company = rng.choice(by_owner[owner])
            if company["TITLE"] in names.FEATURED:
                continue  # featured clients only carry the planted deals below
            created = g.now - timedelta(days=rng.uniform(0, horizon), hours=rng.uniform(0, 8))
            age = (g.now - created).days
            cycle = CYCLE[fid] * rng.uniform(0.6, 1.6)
            process, *_ = _stage_path(fid)
            if age > cycle:
                outcome = "won" if rng.random() < win * 0.9 else "lost"
                moved = created + timedelta(days=cycle)
                _add_deal(
                    g,
                    fid=fid,
                    title=f"{item} — {short(company['TITLE'])}",
                    company=company,
                    owner=owner,
                    value=amount(rng, low, high),
                    created=created,
                    stage_index=None,
                    outcome=outcome,
                    moved=moved,
                )
            else:
                idx = min(len(process) - 1, int(age / cycle * len(process)))
                moved = created + timedelta(days=age * rng.uniform(0.5, 1.0))
                _add_deal(
                    g,
                    fid=fid,
                    title=f"{item} — {short(company['TITLE'])}",
                    company=company,
                    owner=owner,
                    value=amount(rng, low, high),
                    created=created,
                    stage_index=idx,
                    outcome=None,
                    moved=moved,
                )
    _planted_deals(g)


def _planted_deals(g: Gen) -> None:
    now, wd = g.now, g.workdays(12)
    month_start = g.today.replace(day=1)

    def this_month(days_ago: int) -> datetime:
        d = max(month_start, g.today - timedelta(days=days_ago))
        return g.at(d, 15, 20)

    def plant(key: str, **kw: Any) -> None:
        deal = _add_deal(g, **kw)
        g.story.setdefault("deals", {})[key] = int(deal["ID"])

    termal = _company(g, "Завод «Термаль»")
    plant(
        "stale_offer",
        fid=0,
        title="Чиллер 120 кВт и насосная группа — Термаль",
        company=termal,
        owner=14,
        value=2_400_000,
        created=now - timedelta(days=24),
        stage_index=2,
        outcome=None,
        moved=g.at(g.today - timedelta(days=9), 11, 40),
    )
    plant(
        "won_no_shipment",
        fid=0,
        title="Чиллер 120 кВт — Термаль",
        company=termal,
        owner=14,
        value=1_240_000,
        created=now - timedelta(days=31),
        stage_index=None,
        outcome="won",
        moved=this_month(12),
    )
    plant(
        "survey_overdue",
        fid=1,
        title="Вентиляция 3–4 этажей — Невский 38",
        company=_company(g, "БЦ «Невский 38»"),
        owner=15,
        value=3_500_000,
        created=g.at(wd[-5], 10, 5),
        stage_index=0,
        outcome=None,
        moved=g.at(wd[-5], 10, 5),
    )
    plant(
        "missed_client",
        fid=1,
        title="Кондиционирование клиники — Медиус",
        company=_company(g, "Клиника «Медиус»"),
        owner=13,
        value=3_420_000,
        created=now - timedelta(days=19),
        stage_index=2,
        outcome=None,
        moved=now - timedelta(days=3),
    )
    plant(
        "low_score",
        fid=0,
        title="Фанкойлы, партия — Зелёный квартал",
        company=_company(g, "ЖК «Зелёный квартал»"),
        owner=13,
        value=1_150_000,
        created=now - timedelta(days=6),
        stage_index=1,
        outcome=None,
        moved=now - timedelta(days=2),
    )
    plant(
        "erp_less",
        fid=1,
        title="ИТП под ключ — Онега",
        company=_company(g, "Гостиница «Онега»"),
        owner=16,
        value=860_000,
        created=now - timedelta(days=50),
        stage_index=None,
        outcome="won",
        moved=this_month(8),
    )
    plant(
        "erp_other_counterparty",
        fid=0,
        title="Насосная группа — Аквалайн",
        company=_company(g, "ООО «Аквалайн»"),
        owner=11,
        value=290_000,
        created=now - timedelta(days=20),
        stage_index=None,
        outcome="won",
        moved=this_month(6),
    )
    plant(
        "erp_missing",
        fid=0,
        title="Тепловая завеса — Галерея Парк",
        company=_company(g, "ТЦ «Галерея Парк»"),
        owner=15,
        value=140_000,
        created=now - timedelta(days=12),
        stage_index=None,
        outcome="won",
        moved=this_month(4),
    )
    for title, owner in [("ГК «СтройМонолит»", 12), ("ТехПарк «Северный»", 11)]:
        c = _company(g, title)
        _add_deal(
            g,
            fid=1,
            title=f"Монтаж VRF — {short(title)}",
            company=c,
            owner=owner,
            value=2_800_000,
            created=now - timedelta(days=15),
            stage_index=1,
            outcome=None,
            moved=now - timedelta(days=2),
        )
    g.story["quiet_since"] = {str(termal["ID"]): b24(g.at(g.today - timedelta(days=9), 11, 40))}


# ---------------------------------------------------------------- calls (telephony + CRM activities)


def _calls(g: Gen) -> None:
    rng = g.rng
    g.data["calls"], g.data["activities"] = [], []
    people = {p[0]: p for p in names.PEOPLE}
    open_deals: dict[tuple[int, int], dict[str, Any]] = {}
    for d in g.data["deals"]:
        if d["CLOSED"] == "N":
            open_deals[(int(d["COMPANY_ID"]), int(d["ASSIGNED_BY_ID"]))] = d
    companies = {int(c["ID"]): c for c in g.data["companies"]}
    portfolio: dict[int, list[int]] = {}
    for cid, c in companies.items():
        weight = 4 if (cid, int(c["ASSIGNED_BY_ID"])) in open_deals else 1
        portfolio.setdefault(int(c["ASSIGNED_BY_ID"]), []).extend([cid] * weight)
    featured = set(g.story["company_ids"].values())
    quiet = {int(k): datetime.fromisoformat(v) for k, v in g.story["quiet_since"].items()}
    days = g.workdays(CALL_DAYS)
    newbie_from = g.today - timedelta(days=names.NEWBIE_START_DAYS)
    for day in days:
        for uid in [*names.MANAGERS, 2, 21]:
            _, _, _, _, _, role, per_day, connect, _ = people[uid]
            if role == "newbie" and day < newbie_from:
                continue
            n = per_day * rng.uniform(0.82, 1.15) * (1.08 if day.weekday() == 0 else 1.0)
            if uid == names.SLUMPING and day in days[-7:]:
                n *= 0.38
            if role == "newbie":
                n *= 0.6 + 0.4 * min(1.0, (day - newbie_from).days / names.NEWBIE_START_DAYS)
            for _ in range(round(n)):
                cid = rng.choice(portfolio.get(uid) or list(companies))
                started = g.day_time(day)
                if cid in featured or (cid in quiet and started >= quiet[cid]):
                    continue
                _one_call(g, uid, cid, started, connect, open_deals)
    _planted_calls(g, open_deals)
    g.data["calls"].sort(key=lambda c: c["CALL_START_DATE"])
    g.data["activities"].sort(key=lambda a: a["START_TIME"])


def _one_call(
    g: Gen,
    uid: int,
    cid: int,
    started: datetime,
    connect: float,
    open_deals: dict[tuple[int, int], dict[str, Any]],
    *,
    inbound: bool | None = None,
    missed: bool | None = None,
    duration: int | None = None,
    callback: bool = True,
) -> dict[str, Any]:
    rng = g.rng
    company = next(c for c in g.data["companies"] if int(c["ID"]) == cid)
    number = company["PHONE"][0]["VALUE"]
    inbound = rng.random() < 0.26 if inbound is None else inbound
    if missed is None:
        missed = inbound and rng.random() < (0.12 if uid == names.SLUMPING else 0.06)
    if duration is None:
        if missed:
            duration = 0
        elif inbound or rng.random() < connect:
            duration = int(min(1500, max(25, rng.lognormvariate(5.0, 0.7))))
        else:
            duration = rng.randint(0, 22)
    failed = "304" if missed else ("200" if duration >= 25 else rng.choice(["486", "480", "603"]))
    deal = open_deals.get((cid, uid))
    activity_id = g.next_id("activity", 20000)
    call = {
        "ID": str(g.next_id("call", 70000)),
        "PORTAL_USER_ID": str(uid),
        "PORTAL_NUMBER": "+78123090000",
        "PHONE_NUMBER": number,
        "CALL_ID": f"externalCall.{rng.getrandbits(64):016x}.{int(started.timestamp())}",
        "CALL_CATEGORY": "external",
        "CALL_DURATION": str(duration),
        "CALL_START_DATE": b24(started),
        "CALL_VOTE": "0",
        "COST": "0.0000",
        "CALL_FAILED_CODE": failed,
        "CRM_ENTITY_TYPE": "COMPANY",
        "CRM_ENTITY_ID": str(cid),
        "CRM_ACTIVITY_ID": str(activity_id),
        "TRANSCRIPT_PENDING": "N",
        "RECORD_FILE_ID": rng.randint(1000, 99999) if duration >= 25 else None,
        "CALL_TYPE": "2" if inbound else "1",
    }
    end = started + timedelta(seconds=duration)
    subject = "Пропущенный звонок" if missed else ("Входящий звонок" if inbound else "Исходящий звонок")
    g.data["calls"].append(call)
    g.data["activities"].append(
        {
            "ID": str(activity_id),
            "OWNER_ID": deal["ID"] if deal else str(cid),
            "OWNER_TYPE_ID": "2" if deal else "4",
            "TYPE_ID": "2",
            "PROVIDER_ID": "VOXIMPLANT_CALL",
            "PROVIDER_TYPE_ID": "CALL",
            "SUBJECT": f"{subject} {number}",
            "CREATED": b24(started),
            "LAST_UPDATED": b24(end),
            "START_TIME": b24(started),
            "END_TIME": b24(end),
            "DEADLINE": b24(started),
            "COMPLETED": "N" if missed else "Y",
            "STATUS": "1" if missed else "2",
            "RESPONSIBLE_ID": str(uid),
            "AUTHOR_ID": str(uid),
            "DIRECTION": "1" if inbound else "2",
            "PRIORITY": "2",
            "COMMUNICATIONS": [{"VALUE": number, "ENTITY_ID": str(cid), "ENTITY_TYPE_ID": "4", "TYPE": "PHONE"}],
            "SETTINGS": {},
            "ORIGIN_ID": call["CALL_ID"],
        }
    )
    if missed and callback:
        late = uid == names.SLUMPING
        if g.rng.random() < (0.6 if late else 0.88):
            back = started + timedelta(minutes=g.rng.randint(25, 180) if late else g.rng.randint(3, 35))
            if back.hour < 20:
                _one_call(g, uid, cid, back, 1.0, open_deals, inbound=False, missed=False)
    return call


def _planted_calls(g: Gen, open_deals: dict[tuple[int, int], dict[str, Any]]) -> None:
    ids = g.story["company_ids"]
    prev, last = g.workdays(2)
    yesterday = prev if last == g.today else last  # the last working day before today
    planted = g.story.setdefault("calls", {})
    for key, hh, mm in (("missed_1", 11, 20), ("missed_2", 13, 35)):
        c = _one_call(
            g,
            13,
            ids["Клиника «Медиус»"],
            g.at(g.today, hh, mm),
            1,
            open_deals,
            inbound=True,
            missed=True,
            callback=False,
        )
        planted[key] = int(c["ID"])
    c = _one_call(
        g,
        15,
        ids["Гостиница «Онега»"],
        g.at(yesterday, 18, 40),
        1,
        open_deals,
        inbound=True,
        missed=True,
        callback=False,
    )
    planted["missed_yesterday"] = int(c["ID"])
    c = _one_call(
        g, 13, ids["ЖК «Зелёный квартал»"], g.at(yesterday, 15, 12), 1, open_deals, inbound=False, duration=238
    )
    planted["low_score"] = int(c["ID"])
    c = _one_call(g, 15, ids["БЦ «Невский 38»"], g.at(yesterday, 16, 4), 1, open_deals, inbound=True, duration=312)
    planted["review"] = int(c["ID"])
    c = _one_call(g, 12, ids["ГК «СтройМонолит»"], g.at(yesterday, 11, 30), 1, open_deals, inbound=False, duration=421)
    planted["best"] = int(c["ID"])


# ---------------------------------------------------------------- tasks and leads


def _tasks(g: Gen) -> None:
    rng = g.rng
    g.data["tasks"] = []
    open_by_owner: dict[int, list[dict[str, Any]]] = {}
    for d in g.data["deals"]:
        if d["CLOSED"] == "N":
            open_by_owner.setdefault(int(d["ASSIGNED_BY_ID"]), []).append(d)
    sloppy = {13: 0.35, 15: 0.3}
    for uid in names.MANAGERS:
        horizon = names.NEWBIE_START_DAYS if uid == 15 else 60
        for _ in range(rng.randint(26, 40) if uid != 15 else 12):
            deal = rng.choice(open_by_owner.get(uid) or g.data["deals"])
            created = g.now - timedelta(days=rng.uniform(0, horizon))
            deadline = created + timedelta(days=rng.randint(1, 6), hours=rng.randint(0, 6))
            # Recent deadlines slip often for some managers; old ones are almost always closed eventually.
            recent = (g.now - deadline).days < 7
            miss = sloppy.get(uid, 0.08) if recent else (0.12 if uid in sloppy else 0.02)
            done = deadline < g.now and rng.random() > miss
            closed = min(g.now, deadline - timedelta(hours=rng.randint(0, 20))) if done else None
            client = next(c["TITLE"] for c in g.data["companies"] if c["ID"] == deal["COMPANY_ID"])
            _add_task(
                g,
                f"{rng.choice(names.TASK_TITLES)}: {short(client)}",
                uid,
                created,
                deadline,
                closed,
                deal,
            )
    deal_id = g.story["deals"]["survey_overdue"]
    deal = next(d for d in g.data["deals"] if int(d["ID"]) == deal_id)
    wd = g.workdays(6)
    task = _add_task(
        g, "Назначить выезд замерщика: Невский 38", 15, g.at(wd[0], 10, 30), g.at(wd[-3], 18, 0), None, deal
    )
    g.story["tasks"] = {"survey_overdue": int(task["id"])}


def _add_task(
    g: Gen, title: str, uid: int, created: datetime, deadline: datetime, closed: datetime | None, deal: dict[str, Any]
) -> dict[str, Any]:
    task = {
        "id": str(g.next_id("task", 300)),
        "title": title,
        "description": "",
        "priority": "1",
        "status": "5" if closed else g.rng.choice(["2", "3"]),
        "responsibleId": str(uid),
        "createdBy": str(uid),
        "createdDate": b24(created),
        "changedDate": b24(closed or created),
        "deadline": b24(deadline),
        "closedDate": b24(closed) if closed else None,
        "groupId": "0",
        "ufCrmTask": [f"D_{deal['ID']}"],
        "subStatus": "-1" if not closed and deadline < g.now else "-2",
    }
    g.data["tasks"].append(task)
    return task


def _leads(g: Gen) -> None:
    rng = g.rng
    g.data["leads"] = []
    hunters = [11, 13, 15]
    for _ in range(26):
        created = g.now - timedelta(days=rng.uniform(1, 30), hours=rng.uniform(0, 8))
        age = (g.now - created).days
        status = rng.choice(["CONVERTED", "JUNK", "IN_PROCESS"]) if age > 3 else rng.choice(["NEW", "IN_PROCESS"])
        _add_lead(
            g,
            f"{rng.choice(names.LEAD_TITLES)}",
            rng.choice(hunters),
            created,
            status,
            f"{rng.choice(names.CLIENT_PREFIX)} «{rng.choice(names.CLIENT_NAMES)}»",
        )
    lead = _add_lead(
        g, "Заявка с сайта: вентиляция склада 3 000 м²", 11, g.at(g.today, 10, 15), "NEW", "Логистик-Центр «Восток»"
    )
    g.story["leads"] = {"no_action": int(lead["ID"])}


def _add_lead(g: Gen, title: str, uid: int, created: datetime, status: str, company: str) -> dict[str, Any]:
    sem = {"CONVERTED": "S", "JUNK": "F"}.get(status, "P")
    lead = {
        "ID": str(g.next_id("lead", 400)),
        "TITLE": title,
        "STATUS_ID": status,
        "STATUS_SEMANTIC_ID": sem,
        "ASSIGNED_BY_ID": str(uid),
        "DATE_CREATE": b24(created),
        "DATE_MODIFY": b24(created),
        "COMPANY_TITLE": company,
        "SOURCE_ID": rng_choice(g, ["WEB", "CALL", "EMAIL", "TRADE_SHOW"]),
        "OPENED": "Y",
    }
    g.data["leads"].append(lead)
    return lead


def rng_choice(g: Gen, options: list[str]) -> str:
    return g.rng.choice(options)


# ---------------------------------------------------------------- derived fields


def _last_activity(g: Gen) -> None:
    """LAST_ACTIVITY_TIME on a deal is the latest call bound to it (Bitrix24 maintains it the same way)."""
    latest: dict[str, str] = {}
    for a in g.data["activities"]:
        if a["OWNER_TYPE_ID"] == "2" and a["COMPLETED"] == "Y":
            latest[a["OWNER_ID"]] = max(latest.get(a["OWNER_ID"], ""), a["START_TIME"])
    for d in g.data["deals"]:
        if d["ID"] in latest and latest[d["ID"]] > d["LAST_ACTIVITY_TIME"]:
            d["LAST_ACTIVITY_TIME"] = latest[d["ID"]]
            d["DATE_MODIFY"] = max(d["DATE_MODIFY"], latest[d["ID"]])
