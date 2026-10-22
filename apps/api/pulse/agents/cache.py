"""Cached deterministic answers for preset questions.

Evaluates questions against live data (data.load()) instantaneously and for free,
without making external LLM calls. Provides realistic traces for the UI.
"""

import uuid
from typing import Any

from pulse import data
from pulse.modules import integrations, overview
from pulse.modules.sales import calls, deals, signals, team


def _normalize(text: str) -> str:
    return "".join(c.lower() for c in text if c.isalnum() or c.isspace()).strip()


def find_answer(query: str, d: data.Data) -> dict[str, Any] | None:
    """Matches a query against preset questions and computes a live grounded answer."""
    norm = _normalize(query)

    # 1. Просевшие менеджеры
    if any(k in norm for k in ["просел", "отстает", "просадк", "хуже всех"]):
        team_rows = team.team(d)

        danger = [m for m in team_rows if m["status"] == "danger"]
        warning = [m for m in team_rows if m["status"] == "warning"]

        text_lines = ["**Анализ активности отдела продаж за текущую неделю:**\n"]
        if danger:
            for m in danger:
                text_lines.append(
                    f"🔴 **{m['name']}** — {m['note']}. Звонков сегодня: {m['callsToday']} из {m['callsNorm']} нормы. "
                    f"Оценка качества разговоров: **{m['quality']}/100**."
                )
        if warning:
            for m in warning:
                text_lines.append(f"🟡 **{m['name']}** — {m['note']}.")

        best = max(team_rows, key=lambda x: x["callsToday"])
        text_lines.append(f"\nЛидер по активности: **{best['name']}** ({best['callsToday']} звонков).")

        return {
            "text": "\n".join(text_lines),
            "sources": [{"label": "Команда продаж", "href": "/sales/team"}],
            "tools": ["team_status"],
            "lanes": [("Hermes", "team_status", "team(snapshot)", 120)],
        }

    # 2. Зависшие сделки
    if any(k in norm for k in ["завис", "застря", "без движения", "тишина"]):
        board = deals.board(d)

        stale = [deal for deal in board if deal.get("isStale")]
        text_lines = [f"В CRM обнаружено **{len(stale)} сделок без движения** более 7 дней:\n"]
        for s in stale[:5]:
            amt_mln = s["amount"] / 1_000_000
            text_lines.append(
                f"- **{s['title']}** ({s['client']}): {amt_mln:.2f} млн ₽. "
                f"Стадия: _{s['stageLabel']}_. Ответственный: **{s['manager']}**."
            )
        text_lines.append("\nРекомендация: связаться с ЛПР или актуализировать следующий шаг.")
        return {
            "text": "\n".join(text_lines),
            "sources": [{"label": "Доска сделок", "href": "/sales/deals"}],
            "tools": ["get_deals"],
            "lanes": [("Hermes", "get_deals", "stale_only=True", 90)],
        }

    # 3. Сверка CRM с 1С
    if any(k in norm for k in ["сравн", "сверк", "оплат", "реализаци"]):
        rec = integrations.reconciliation(d)

        crm_mln = rec["crmAmount"] / 1_000_000
        erp_mln = rec["erpAmount"] / 1_000_000
        diff_mln = (rec["crmAmount"] - rec["erpAmount"]) / 1_000_000

        text_lines = [
            f"За {rec['period'].lower()} в CRM **{rec['crmDeals']} оплаченных сделок** на **{crm_mln:.1f} млн ₽**, "
            f"в 1С проведено **{rec['erpPosted']} реализаций** на **{erp_mln:.1f} млн ₽**.\n",
            f"Разница составляет **{diff_mln:.2f} млн ₽** в {len(rec['gaps'])} сделках:\n",
        ]
        for i, g in enumerate(rec["gaps"], 1):
            if g["amount"] >= 1_000_000:
                amt_str = f"{g['amount'] / 1_000_000:.2f} млн ₽"
            else:
                amt_str = f"{g['amount']:,.0f} ₽".replace(",", " ")
            text_lines.append(f"{i}. **{g['client']}** ({g['deal']}): {amt_str} — {g['issue']} ({g['manager']}).")


        text_lines.append("\nМогу сформировать черновики задач ответственным менеджерам для устранения расхождений.")

        return {
            "text": "\n".join(text_lines),
            "sources": [
                {"label": f"CRM: {rec['crmDeals']} сделок", "href": "/sales/deals"},
                {"label": f"1С: {rec['erpPosted']} реализаций", "href": "/integrations"},
                {"label": "Сверка интеграций", "href": "/integrations"},
            ],
            "tools": ["sales_month", "erp_sales", "reconcile"],
            "lanes": [
                ("Подагент 1", "sales_month", "crm_deals()", 180),
                ("Подагент 2", "erp_sales", "erp_postings()", 220),
                ("Hermes", "reconcile", "find_gaps()", 110),
            ],
        }

    # 4. Худший звонок
    if any(k in norm for k in ["худш", "разбор звонк", "оценк звонк", "низкая оценка"]):
        feed = calls.feed(d)

        scored = [c for c in feed if c.get("score") is not None]
        if scored:
            worst = min(scored, key=lambda x: x["score"])
            review = calls.review(d, worst["id"])
            if review:
                crit_lines = []
                for cr in review["criteria"]:
                    label = cr.get("label") or cr.get("title") or "Критерий"
                    if cr["score"] < cr["max"]:
                        quote = f" (цитата: «{cr['quote']}»)" if "quote" in cr else ""
                        crit_lines.append(f"- ❌ **{label}**: {cr['score']}/{cr['max']} баллов{quote}")
                    else:
                        crit_lines.append(f"- ✅ **{label}**: {cr['score']}/{cr['max']} баллов")

                text = (
                    f"Звонок менеджера **{worst['manager']}** с клиентом **{worst['client']}** "
                    f"получил оценку **{worst['score']}/100**:\n\n"
                    + "\n".join(crit_lines)
                    + f"\n\n💡 **Совет РОПа:** {review['advice']}"
                )
                return {
                    "text": text,
                    "sources": [{"label": f"Звонок #{worst['id']}", "href": "/sales/calls"}],
                    "tools": ["call_review"],
                    "lanes": [("Hermes", "call_review", f"id={worst['id']}", 150)],
                }

    # 5. Документы
    if any(k in norm for k in ["документ", "счет", "акт"]):
        return {

            "text": (
                "В очереди обработки документов находятся **2 документа**, требующих внимания человека:\n\n"
                "1. **Счёт № 2417** от ООО «ВентТехСнаб» на 149 000 ₽ — сумма превышает заказ на 9 000 ₽.\n"
                "2. **Договор поставки** с Клиникой «Медиус» — модель не уверена в сроках (уверенность 0.74).\n\n"
                "Остальные 18 документов за неделю сопоставлены с заказами 1С и подтверждены автоматически."
            ),
            "sources": [{"label": "Модуль «Документы»", "href": "/docs"}],
            "tools": ["docs_queue"],
            "lanes": [("Hermes", "docs_queue", "pending_confirmation", 100)],
        }


    # 6. Скидки
    if any(k in norm for k in ["скидк", "дилер"]):
        return {

            "text": (
                "Согласно **Регламенту ценообразования 2026 (§ 3.2)**:\n\n"
                "- Скидка **до 7%** предоставляется менеджером самостоятельно.\n"
                "- Скидка **от 7% до 12%** требует согласования с РОПом в сделке.\n"
                "- Скидка **свыше 12%** — только с генеральным директором и при предоплате от 50%.\n\n"
                "⚠️ *На заказные позиции и импортное оборудование скидки не распространяются.*"
            ),
            "sources": [{"label": "Регламент ценообразования", "href": "/knowledge"}],
            "tools": ["knowledge_search"],
            "lanes": [("Hermes", "knowledge_search", "query='скидка дилерам'", 95)],
        }


    # 7. Что требует внимания сегодня / Главное
    if any(k in norm for k in ["внимани", "главн", "сделать", "приоритет"]):
        ov = overview.overview(d)

        actions = ov["actions"][:4]
        text_lines = ["**Главные приоритеты на сегодня:**\n"]
        for a in actions:
            text_lines.append(f"- 🔴 **{a['title']}**: {a['reason']} → _{a['action']}_ ({a['owner']})")
        return {
            "text": "\n".join(text_lines),
            "sources": [{"label": "Обзор компании", "href": "/"}],
            "tools": ["sales_pulse", "get_signals"],
            "lanes": [("Hermes", "overview", "action_items", 80)],
        }

    # 8. Пропущенные без перезвона
    if any(k in norm for k in ["пропущенные", "без перезвона", "не перезвонили"]):
        sigs = [s for s in signals.build(d) if s.get("rule") == "no-callback"]
        if not sigs:
            return {
                "text": "Отличная новость: все пропущенные вызовы обработаны, клиентов без перезвона нет.",
                "sources": [{"label": "Звонки", "href": "/sales/calls"}],
                "tools": ["get_signals"],
                "lanes": [("Hermes", "get_signals", "rule='no-callback'", 70)],
            }

        text_lines = [f"Обнаружено **{len(sigs)} пропущенных звонков без обратной связи**:\n"]
        for s in sigs:
            text_lines.append(f"- **{s['client']}**: {s['reason']} (ответственный: **{s['manager']}**)")
        return {
            "text": "\n".join(text_lines),
            "sources": [{"label": "Звонки", "href": "/sales/calls"}],
            "tools": ["get_signals"],
            "lanes": [("Hermes", "get_signals", "rule='no-callback'", 75)],
        }

    # 9. Просрочки
    if any(k in norm for k in ["просрочк", "просроченные задачи"]):
        sigs = [s for s in signals.build(d) if s.get("rule") == "overdue-task"]
        text_lines = [f"В CRM зафиксировано **{len(sigs)} просроченных задач**:\n"]
        for s in sigs[:5]:
            text_lines.append(f"- **{s['title']}** — {s['reason']} ({s['manager']})")
        return {
            "text": "\n".join(text_lines),
            "sources": [{"label": "Продажи", "href": "/sales"}],
            "tools": ["get_signals"],
            "lanes": [("Hermes", "get_signals", "rule='overdue-task'", 80)],
        }

    # 10. Склад / Остатки
    if any(k in norm for k in ["склад", "остатки", "чиллеры", "наличии"]):
        stocks = [item for item in d.stock if "чиллер" in item.name.lower()]
        text_lines = ["**Остатки оборудования на складе (1С):**\n"]
        for st in stocks[:5]:
            text_lines.append(
                f"- **{st.name}** (арт. {st.sku}): всего {st.qty} {st.unit}, "
                f"в резерве {st.reserved} {st.unit}, **доступно к отгрузке: {st.free} {st.unit}**."
            )
        return {
            "text": "\n".join(text_lines),
            "sources": [{"label": "1С:ERP", "href": "/integrations"}],
            "tools": ["erp_stock"],
            "lanes": [("Hermes", "erp_stock", "query='чиллер'", 60)],
        }

    # 11. Выручка и прогноз
    if any(k in norm for k in ["выручка", "прогноз", "план"]):
        ov = overview.overview(d)
        rev = ov["revenue"]
        fact_mln = rev["fact"] / 1_000_000
        plan_mln = rev["plan"] / 1_000_000
        fore_mln = rev["forecast"] / 1_000_000
        pct = (rev["forecast"] / rev["plan"]) * 100
        text = (
            f"Выручка октября: **{fact_mln:.1f} млн ₽** при плане **{plan_mln:.1f} млн ₽**.\n\n"
            f"Текущий прогноз к концу месяца: **{fore_mln:.1f} млн ₽** ({pct:.0f}% от плана). "
            f"До конца месяца осталось {rev['daysLeft']} рабочих дней."
        )
        return {
            "text": text,
            "sources": [{"label": "Обзор компании", "href": "/"}],
            "tools": ["sales_pulse"],
            "lanes": [("Hermes", "sales_pulse", "kpis", 75)],
        }

    # 12. Сделки конкретного менеджера
    if "соколова" in norm or "марина" in norm:
        board = deals.board(d)
        marina_deals = [x for x in board if "соколова" in x.get("manager", "").lower()]
        text_lines = [f"У менеджера **Марина Соколова** в работе **{len(marina_deals)} сделок**:\n"]
        for m in marina_deals[:5]:
            if m["amount"] >= 1_000_000:
                amt = f"{m['amount'] / 1_000_000:.2f} млн ₽"
            else:
                amt = f"{m['amount']:,.0f} ₽".replace(",", " ")
            text_lines.append(f"- **{m['title']}** ({m['client']}): {amt} — стадия _{m['stageLabel']}_")
        return {
            "text": "\n".join(text_lines),
            "sources": [{"label": "Сделки", "href": "/sales/deals"}],
            "tools": ["get_deals"],
            "lanes": [("Hermes", "get_deals", "manager='Марина Соколова'", 85)],
        }


    return None


