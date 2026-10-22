"""Initial seed documents for the demo stand («Норд Инжиниринг»)."""

from typing import Any

from pulse.modules.docs.model import DocCheck, DocField, GraphStep

STEPS_POSTED = [
    GraphStep(node="classify", label="Тип документа", status="done", ms=420, note="УПД, уверенность 0,98").to_dict(),
    GraphStep(node="extract", label="Извлечение полей", status="done", ms=2840, note="14 полей").to_dict(),
    GraphStep(node="validate", label="Сверка с 1С и CRM", status="done", ms=310, note="расхождений нет").to_dict(),
    GraphStep(node="review", label="Подтверждение", status="done", note="автоматически, уверенность > 0,95").to_dict(),
    GraphStep(node="draft", label="Проводка в 1С", status="done", ms=180, note="документ проведён").to_dict(),
]


def get_seed_docs() -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "kind": "invoice",
            "kind_label": "Счёт",
            "number": "№ 2417",
            "date": "21.10.2026",
            "counterparty": "ООО «ВентТехСнаб»",
            "amount": 421_300.0,
            "status": "mismatch",
            "confidence": 0.93,
            "received_ago": "12 мин назад",
            "steps": [
                GraphStep(
                    node="classify", label="Тип документа", status="done", ms=380, note="Счёт на оплату, 0,99"
                ).to_dict(),
                GraphStep(node="extract", label="Извлечение полей", status="done", ms=3120, note="12 полей").to_dict(),
                GraphStep(
                    node="validate",
                    label="Сверка с 1С и CRM",
                    status="error",
                    ms=290,
                    note="сумма не совпадает с заказом",
                ).to_dict(),
                GraphStep(node="review", label="Подтверждение", status="active", note="ждёт человека").to_dict(),
                GraphStep(node="draft", label="Проводка в 1С", status="waiting").to_dict(),
            ],
            "fields": [
                DocField("supplier", "Поставщик", "ООО «ВентТехСнаб»", 0.99).to_dict(),
                DocField("inn", "ИНН", "7814 562 019", 0.98).to_dict(),
                DocField("number", "Номер и дата", "№ 2417 от 21.10.2026", 0.99).to_dict(),
                DocField("order", "Основание", "Заказ поставщику № ЗП-0388", 0.91).to_dict(),
                DocField("amount", "Сумма с НДС", "421 300,00 ₽", 0.97, expected="412 300,00 ₽").to_dict(),
                DocField("vat", "НДС 20%", "70 216,67 ₽", 0.95).to_dict(),
                DocField("due", "Оплатить до", "28.10.2026", 0.88).to_dict(),
            ],
            "checks": [
                DocCheck("Контрагент есть в 1С", True, "карточка поставщика, договор № 14/2025").to_dict(),
                DocCheck("Есть заказ-основание", True, "ЗП-0388 от 14.10.2026").to_dict(),
                DocCheck(
                    "Сумма совпадает с заказом",
                    False,
                    "в заказе 412 300 ₽, в счёте 421 300 ₽ (+9 000 ₽)",
                ).to_dict(),
                DocCheck("Счёт не оплачен ранее", True, "дублей не найдено").to_dict(),
            ],
        },
        {
            "id": 2,
            "kind": "upd",
            "kind_label": "УПД",
            "number": "№ 1182",
            "date": "21.10.2026",
            "counterparty": "АО «ТермоКомплект»",
            "amount": 1_186_400.0,
            "status": "posted",
            "confidence": 0.98,
            "received_ago": "1 ч назад",
            "steps": STEPS_POSTED,
            "fields": [
                DocField("supplier", "Поставщик", "АО «ТермоКомплект»", 0.99).to_dict(),
                DocField("amount", "Сумма с НДС", "1 186 400,00 ₽", 0.99).to_dict(),
            ],
            "checks": [
                DocCheck("Сверка с заказом", True, "совпадает").to_dict(),
            ],
        },
        {
            "id": 3,
            "kind": "contract",
            "kind_label": "Договор",
            "number": "№ М-77/10",
            "date": "20.10.2026",
            "counterparty": "Клиника «Медиус»",
            "amount": 3_420_000.0,
            "status": "review",
            "confidence": 0.86,
            "received_ago": "3 ч назад",
            "steps": [
                GraphStep(
                    node="classify", label="Тип документа", status="done", ms=410, note="Договор подряда, 0,97"
                ).to_dict(),
                GraphStep(
                    node="extract", label="Извлечение полей", status="done", ms=5210, note="18 полей, 2 неуверенно"
                ).to_dict(),
                GraphStep(
                    node="validate", label="Сверка с 1С и CRM", status="done", ms=340, note="сделка найдена"
                ).to_dict(),
                GraphStep(node="review", label="Подтверждение", status="active", note="уверенность ниже 0,9").to_dict(),
                GraphStep(node="draft", label="Проводка в 1С", status="waiting").to_dict(),
            ],
            "fields": [
                DocField("client", "Заказчик", "ООО «Медиус Клиник»", 0.97).to_dict(),
                DocField("amount", "Цена договора", "3 420 000,00 ₽", 0.96).to_dict(),
                DocField("term", "Срок работ", "45 рабочих дней", 0.81).to_dict(),
                DocField("penalty", "Неустойка", "0,1% в день", 0.78).to_dict(),
            ],
            "checks": [
                DocCheck("Сделка в CRM", True, "Монтаж · «Договор», 3 420 000 ₽").to_dict(),
                DocCheck("Неустойка в пределах политики", True, "лимит 0,1% в день").to_dict(),
            ],
        },
        {
            "id": 4,
            "kind": "act",
            "kind_label": "Акт",
            "number": "№ 842",
            "date": "20.10.2026",
            "counterparty": "ООО «ВентТехСнаб»",
            "amount": 140_000.0,
            "status": "posted",
            "confidence": 0.97,
            "received_ago": "5 ч назад",
            "steps": STEPS_POSTED,
            "fields": [
                DocField("supplier", "Исполнитель", "ООО «ВентТехСнаб»", 0.99).to_dict(),
                DocField("amount", "Сумма работ", "140 000,00 ₽", 0.98).to_dict(),
            ],
            "checks": [DocCheck("Акт сверен со сметой", True, "отклонений нет").to_dict()],
        },
        {
            "id": 5,
            "kind": "upd",
            "kind_label": "УПД",
            "number": "№ 904",
            "date": "19.10.2026",
            "counterparty": "АО «ТермоКомплект»",
            "amount": 480_000.0,
            "status": "posted",
            "confidence": 0.96,
            "received_ago": "1 дн назад",
            "steps": STEPS_POSTED,
            "fields": [],
            "checks": [],
        },
        {
            "id": 6,
            "kind": "invoice",
            "kind_label": "Счёт",
            "number": "№ 3102",
            "date": "19.10.2026",
            "counterparty": "ООО «Климат-Опт»",
            "amount": 290_000.0,
            "status": "posted",
            "confidence": 0.95,
            "received_ago": "1 дн назад",
            "steps": STEPS_POSTED,
            "fields": [],
            "checks": [],
        },
        {
            "id": 7,
            "kind": "upd",
            "kind_label": "УПД",
            "number": "№ 1301",
            "date": "18.10.2026",
            "counterparty": "ООО «Аквалайн»",
            "amount": 1_120_000.0,
            "status": "posted",
            "confidence": 0.99,
            "received_ago": "2 дн назад",
            "steps": STEPS_POSTED,
            "fields": [],
            "checks": [],
        },
        {
            "id": 8,
            "kind": "act",
            "kind_label": "Акт",
            "number": "№ 918",
            "date": "18.10.2026",
            "counterparty": "ТЦ «Галерея Парк»",
            "amount": 640_000.0,
            "status": "posted",
            "confidence": 0.98,
            "received_ago": "2 дн назад",
            "steps": STEPS_POSTED,
            "fields": [],
            "checks": [],
        },
    ]
