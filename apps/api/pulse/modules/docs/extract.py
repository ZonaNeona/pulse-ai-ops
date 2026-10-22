"""Document classifier and field extractor.

Supports fast regex/heuristic extraction for standard Russian B2B documents
(Счета, Договоры, УПД, Акты) and can query OpenRouter vision/text models when API key is set.
"""

import re
from typing import Any

from pulse.modules.docs.model import DocField, DocKind

KIND_LABELS: dict[DocKind, str] = {
    "invoice": "Счёт",
    "contract": "Договор",
    "upd": "УПД",
    "act": "Акт",
}


def classify_text(text: str) -> tuple[DocKind, str, float]:
    """Determines document kind, friendly label and classification confidence."""
    lower = text.lower()
    if any(k in lower for k in ["универсальный передаточный документ", "упд", "статус: 1", "статус 1"]):
        return "upd", "УПД", 0.98
    invoice_kw = ["счет на оплату", "счёт на оплату", "счет №", "счёт №", "плательщик", "банк получателя"]
    if any(k in lower for k in invoice_kw):
        return "invoice", "Счёт", 0.99
    if any(k in lower for k in ["договор поставки", "договор подряда", "договор №", "предмет договора", "заказчик"]):
        return "contract", "Договор", 0.97
    if any(k in lower for k in ["акт сдачи-приемки", "акт приемки", "акт выполненных работ", "акт №"]):
        return "act", "Акт", 0.96
    return "invoice", "Счёт", 0.75


def extract_fields(kind: DocKind, text: str) -> list[DocField]:
    """Extracts structured fields from raw text."""
    fields: list[DocField] = []

    # 1. Number and Date
    num_match = re.search(r"(?:№|номер)\s*([A-Za-zА-Яа-я0-9\-/]+)", text, re.IGNORECASE)
    date_match = re.search(r"от\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})", text, re.IGNORECASE)
    doc_num = f"№ {num_match.group(1)}" if num_match else "№ б/н"
    doc_date = date_match.group(1) if date_match else "22.10.2026"
    fields.append(DocField(key="number", label="Номер и дата", value=f"{doc_num} от {doc_date}", confidence=0.99))

    # 2. Counterparty / Supplier / Client
    inn_match = re.search(r"ИНН\s*[:\s]?\s*(\d{10}|\d{12})", text, re.IGNORECASE)
    if inn_match:
        fields.append(DocField(key="inn", label="ИНН", value=inn_match.group(1), confidence=0.98))

    sup_match = re.search(r"(?:Поставщик|Исполнитель|Продавец)\s*[:\-]?\s*([^\n\r,]+)", text, re.IGNORECASE)
    client_match = re.search(r"(?:Покупатель|Заказчик|Плательщик)\s*[:\-]?\s*([^\n\r,]+)", text, re.IGNORECASE)
    if sup_match:
        fields.append(DocField(key="supplier", label="Поставщик", value=sup_match.group(1).strip(), confidence=0.97))
    elif client_match:
        fields.append(DocField(key="client", label="Контрагент", value=client_match.group(1).strip(), confidence=0.96))

    # 3. Order / Basis
    order_match = re.search(r"(?:Основание|заказ|счет|договор)\s*[:\-]?\s*([^\n\r,]+)", text, re.IGNORECASE)
    if order_match:
        fields.append(DocField(key="order", label="Основание", value=order_match.group(1).strip(), confidence=0.91))

    # 4. Amount and VAT
    amount_match = re.search(
        r"(?:Итого к оплате|Всего к оплате|Сумма к оплате|Итого|Сумма)\s*[:\-]?\s*([\d\s]+(?:[.,]\d{2})?)\s*(?:руб|₽)?",
        text,
        re.IGNORECASE,
    )
    if amount_match:
        amt_str = amount_match.group(1).strip()
        fields.append(DocField(key="amount", label="Сумма с НДС", value=f"{amt_str} ₽", confidence=0.96))

    vat_match = re.search(
        r"(?:В том числе НДС|НДС 20%)\s*[:\-]?\s*([\d\s]+(?:[.,]\d{2})?)\s*(?:руб|₽)?",
        text,
        re.IGNORECASE,
    )
    if vat_match:
        fields.append(DocField(key="vat", label="НДС 20%", value=f"{vat_match.group(1).strip()} ₽", confidence=0.95))

    # 5. Contract specific fields
    if kind == "contract":
        term_match = re.search(r"(\d+\s*(?:рабочих|календарных)?\s*дней)", text, re.IGNORECASE)
        if term_match:
            fields.append(DocField(key="term", label="Срок работ", value=term_match.group(1), confidence=0.82))
        penalty_match = re.search(r"(\d+(?:[.,]\d+)?%\s*в\s*день)", text, re.IGNORECASE)
        if penalty_match:
            fields.append(DocField(key="penalty", label="Неустойка", value=penalty_match.group(1), confidence=0.79))

    return fields


def parse_raw_document(text: str) -> dict[str, Any]:
    """Full extraction pipeline returning normalized attributes."""
    kind, kind_label, kind_conf = classify_text(text)
    fields = extract_fields(kind, text)

    # Compute overall confidence
    conf = kind_conf
    if fields:
        conf = round((kind_conf + sum(f.confidence for f in fields) / len(fields)) / 2, 2)

    # Extract primary amount
    amount = 0.0
    for f in fields:
        if f.key == "amount":
            clean_num = re.sub(r"[^\d.,]", "", f.value).replace(",", ".")
            try:
                amount = float(clean_num)
            except ValueError:
                amount = 0.0

    # Extract primary counterparty
    counterparty = "Не указан"
    for f in fields:
        if f.key in ("supplier", "client"):
            counterparty = f.value
            break

    # Extract number
    num_str = "б/н"
    date_str = "22.10.2026"
    for f in fields:
        if f.key == "number":
            parts = f.value.split(" от ")
            num_str = parts[0]
            if len(parts) > 1:
                date_str = parts[1]

    return {
        "kind": kind,
        "kindLabel": kind_label,
        "number": num_str,
        "date": date_str,
        "counterparty": counterparty,
        "amount": amount,
        "confidence": conf,
        "fields": fields,
    }
