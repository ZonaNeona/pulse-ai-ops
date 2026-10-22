"""Bitrix24 REST emulator for the demo company.

Answers the same methods as `Bitrix24RestAdapter`, validated by the same allowlist, in the same response
format as a real portal (field names, string-typed numbers, `total` / `next` paging by 50, the `time` block).
Records dated later today stay hidden until their time comes, so the demo day unfolds live:
calls and tasks appear on the dashboard as the clock moves.
"""

import functools
import json
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from pulse.core import clock
from pulse.crm.rest import validate

PAGE = 50
OPS = (">=", "<=", "!@", "!=", ">", "<", "!", "@", "=", "%")

# method → (collection, wrapper key for list results, field that gates visibility by time)
LISTS: dict[str, tuple[str, str | None, str | None]] = {
    "department.get": ("departments", None, None),
    "user.get": ("users", None, None),
    "crm.status.list": ("statuses", None, None),
    "crm.company.list": ("companies", None, "DATE_CREATE"),
    "crm.contact.list": ("contacts", None, "DATE_CREATE"),
    "crm.deal.list": ("deals", None, "DATE_CREATE"),
    "crm.lead.list": ("leads", None, "DATE_CREATE"),
    "crm.activity.list": ("activities", None, "START_TIME"),
    "tasks.task.list": ("tasks", "tasks", "createdDate"),
    "voximplant.statistic.get": ("calls", None, "CALL_START_DATE"),
    "crm.stagehistory.list": ("stagehistory", "items", "CREATED_TIME"),
    "crm.item.list": ("items", "items", "createdTime"),
}


def _norm(value: Any) -> Any:
    """Bring a field or filter value to a comparable form: Y/N flags, numbers, datetimes, strings."""
    if isinstance(value, bool):
        return "Y" if value else "N"
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return _norm_str(value)
    return value


@functools.lru_cache(maxsize=262_144)
def _norm_str(value: str) -> Any:
    low = value.lower()
    if low in ("true", "false"):
        return "Y" if low == "true" else "N"
    if len(value) >= 10 and value[4:5] == "-" and value[7:8] == "-":
        try:
            return clock.parse(value if "T" in value or " " in value else value + "T00:00:00")
        except ValueError:
            return value
    try:
        return float(value)
    except ValueError:
        return value


def _cmp(a: Any, b: Any) -> int | None:
    """-1/0/1, or None when the values cannot be ordered (missing or of different kinds)."""
    a, b = _norm(a), _norm(b)
    if a is None or b is None:
        return None
    if type(a) is not type(b):
        return 0 if str(a) == str(b) else None
    return int(a > b) - int(a < b)


def _sortable(value: Any) -> tuple[int, float, str]:
    """Numbers and dates first (by value), then strings, then empty values."""
    v = _norm(value)
    if v is None:
        return (2, 0.0, "")
    if isinstance(v, datetime):
        return (0, v.timestamp(), "")
    if isinstance(v, float):
        return (0, v, "")
    return (1, 0.0, str(v))


def _split(key: str) -> tuple[str, str]:
    for op in OPS:
        if key.startswith(op):
            return op, key[len(op) :]
    return "=", key


def _matches(record: dict[str, Any], flt: dict[str, Any], field: Callable[[str], str]) -> bool:
    for key, expected in flt.items():
        op, name = _split(key)
        actual = record.get(field(name))
        values = expected if isinstance(expected, list | tuple) else [expected]
        if op in ("=", "@"):
            if not any(_cmp(actual, v) == 0 for v in values):
                return False
        elif op in ("!", "!=", "!@"):
            if any(_cmp(actual, v) == 0 for v in values):
                return False
        elif op == "%":
            if str(expected).lower() not in str(actual or "").lower():
                return False
        else:
            c = _cmp(actual, expected)
            if c is None or not {">": c > 0, ">=": c >= 0, "<": c < 0, "<=": c <= 0}[op]:
                return False
    return True


def _same(name: str) -> str:
    return name


def _camel(name: str) -> str:
    """RESPONSIBLE_ID → responsibleId (tasks.task.list accepts upper-case filters, returns camelCase)."""
    if name == "REAL_STATUS":
        return "status"
    if not name.isupper():
        return name
    head, *rest = name.lower().split("_")
    return head + "".join(p.capitalize() for p in rest)


