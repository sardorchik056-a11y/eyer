import asyncio
import html
import logging

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

BOT_TOKEN = "8712603440:AAGc7SV7cAuHYVYZbVv0dSpxUKtmKlDehqM"
ADMIN_ID = 8118184388
DB_PATH = "bot.db"
TITLE = "DASFFING"

ID_SUPPORT = "5391112412445288650"
ID_DENIED = "5210952531676504517"
ID_MAIL = "5253742260054409879"
ID_WAIT = "5386367538735104399"

ID_USER = ""
ID_WALLET = ""
ID_BOX = ""
ID_TG = ""
ID_MAX = ""
ID_BUY = ""

ID_BTN_TOPUP = ""
ID_BTN_PROFILE = ""
ID_BTN_STATS = ""
ID_BTN_CATALOG = ""
ID_BTN_INFO = ""


def ce(emoji_id: str, fallback: str) -> str:
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


E_SUPPORT = ce(ID_SUPPORT, "🥸")
E_DENIED = ce(ID_DENIED, "❌")
E_MAIL = ce(ID_MAIL, "✉️")
E_WAIT = ce(ID_WAIT, "⌛")

TEXT_START = (
    f"{E_DENIED} <b>ДОСТУП ОГРАНИЧЕН</b>\n\n"
    "<i>Для начала работы сначала подайте заявку.</i>"
)
TEXT_SUBMITTED = (
    f"{E_MAIL} <b>ЗАЯВКА ПОДАНА, ОЖИДАЙТЕ РАССМОТРЕНИЯ</b>\n\n"
    f"{E_SUPPORT} <b>ПОДДЕРЖКА</b> @DqASAQ"
)
TEXT_ALREADY = f"<b>ЗАЯВКА УЖЕ В РАССМОТРЕНИИ</b> {E_WAIT}"
TEXT_APPROVED = "<b>ЗАЯВКА ОДОБРЕНА</b>"
TEXT_REJECTED = f"{E_DENIED} <b>ЗАЯВКА ОТКЛОНЕНА</b>\n\n{E_SUPPORT} <b>ПОДДЕРЖКА</b> @DqASAQ"

router = Router()


def apply_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подать заявку",
                    callback_data="apply",
                    style="success",
                    icon_custom_emoji_id=ID_MAIL,
                )
            ]
        ]
    )


def decision_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Принять", callback_data=f"acc:{user_id}", style="success"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"rej:{user_id}", style="danger"),
            ]
        ]
    )


def menu_kb() -> InlineKeyboardMarkup:
    def btn(text: str, data: str, icon: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=text, callback_data=data, icon_custom_emoji_id=icon or None)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Пополнить", "topup", ID_BTN_TOPUP), btn("Профиль", "profile", ID_BTN_PROFILE)],
            [btn("Статистика", "stats", ID_BTN_STATS), btn("Каталог", "catalog", ID_BTN_CATALOG)],
            [btn("Инфо", "info", ID_BTN_INFO)],
        ]
    )


def menu_text(user: aiosqlite.Row, stock: dict) -> str:
    return (
        f"{TITLE}\n\n"
        f"{ce(ID_USER, '👤')} Ваш ID: {user['user_id']}\n"
        f"{ce(ID_WALLET, '👛')} Баланс: {user['balance']:g} $\n\n"
        f"{ce(ID_BOX, '📦')} На складе:\n"
        f"{ce(ID_TG, '✈️')} ТГ — {stock.get('tg', 0)} шт.\n"
        f"{ce(ID_MAX, '💬')} MAX — {stock.get('max', 0)} шт.\n\n"
        f"{ce(ID_BUY, '🛍')} Куплено:\n"
        f"{ce(ID_TG, '✈️')} ТГ — {user['bought_tg']} шт.\n"
        f"{ce(ID_MAX, '💬')} MAX — {user['bought_max']} шт."
    )


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "user_id INTEGER PRIMARY KEY, "
            "username TEXT, "
            "full_name TEXT, "
            "status TEXT NOT NULL DEFAULT 'pending', "
            "balance REAL NOT NULL DEFAULT 0, "
            "bought_tg INTEGER NOT NULL DEFAULT 0, "
            "bought_max INTEGER NOT NULL DEFAULT 0, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS stock (platform TEXT PRIMARY KEY, qty INTEGER NOT NULL DEFAULT 0)"
        )
        await db.execute("INSERT OR IGNORE INTO stock (platform, qty) VALUES ('tg', 472), ('max', 1488)")
        await db.commit()


