"""Document type and fields: by the model when it is connected, by rules otherwise.

Rules read the labelled lines Russian invoices, UPDs, acts and contracts always have ("Поставщик:",
"Всего к оплате:"…). A field the rules could not find is reported as missing with zero confidence, so the
document goes to a person instead of being posted on a guess.
"""

import re
from typing import Any

from pulse.core import llm
from pulse.core.config import get_settings
from pulse.modules.docs.model import DocKind, Extracted, Field
from pulse.modules.docs.read import money, rub

LABELS = {
    "number": "Номер",
    "date": "Дата",
    "counterparty": "Контрагент",
    "inn": "ИНН",
    "order": "Основание",
    "total": "Сумма с НДС",
    "vat": "НДС",
    "due": "Оплатить до",
    "term": "Срок работ",
    "penalty": "Неустойка",
}
REQUIRED = ("number", "date", "counterparty", "total")


def classify(text: str) -> DocKind:
    head = text.strip().lower()[:300]
    if "универсальный передаточный" in head or re.search(r"\bупд\b", head):
        return "upd"
    if head.startswith("акт") or "акт выполненных" in head or "акт оказанных" in head:
        return "act"
    if head.startswith("договор") or "договор поставки" in head or "договор подряда" in head:
        return "contract"
    if "счёт" in head or "счет" in head:
        return "invoice"
    return "unknown"


def _find(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return " ".join(m.group(1).split()) if m else ""


def by_rules(text: str) -> Extracted:
    kind = classify(text)
    party = "Заказчик" if kind == "contract" else r"(?:Поставщик|Исполнитель|Продавец)"
    found = {
        "number": _find(r"^[^\n]*?№\s*([\w\-/]+)", text),
        "date": _find(r"^[^\n]*?от\s+(\d{2}\.\d{2}\.\d{4})", text),
        "counterparty": _find(rf"^{party}\s*:\s*([^,\n]+?)(?:,|\s+ИНН|$)", text),
        "inn": _find(rf"^{party}\s*:[^\n]*?ИНН\s*(\d{{10}}|\d{{12}})", text),
        "order": _find(r"(ЗП-\d+)", text) or _find(r"^Основание\s*:\s*([^\n]+)", text),
        "total": _find(
            r"^(?:Всего к оплате|Итого к оплате|Итого с НДС|Цена договора|Всего)\s*:?\s*([\d\s ]+(?:,\d{2})?)", text
        ),
        "vat": _find(r"^(?:В том числе )?НДС[^:\n]*:\s*([\d\s ]+(?:,\d{2})?)", text),
        "due": _find(r"Оплатить до\s*(\d{2}\.\d{2}\.\d{4})", text),
        "term": _find(r"Срок (?:выполнения )?работ\s*:?\s*([^\n.]+)", text),
        "penalty": _find(r"(\d+(?:[.,]\d+)?\s*%\s*(?:в день|за каждый день))", text),
    }
    fields = []
    for key, value in found.items():
        if key in ("total", "vat") and value:
            amount = money(value)
            value = rub(amount) if amount is not None else value
        if value:
            fields.append(Field(key, LABELS[key], value, 0.99))
        elif key in REQUIRED:
            fields.append(Field(key, LABELS[key], "не найдено", 0.0))
    return Extracted(kind, fields, "rules")


OWN_NAME = "норд инжиниринг"  # we are the buyer on every incoming document; never the counterparty
OWN_INN = "7802654321"

SCHEMA_PROMPT = """Ты извлекаешь реквизиты из входящего документа компании ООО «Норд Инжиниринг» (ИНН 7802654321).
«Норд Инжиниринг» — это мы: покупатель в счетах, УПД и актах, исполнитель в договорах. Нас в counterparty и inn
не указывай никогда — там вторая сторона.
Верни JSON с ключами:
kind: "invoice" | "upd" | "act" | "contract" | "unknown";
fields: объект, где для каждого найденного поля {"value": строка, "confidence": 0..1}.
Поля: number (номер без знака №), date (ДД.ММ.ГГГГ), counterparty (наименование второй стороны: для счёта, УПД,
акта — поставщик/исполнитель, для договора — заказчик), inn, order (номер заказа или основание), total (сумма с НДС
числом), vat (НДС числом), due (оплатить до), term (срок работ), penalty (неустойка, как в тексте).
Не придумывай: поля, которых в документе нет, не возвращай. confidence ниже 0.9 — если читаешь неуверенно."""


async def by_model(*, text: str | None, image: str | None, visitor: str) -> Extracted:
    content: Any = (
        text
        if text is not None
        else [
            {"type": "text", "text": "Документ на изображении:"},
            {"type": "image_url", "image_url": {"url": image}},
        ]
    )
    res = await llm.chat(
        [{"role": "system", "content": SCHEMA_PROMPT}, {"role": "user", "content": content}],
        visitor=visitor,
        action="document",
        model=get_settings().llm_vision_model if image else None,
        json_mode=True,
    )
    data = llm.parse_json(res.text)
    raw = data.get("fields") or {}
    fields = []
    for key, label in LABELS.items():
        item = raw.get(key)
        if isinstance(item, dict) and str(item.get("value") or "").strip():
            value = str(item["value"]).strip()
            if key in ("total", "vat"):
                amount = money(value)
                value = rub(amount) if amount is not None else value
            conf = float(item.get("confidence") or 0.0)
            if (key == "counterparty" and OWN_NAME in value.lower().replace("ё", "е")) or (
                key == "inn" and value == OWN_INN
            ):
                # The model took our own company for the other side: better «не найдено» than a wrong match.
                if key in REQUIRED:
                    fields.append(Field(key, label, "не найдено", 0.0))
                continue
            fields.append(Field(key, label, value, max(0.0, min(1.0, conf))))
        elif key in REQUIRED:
            fields.append(Field(key, label, "не найдено", 0.0))
    kind: DocKind = data["kind"] if data.get("kind") in ("invoice", "upd", "act", "contract") else "unknown"
    return Extracted(kind, fields, "model", res.model, res.cost_usd)
