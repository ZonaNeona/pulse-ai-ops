"""What the bot says. Every reply comes from the same modules as the web screens; the bot invents nothing.

A Telegram user is a visitor like any other: their documents, drafts and AI limits are their own.
"""

import hashlib
import html
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, User, WebAppInfo

from pulse import data
from pulse.agents import runner, tools
from pulse.core import fmt
from pulse.core.config import get_settings
from pulse.core.visitor import Visitor
from pulse.modules import docs, overview
from pulse.modules.docs.model import KIND_LABEL
from pulse.modules.sales import team

router = Router(name="pulse")
COMMANDS = [
    ("start", "Открыть Пульс"),
    ("today", "Сводка дня"),
    ("team", "Команда продаж"),
    ("doc", "Документы на проверке"),
]
ICON = {"success": "🟢", "warning": "🟡", "danger": "🔴", "neutral": "⚪"}
Button = InlineKeyboardButton


def who(user: User | None) -> Visitor:
    uid = str(user.id if user else 0)
    return Visitor(session=f"tg-{uid}", quota="tg-" + hashlib.sha256(uid.encode()).hexdigest()[:16])


def app(path: str = "/") -> WebAppInfo:
    return WebAppInfo(url=get_settings().public_url.rstrip("/") + "/#" + path)


def rich(text: str) -> str:
    """The agent's **bold** → Telegram HTML, everything else escaped."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(text))


def keyboard(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


async def reply(event: Message | CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer()
        if isinstance(event.message, Message):
            await event.message.answer(text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "<b>Пульс</b> — демо ИИ-платформы для компании «Норд Инжиниринг». Данные вымышленные и обновляются каждую "
        "ночь.\n\n"
        "/today — сводка дня\n/team — команда продаж\n/doc — документы, которые ждут решения\n\n"
        "Или спросите текстом: «какие сделки зависли?», «какая скидка допустима для дилера?»",
        reply_markup=keyboard(
            [Button(text="Открыть Пульс", web_app=app())],
            [Button(text="Сводка дня", callback_data="today"), Button(text="Документы", callback_data="doc")],
        ),
    )


@router.message(Command("today"))
@router.callback_query(F.data == "today")
async def today(event: Message | CallbackQuery) -> None:
    v = who(event.from_user)
    await docs.queue(v.session)
    ov = overview.overview(data.load())
    rev = ov["revenue"]
    lines = [
        f"<b>{ov['company']['today']}</b>",
        f"Выручка месяца: <b>{fmt.rub_short(rev['fact'])}</b> из {fmt.rub_short(rev['plan'])}, прогноз "
        f"{fmt.rub_short(rev['forecast'])}",
        "",
    ]
    lines += [f"{ICON.get(m['status'], '⚪')} {m['title']}: {m['headline']}" for m in ov["modules"]]
    pending = docs.pending(v.session)
    if pending:
        lines.append(f"🔴 Документы: {len(pending)} ждут решения")
    lines += ["", "<b>Сделать сейчас</b>"] + [
        f"• {html.escape(a['title'])} — {html.escape(a['reason'])}" for a in ov["actions"][:4]
    ]
    await reply(event, "\n".join(lines), keyboard([Button(text="Открыть обзор", web_app=app())]))


@router.message(Command("team"))
@router.callback_query(F.data == "team")
async def team_cmd(event: Message | CallbackQuery) -> None:
    rows = sorted(team.team(data.load()), key=lambda m: -m["quality"])
    lines = ["<b>Команда продаж</b> (звонки к норме этого часа · оценка звонков за 7 дней)"]
    lines += [
        f"{ICON.get(m['status'], '⚪')} {m['name']}: {m['callsToday']}/{m['callsNorm']} · {m['quality']}/100 · "
        f"просрочек {m['overdue']}"
        for m in rows
    ]
    await reply(event, "\n".join(lines), keyboard([Button(text="Открыть команду", web_app=app("/sales/team"))]))


@router.message(Command("doc"))
@router.callback_query(F.data == "doc")
async def doc_cmd(event: Message | CallbackQuery) -> None:
    v = who(event.from_user)
    await docs.queue(v.session)
    pending = docs.pending(v.session)
    if not pending:
        await reply(event, "Документов на проверке нет — всё проверено.")
        return
    d = pending[0]
    checks = "\n".join(f"{'✅' if c.ok else '❌'} {html.escape(c.label)}: {html.escape(c.detail)}" for c in d.checks)
    title = f"{KIND_LABEL.get(d.kind, 'Документ')} № {d.value('number')}"
    head = f"<b>{html.escape(title)}</b>, {html.escape(d.value('counterparty'))}, {fmt.rub(d.amount)}"
    text = f"{head}\n\n{checks}\n\nГраф остановлен до решения человека. Ещё на проверке: {len(pending) - 1}."
    await reply(
        event,
        text,
        keyboard(
            [
                Button(text="Провести", callback_data=f"doc:ok:{d.id}"),
                Button(text="Отклонить", callback_data=f"doc:no:{d.id}"),
            ],
            [Button(text="Открыть документ", web_app=app(f"/docs?id={d.id}"))],
        ),
    )


@router.callback_query(F.data.startswith("doc:"))
async def doc_decide(query: CallbackQuery) -> None:
    _, verdict, doc_id = (query.data or "doc::0").split(":")
    try:
        d = await docs.decide(who(query.from_user).session, int(doc_id), verdict == "ok")
    except (docs.NotAllowed, ValueError) as exc:
        await query.answer(str(exc), show_alert=True)
        return
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.edit_text(f"<b>№ {html.escape(d.value('number'))}</b>: {html.escape(d.decision)}")


@router.callback_query(F.data.startswith("draft:"))
async def draft_decide(query: CallbackQuery) -> None:
    _, verdict, draft_id = (query.data or "draft::").split(":")
    status = "confirmed" if verdict == "ok" else "discarded"
    if tools.set_draft(draft_id, who(query.from_user).session, status) is None:
        await query.answer("Черновик уже решён", show_alert=True)
        return
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.answer(
            "Подтверждено. В демо задача сохраняется только у вас — во внешние системы ничего не уходит."
            if status == "confirmed"
            else "Черновик отклонён."
        )


@router.message(F.text)
async def question(message: Message) -> None:
    if message.bot:
        await message.bot.send_chat_action(message.chat.id, "typing")
    answer = await runner.ask(message.text or "", who(message.from_user))
    kb = None
    if answer["drafts"]:
        d = answer["drafts"][-1]
        kb = keyboard(
            [
                Button(text="Подтвердить", callback_data=f"draft:ok:{d['draft_id']}"),
                Button(text="Отклонить", callback_data=f"draft:no:{d['draft_id']}"),
            ]
        )
    await message.answer(rich(answer["text"])[:4000], reply_markup=kb)
