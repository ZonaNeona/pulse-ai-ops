"""Checks a document against 1С, the CRM and the company's own regulations.

Every check is plain code over synced data, and names the regulation section it enforces, so the screen
can say *why* a document was stopped. Nothing here is decided by the model.
"""

import re
from typing import Any

from pulse.data import Data
from pulse.modules.docs.model import Check, Doc
from pulse.modules.docs.read import money, rub

TOLERANCE = 0.005  # «Работа с первичными документами поставщиков», § 1.1: up to 0.5 % for rounding
MAX_PENALTY = 0.1  # «Регламент согласования сделок и договоров», § 1.3: % per day
VAT_RATE = 0.20
FORMS = re.compile(r"\b(ооо|оао|зао|пао|ао|ип|гк|нко)\b")


def norm(name: str) -> str:
    return " ".join(FORMS.sub(" ", re.sub(r"[«»\"'“”]", " ", name.lower())).split())


def _supplier(doc: Doc, data: Data) -> Any:
    inn, name = doc.value("inn"), norm(doc.value("counterparty"))
    for cp in data.counterparties:
        if (inn and cp.inn == inn) or (name and norm(cp.name) == name):
            return cp
    return None


def supplier_checks(doc: Doc, data: Data, others: list[Doc]) -> list[Check]:
    checks: list[Check] = []
    total = doc.amount
    cp = _supplier(doc, data)
    if cp is None:
        checks.append(
            Check(
                "Контрагент есть в 1С",
                False,
                f"{doc.value('counterparty')} не найден в 1С ни по ИНН, ни по названию",
                "Работа с первичными документами поставщиков, § 1.3",
            )
        )
        return checks
    inn = doc.value("inn")
    if inn and inn != cp.inn:
        checks.append(
            Check(
                "ИНН совпадает с карточкой 1С",
                False,
                f"в документе {inn}, в 1С у {cp.name} — {cp.inn}",
                "Работа с первичными документами поставщиков, § 1.3",
            )
        )
    else:
        checks.append(Check("Контрагент есть в 1С", True, f"{cp.name}, ИНН {cp.inn}"))

    orders = [o for o in data.orders if o.supplier_key == cp.key]
    ref = doc.value("order")
    order = next((o for o in orders if o.number in ref), None) if ref else None
    if order is None and orders:
        order = min(orders, key=lambda o: abs(o.amount - total))
    if order is None:
        checks.append(
            Check(
                "Есть заказ-основание",
                False,
                "у поставщика нет заказов в 1С",
                "Работа с первичными документами поставщиков, § 1.1",
            )
        )
        return checks
    checks.append(
        Check("Есть заказ-основание", True, f"{order.number} от {order.date:%d.%m.%Y} на {rub(order.amount)}")
    )

    diff = total - order.amount
    if order.amount and abs(diff) / order.amount > TOLERANCE:
        sign = "+" if diff > 0 else "−"
        checks.append(
            Check(
                "Сумма совпадает с заказом",
                False,
                f"в заказе {rub(order.amount)}, в документе {rub(total)} ({sign}{rub(abs(diff))})",
                "Работа с первичными документами поставщиков, § 1.2",
            )
        )
        for f in doc.fields:
            if f.key == "total":
                f.expected = rub(order.amount)
    else:
        checks.append(Check("Сумма совпадает с заказом", True, f"{rub(total)} — в пределах 0,5 %"))

    vat = money(doc.value("vat"))
    if vat is not None and total:
        expected_vat = round(total * VAT_RATE / (1 + VAT_RATE), 2)
        ok = abs(vat - expected_vat) <= 1
        checks.append(
            Check(
                "НДС посчитан верно",
                ok,
                f"НДС {rub(vat)}" if ok else f"НДС в документе {rub(vat)}, а 20 % от суммы — {rub(expected_vat)}",
            )
        )

    number = doc.value("number")
    dup = next(
        (
            o
            for o in others
            if o.id != doc.id
            and o.status == "posted"
            and o.value("number") == number
            and norm(o.value("counterparty")) == norm(doc.value("counterparty"))
        ),
        None,
    )
    checks.append(
        Check(
            "Документ не проведён ранее",
            dup is None,
            "дублей нет" if dup is None else f"уже проведён как документ #{dup.id}",
        )
    )
    return checks


def contract_checks(doc: Doc, data: Data) -> list[Check]:
    checks: list[Check] = []
    name = norm(doc.value("counterparty"))
    company = next(
        (c for c in data.companies.values() if norm(c.title) == name or (name and name in norm(c.title))), None
    )
    if company is None:
        checks.append(Check("Заказчик есть в CRM", False, f"{doc.value('counterparty')} не найден в компаниях"))
        return checks
    checks.append(Check("Заказчик есть в CRM", True, company.title))
    total = doc.amount
    deals = [d for d in data.deals if d.company_id == company.id and d.semantics == "process"]
    deal = min(deals, key=lambda d: abs(d.amount - total), default=None)
    if deal is None:
        checks.append(Check("Есть открытая сделка", False, "у компании нет сделок в работе"))
    elif deal.amount and abs(deal.amount - total) / deal.amount > TOLERANCE:
        checks.append(
            Check("Сумма совпадает со сделкой", False, f"в сделке {rub(deal.amount)}, в договоре {rub(total)}")
        )
    else:
        checks.append(
            Check("Сумма совпадает со сделкой", True, f"сделка «{deal.title}», {data.stage_name(deal.stage_id)}")
        )
    penalty = doc.value("penalty")
    if penalty:
        rate = money(penalty.split("%")[0]) or 0.0
        ok = rate <= MAX_PENALTY
        checks.append(
            Check(
                "Неустойка в пределах политики",
                ok,
                f"неустойка {penalty}" + ("" if ok else " — выше 0,1 % в день, нужна подпись директора"),
                "" if ok else "Регламент согласования сделок и договоров, § 1.3",
            )
        )
    return checks


def run(doc: Doc, data: Data, others: list[Doc]) -> list[Check]:
    if doc.kind == "unknown":
        return [Check("Тип документа определён", False, "не похоже на счёт, УПД, акт или договор")]
    missing = [f.label for f in doc.fields if f.value == "не найдено"]
    head = [Check("Реквизиты прочитаны", False, "не найдено: " + ", ".join(missing))] if missing else []
    if doc.kind == "contract":
        return head + contract_checks(doc, data)
    return head + supplier_checks(doc, data, others)
