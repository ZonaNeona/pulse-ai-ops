"""1С OData emulator: the same entity sets and query options ($filter, $top, $skip) as a real 1С.

`$filter` supports what the integration uses: comparisons (eq, ne, gt, ge, lt, le) joined with `and`,
with datetime'…', guid'…', 'string', numbers and true/false literals.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pulse.erp.odata import ENTITY_SETS

TERM = re.compile(r"^\s*(\S+)\s+(eq|ne|gt|ge|lt|le)\s+(.+?)\s*$")


def _literal(raw: str) -> Any:
    raw = raw.strip()
    for prefix in ("datetime'", "guid'"):
        if raw.startswith(prefix) and raw.endswith("'"):
            value = raw[len(prefix) : -1]
            return datetime.fromisoformat(value) if prefix == "datetime'" else value
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"Неподдерживаемое значение в $filter: {raw}") from None


def _value(record: dict[str, Any], field: str, sample: Any) -> Any:
    v = record.get(field)
    if isinstance(sample, datetime) and isinstance(v, str):
        return datetime.fromisoformat(v)
    if isinstance(sample, float) and isinstance(v, int | float) and not isinstance(v, bool):
        return float(v)
    return v


def parse_filter(expr: str) -> list[tuple[str, str, Any]]:
    terms = []
    for part in re.split(r"\s+and\s+", expr.strip()):
        m = TERM.match(part)
        if not m:
            raise ValueError(f"Неподдерживаемое выражение $filter: {part}")
        terms.append((m.group(1), m.group(2), _literal(m.group(3))))
    return terms


def matches(record: dict[str, Any], terms: list[tuple[str, str, Any]]) -> bool:
    for field, op, expected in terms:
        actual = _value(record, field, expected)
        if actual is None:
            return False
        try:
            ok = {
                "eq": actual == expected,
                "ne": actual != expected,
                "gt": actual > expected,
                "ge": actual >= expected,
                "lt": actual < expected,
                "le": actual <= expected,
            }[op]
        except TypeError:
            return False
        if not ok:
            return False
    return True


class OneCEmulator:
    def __init__(self, dataset: dict[str, list[dict[str, Any]]]):
        self.data = dataset
        self.calls = 0

    @classmethod
    def from_file(cls, path: Path) -> "OneCEmulator":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    async def get(self, entity_set: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if entity_set not in ENTITY_SETS:
            raise ValueError(f"Набор {entity_set} не входит в список чтения")
        self.calls += 1
        params = params or {}
        rows = self.data.get(entity_set, [])
        if params.get("$filter"):
            terms = parse_filter(params["$filter"])
            rows = [r for r in rows if matches(r, terms)]
        skip = int(params.get("$skip") or 0)
        top = int(params.get("$top") or 1000)
        return {
            "odata.metadata": f"http://1c.local/odata/standard.odata/$metadata#{entity_set}",
            "value": rows[skip : skip + top],
        }
