"""Russian formatting for texts the API sends to screens and to the bot."""

from datetime import datetime

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]
MONTHS_NOMINATIVE = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]
WEEKDAYS_FULL = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def plural(n: int, forms: tuple[str, str, str]) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def count(n: int, forms: tuple[str, str, str]) -> str:
    return f"{n} {plural(n, forms)}"


def num(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ")


def rub(v: float) -> str:
    return f"{num(v)} ₽"


def rub_short(v: float) -> str:
    a = abs(v)
    if a >= 1_000_000:
        digits = 1 if a >= 10_000_000 else 2
        text = f"{v / 1_000_000:.{digits}f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{text} млн ₽"
    if a >= 10_000:
        return f"{round(v / 1000)} тыс. ₽"
    return rub(v)


def ago(minutes: float) -> str:
    m = int(minutes)
    if m < 1:
        return "только что"
    if m < 60:
        return f"{m} мин назад"
    h = m // 60
    if h < 24:
        rest = m % 60
        return f"{h} ч {rest} мин назад" if rest and h < 3 else f"{count(h, ('час', 'часа', 'часов'))} назад"
    d = h // 24
    return f"{count(d, ('день', 'дня', 'дней'))} назад"


def age_short(minutes: float) -> str:
    m = int(minutes)
    if m < 60:
        return f"{max(1, m)} мин"
    if m < 60 * 24:
        return f"{m // 60} ч"
    return f"{m // (60 * 24)} дн"


def day_title(d: datetime) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}, {WEEKDAYS_FULL[d.weekday()]}"


def pct_delta(current: float, base: float) -> int | None:
    return None if base <= 0 else round((current - base) / base * 100)