class Bitrix24Emulator:
    def __init__(self, dataset: dict[str, Any]):
        self.data = dataset
        self.calls = 0
        self._memo: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    @classmethod
    def from_file(cls, path: Path) -> "Bitrix24Emulator":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        validate(method, params)
        self.calls += 1
        started = time.time()
        result, extra = self._dispatch(method, params)
        finished = time.time()
        return {
            "result": result,
            **extra,
            "time": {
                "start": started,
                "finish": finished,
                "duration": finished - started,
                "processing": 0,
                "date_start": clock.b24(clock.now()),
                "date_finish": clock.b24(clock.now()),
                "operating_reset_at": int(started) + 600,
                "operating": 0,
            },
        }

    def _dispatch(self, method: str, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        if method == "scope":
            return ["crm", "task", "user", "department", "telephony", "disk"], {}
        if method == "server.time":
            return clock.b24(clock.now()), {}
        if method == "crm.deal.fields":
            return self.data.get("deal_fields", {}), {}
        if method == "crm.category.list":
            cats = self.data["categories"] if int(params.get("entityTypeId", 2)) == 2 else []
            return {"categories": cats}, {"total": len(cats)}
        if method == "crm.activity.call.getTranscript":
            return self.data.get("transcripts", {}).get(str(params["activityId"])), {}
        if method in LISTS:
            return self._list(method, params)
        raise ValueError(f"Эмулятор не реализует {method}")

    def _list(self, method: str, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, wrapper, _ = LISTS[method]
        rows = self._query(method, params)
        start = int(params.get("start") or 0)
        page = rows[start : start + PAGE]
        extra: dict[str, Any] = {"total": len(rows)}
        if start + PAGE < len(rows):
            extra["next"] = start + PAGE
        return ({wrapper: page} if wrapper else page), extra

    def _query(self, method: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Filtered, ordered, projected rows. A paged read asks for the same query page after page,
        so the result is kept for a short while (the clock gate moves in minutes, not milliseconds)."""
        key = json.dumps([method, {k: v for k, v in params.items() if k != "start"}], sort_keys=True, default=str)
        hit = self._memo.get(key)
        if hit and time.monotonic() - hit[0] < 20:
            return hit[1]
        rows = self._compute(method, params)
        if len(self._memo) > 64:
            self._memo.clear()
        self._memo[key] = (time.monotonic(), rows)
        return rows

    def _compute(self, method: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        collection, _, gate = LISTS[method]
        tasks = method == "tasks.task.list"
        field: Callable[[str], str] = _camel if tasks else _same
        now = clock.now()
        rows = [r for r in self.data.get(collection, []) if not gate or not r.get(gate) or _norm(r[gate]) <= now]
        if method in ("crm.stagehistory.list", "crm.item.list"):
            etype = int(params.get("entityTypeId", 2))
            rows = [r for r in rows if int(r.get("entityTypeId", 2)) == etype]

        flt = params.get("FILTER") if method == "voximplant.statistic.get" else params.get("filter")
        if flt:
            rows = [r for r in rows if _matches(r, flt, field)]

        if method == "voximplant.statistic.get":
            order = {params["SORT"]: params.get("ORDER", "ASC")} if params.get("SORT") else {}
        elif method in ("user.get", "department.get"):  # these take sort=<field>, order=ASC|DESC
            order = {params.get("sort") or "ID": params.get("order") or "ASC"}
        else:
            order = params.get("order") or ({"ID": "ASC"} if not tasks else {"id": "ASC"})
        for key, direction in reversed(list(order.items())):  # stable sorts: last key first
            name = field(key)

            def by(row: dict[str, Any], name: str = name) -> tuple[int, float, str]:
                return _sortable(row.get(name))

            rows.sort(key=by, reverse=str(direction).upper() == "DESC")

        select = params.get("select")
        if select and "*" not in select:
            wanted = {field(s) for s in select} | {"ID", "id"}
            rows = [{k: v for k, v in r.items() if k in wanted} for r in rows]
        elif select and "UF_*" not in select and not tasks:
            rows = [{k: v for k, v in r.items() if not k.startswith("UF_")} for r in rows]
        return rows