async def get_user(user_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


async def get_stock() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT platform, qty FROM stock") as cur:
            return {p: q for p, q in await cur.fetchall()}


async def create_application(user_id: int, username: str | None, full_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, status) VALUES (?, ?, ?, 'pending') "
            "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, "
            "full_name = excluded.full_name, status = 'pending'",
            (user_id, username, full_name),
        )
        await db.commit()


async def set_status(user_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
        await db.commit()


async def send_menu(bot: Bot, chat_id: int, user_id: int) -> None:
    user = await get_user(user_id)
    stock = await get_stock()
    await bot.send_message(chat_id, menu_text(user, stock), reply_markup=menu_kb())


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user = await get_user(message.from_user.id)
    if user and user["status"] == "approved":
        await send_menu(bot, message.chat.id, message.from_user.id)
        return
    if user and user["status"] == "pending":
        await message.answer(TEXT_ALREADY)
        return
    await message.answer(TEXT_START, reply_markup=apply_kb())


@router.callback_query(F.data == "apply")
async def on_apply(call: CallbackQuery, bot: Bot) -> None:
    tg_user = call.from_user
    user = await get_user(tg_user.id)

    if user and user["status"] == "pending":
        await call.answer()
        await call.message.answer(TEXT_ALREADY)
        return

    if user and user["status"] == "approved":
        await call.answer()
        await call.message.delete()
        await send_menu(bot, call.message.chat.id, tg_user.id)
        return

    await create_application(tg_user.id, tg_user.username, tg_user.full_name)
    await call.answer()
    await call.message.edit_text(TEXT_SUBMITTED, reply_markup=None)

    username = f"@{tg_user.username}" if tg_user.username else "нет"
    text = (
        "<b>Новая заявка</b>\n\n"
        f"Имя: {html.escape(tg_user.full_name)}\n"
        f"Username: {html.escape(username)}\n"
        f"ID: <code>{tg_user.id}</code>"
    )
    try:
        await bot.send_message(ADMIN_ID, text, reply_markup=decision_kb(tg_user.id))
    except TelegramAPIError:
        logging.exception("Не удалось отправить заявку админу")


@router.callback_query(F.data.startswith("acc:") | F.data.startswith("rej:"))
async def on_decision(call: CallbackQuery, bot: Bot) -> None:
    if call.from_user.id != ADMIN_ID:
        await call.answer()
        return

    action, raw_id = call.data.split(":")
    user_id = int(raw_id)
    user = await get_user(user_id)

    if not user or user["status"] != "pending":
        await call.answer("Заявка уже обработана", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
        return

    approved = action == "acc"
    await set_status(user_id, "approved" if approved else "rejected")
    await call.answer()
    await call.message.edit_text(
        f"{call.message.html_text}\n\n<b>{'ПРИНЯТО' if approved else 'ОТКЛОНЕНО'}</b>",
        reply_markup=None,
    )

    try:
        if approved:
            await bot.send_message(user_id, TEXT_APPROVED)
            await send_menu(bot, user_id, user_id)
        else:
            await bot.send_message(user_id, TEXT_REJECTED)
    except TelegramAPIError:
        logging.exception("Не удалось уведомить пользователя %s", user_id)


@router.callback_query(F.data.in_({"topup", "profile", "stats", "catalog", "info"}))
async def on_menu_button(call: CallbackQuery) -> None:
    await call.answer("Раздел в разработке", show_alert=True)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
