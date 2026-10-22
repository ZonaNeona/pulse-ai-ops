"""Accounting (1С) domain model."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Counterparty:
    key: str
    name: str
    inn: str
    supplier: bool


@dataclass(frozen=True, slots=True)
class StockItem:
    sku: str
    name: str
    unit: str
    price: float
    qty: float
    reserved: float
    min_qty: float
    supplier: str
    lead_days: int

    @property
    def free(self) -> float:
        return self.qty - self.reserved


@dataclass(frozen=True, slots=True)
class SaleDoc:
    """Реализация товаров и услуг (shipment / act) — revenue recognised in accounting."""

    key: str
    number: str
    date: date
    counterparty: str
    counterparty_key: str
    amount: float
    deal_id: int | None


@dataclass(frozen=True, slots=True)
class Payment:
    key: str
    number: str
    date: date
    counterparty: str
    amount: float
    deal_id: int | None


@dataclass(frozen=True, slots=True)
class SupplierOrderLine:
    sku: str
    name: str
    qty: float
    price: float


@dataclass(frozen=True, slots=True)
class SupplierOrder:
    key: str
    number: str
    date: date
    supplier: str
    supplier_key: str
    amount: float
    lines: tuple[SupplierOrderLine, ...]
