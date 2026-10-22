"""Aiogram 3 handlers for Telegram Bot and Mini App integration."""

import html
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from pulse import data
from pulse.agents import runner, tools
from pulse.core import fmt
from pulse.core.config import get_settings
from pulse.modules import docs as docs_mod
from pulse.modules import overview
from pulse.modules.sales import team

log = logging.getLogger(__name__)

router = Router(name="pulse_bot")


def _get_public_url() -> str:
    s = get_settings()
    url = s.public_url.rstrip("/")
    if url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
        return "https://demo.shvarev-demo.ru"
    return url


def get_start_keyboard(public_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть Пульс (Mini App)",
                    web_app=WebAppInfo(url=public_url),
                )
            ],
            [
                InlineKeyboardButton(text="📊 Сводка дня", callback_data="cmd:today"),
                InlineKeyboardButton(text="👥 Команда", callback_data="cmd:team"),
            ],
            [
                InlineKeyboardButton(text="📄 Документы (LangGraph)", callback_data="cmd:doc"),
            ],
        ]
    )


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Welcomes the user and offers the Mini App launch button and fast commands."""
    public_url = _get_public_url()
    text = (
        "<b>👋 Добро пожаловать в «Пульс»</b> — демо ИИ-платформы для бизнеса компании «Норд Инжиниринг».\n\n"
        "📱 Нажмите кнопку ниже, чтобы открыть <b>полноценный Mini App</b> прямо внутри Telegram.\n\n"
        "⚡ <b>Быстрые команды:</b>\n"
        "• /today — сводка дня, выручка к плану и светофор модулей\n"
        "• /team — статус команды продаж, нормы и отставания\n"
        "• /doc — очередь документов LangGraph на подтверждение (Human-in-the-loop)\n"
        "• <i>Или задайте любой вопрос текстом</i> — ответит Копилот (Hermes Agent)"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_start_keyboard(public_url))


@router.message(Command("today"))
@router.callback_query(F.data == "cmd:today")
async def handle_today(event: Message | CallbackQuery) -> None:
    """Delivers executive daily overview with headline KPIs and do-now action feed."""
    d = data.load()
    ov = overview.overview(d)
    rev = ov["revenue"]
    public_url = _get_public_url()

    status_icon = {
        "success": "🟢",
        "warning": "🟡",
        "danger": "🔴",
        "neutral": "⚪",
    }

    module_lines = []
    for m in ov["modules"]:
        icon = status_icon.get(m["status"], "⚪")
        module_lines.append(f"{icon} <b>{m['title']}:</b> {m['headline']} (<i>{m['detail']}</i>)")

    action_lines = []
    for i, a in enumerate(ov["actions"][:3], start=1):
        action_lines.append(f"{i}. <b>{a['title']}</b>: {a['reason']} → <i>{a['action']} ({a['owner']})</i>")

    text = (
        f"<b>📊 Пульс компании «Норд Инжиниринг»</b>\n"
        f"📅 {ov['company']['today']}\n\n"
        f"💰 <b>Выручка:</b> {fmt.rub(rev['fact'])} "
        f"(план: {fmt.rub(rev['plan'])}, прогноз: {fmt.rub(rev['forecast'])}, дней: {rev['daysLeft']})\n\n"
        f"🚥 <b>Светофор модулей:</b>\n" + "\n".join(module_lines) + "\n\n"
        "⚡ <b>Сделать сейчас:</b>\n" + "\n".join(action_lines)
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть обзор в Mini App", web_app=WebAppInfo(url=f"{public_url}/"))],
            [InlineKeyboardButton(text="📄 Очередь документов", callback_data="cmd:doc")],
        ]
    )

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message and isinstance(event.message, Message):
            await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("team"))
@router.callback_query(F.data == "cmd:team")
async def handle_team(event: Message | CallbackQuery) -> None:
    """Sales team status: calls, talk time, quality rating and leaders."""
    d = data.load()
    members = team.team(d)
    public_url = _get_public_url()

    lines = []
    for m in members:
        icon = "🏆" if m["rank"] == 1 else "⚠️" if m["status"] == "danger" else "👤"
        lines.append(
            f"{icon} <b>{m['name']}</b>: {m['callsToday']}/{m['callsNorm']} зв. · "
            f"оценка <b>{m['qualityScore']}</b> · {m['staleDeals']} зависших"
        )

    text = "<b>👥 Команда продаж «Норд Инжиниринг»</b>\n\n" + "\n".join(lines)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть продажи в Mini App", web_app=WebAppInfo(url=f"{public_url}/sales"))]
        ]
    )

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message and isinstance(event.message, Message):
            await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("doc"))
@router.callback_query(F.data == "cmd:doc")
async def handle_doc(event: Message | CallbackQuery) -> None:
    """Incoming documents queue needing human-in-the-loop approval."""
    docs = docs_mod.list_docs()
    pending = [d for d in docs if d.status in ("mismatch", "review")]
    public_url = _get_public_url()

    if not pending:
        msg = "<b>📄 Очередь документов пуста</b>\nВсе входящие документы сверены и проведены в 1С."
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 Открыть документы", web_app=WebAppInfo(url=f"{public_url}/docs"))]
            ]
        )
        if isinstance(event, CallbackQuery):
            await event.answer()
            if event.message and isinstance(event.message, Message):
                await event.message.answer(msg, parse_mode="HTML", reply_markup=kb)
        else:
            await event.answer(msg, parse_mode="HTML", reply_markup=kb)
        return

    doc = pending[0]
    checks_str = "\n".join(f"• {'❌' if not c.ok else '✅'} {c.label}: {c.detail}" for c in doc.checks[:3])

    text = (
        f"<b>📄 Входящий документ ждёт подтверждения (Human-in-the-loop)</b>\n\n"
        f"<b>{doc.kind_label} {doc.number}</b> от {doc.date}\n"
        f"Контрагент: <b>{doc.counterparty}</b>\n"
        f"Сумма: <b>{fmt.rub(doc.amount)}</b>\n"
        f"Статус: <b>{doc.status}</b> (уверенность {int(doc.confidence * 100)}%)\n\n"
        f"🔍 <b>Сверка с 1С и CRM:</b>\n{checks_str}\n\n"
        f"<i>Подтвердите проведение черновика в 1С или отправьте запрос поставщику на исправление.</i>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить проводку", callback_data=f"confirm_doc:{doc.id}"),
                InlineKeyboardButton(text="✉️ Запрос на исправление", callback_data=f"reject_doc:{doc.id}"),
            ],
            [
                InlineKeyboardButton(
                    text="📱 Открыть карточку в Mini App",
                    web_app=WebAppInfo(url=f"{public_url}/docs?id={doc.id}"),
                )
            ],
        ]
    )

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message and isinstance(event.message, Message):
            await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("confirm_doc:"))
async def handle_confirm_doc(query: CallbackQuery) -> None:
    assert query.data is not None
    doc_id = int(query.data.split(":")[1])
    try:
        updated = docs_mod.confirm_doc(doc_id)
        await query.answer("Документ проведён в 1С!", show_alert=False)
        if query.message and isinstance(query.message, Message):
            await query.message.edit_text(
                f"✅ <b>Документ {updated.number} подтверждён человеком</b>\n"
                f"Черновик документа проведён в 1С:Управление торговлей.",
                parse_mode="HTML",
            )
    except Exception as e:
        await query.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("reject_doc:"))
async def handle_reject_doc(query: CallbackQuery) -> None:
    assert query.data is not None
    doc_id = int(query.data.split(":")[1])
    try:
        updated = docs_mod.reject_doc(doc_id)
        await query.answer("Запрос отправлен поставщику", show_alert=False)
        if query.message and isinstance(query.message, Message):
            await query.message.edit_text(
                f"✉️ <b>По документу {updated.number} запрошено исправление</b>\n"
                f"Поставщику отправлено уведомление о расхождении сумм со счётом-основанием.",
                parse_mode="HTML",
            )
    except Exception as e:
        await query.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_draft:"))
async def handle_confirm_draft(query: CallbackQuery) -> None:
    assert query.data is not None
    draft_id = query.data.split(":")[1]
    try:
        tools.tool_confirm_draft(draft_id)
        await query.answer("Действие подтверждено и применено в CRM!", show_alert=False)
        if query.message and isinstance(query.message, Message):
            await query.message.edit_text(
                "✅ <b>Действие подтверждено человеком</b>\n"
                "Черновик успешно применён в CRM.",
                parse_mode="HTML",
            )
    except Exception as e:
        await query.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("undo_draft:"))
async def handle_undo_draft(query: CallbackQuery) -> None:
    assert query.data is not None
    draft_id = query.data.split(":")[1]
    try:
        tools.tool_undo_draft(draft_id)
        await query.answer("Черновик отменён", show_alert=False)
        if query.message and isinstance(query.message, Message):
            await query.message.edit_text(
                "❌ <b>Действие агента отменено</b>\nНикаких изменений в CRM не внесено.",
                parse_mode="HTML",
            )
    except Exception as e:
        await query.answer(f"Ошибка: {e}", show_alert=True)


@router.message(F.text)
async def handle_freeform_question(message: Message) -> None:
    """Answers any natural language question through unified Hermes Agent runner."""
    text = (message.text or "").strip()
    if not text:
        return

    visitor_id = f"tg_{message.from_user.id}" if message.from_user else "tg_guest"

    # Send typing action or thinking placeholder
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")  # type: ignore[union-attr]

    ans = await runner.answer(text, session_id=visitor_id, visitor_id=visitor_id)
    answer_text = ans.get("text", "Ответ получен.")
    sources = ans.get("sources", [])

    formatted = html.escape(answer_text)
    if sources:
        src_lines = [f"• {html.escape(s['label'])}" for s in sources]
        formatted += "\n\n<i>Источники:</i>\n" + "\n".join(src_lines)

    # Check if drafts were created during this turn
    drafts = tools.get_drafts(session_id=visitor_id)
    active_drafts = [d for d in drafts if d.get("status") == "pending"]

    kb: InlineKeyboardMarkup | None = None
    if active_drafts:
        last_draft = active_drafts[-1]
        draft_title = str(last_draft.get("title", ""))[:25]
        draft_id = str(last_draft.get("id", ""))
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"✅ Подтвердить: {draft_title}",
                        callback_data=f"confirm_draft:{draft_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"undo_draft:{draft_id}",
                    ),
                ]
            ]
        )

    await message.answer(formatted, parse_mode="HTML", reply_markup=kb)
