"""CRM domain model. Modules work with these types only and never see Bitrix24 field names."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

Semantics = Literal["process", "success", "failure"]


@dataclass(frozen=True, slots=True)
class User:
    id: int
    name: str
    position: str
    department_ids: tuple[int, ...]
    active: bool


@dataclass(frozen=True, slots=True)
class Stage:
    id: str
    funnel_id: int
    name: str
    sort: int
    semantics: Semantics


@dataclass(frozen=True, slots=True)
class Funnel:
    id: int
    name: str
    stages: tuple[Stage, ...]


@dataclass(frozen=True, slots=True)
class Company:
    id: int
    title: str
    assigned_id: int
    industry: str
    phone: str | None
    created: datetime


@dataclass(frozen=True, slots=True)
class Deal:
    id: int
    title: str
    funnel_id: int
    stage_id: str
    semantics: Semantics
    amount: float
    company_id: int | None
    assigned_id: int
    created: datetime
    modified: datetime
    moved: datetime | None
    last_activity: datetime | None
    close_date: date | None


@dataclass(frozen=True, slots=True)
class Call:
    id: int
    user_id: int
    phone: str
    started: datetime
    duration_s: int
    direction: Literal["in", "out"]
    missed: bool
    company_id: int | None
    deal_id: int | None
    activity_id: int | None
    has_record: bool


@dataclass(frozen=True, slots=True)
class Task:
    id: int
    title: str
    responsible_id: int
    created: datetime
    deadline: datetime | None
    closed: datetime | None
    status: int  # 2 waiting, 3 in progress, 4 awaiting control, 5 done, 6 deferred
    crm: tuple[str, ...]  # bindings like "D_123" (deal), "CO_45" (company)

    @property
    def done(self) -> bool:
        return self.status == 5


@dataclass(frozen=True, slots=True)
class Lead:
    id: int
    title: str
    assigned_id: int
    status_id: str
    created: datetime
    company_title: str
    in_progress: bool


@dataclass(frozen=True, slots=True)
class StageChange:
    id: int
    deal_id: int
    funnel_id: int
    stage_id: str
    at: datetime
