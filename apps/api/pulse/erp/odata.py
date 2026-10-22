"""1С standard OData interface: the transport protocol, a live client and the `ErpPort` mapping on top.

A live 1С answers `GET <base>/odata/standard.odata/<EntitySet>?$format=json&$filter=...`; the emulator
answers the same entity sets with the same query options, so `OneCErp` does not know which one it talks to.
"""

from datetime import date, datetime
from typing import Any, Protocol

import httpx

from pulse.erp.model import Counterparty, Payment, SaleDoc, StockItem, SupplierOrder, SupplierOrderLine

COUNTERPARTIES = "Catalog_Контрагенты"
PRODUCTS = "Catalog_Номенклатура"
STOCK = "AccumulationRegister_ТоварыНаСкладах_Balance"
SALES = "Document_РеализацияТоваровУслуг"
PAYMENTS = "Document_ПоступлениеБезналичныхДенежныхСредств"
SUPPLIER_ORDERS = "Document_ЗаказПоставщику"
ENTITY_SETS = (COUNTERPARTIES, PRODUCTS, STOCK, SALES, PAYMENTS, SUPPLIER_ORDERS)


class ODataTransport(Protocol):
    async def get(self, entity_set: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...


class OneCODataClient:
    """Live 1С over HTTP (read-only GET, basic auth). Only the entity sets above can be requested."""

    def __init__(self, base_url: str, user: str, password: str, transport: httpx.AsyncBaseTransport | None = None):
        self._base = base_url.rstrip("/") + "/odata/standard.odata/"
        self._auth = (user, password)
        self._transport = transport

    async def get(self, entity_set: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if entity_set not in ENTITY_SETS:
            raise ValueError(f"Набор {entity_set} не входит в список чтения")
        query = {"$format": "json", **(params or {})}
        try:
            async with httpx.AsyncClient(timeout=30, auth=self._auth, transport=self._transport) as client:
                res = await client.get(self._base + entity_set, params=query)
                res.raise_for_status()
                data: dict[str, Any] = res.json()
                return data
        except httpx.HTTPError:
            raise RuntimeError("1С недоступна или вернула ошибку") from None


def since_filter(field: str, since: date) -> str:
    return f"{field} ge datetime'{since.isoformat()}T00:00:00'"


def _date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _deal(comment: str | None) -> int | None:
    # The CRM integration writes "CRM:D_<id>" into the document comment.
    if comment and comment.startswith("CRM:D_"):
        try:
            return int(comment[6:].split()[0])
        except ValueError:
            return None
    return None


class OneCErp:
    def __init__(self, transport: ODataTransport):
        self.transport = transport
        self._names: dict[str, str] | None = None

    async def _all(self, entity_set: str, flt: str | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        skip = 0
        while True:
            params: dict[str, Any] = {"$top": 500, "$skip": skip}
            if flt:
                params["$filter"] = flt
            page = (await self.transport.get(entity_set, params)).get("value", [])
            out.extend(page)
            if len(page) < 500:
                return out
            skip += 500

    async def counterparties(self) -> list[Counterparty]:
        rows = await self._all(COUNTERPARTIES)
        self._names = {r["Ref_Key"]: r["Description"] for r in rows}
        return [
            Counterparty(
                key=r["Ref_Key"], name=r["Description"], inn=r.get("ИНН") or "", supplier=bool(r.get("Поставщик"))
            )
            for r in rows
        ]

    async def _name(self, key: str) -> str:
        if self._names is None:
            await self.counterparties()
        return (self._names or {}).get(key, "—")

    async def stock(self) -> list[StockItem]:
        products = {p["Ref_Key"]: p for p in await self._all(PRODUCTS)}
        out = []
        for b in await self._all(STOCK):
            p = products[b["Номенклатура_Key"]]
            out.append(
                StockItem(
                    sku=p["Артикул"],
                    name=p["Description"],
                    unit=p.get("ЕдиницаИзмерения") or "шт",
                    price=float(p.get("Цена") or 0),
                    qty=float(b["КоличествоBalance"]),
                    reserved=float(b.get("ВРезервеBalance") or 0),
                    min_qty=float(b.get("МинимальныйОстаток") or 0),
                    supplier=await self._name(p.get("Поставщик_Key") or ""),
                    lead_days=int(b.get("СрокПоставкиДней") or 0),
                )
            )
        return out

    async def sales(self, since: date) -> list[SaleDoc]:
        rows = await self._all(SALES, since_filter("Date", since) + " and Posted eq true")
        return [
            SaleDoc(
                key=r["Ref_Key"],
                number=r["Number"],
                date=_date(r["Date"]),
                counterparty=await self._name(r["Контрагент_Key"]),
                counterparty_key=r["Контрагент_Key"],
                amount=float(r["СуммаДокумента"]),
                deal_id=_deal(r.get("Комментарий")),
            )
            for r in rows
        ]

    async def payments(self, since: date) -> list[Payment]:
        rows = await self._all(PAYMENTS, since_filter("Date", since) + " and Posted eq true")
        return [
            Payment(
                key=r["Ref_Key"],
                number=r["Number"],
                date=_date(r["Date"]),
                counterparty=await self._name(r["Контрагент_Key"]),
                amount=float(r["СуммаДокумента"]),
                deal_id=_deal(r.get("Комментарий")),
            )
            for r in rows
        ]

    async def supplier_orders(self, since: date) -> list[SupplierOrder]:
        products = {p["Ref_Key"]: p for p in await self._all(PRODUCTS)}
        rows = await self._all(SUPPLIER_ORDERS, since_filter("Date", since))
        out = []
        for r in rows:
            lines = tuple(
                SupplierOrderLine(
                    sku=products[x["Номенклатура_Key"]]["Артикул"],
                    name=products[x["Номенклатура_Key"]]["Description"],
                    qty=float(x["Количество"]),
                    price=float(x["Цена"]),
                )
                for x in r.get("Товары", [])
            )
            out.append(
                SupplierOrder(
                    key=r["Ref_Key"],
                    number=r["Number"],
                    date=_date(r["Date"]),
                    supplier=await self._name(r["Контрагент_Key"]),
                    supplier_key=r["Контрагент_Key"],
                    amount=float(r["СуммаДокумента"]),
                    lines=lines,
                )
            )
        return out
