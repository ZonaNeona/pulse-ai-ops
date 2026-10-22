"""Generates the 1С side (OData entity sets) consistent with the CRM data.

Every won deal gets a payment and a shipment document (реализация). Four planted gaps make the
CRM ↔ 1С reconciliation interesting: two shipments missing, one with a smaller sum, one on another counterparty.
"""

import random
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from pulse.erp import odata
from pulse.seed import names

NS = uuid.UUID("6f1c2a4e-7d1b-4c56-9a8e-3b2f1d0c9e77")


def key(*parts: object) -> str:
    return str(uuid.uuid5(NS, "/".join(map(str, parts))))


def inn(rng: random.Random) -> str:
    return f"78{rng.randint(10_000_000, 99_999_999)}"


def ts(d: date, hour: int = 12) -> str:
    return datetime(d.year, d.month, d.day, hour).isoformat()


def generate(
    b24: dict[str, Any], story: dict[str, Any], today: date, seed: int = 2026
) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(seed + 1)
    counterparties = [
        {
            "Ref_Key": key("cp", c["ID"]),
            "Code": f"{int(c['ID']):09d}",
            "Description": c["TITLE"],
            "ИНН": inn(rng),
            "ЮрФизЛицо": "ЮрЛицо",
            "Покупатель": True,
            "Поставщик": False,
        }
        for c in b24["companies"]
    ] + [
        {
            "Ref_Key": key("sup", i),
            "Code": f"9{i:08d}",
            "Description": s,
            "ИНН": inn(rng),
            "ЮрФизЛицо": "ЮрЛицо",
            "Покупатель": False,
            "Поставщик": True,
        }
        for i, s in enumerate(names.SUPPLIERS)
    ]
    products, stock = [], []
    for sku, name, unit, price, qty, reserved, min_qty, sup, lead in names.PRODUCTS:
        ref = key("item", sku)
        products.append(
            {
                "Ref_Key": ref,
                "Code": sku,
                "Description": name,
                "Артикул": sku,
                "ЕдиницаИзмерения": unit,
                "Цена": price,
                "Поставщик_Key": key("sup", sup),
            }
        )
        stock.append(
            {
                "Номенклатура_Key": ref,
                "Склад": "Основной склад",
                "КоличествоBalance": qty,
                "ВРезервеBalance": reserved,
                "МинимальныйОстаток": min_qty,
                "СрокПоставкиДней": lead,
            }
        )

    planted = story.get("deals", {})
    skip_shipment = {planted.get("won_no_shipment"), planted.get("erp_missing")}
    less = planted.get("erp_less")
    other = planted.get("erp_other_counterparty")
    sales, payments = [], []
    for n, d in enumerate(
        sorted((d for d in b24["deals"] if d["STAGE_SEMANTIC_ID"] == "S"), key=lambda d: d["MOVED_TIME"])
    ):
        deal_id = int(d["ID"])
        closed = datetime.fromisoformat(d["MOVED_TIME"]).date()
        value = float(d["OPPORTUNITY"])
        cp = key("cp", d["COMPANY_ID"])
        paid = closed - timedelta(days=rng.randint(0, 2))
        payments.append(
            {
                "Ref_Key": key("pay", deal_id),
                "Number": f"ПВ00-{2000 + n:06d}",
                "Date": ts(paid, 10),
                "Posted": True,
                "Контрагент_Key": cp,
                "СуммаДокумента": value,
                "Комментарий": f"CRM:D_{deal_id}",
                "НазначениеПлатежа": f"Оплата по счёту, сделка {deal_id}",
            }
        )
        if deal_id in skip_shipment:
            continue
        shipped = min(today, closed + timedelta(days=rng.randint(0, 3)))
        amount = value - 40_000 if deal_id == less else value
        counterparty = key("cp", _neighbour(b24, d["COMPANY_ID"])) if deal_id == other else cp
        sales.append(
            {
                "Ref_Key": key("sale", deal_id),
                "Number": f"НЭ00-{1000 + n:06d}",
                "Date": ts(shipped, 14),
                "Posted": True,
                "Контрагент_Key": counterparty,
                "СуммаДокумента": amount,
                "Комментарий": f"CRM:D_{deal_id}",
            }
        )

    orders = []
    for i in range(12):
        sup = rng.randrange(len(names.SUPPLIERS))
        items = [p for p in names.PRODUCTS if p[7] == sup] or list(names.PRODUCTS[:3])
        lines = [(p, rng.randint(1, 6)) for p in rng.sample(items, k=min(len(items), rng.randint(1, 3)))]
        d = today - timedelta(days=rng.randint(10, 60))
        orders.append(_order(f"ЗП-{350 + i * 3:04d}", d, sup, lines))
    # The order behind the mismatching invoice in the documents module: 412 300 ₽ ordered, 421 300 ₽ invoiced.
    vt = next(p for p in names.PRODUCTS if p[0] == "VT-PU-3000")
    orders.append(_order("ЗП-0388", today - timedelta(days=8), 0, [(vt, 1)]))
    story["erp"] = {
        "supplier_order": "ЗП-0388",
        "supplier": names.SUPPLIERS[0],
        "ordered": 412_300,
        "invoiced": 421_300,
    }

    return {
        odata.COUNTERPARTIES: counterparties,
        odata.PRODUCTS: products,
        odata.STOCK: stock,
        odata.SALES: sales,
        odata.PAYMENTS: payments,
        odata.SUPPLIER_ORDERS: orders,
    }


def _order(number: str, d: date, sup: int, lines: list[tuple[tuple[Any, ...], int]]) -> dict[str, Any]:
    rows = [
        {"Номенклатура_Key": key("item", p[0]), "Количество": qty, "Цена": p[3], "Сумма": p[3] * qty}
        for p, qty in lines
    ]
    return {
        "Ref_Key": key("order", number),
        "Number": number,
        "Date": ts(d, 11),
        "Posted": True,
        "Контрагент_Key": key("sup", sup),
        "СуммаДокумента": sum(r["Сумма"] for r in rows),
        "Товары": rows,
    }


def _neighbour(b24: dict[str, Any], company_id: str) -> str:
    ids: list[str] = [c["ID"] for c in b24["companies"]]
    return ids[(ids.index(company_id) + 7) % len(ids)]
