from pulse.core.config import get_settings
from pulse.erp.emulator import OneCEmulator
from pulse.erp.odata import ODataTransport, OneCErp, OneCODataClient


def transport() -> ODataTransport:
    """ERP_MODE=emulator → demo 1С; ERP_MODE=live → your 1С standard OData interface."""
    settings = get_settings()
    if settings.erp_mode == "live":
        return OneCODataClient(settings.onec_odata_url, settings.onec_user, settings.onec_password)
    from pulse.seed import seed_dir

    return OneCEmulator.from_file(seed_dir() / "erp.json")


def erp() -> OneCErp:
    return OneCErp(transport())
