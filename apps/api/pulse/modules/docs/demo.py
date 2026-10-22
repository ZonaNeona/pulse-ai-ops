"""The demo queue: real-looking incoming documents built from today's 1С and CRM data.

They are plain texts, exactly what a supplier's PDF turns into, and they go through the same graph as an
uploaded file — nothing about their result is written in advance. Six documents cover every outcome:
posted automatically, sum above the order, wrong VAT, unknown supplier, contract penalty above policy.
"""

from datetime import date, timedelta
from typing import Any

from pulse.core import clock
from pulse.data import Data
from pulse.erp.model import Counterparty, SupplierOrder
from pulse.modules.docs import graph, store
from pulse.modules.docs.model import Doc
from pulse.modules.docs.read import rub

BUYER = "Покупатель: ООО «Норд Инжиниринг», ИНН 7802654321"


def _num(v: float) -> str:
    return rub(v).removesuffix(" ₽")


def _lines(order: SupplierOrder, total: float) -> list[str]:
    scale = total / order.amount if order.amount else 1.0
    out = []
    for i, line in enumerate(order.lines, 1):
        price = round(line.price * scale, 2)
        out.append(f"{i}. {line.name} — {line.qty:g} шт × {_num(price)} = {_num(price * line.qty)}")
    return out


def supplier_doc(
    kind: str,
    number: str,
    day: date,
    cp: Counterparty,
    order: SupplierOrder | None,
    total: float,
    vat: float | None = None,
    due: date | None = None,
) -> str:
    title = {
        "invoice": "Счёт на оплату",
        "upd": "Универсальный передаточный документ (УПД)",
        "act": "Акт выполненных работ",
    }[kind]
    party = "Исполнитель" if kind == "act" else "Поставщик"
    vat = round(total * 20 / 120, 2) if vat is None else vat
    rows = [
        f"{title} № {number} от {day:%d.%m.%Y}",
        f"{party}: {cp.name}, ИНН {cp.inn}",
        BUYER,
    ]
    if order:
        rows += [f"Основание: заказ поставщику {order.number} от {order.date:%d.%m.%Y}", "", *_lines(order, total)]
    rows += ["", f"Всего к оплате: {_num(total)} руб.", f"В том числе НДС 20%: {_num(vat)}"]
    if due:
        rows.append(f"Оплатить до {due:%d.%m.%Y}")
    return "\n".join(rows)


def contract_doc(number: str, day: date, client: str, total: float, penalty: str, term: str) -> str:
    return "\n".join(
        [
            f"Договор подряда № {number} от {day:%d.%m.%Y}",
            "Исполнитель: ООО «Норд Инжиниринг», ИНН 7802654321",
            f"Заказчик: {client}",
            "Предмет: поставка и монтаж системы кондиционирования",
            f"Цена договора: {_num(total)} руб., в том числе НДС 20%",
            f"Срок выполнения работ: {term}",
            f"За нарушение сроков Исполнитель уплачивает неустойку {penalty} от цены договора.",
        ]
    )


def build(data: Data) -> list[tuple[str, str, int]]:
    """(filename, text, minutes ago) for the day's queue."""
    today = clock.today()
    cps = {c.name: c for c in data.counterparties}
    orders: dict[str, list[SupplierOrder]] = {}
    for o in sorted(data.orders, key=lambda o: o.date, reverse=True):
        orders.setdefault(o.supplier_key, []).append(o)
    out: list[tuple[str, str, int]] = []

    vent = cps.get("ООО «ВентТехСнаб»")
    planted = next((o for o in data.orders if o.number == "ЗП-0388"), None)
    if vent and planted:  # the invoice is 9 000 ₽ above the order it refers to
        out.append(
            (
                "schet-2417.pdf",
                supplier_doc(
                    "invoice",
                    "2417",
                    today - timedelta(days=1),
                    vent,
                    planted,
                    planted.amount + 9_000,
                    due=today + timedelta(days=6),
                ),
                12,
            )
        )
    # Other suppliers with orders: two documents that match and go through on their own, one with VAT
    # typed at the old 18 % rate — a real-life mistake the checks must catch.
    others = [
        (cp, orders[cp.key][0]) for cp in data.counterparties if cp.supplier and cp.key in orders and cp is not vent
    ]
    kinds = [("upd", "1182", 64, None), ("invoice", "904", 190, None), ("act", "342", 260, 0.18)]
    for (cp, o), (kind, number, minutes, wrong_vat) in zip(others, kinds, strict=False):
        vat = round(o.amount * wrong_vat, 2) if wrong_vat else None
        due = today + timedelta(days=3) if kind == "invoice" else None
        out.append(
            (
                f"{kind}-{number}.pdf",
                supplier_doc(kind, number, today - timedelta(days=2), cp, o, o.amount, vat, due),
                minutes,
            )
        )
    stranger = Counterparty(key="", name="ООО «СтройТехРесурс»", inn="7811402956", supplier=True)
    out.append(
        (
            "schet-77.pdf",
            supplier_doc("invoice", "77", today, stranger, None, 186_000, due=today + timedelta(days=3)),
            35,
        )
    )
    deal_id = data.story.get("deals", {}).get("missed_client")
    deal = next((d for d in data.deals if d.id == deal_id), None)
    if deal:
        out.append(
            (
                "dogovor-m-77.pdf",
                contract_doc(
                    "М-77/10",
                    today - timedelta(days=1),
                    data.client(deal.company_id),
                    deal.amount,
                    "0,2 % за каждый день",
                    "45 рабочих дней",
                ),
                180,
            )
        )
    return out


async def ensure_queue(session: str, data: Data) -> None:
    """First visit of a session: put the day's demo documents through the graph (rules only, free)."""
    if store.has_session(session):
        return
    now = clock.now()
    for filename, text, minutes in reversed(build(data)):
        doc = store.create(session, "demo", filename, text, created=now - timedelta(minutes=minutes))
        await graph.process(doc, use_model=False)


def to_list(docs: list[Doc]) -> list[dict[str, Any]]:
    rank = {"mismatch": 0, "review": 1, "processing": 2, "failed": 3, "posted": 4, "rejected": 5}
    return [d.to_dict() for d in sorted(docs, key=lambda d: (rank.get(d.status, 9), -d.id))]