def build_trace(query: str, answer_spec: dict[str, Any]) -> dict[str, Any]:
    """Builds a TraceRun structure matching api/types.ts."""
    steps = [
        {
            "id": "s1",
            "kind": "llm",
            "name": "plan",
            "label": "План ответа",
            "lane": "Hermes",
            "startMs": 0,
            "durMs": 60,
            "costUsd": 0.0,
        }
    ]

    cur_ms = 70
    for lane, name, detail, dur in answer_spec.get("lanes", []):
        is_sub = lane.startswith("Подагент")
        steps.append({
            "id": f"s_{uuid.uuid4().hex[:6]}",
            "kind": "subagent" if is_sub else "tool",
            "name": name,
            "label": f"{name}()",
            "lane": lane,
            "startMs": cur_ms,
            "durMs": dur,
            "detail": detail,
            "costUsd": 0.0,
        })
        cur_ms += dur + 15

    steps.append({
        "id": "s_final",
        "kind": "llm",
        "name": "answer",
        "label": "Синтез ответа",
        "lane": "Hermes",
        "startMs": cur_ms,
        "durMs": 50,
        "costUsd": 0.0,
    })

    total_ms = cur_ms + 50

    return {
        "id": f"run_{uuid.uuid4().hex[:8]}",
        "question": query,
        "engine": "hermes",
        "model": "deepseek-chat (кэш/правила)",
        "startedAgo": "только что",
        "totalMs": total_ms,
        "costUsd": 0.0,
        "tokens": 1250,
        "steps": steps,
    }
