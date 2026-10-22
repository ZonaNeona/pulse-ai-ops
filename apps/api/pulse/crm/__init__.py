from typing import Any

from pulse.core.config import get_settings
from pulse.crm.bitrix import B24Crm
from pulse.crm.emulator import Bitrix24Emulator
from pulse.crm.port import B24Transport
from pulse.crm.rest import Bitrix24RestAdapter


def transport() -> B24Transport:
    """CRM_MODE=emulator → the demo company; CRM_MODE=live → your portal through B24_WEBHOOK_URL."""
    settings = get_settings()
    if settings.crm_mode == "live":
        return Bitrix24RestAdapter(settings.b24_webhook_url)
    from pulse.seed import seed_dir

    path = seed_dir() / "b24.json"
    stamp = path.stat().st_mtime
    if _cache.get("stamp") != stamp:  # parse the 13 MB dataset once per reset, not per sync
        _cache.update(stamp=stamp, emulator=Bitrix24Emulator.from_file(path))
    emulator: Bitrix24Emulator = _cache["emulator"]
    return emulator


_cache: dict[str, Any] = {}


def crm() -> B24Crm:
    return B24Crm(transport())
