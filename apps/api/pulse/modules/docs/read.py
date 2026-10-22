"""Getting text out of an uploaded file, and reading money and dates the way Russian documents write them.

Text and PDF files with a text layer are read locally. Scans and photos have no text to read — they go
to the vision model when one is connected; otherwise the visitor is told so, nothing is made up.
"""

import base64
import io
import re

from pypdf import PdfReader

MAX_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


class Unreadable(ValueError):
    """The file cannot be turned into text; the message is shown to the visitor."""


def suffix(filename: str) -> str:
    return ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""


def text_of(filename: str, content: bytes) -> str | None:
    """Plain text of a document, or None when it is an image that needs the vision model."""
    if len(content) > MAX_BYTES:
        raise Unreadable("Файл больше 5 МБ")
    ext = suffix(filename)
    if ext in IMAGE_TYPES:
        return None
    if ext == ".pdf" or content[:5] == b"%PDF-":
        try:
            pages = PdfReader(io.BytesIO(content)).pages[:10]
            text = "\n".join(p.extract_text() or "" for p in pages)
        except Exception:
            raise Unreadable("PDF не открывается — файл повреждён или защищён паролем") from None
        if len(text.strip()) < 40:
            raise Unreadable(
                "В PDF нет текстового слоя (это скан). Загрузите скан как изображение — его прочитает модель"
            )
        return text
    if ext not in (".txt", ".text", ""):
        raise Unreadable("Поддерживаются PDF, TXT, PNG и JPG")
    for encoding in ("utf-8", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise Unreadable("Не удалось прочитать файл: поддерживаются PDF, TXT, PNG и JPG")


def data_url(filename: str, content: bytes) -> str:
    return f"data:{IMAGE_TYPES[suffix(filename)]};base64,{base64.b64encode(content).decode()}"


def money(value: str) -> float | None:
    """ "421 300,00 ₽", "421300.00", "1 186 400 руб." → float."""
    cleaned = re.sub(r"[^\d,.\-]", "", value.replace(" ", " ").replace(" ", ""))
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def rub(value: float) -> str:
    whole, frac = f"{value:,.2f}".split(".")
    return f"{whole.replace(',', ' ')},{frac} ₽"
