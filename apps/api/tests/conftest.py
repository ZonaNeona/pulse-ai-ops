from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pulse.core import clock
from pulse.core.config import get_settings

# A fixed Wednesday afternoon: the planted story (missed calls at 11:20 and 13:35) is already visible.
NOW = datetime(2026, 10, 21, 16, 40, tzinfo=ZoneInfo("Europe/Moscow"))


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("PULSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CRM_MODE", "emulator")
    monkeypatch.setenv("ERP_MODE", "emulator")
    monkeypatch.setenv("ADMIN_KEY", "test-admin")
    get_settings.cache_clear()
    clock.freeze(NOW)
    yield tmp_path
    clock.freeze(None)
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def dataset() -> tuple[dict, dict]:  # type: ignore[type-arg]
    from pulse.seed import b24

    return b24.generate(NOW)
