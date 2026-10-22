"""Integrations screen: connection cards, exchange log and the CRM ↔ 1С reconciliation."""

from datetime import datetime
from typing import Any

from pulse.core import db, fmt
from pulse.core.config import get_settings
from pulse.data import Data


def month_start(data: Data) -> datetime:
    return data.now.replace(day=1, hour=0, minute=0, second=0)


def reconciliation(data: Data) -> dict[str, Any]:
    """Deals paid in the CRM this month against shipments (реализации) posted in 1С for them."""
    start = month_start(data)
    won = [d for d in data.deals if d.semantics == "success" and (d.moved or d.modified) >= start]
    by_deal = {s.deal_id: s for s in data.sales if s.deal_id}
    names = {c.key: c.name for c in data.counterparties}
    gaps: list[dict[str, Any]] = []
    posted = []
    for d in won:
        sale = by_deal.get(d.id)
        client = data.client(d.company_id)
        issue = None
        if sale is None:
            issue = "Оплачено в CRM, реализации в 1С нет"
        else:
            posted.append(sale)
            if names.get(sale.counterparty_key) != client:
                issue = f"Реализация на другого контрагента: {names.get(sale.counterparty_key, '—')}"
            elif abs(sale.amount - d.amount) >= 1:
                direction = "меньше" if sale.amount < d.amount else "больше"
                issue = f"Сумма в 1С {direction} на {fmt.rub(abs(d.amount - sale.amount))}"
        if issue:
            gaps.append(
                {
                    "deal": d.title,
                    "dealId": d.id,
                    "client": client,
                    "amount": d.amount,
                    "issue": issue,
                    "manager": data.name(d.assigned_id),
                }
            )
    gaps.sort(key=lambda g: -g["amount"])
    return {
        "period": f"{fmt.MONTHS_NOMINATIVE[start.month - 1]} {start.year}",
        "crmDeals": len(won),
        "crmAmount": round(sum(d.amount for d in won)),
        "erpPosted": len(posted),
        "erpAmount": round(sum(s.amount for s in posted)),
        "gaps": gaps,
    }


def _since(stamp: str | None, now: datetime) -> str:
    if not stamp:
        return "не было"
    return fmt.ago((now - datetime.fromisoformat(stamp)).total_seconds() / 60)


def cards(data: Data) -> list[dict[str, Any]]:
    s = get_settings()
    now = data.now
    last = db.get_setting("last_sync")
    fresh = bool(last) and (now - datetime.fromisoformat(last)).total_seconds() < s.sync_interval_s * 3
    gaps = len(reconciliation(data)["gaps"])
    today_calls = sum(1 for c in data.calls if c.started.date() == data.day)
    return [
        {
            "id": "b24",
            "name": "Битрикс24",
            "kind": "CRM",
            "mode": "Эмулятор REST" if s.crm_mode == "emulator" else "Живой портал",
            "status": "success" if fresh else "warning",
            "statusLabel": "Синхронно" if fresh else "Нет синка",
            "lastSync": _since(last, now),
            "detail": "Сделки, компании, звонки, задачи, лиды, история стадий",
            "metrics": [
                {"label": "Сделок", "value": fmt.num(len(data.deals))},
                {"label": "Звонков за день", "value": fmt.num(today_calls)},
                {"label": "Компаний", "value": fmt.num(len(data.companies))},
            ],
        },
        {
            "id": "erp",
            "name": "1С:ERP",
            "kind": "Учёт",
            "mode": "Эмулятор OData" if s.erp_mode == "emulator" else "Живая 1С",
            "status": "warning" if gaps else "success",
            "statusLabel": fmt.count(gaps, ("расхождение", "расхождения", "расхождений")) if gaps else "Сходится",
            "lastSync": _since(last, now),
            "detail": "Остатки, реализации, оплаты, заказы поставщикам",
            "metrics": [
                {"label": "Реализаций", "value": fmt.num(len(data.sales))},
                {"label": "Позиций", "value": fmt.num(len(data.stock))},
                {"label": "Расхождений", "value": str(gaps)},
            ],
        },
        {
            "id": "tg",
            "name": "Telegram",
            "kind": "Канал",
            "mode": "Бот + Mini App",
            "status": "success" if s.telegram_bot_token else "neutral",
            "statusLabel": "Онлайн" if s.telegram_bot_token else "Не подключён",
            "lastSync": "—",
            "detail": "Команды, вопросы копилоту, черновики с подтверждением",
            "metrics": [],
        },
        {
            "id": "llm",
            "name": "OpenRouter",
            "kind": "Модели",
            "mode": s.llm_model.split("/")[-1],
            "status": "success" if s.llm_api_key else "neutral",
            "statusLabel": "Подключён" if s.llm_api_key else "Без ключа",
            "lastSync": "—",
            "detail": "Свободные вопросы копилота, ответы по регламентам, чтение загруженных документов",
            "metrics": [{"label": "Лимит в сутки", "value": f"${s.ai_daily_usd:.2f}".replace(".", ",")}],
        },
        {
            "id": "hermes",
            "name": "Hermes Agent",
            "kind": "Агенты",
            "mode": "API-сервер, MCP",
            "status": "success" if s.hermes_api_url else "neutral",
            "statusLabel": "Подключён" if s.hermes_api_url else "Не подключён",
            "lastSync": "—",
            "detail": "Инструменты через MCP, скиллы, подагенты. Без него — встроенный цикл на тех же инструментах",
            "metrics": [],
        },
    ]


def log(limit: int = 12) -> list[dict[str, Any]]:
    tone = {"success": "success", "info": "info", "warning": "warning", "danger": "danger"}
    return [
        {
            "at": datetime.fromisoformat(r["at"]).strftime("%H:%M"),
            "source": r["source"],
            "event": r["event"],
            "detail": r["detail"],
            "status": tone.get(r["status"], "info"),
        }
        for r in db.recent_log(limit)
    ]
