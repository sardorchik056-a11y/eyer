import asyncio
import html
import io
import logging
import math
import os
import re
import uuid
from datetime import datetime

import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8712603440:AAGc7SV7cAuHYVYZbVv0dSpxUKtmKlDehqM")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "582363:AALEf7JOugnrQyrkMHzH5UrO7pdOjjYnTQy")
CRYPTO_API = "https://pay.crypt.bot/api"
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMwMDgzMiIsImp0aSI6ImFwcDozMDA4MzI6NjY1NzBkYzktMzk4Ny00MWM5LWE1MjAtMzljNTk5ZWUxNjAzIiwiaWF0IjoxNzkwOTUwMzI3fQ.40uVUkYIFEep0eCAewabSQJs7C-XufroQUyzX5UVItc")
XROCKET_API = os.getenv("XROCKET_API", "https://pay.api.xrocket.exchange")  # тестнет: https://pay.api.testnet.xrocket.exchange
CRYPTOBOT_TOKEN_2 = os.getenv("CRYPTOBOT_TOKEN_2", "582363:AALEf7JOugnrQyrkMHzH5UrO7pdOjjYnTQy")
XROCKET_TOKEN_2 = os.getenv("XROCKET_TOKEN_2", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMwMDgzMiIsImp0aSI6ImFwcDozMDA4MzI6NjY1NzBkYzktMzk4Ny00MWM5LWE1MjAtMzljNTk5ZWUxNjAzIiwiaWF0IjoxNzkwOTUwMzI3fQ.40uVUkYIFEep0eCAewabSQJs7C-XufroQUyzX5UVItc")
SPLIT_FROM = 40
ADMIN_ID = 8118184388
DB_PATH = "bot.db"
TITLE = "DASFFING"
REF_PERCENT = 5
DIVIDER = "━━━━━━━━━━━━━━━━━━━━"

ID_SUPPORT = "5391112412445288650"
ID_DENIED = "5210952531676504517"
ID_MAIL = "5253742260054409879"
ID_WAIT = "5386367538735104399"

ID_USER = "5258011929993026890"
ID_WALLET = "5258204546391351475"
ID_BOX = "5258134813302332906"
ID_TG = "5285350148451344065"
ID_MAX = "5449407131675558756"
ID_BUY = "5440841102871517055"

ID_BADGE = ""
ID_USERNAME = ""
ID_GIFT = ""
ID_USERS = ""
ID_LINK = ""
ID_PIN = ""
ID_CALENDAR = ""
ID_PROMO = ""
ID_BACK = ""

# ---- эмодзи для каталога (из вашего списка) ----
ID_OK = "5206607081334906820"      # ✔️
ID_WARN = "5447644880824181073"    # ⚠️
ID_SHOP = "5229064374403998351"    # 🛍
ID_STATS = "5231200819986047254"   # 📊
ID_PRICE = "5409048419211682843"   # 💵
ID_PAY = "5231005931550030290"     # 💸
ID_NOTE = "5334544901428229844"    # ℹ️

# ---- магазин ----
CUR = "$"
DEFAULT_MIN = 10
MIN_TOPUP = 1
MAX_TOPUP = 1000
SUPPORT_USERNAME = "DqASAQ"
PRODUCTS = {
    "tg": {"name": "Telegram нерег", "short": "Telegram", "icon": ID_TG, "fb": "✈️", "price": 0.60, "min": DEFAULT_MIN, "col": "bought_tg"},
    "max": {"name": "MAX нерег", "short": "MAX", "icon": ID_MAX, "fb": "🟣", "price": 0.50, "min": DEFAULT_MIN, "col": "bought_max"},
}
QTY_PRESETS = (10, 25, 50, 100)
TOPUP_PRESETS = (5, 10, 25, 50)
BUSY: set[int] = set()

ID_BTN_TOPUP = "5258204546391351475"
ID_BTN_PROFILE = "5258011929993026890"
ID_BTN_STATS = "5231200819986047254"
ID_BTN_CATALOG = "5406683434124859552"
ID_BTN_INFO = "5334544901428229844"


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


def btn(text: str, data: str, icon: str = "", fb: str = "", style: str | None = None) -> InlineKeyboardButton:
    if not icon and fb:
        text = f"{fb} {text}"
    return InlineKeyboardButton(text=text, callback_data=data, icon_custom_emoji_id=icon or None, style=style)


def url_btn(text: str, url: str, icon: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url, icon_custom_emoji_id=icon or None)


def back_btn(data: str, text: str = "Назад") -> InlineKeyboardButton:
    return btn(text, data, ID_BACK, "⬅️")


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


def menu_kb(user_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        [btn("Пополнить", "topup", ID_BTN_TOPUP), btn("Профиль", "profile", ID_BTN_PROFILE)],
        [btn("Статистика", "stats", ID_BTN_STATS), btn("Каталог", "catalog", ID_BTN_CATALOG)],
        [btn("Инфо", "info", ID_BTN_INFO)],
    ]
    if user_id == ADMIN_ID:
        rows.append([btn("Админка", "adm", ID_SUPPORT, "🛠")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Пополнить", "topup", ID_BTN_TOPUP)],
            [btn("Реф-ссылка", "reflink", ID_GIFT)],
            [btn("Мои рефералы", "refs", ID_USERS)],
            [btn("Промокод", "promo", ID_PROMO)],
            [back_btn("menu")],
        ]
    )


def back_kb(data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[back_btn(data)]])


def fmt_date(value: str | None) -> str:
    if not value:
        return "—"
    return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d.%m.%Y")


def menu_text(user: aiosqlite.Row, stock: dict) -> str:
    return (
        f"{TITLE}\n\n"
        f"{ce(ID_USER, '👤')} Ваш ID: {user['user_id']}\n"
        f"{ce(ID_WALLET, '💰')} Баланс: {money(user['balance'])}\n\n"
        f"{ce(ID_BOX, '📦')} На складе:\n"
        f"{ce(ID_TG, '💬')} ТГ — {stock.get('tg', 0)} шт.\n"
        f"{ce(ID_MAX, '📲')} MAX — {stock.get('max', 0)} шт.\n\n"
        f"{ce(ID_BUY, '🛒')} Куплено:\n"
        f"{ce(ID_TG, '💬')} ТГ — {user['bought_tg']} шт.\n"
        f"{ce(ID_MAX, '📲')} MAX — {user['bought_max']} шт."
    )


def profile_text(user: aiosqlite.Row, username: str | None, ref_count: int, link: str) -> str:
    shown_username = f"@{html.escape(username)}" if username else "не указан"
    return (
        f"{ce(ID_USER, '👤')} Профиль\n\n"
        f"{ce(ID_BADGE, '🆔')} ID: {user['user_id']}\n"
        f"{ce(ID_USERNAME, '📛')} Username: {shown_username}\n"
        f"{ce(ID_WALLET, '💰')} Баланс: {money(user['balance'])}\n\n"
        f"{ce(ID_BOX, '📦')} Куплено всего:\n"
        f"{ce(ID_TG, '💬')} Telegram: {user['bought_tg']} шт.\n"
        f"{ce(ID_MAX, '📲')} MAX: {user['bought_max']} шт.\n"
        f"{ce(ID_WALLET, '💰')} Потрачено: {money(user['spent'])}\n\n"
        f"{DIVIDER}\n"
        f"{ce(ID_GIFT, '🎁')} Реферальная система\n"
        f"{DIVIDER}\n"
        f"{ce(ID_USERS, '👥')} Приглашено: {ref_count} чел.\n"
        f"{ce(ID_WALLET, '💰')} Заработано: {money(user['ref_earned'])}\n\n"
        f"{ce(ID_LINK, '🔗')} Ваша ссылка:\n"
        f"{link}\n\n"
        f"{ce(ID_PIN, '📌')} За каждое пополнение : {REF_PERCENT}%\n\n"
        f"{ce(ID_CALENDAR, '📅')} Регистрация: {fmt_date(user['created_at'])}"
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
            "spent REAL NOT NULL DEFAULT 0, "
            "referrer_id INTEGER, "
            "ref_earned REAL NOT NULL DEFAULT 0, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        async with db.execute("PRAGMA table_info(users)") as cur:
            columns = {row[1] for row in await cur.fetchall()}
        for name, ddl in (
            ("spent", "REAL NOT NULL DEFAULT 0"),
            ("referrer_id", "INTEGER"),
            ("ref_earned", "REAL NOT NULL DEFAULT 0"),
        ):
            if name not in columns:
                await db.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS stock (platform TEXT PRIMARY KEY, qty INTEGER NOT NULL DEFAULT 0)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS accounts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL, "
            "data TEXT NOT NULL, sold INTEGER NOT NULL DEFAULT 0)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS invoices ("
            "invoice_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, amount REAL NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS xr_invoices (\n"
            "invoice_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, amount REAL NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        for table in ("invoices", "xr_invoices"):
            async with db.execute(f"PRAGMA table_info({table})") as cur:
                cols = {row[1] for row in await cur.fetchall()}
            if "tier" not in cols:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN tier INTEGER NOT NULL DEFAULT 0")
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
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


async def ensure_user(user_id: int, ref_id: int | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cur:
            if await cur.fetchone():
                return
        referrer = None
        if ref_id and ref_id != user_id:
            async with db.execute(
                "SELECT 1 FROM users WHERE user_id = ? AND status = 'approved'", (ref_id,)
            ) as cur:
                if await cur.fetchone():
                    referrer = ref_id
        await db.execute(
            "INSERT INTO users (user_id, status, referrer_id) VALUES (?, 'new', ?)",
            (user_id, referrer),
        )
        await db.commit()


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


async def count_refs(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ? AND status = 'approved'", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0]


async def get_referrals(user_id: int, limit: int = 30) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, full_name, created_at FROM users "
            "WHERE referrer_id = ? AND status = 'approved' ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return await cur.fetchall()


async def add_balance(user_id: int, amount: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = ROUND(balance + ?, 2) WHERE user_id = ?", (amount, user_id))
        async with db.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        if row and row[0]:
            bonus = round(amount * REF_PERCENT / 100, 2)
            await db.execute(
                "UPDATE users SET balance = ROUND(balance + ?, 2), ref_earned = ROUND(ref_earned + ?, 2) WHERE user_id = ?",
                (bonus, bonus, row[0]),
            )
        await db.commit()


async def send_menu(bot: Bot, chat_id: int, user_id: int) -> None:
    user = await get_user(user_id)
    stock = await get_stock()
    await bot.send_message(chat_id, menu_text(user, stock), reply_markup=menu_kb(user_id))


async def require_approved(call: CallbackQuery) -> aiosqlite.Row | None:
    user = await get_user(call.from_user.id)
    if not user or user["status"] != "approved":
        await call.answer("Доступ ограничен", show_alert=True)
        return None
    return user


async def ref_link(bot: Bot, user_id: int) -> str:
    me = await bot.me()
    return f"https://t.me/{me.username}?start=ref_{user_id}"


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    ref_id = None
    if command.args and command.args.startswith("ref_") and command.args[4:].isdigit():
        ref_id = int(command.args[4:])

    await ensure_user(message.from_user.id, ref_id)
    user = await get_user(message.from_user.id)

    if not await is_subscribed(bot, message.from_user.id):
        await message.answer(TEXT_SUB, reply_markup=await sub_kb())
        return
    if user["status"] == "approved":
        await send_menu(bot, message.chat.id, message.from_user.id)
        return
    if user["status"] == "pending":
        await message.answer(TEXT_ALREADY)
        return
    await message.answer(TEXT_START, reply_markup=apply_kb())


@router.callback_query(F.data == "apply")
async def on_apply(call: CallbackQuery, bot: Bot) -> None:
    tg_user = call.from_user
    if not await is_subscribed(bot, tg_user.id):
        await call.answer("Сначала подпишитесь на канал", show_alert=True)
        await call.message.edit_text(TEXT_SUB, reply_markup=await sub_kb())
        return
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

    if await get_setting("auto_accept") == "1":
        await set_status(tg_user.id, "approved")
        await call.answer()
        await call.message.edit_text(TEXT_APPROVED, reply_markup=None)
        await send_menu(bot, call.message.chat.id, tg_user.id)
        try:
            await bot.send_message(
                ADMIN_ID,
                f"<b>Автоприём:</b> {html.escape(tg_user.full_name)} (<code>{tg_user.id}</code>)",
            )
        except TelegramAPIError:
            pass
        return

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


@router.callback_query(F.data == "menu")
async def on_menu(call: CallbackQuery, state: FSMContext) -> None:
    user = await require_approved(call)
    if not user:
        return
    await state.clear()
    stock = await get_stock()
    await call.answer()
    await call.message.edit_text(menu_text(user, stock), reply_markup=menu_kb(call.from_user.id))


@router.callback_query(F.data == "profile")
async def on_profile(call: CallbackQuery, bot: Bot) -> None:
    user = await require_approved(call)
    if not user:
        return
    link = await ref_link(bot, user["user_id"])
    refs = await count_refs(user["user_id"])
    await call.answer()
    await call.message.edit_text(
        profile_text(user, call.from_user.username, refs, link),
        reply_markup=profile_kb(),
    )


@router.callback_query(F.data == "reflink")
async def on_reflink(call: CallbackQuery, bot: Bot) -> None:
    user = await require_approved(call)
    if not user:
        return
    link = await ref_link(bot, user["user_id"])
    text = (
        f"{ce(ID_GIFT, '🎁')} <b>Реф-ссылка</b>\n\n"
        f"{ce(ID_LINK, '🔗')} Ваша ссылка:\n"
        f"<code>{link}</code>\n\n"
        f"{ce(ID_PIN, '📌')} За каждое пополнение : {REF_PERCENT}%"
    )
    await call.answer()
    await call.message.edit_text(text, reply_markup=back_kb("profile"))


@router.callback_query(F.data == "refs")
async def on_refs(call: CallbackQuery) -> None:
    user = await require_approved(call)
    if not user:
        return
    total = await count_refs(user["user_id"])
    rows = await get_referrals(user["user_id"])

    lines = [f"{ce(ID_USERS, '👥')} <b>Мои рефералы:</b> {total}\n"]
    if not rows:
        lines.append("Пока никого нет.")
    for i, row in enumerate(rows, 1):
        name = f"@{row['username']}" if row["username"] else (row["full_name"] or str(row["user_id"]))
        lines.append(f"{i}. {html.escape(name)} — {fmt_date(row['created_at'])}")
    if total > len(rows):
        lines.append(f"\nи ещё {total - len(rows)}")

    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb("profile"))


# ======================================================================
#                              КАТАЛОГ
# ======================================================================
class Flow(StatesGroup):
    qty = State()
    topup = State()


class DeliveryError(Exception):
    pass


def money(value: float) -> str:
    return f"{CUR}{value:,.2f}"


def total_price(key: str, qty: int) -> float:
    return round(PRODUCTS[key]["price"] * qty, 2)


def p_icon(p: str) -> str:
    return ce(PRODUCTS[p]["icon"], PRODUCTS[p]["fb"])


def err(text: str) -> str:
    return f"{ce(ID_DENIED, '❌')} {text}"


# ---------- тексты экранов ----------
def catalog_text() -> str:
    lines = [f"{ce(ID_SHOP, '🛍')} <b>Каталог товаров</b>\n"]
    for key, p in PRODUCTS.items():
        lines.append(f"{p_icon(key)} <b>{p['name']}</b>\n{ce(ID_PRICE, '💵')} Цена: {money(p['price'])} за шт.\n")
    return "\n".join(lines)


def item_text(key: str, stock: int, balance: float) -> str:
    p = PRODUCTS[key]
    return (
        f"{p_icon(key)} <b>{p['name']}</b>\n\n"
        f"{ce(ID_PRICE, '💵')} Цена: {money(p['price'])} за шт.\n"
        f"{ce(ID_STATS, '📊')} В наличии: {stock} шт.\n"
        f"{ce(ID_WALLET, '💰')} Ваш баланс: {money(balance)}"
    )


def no_funds_text(balance: float) -> str:
    return (
        f"{err('<b>Недостаточно средств</b>')}\n\n"
        f"{ce(ID_WALLET, '💰')} Ваш баланс: {money(balance)}\n\n"
        "Пополните баланс, чтобы продолжить покупку."
    )


def buy_text(key: str, stock: int, balance: float) -> str:
    p = PRODUCTS[key]
    return (
        f"{ce(ID_BUY, '🛒')} <b>Покупка {p['short']}</b>\n\n"
        f"{ce(ID_PRICE, '💵')} Цена: {money(p['price'])} за шт.\n"
        f"{ce(ID_STATS, '📊')} В наличии: {stock} шт.\n"
        f"{ce(ID_WALLET, '💰')} Ваш баланс: {money(balance)}\n\n"
        f"{ce(ID_WARN, '⚠️')} Минимальная покупка: {p['min']} шт.\n"
        f"{ce(ID_PAY, '💸')} Минимальная сумма: {money(total_price(key, p['min']))}\n\n"
        "Выберите количество кнопкой или отправьте число сообщением."
    )


def qty_prompt_text(key: str, balance: float) -> str:
    p = PRODUCTS[key]
    return (
        f"✏️ <b>Введите количество</b>\n\n"
        f"Товар: {p_icon(key)} {p['short']}\n"
        f"Цена: {money(p['price'])} за шт.\n"
        f"Минимум: {p['min']} шт.\n"
        f"{ce(ID_WALLET, '💰')} Ваш баланс: {money(balance)}\n\n"
        "Отправьте число сообщением."
    )


def confirm_text(key: str, qty: int, balance: float) -> str:
    p = PRODUCTS[key]
    total = total_price(key, qty)
    return (
        f"{ce(ID_BUY, '🛒')} <b>Подтвердите покупку</b>\n\n"
        f"Товар: {p_icon(key)} {p['short']}\n"
        f"Количество: {qty} шт.\n"
        f"Цена за шт.: {money(p['price'])}\n"
        f"Итого: {money(total)}\n"
        f"Остаток после покупки: {money(round(balance - total, 2))}"
    )


def delivery_error_text(key: str, qty: int, total: float, user_id: int) -> str:
    p = PRODUCTS[key]
    return (
        f"{err('<b>Ошибка выдачи товара</b>')}\n\n"
        f"Товар: {p_icon(key)} {p['short']}\n"
        f"Количество: {qty} шт.\n"
        f"Списано: {money(total)}\n\n"
        f"{ce(ID_WARN, '⚠️')} Произошла ошибка на стороне склада.\n"
        "Аккаунты временно недоступны.\n\n"
        f"Обратитесь в поддержку: @{SUPPORT_USERNAME}\n"
        f"Укажите ваш ID: <code>{user_id}</code>"
    )


def topup_text() -> str:
    return (
        f"{ce(ID_PAY, '💸')} <b>Пополнение баланса</b>\n\n"
        f"Введите сумму пополнения.\nМинимум: {money(MIN_TOPUP)}.\n\n"
        "Оплата через CryptoBot или xRocket, баланс зачисляется автоматически."
    )


# ---------- клавиатуры ----------
def catalog_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn(p["short"], f"item:{k}", p["icon"]) for k, p in PRODUCTS.items()],
            [back_btn("menu")],
        ]
    )


def item_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Купить", f"buy:{key}", ID_BUY, "🛒", "success")],
            [btn("Пополнить баланс", "topup", ID_PAY, "💸")],
            [back_btn("catalog")],
        ]
    )


def no_funds_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[btn("Пополнить баланс", "topup", ID_PAY, "💸")], [back_btn(f"item:{key}")]]
    )


def buy_kb(key: str) -> InlineKeyboardMarkup:
    mn = PRODUCTS[key]["min"]
    presets = [n for n in QTY_PRESETS if n >= mn] or [mn]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn(str(n), f"qty:{key}:{n}") for n in presets],
            [back_btn(f"item:{key}")],
        ]
    )


def confirm_kb(key: str, qty: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Подтвердить", f"ok:{key}:{qty}", ID_OK, "✔️", "success")],
            [btn("Отменить", f"item:{key}", ID_DENIED, "❌", "danger")],
        ]
    )


def delivery_error_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [url_btn("Поддержка", f"https://t.me/{SUPPORT_USERNAME}", ID_SUPPORT)],
            [back_btn("catalog", "В каталог")],
            [btn("Главное меню", "menu", fb="🏠")],
        ]
    )


def topup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn(f"{CUR}{n}", f"tu:{n}") for n in TOPUP_PRESETS],
            [btn("Своя сумма", "tuc", fb="✏️")],
            [back_btn("menu")],
        ]
    )


# ---------- логика ----------
def check_qty(user: aiosqlite.Row, key: str, qty: int, stock: int) -> str | None:
    if qty < PRODUCTS[key]["min"]:
        return f"Минимум {PRODUCTS[key]['min']} шт."
    if qty > stock:
        return f"В наличии только {stock} шт"
    if total_price(key, qty) > round(user["balance"], 2):
        return "Недостаточно баланса"
    return None


async def charge(user_id: int, total: float) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET balance = ROUND(balance - ?, 2), spent = ROUND(spent + ?, 2) "
            "WHERE user_id = ? AND ROUND(balance, 2) >= ?",
            (total, total, user_id, total),
        )
        await db.commit()
        return cur.rowcount == 1


async def deliver_accounts(key: str, qty: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            "SELECT id, data FROM accounts WHERE platform = ? AND sold = 0 ORDER BY id LIMIT ?", (key, qty)
        ) as cur:
            rows = await cur.fetchall()
        if len(rows) < qty:
            await db.rollback()
            raise DeliveryError(f"на складе {len(rows)} из {qty}")
        ids = [r[0] for r in rows]
        marks = ",".join("?" * len(ids))
        await db.execute(f"UPDATE accounts SET sold = 1 WHERE id IN ({marks})", ids)
        await db.commit()
        return [r[1] for r in rows]


async def finalize_purchase(user_id: int, key: str, qty: int) -> None:
    col = PRODUCTS[key]["col"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE stock SET qty = MAX(qty - ?, 0) WHERE platform = ?", (qty, key))
        await db.execute(f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?", (qty, user_id))
        await db.commit()


# ---------- обработчики каталога ----------
@router.callback_query(F.data == "catalog")
async def on_catalog(call: CallbackQuery, state: FSMContext) -> None:
    if not await require_approved(call):
        return
    await state.clear()
    await call.answer()
    await call.message.edit_text(catalog_text(), reply_markup=catalog_kb())


@router.callback_query(F.data.startswith("item:"))
async def on_item(call: CallbackQuery, state: FSMContext) -> None:
    user = await require_approved(call)
    key = call.data.split(":")[1]
    if not user or key not in PRODUCTS:
        return
    await state.clear()
    stock = (await get_stock()).get(key, 0)
    await call.answer()
    await call.message.edit_text(item_text(key, stock, user["balance"]), reply_markup=item_kb(key))


@router.callback_query(F.data.startswith("buy:"))
async def on_buy(call: CallbackQuery, state: FSMContext) -> None:
    user = await require_approved(call)
    key = call.data.split(":")[1]
    if not user or key not in PRODUCTS:
        return
    await state.clear()
    await call.answer()
    if user["balance"] < total_price(key, PRODUCTS[key]["min"]):
        await call.message.edit_text(no_funds_text(user["balance"]), reply_markup=no_funds_kb(key))
        return
    stock = (await get_stock()).get(key, 0)
    await call.message.edit_text(buy_text(key, stock, user["balance"]), reply_markup=buy_kb(key))
    await state.set_state(Flow.qty)  # число можно сразу написать сообщением
    await state.update_data(key=key)


@router.callback_query(F.data.startswith("qty:"))
async def on_qty_preset(call: CallbackQuery, state: FSMContext) -> None:
    user = await require_approved(call)
    if not user:
        return
    _, key, raw = call.data.split(":")
    if key not in PRODUCTS:
        return
    qty = int(raw)
    stock = (await get_stock()).get(key, 0)
    problem = check_qty(user, key, qty, stock)
    if problem:
        await call.answer(f"❌ {problem}", show_alert=True)
        return
    await state.clear()
    await call.answer()
    await call.message.edit_text(confirm_text(key, qty, user["balance"]), reply_markup=confirm_kb(key, qty))


@router.callback_query(F.data.startswith("qtyc:"))
async def on_qty_custom(call: CallbackQuery, state: FSMContext) -> None:
    user = await require_approved(call)
    key = call.data.split(":")[1]
    if not user or key not in PRODUCTS:
        return
    await state.set_state(Flow.qty)
    await state.update_data(key=key)
    await call.answer()
    await call.message.edit_text(
        qty_prompt_text(key, user["balance"]),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn(f"buy:{key}", "Отмена")]]),
    )


@router.message(Flow.qty, F.text)
async def on_qty_message(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user or user["status"] != "approved":
        return
    key = (await state.get_data()).get("key")
    if key not in PRODUCTS:
        await state.clear()
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer(err("Отправьте число"))
        return
    qty = int(raw)
    stock = (await get_stock()).get(key, 0)
    problem = check_qty(user, key, qty, stock)
    if problem:
        await message.answer(err(problem))
        return
    await state.clear()
    await message.answer(confirm_text(key, qty, user["balance"]), reply_markup=confirm_kb(key, qty))


@router.callback_query(F.data.startswith("ok:"))
async def on_confirm(call: CallbackQuery, bot: Bot) -> None:
    user = await require_approved(call)
    if not user:
        return
    _, key, raw = call.data.split(":")
    if key not in PRODUCTS:
        return
    uid = user["user_id"]
    if uid in BUSY:
        await call.answer()
        return
    BUSY.add(uid)
    try:
        qty = int(raw)
        stock = (await get_stock()).get(key, 0)
        problem = check_qty(user, key, qty, stock)
        if problem:
            await call.answer(f"❌ {problem}", show_alert=True)
            return
        total = total_price(key, qty)
        await call.answer()
        await call.message.edit_reply_markup(reply_markup=None)

        if not await charge(uid, total):
            await call.message.edit_text(no_funds_text(user["balance"]), reply_markup=no_funds_kb(key))
            return

        try:
            accounts = await deliver_accounts(key, qty)
        except Exception as exc:  # баланс уже списан — как на экране 8
            logging.exception("Ошибка выдачи для %s", uid)
            await call.message.edit_text(delivery_error_text(key, qty, total, uid), reply_markup=delivery_error_kb())
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>Ошибка выдачи</b>\nПользователь: <code>{uid}</code>\n"
                    f"Товар: {PRODUCTS[key]['short']} × {qty}\nСписано: {money(total)}\n"
                    f"Причина: {html.escape(str(exc))}",
                )
            except TelegramAPIError:
                pass
            return

        await finalize_purchase(uid, key, qty)
        fresh = await get_user(uid)
        await call.message.edit_text(
            f"{ce(ID_OK, '✔️')} <b>Покупка выполнена</b>\n\n"
            f"Товар: {p_icon(key)} {PRODUCTS[key]['short']}\n"
            f"Количество: {qty} шт.\n"
            f"Списано: {money(total)}\n"
            f"{ce(ID_WALLET, '💰')} Баланс: {money(fresh['balance'])}\n\n"
            "Аккаунты — в файле ниже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn("catalog", "В каталог")]]),
        )
        file = BufferedInputFile("\n".join(accounts).encode("utf-8"), filename=f"{key}_{qty}.txt")
        await bot.send_document(uid, file)
    finally:
        BUSY.discard(uid)


# ======================================================================
#                ПОПОЛНЕНИЕ (CryptoBot + xRocket), суммы в USD
# ======================================================================
def parse_amount(raw: str) -> float | None:
    try:
        value = float(raw.strip().replace(",", ".").lstrip("$"))
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return round(value, 2)


def not_configured(token: str) -> bool:
    return token.startswith("ВСТАВЬТЕ")


# ---------- CryptoBot ----------
def cb_token(tier: int = 0) -> str:
    if tier == 1 and not not_configured(CRYPTOBOT_TOKEN_2):
        return CRYPTOBOT_TOKEN_2
    return CRYPTOBOT_TOKEN


def xr_token(tier: int = 0) -> str:
    if tier == 1 and not not_configured(XROCKET_TOKEN_2):
        return XROCKET_TOKEN_2
    return XROCKET_TOKEN


async def invoice_tiers(table: str, ids: list) -> dict:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(f"SELECT invoice_id, tier FROM {table} WHERE invoice_id IN ({marks})", ids) as cur:
            return {r[0]: r[1] for r in await cur.fetchall()}


async def crypto_api(method: str, post: bool = False, _tk: str | None = None, **params):
    token = _tk or CRYPTOBOT_TOKEN
    if not_configured(token):
        raise RuntimeError("CRYPTOBOT_TOKEN не задан")
    headers = {"Crypto-Pay-API-Token": token}
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        kwargs = {"json": params} if post else {"params": params}
        async with session.request("POST" if post else "GET", f"{CRYPTO_API}/{method}", headers=headers, **kwargs) as r:
            data = await r.json()
    if not data.get("ok"):
        raise RuntimeError(f"CryptoBot: {data}")
    return data["result"]


async def create_invoice(user_id: int, amount: float) -> tuple[int, str]:
    tier = 1 if amount > SPLIT_FROM and not not_configured(CRYPTOBOT_TOKEN_2) else 0
    res = await crypto_api(
        "createInvoice",
        post=True,
        _tk=cb_token(tier),
        currency_type="fiat",
        fiat="USD",
        amount=f"{amount:.2f}",
        description=f"Пополнение баланса {TITLE}",
        payload=str(user_id),
        expires_in=3600,
    )
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO invoices (invoice_id, user_id, amount, tier) VALUES (?, ?, ?, ?)",
            (res["invoice_id"], user_id, amount, tier),
        )
        await db.commit()
    return res["invoice_id"], res.get("bot_invoice_url") or res.get("pay_url")


async def notify_credited(bot: Bot, user_id: int, amount: float) -> None:
    try:
        await bot.send_message(user_id, f"{ce(ID_OK, '✔️')} Баланс пополнен на <b>{money(amount)}</b>")
    except TelegramAPIError:
        pass


async def sync_invoices(bot: Bot, ids: list[int]) -> list[int]:
    """Проверяет счета в CryptoBot, зачисляет оплаченные. Возвращает id зачисленных."""
    credited: list[int] = []
    tiers = await invoice_tiers("invoices", ids)
    batches = []
    for tier in (0, 1):
        tier_ids = [x for x in ids if tiers.get(x, 0) == tier]
        batches += [(tier, tier_ids[i : i + 50]) for i in range(0, len(tier_ids), 50)]
    for tier, chunk in batches:
        res = await crypto_api("getInvoices", _tk=cb_token(tier), invoice_ids=",".join(map(str, chunk)))
        items = res["items"] if isinstance(res, dict) else res
        for inv in items:
            status = inv.get("status")
            if status not in ("paid", "expired"):
                continue
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(
                    "UPDATE invoices SET status = ? WHERE invoice_id = ? AND status = 'pending'",
                    ("paid" if status == "paid" else "expired", inv["invoice_id"]),
                )
                await db.commit()
                if cur.rowcount != 1:
                    continue
                async with db.execute(
                    "SELECT user_id, amount FROM invoices WHERE invoice_id = ?", (inv["invoice_id"],)
                ) as c2:
                    user_id, amount = await c2.fetchone()
            if status == "paid":
                await add_balance(user_id, amount)
                credited.append(inv["invoice_id"])
                await notify_credited(bot, user_id, amount)
    return credited


async def invoice_poller(bot: Bot) -> None:
    while True:
        await asyncio.sleep(20)
        if not_configured(CRYPTOBOT_TOKEN) and not_configured(CRYPTOBOT_TOKEN_2):
            continue
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT invoice_id FROM invoices WHERE status = 'pending'") as cur:
                    ids = [r[0] for r in await cur.fetchall()]
            if ids:
                await sync_invoices(bot, ids)
        except Exception:
            logging.exception("Ошибка проверки счетов CryptoBot")


# ---------- xRocket ----------
class XRocketError(Exception):
    def __init__(self, status: int, problem: str) -> None:
        super().__init__(f"xRocket {status}: {problem}")
        self.status = status


async def xrocket_api(
    method: str, path: str, *, body: dict | None = None, params: dict | None = None, token: str | None = None
):
    token = token or XROCKET_TOKEN
    if not_configured(token):
        raise RuntimeError("XROCKET_TOKEN не задан")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(method, f"{XROCKET_API}{path}", headers=headers, json=body, params=params) as r:
            try:
                data = await r.json(content_type=None)
            except Exception:
                data = None
            if not 200 <= r.status < 300:
                problem = (data or {}).get("type") or (data or {}).get("detail") or "unknown"
                raise XRocketError(r.status, str(problem))
    return data


async def create_xr_invoice(user_id: int, amount: float) -> tuple[str, str]:
    # счёт выставляется в USDT (1 USDT ≈ 1 USD), на баланс зачисляется та же сумма в $
    tier = 1 if amount > SPLIT_FROM and not not_configured(XROCKET_TOKEN_2) else 0
    res = await xrocket_api(
        "POST",
        "/api/v1/invoices",
        token=xr_token(tier),
        body={
            "priceCurrency": "USDT",
            "priceAmount": f"{amount:.2f}",
            "clientInvoiceId": f"{user_id}-{uuid.uuid4().hex[:16]}",
            "description": f"Пополнение баланса {TITLE}",
            "expiresIn": 3_600_000,
        },
    )
    invoice_id = str(res["id"])
    link = (res.get("links") or {}).get("telegramBotLink") or (res.get("links") or {}).get("webLink")
    if not link:
        raise RuntimeError(f"xRocket: нет ссылки на оплату: {res}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO xr_invoices (invoice_id, user_id, amount, tier) VALUES (?, ?, ?, ?)",
            (invoice_id, user_id, amount, tier),
        )
        await db.commit()
    return invoice_id, link


async def sync_xr_invoices(bot: Bot, ids: list[str]) -> list[str]:
    """Проверяет счета xRocket по одному (лимит API: 20 запросов/мин на метод)."""
    credited: list[str] = []
    tiers = await invoice_tiers("xr_invoices", ids)
    for invoice_id in ids:
        try:
            inv = await xrocket_api(
                "GET", "/api/v1/invoice", params={"invoiceId": invoice_id}, token=xr_token(tiers.get(invoice_id, 0))
            )
        except XRocketError as exc:
            if exc.status == 429:
                break  # упёрлись в лимит — продолжим на следующем цикле
            if exc.status == 404:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE xr_invoices SET status = 'expired' WHERE invoice_id = ? AND status = 'pending'",
                        (invoice_id,),
                    )
                    await db.commit()
            logging.warning("xRocket %s: %s", invoice_id, exc)
            continue
        status = inv.get("status")
        if status not in ("paid", "expired", "cancelled"):
            continue
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "UPDATE xr_invoices SET status = ? WHERE invoice_id = ? AND status = 'pending'",
                (status, invoice_id),
            )
            await db.commit()
            if cur.rowcount != 1:
                continue
            async with db.execute(
                "SELECT user_id, amount FROM xr_invoices WHERE invoice_id = ?", (invoice_id,)
            ) as c2:
                user_id, amount = await c2.fetchone()
        if status == "paid":
            await add_balance(user_id, amount)
            credited.append(invoice_id)
            await notify_credited(bot, user_id, amount)
    return credited


async def xrocket_poller(bot: Bot) -> None:
    while True:
        await asyncio.sleep(30)
        if not_configured(XROCKET_TOKEN) and not_configured(XROCKET_TOKEN_2):
            continue
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT invoice_id FROM xr_invoices WHERE status = 'pending' ORDER BY created_at LIMIT 15"
                ) as cur:
                    ids = [r[0] for r in await cur.fetchall()]
            if ids:
                await sync_xr_invoices(bot, ids)
        except Exception:
            logging.exception("Ошибка проверки счетов xRocket")


# ---------- экраны пополнения ----------
def method_text(amount: float) -> str:
    return (
        f"{ce(ID_PAY, '💸')} <b>Пополнение на {money(amount)}</b>\n\n"
        "Выберите способ оплаты:"
    )


def method_kb(amount: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("CryptoBot", f"pm:cb:{amount:.2f}", ID_PAY, "💸")],
            [btn("xRocket", f"pm:xr:{amount:.2f}", ID_PAY, "🚀")],
            [back_btn("topup")],
        ]
    )


async def show_methods(target: Message, amount: float, edit: bool = False) -> None:
    if edit:
        await target.edit_text(method_text(amount), reply_markup=method_kb(amount))
    else:
        await target.answer(method_text(amount), reply_markup=method_kb(amount))


async def start_topup(target: Message, user_id: int, amount: float, method: str) -> None:
    try:
        if method == "xr":
            invoice_id, url = await create_xr_invoice(user_id, amount)
            check = f"chx:{invoice_id}"
            via = "xRocket"
        else:
            invoice_id, url = await create_invoice(user_id, amount)
            check = f"chk:{invoice_id}"
            via = "CryptoBot"
    except Exception:
        logging.exception("Не удалось создать счёт (%s)", method)
        await target.answer(err("Оплата временно недоступна. Попробуйте позже или выберите другой способ."))
        return
    await target.answer(
        f"{ce(ID_PAY, '💸')} <b>Счёт на {money(amount)}</b>\n\n"
        f"Оплатите через {via} — баланс зачислится автоматически.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [url_btn("Оплатить", url, ID_PAY)],
                [btn("Проверить оплату", check, ID_OK, "✔️")],
                [back_btn("menu")],
            ]
        ),
    )


@router.callback_query(F.data == "topup")
async def on_topup(call: CallbackQuery, state: FSMContext) -> None:
    if not await require_approved(call):
        return
    await state.clear()
    await call.answer()
    await call.message.edit_text(topup_text(), reply_markup=topup_kb())


@router.callback_query(F.data.startswith("tu:"))
async def on_topup_preset(call: CallbackQuery) -> None:
    if not await require_approved(call):
        return
    amount = parse_amount(call.data.split(":")[1])
    if amount is None or not MIN_TOPUP <= amount <= MAX_TOPUP:
        await call.answer("❌ Неверная сумма", show_alert=True)
        return
    await call.answer()
    await show_methods(call.message, amount, edit=True)


@router.callback_query(F.data == "tuc")
async def on_topup_custom(call: CallbackQuery, state: FSMContext) -> None:
    if not await require_approved(call):
        return
    await state.set_state(Flow.topup)
    await call.answer()
    await call.message.edit_text(
        f"✏️ <b>Введите сумму</b>\n\nМинимум: {money(MIN_TOPUP)}, максимум: {money(MAX_TOPUP)}.\n"
        "Отправьте число сообщением (можно с копейками, например 2.5).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn("topup", "Отмена")]]),
    )


@router.message(Flow.topup, F.text)
async def on_topup_message(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user or user["status"] != "approved":
        return
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer(err("Отправьте число, например 5 или 2.5"))
        return
    if amount < MIN_TOPUP:
        await message.answer(err(f"Минимум {money(MIN_TOPUP)}"))
        return
    if amount > MAX_TOPUP:
        await message.answer(err(f"Максимум {money(MAX_TOPUP)}"))
        return
    await state.clear()
    await show_methods(message, amount)


@router.callback_query(F.data.startswith("pm:"))
async def on_pay_method(call: CallbackQuery) -> None:
    if not await require_approved(call):
        return
    _, method, raw = call.data.split(":")
    amount = parse_amount(raw)
    if method not in ("cb", "xr") or amount is None or not MIN_TOPUP <= amount <= MAX_TOPUP:
        await call.answer("❌ Неверные данные", show_alert=True)
        return
    await call.answer()
    await call.message.edit_reply_markup(reply_markup=None)
    await start_topup(call.message, call.from_user.id, amount, method)


@router.callback_query(F.data.startswith("chk:"))
async def on_check_payment(call: CallbackQuery, bot: Bot) -> None:
    if not await require_approved(call):
        return
    invoice_id = int(call.data.split(":")[1])
    try:
        credited = await sync_invoices(bot, [invoice_id])
    except Exception:
        logging.exception("Ошибка проверки оплаты CryptoBot")
        await call.answer("❌ Не удалось проверить оплату", show_alert=True)
        return
    await call.answer("✔️ Оплата получена" if credited else "Оплата пока не поступила", show_alert=True)


@router.callback_query(F.data.startswith("chx:"))
async def on_check_xr_payment(call: CallbackQuery, bot: Bot) -> None:
    if not await require_approved(call):
        return
    invoice_id = call.data.split(":", 1)[1]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM xr_invoices WHERE invoice_id = ? AND user_id = ?", (invoice_id, call.from_user.id)
        ) as cur:
            if not await cur.fetchone():
                await call.answer("Счёт не найден", show_alert=True)
                return
    try:
        credited = await sync_xr_invoices(bot, [invoice_id])
    except Exception:
        logging.exception("Ошибка проверки оплаты xRocket")
        await call.answer("❌ Не удалось проверить оплату", show_alert=True)
        return
    await call.answer("✔️ Оплата получена" if credited else "Оплата пока не поступила", show_alert=True)


# ======================================================================
#                      АДМИН: загрузка аккаунтов
# ======================================================================
@router.message(F.document, F.caption.startswith("/load"))
async def on_load_accounts(message: Message, bot: Bot) -> None:
    """Админ отправляет .txt (1 аккаунт = 1 строка) с подписью `/load tg` или `/load max`."""
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.caption.split()
    if len(parts) != 2 or parts[1] not in PRODUCTS:
        await message.answer("Формат подписи: <code>/load tg</code> или <code>/load max</code>")
        return
    key = parts[1]
    buf = io.BytesIO()
    await bot.download(message.document, destination=buf)
    lines = [ln.strip() for ln in buf.getvalue().decode("utf-8", "ignore").splitlines() if ln.strip()]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany("INSERT INTO accounts (platform, data) VALUES (?, ?)", [(key, ln) for ln in lines])
        await db.execute("UPDATE stock SET qty = qty + ? WHERE platform = ?", (len(lines), key))
        await db.commit()
    await message.answer(f"Загружено {len(lines)} шт. ({key})")


@router.callback_query(F.data == "promo")
async def on_stub(call: CallbackQuery) -> None:
    await call.answer("Раздел в разработке", show_alert=True)


# ======================================================================
#                    СТАТИСТИКА И ПРАВИЛА
# ======================================================================
RULES = [
    "1. Товар — цифровой, возврату не подлежит.",
    "2. Гарантия действует 24 часа с момента покупки.",
    "3. Замена возможна при невалиде кода в течение гарантийного срока.",
    "4. После первого входа гарантия снимается.",
    "5. Пополнение баланса невозвратное.",
    "6. Администрация вправе отказать в обслуживании.",
    "7. Использование бота означает согласие с правилами.",
]


def stats_text(user: aiosqlite.Row) -> str:
    return (
        f"{ce(ID_STATS, '📊')} <b>Статистика</b>\n\n"
        f"{ce(ID_USER, '👤')} <b>Ваша статистика:</b>\n"
        f"{ce(ID_TG, '💬')} Куплено Telegram: {user['bought_tg']} шт.\n"
        f"{ce(ID_MAX, '📲')} Куплено MAX: {user['bought_max']} шт.\n"
        f"{ce(ID_WALLET, '💰')} Потрачено: {money(user['spent'])}"
    )


def rules_text() -> str:
    return f"{ce(ID_NOTE, 'ℹ️')} <b>Правила</b>\n\n" + "\n".join(RULES)


@router.callback_query(F.data == "stats")
async def on_stats(call: CallbackQuery) -> None:
    user = await require_approved(call)
    if not user:
        return
    await call.answer()
    await call.message.edit_text(stats_text(user), reply_markup=back_kb("menu"))


@router.callback_query(F.data == "info")
async def on_info(call: CallbackQuery) -> None:
    if not await require_approved(call):
        return
    await call.answer()
    await call.message.edit_text(rules_text(), reply_markup=back_kb("menu"))


# ======================================================================
#                НАСТРОЙКИ, ПОДПИСКА НА КАНАЛ
# ======================================================================
async def get_setting(key: str, default: str | None = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
    return row[0] if row else default


async def set_setting(key: str, value: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        if value is None:
            await db.execute("DELETE FROM settings WHERE key = ?", (key,))
        else:
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        await db.commit()


async def load_settings() -> None:
    for key, p in PRODUCTS.items():
        price = await get_setting(f"price_{key}")
        if price:
            p["price"] = float(price)
        mn = await get_setting(f"min_{key}")
        if mn:
            p["min"] = int(mn)


TEXT_SUB = (
    f"{E_DENIED} <b>ПОДПИШИТЕСЬ НА КАНАЛ</b>\n\n"
    "<i>Чтобы продолжить, подпишитесь на наш канал и нажмите «Проверить подписку».</i>"
)


async def channel_url() -> str | None:
    url = await get_setting("channel_url")
    if url:
        return url
    ch = await get_setting("channel")
    if ch and ch.startswith("@"):
        return f"https://t.me/{ch[1:]}"
    return None


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    ch = await get_setting("channel")
    if not ch:
        return True
    try:
        member = await bot.get_chat_member(ch if ch.startswith("@") else int(ch), user_id)
    except (TelegramAPIError, ValueError):
        logging.exception("Не удалось проверить подписку")
        return True  # не блокируем людей, если канал настроен неверно
    if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        return False
    if member.status == ChatMemberStatus.RESTRICTED and not getattr(member, "is_member", True):
        return False
    return True


async def sub_kb() -> InlineKeyboardMarkup:
    rows = []
    url = await channel_url()
    if url:
        rows.append([url_btn("Подписаться", url, ID_MAIL)])
    rows.append([btn("Проверить подписку", "chksub", ID_OK, "✔️", "success")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "chksub")
async def on_check_sub(call: CallbackQuery, bot: Bot) -> None:
    uid = call.from_user.id
    if not await is_subscribed(bot, uid):
        await call.answer("Вы ещё не подписались", show_alert=True)
        return
    await call.answer()
    await ensure_user(uid, None)
    user = await get_user(uid)
    try:
        await call.message.delete()
    except TelegramAPIError:
        pass
    if user["status"] == "approved":
        await send_menu(bot, call.message.chat.id, uid)
    elif user["status"] == "pending":
        await bot.send_message(call.message.chat.id, TEXT_ALREADY)
    else:
        await bot.send_message(call.message.chat.id, TEXT_START, reply_markup=apply_kb())


# ======================================================================
#                              АДМИНКА
# ======================================================================
class Admin(StatesGroup):
    price = State()
    stock = State()
    minq = State()
    mail = State()
    channel = State()
    bal_user = State()
    bal_amount = State()


ADM_FIELDS = {
    "price": (Admin.price, "новую цену за 1 шт. в $ (например 0.65)"),
    "stock": (Admin.stock, "новый остаток (целое число)"),
    "min": (Admin.minq, "новое минимальное количество для покупки (целое число)"),
}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def adm_cancel(data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[back_btn(data, "Отмена")]])


async def admin_text() -> str:
    ch = await get_setting("channel")
    auto = await get_setting("auto_accept") == "1"
    return (
        f"{ce(ID_NOTE, 'ℹ️')} <b>Админ-панель</b>\n\n"
        f"{ce(ID_MAIL, '✉️')} Приём заявок: <b>{'автоматически' if auto else 'вручную'}</b>\n"
        f"{ce(ID_NOTE, 'ℹ️')} Канал подписки: <b>{html.escape(ch) if ch else 'не задан'}</b>"
    )


async def admin_kb() -> InlineKeyboardMarkup:
    auto = await get_setting("auto_accept") == "1"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Статистика", "adm:stats", ID_STATS, "📊"), btn("Рассылка", "adm:mail", ID_MAIL, "✉️")],
            [btn("Каталог", "adm:cat", ID_SHOP, "🛍"), btn("Выдать баланс", "adm:bal", ID_WALLET, "💰")],
            [btn("Канал подписки", "adm:chan", ID_NOTE, "ℹ️")],
            [btn(f"Автоприём заявок: {'вкл' if auto else 'выкл'}", "adm:auto", ID_OK if auto else ID_DENIED)],
            [back_btn("menu", "В меню")],
        ]
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(await admin_text(), reply_markup=await admin_kb())


@router.callback_query(F.data == "adm")
async def adm_home(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    await call.answer()
    await call.message.edit_text(await admin_text(), reply_markup=await admin_kb())


@router.callback_query(F.data == "adm:auto")
async def adm_auto(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    cur = await get_setting("auto_accept") == "1"
    await set_setting("auto_accept", "0" if cur else "1")
    await call.answer("Автоприём включён" if not cur else "Автоприём выключен")
    await call.message.edit_text(await admin_text(), reply_markup=await admin_kb())


# ---------- статистика ----------
@router.callback_query(F.data == "adm:stats")
async def adm_stats(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*), COALESCE(SUM(status = 'approved'), 0), COALESCE(SUM(status = 'pending'), 0), "
            "COALESCE(SUM(balance), 0), COALESCE(SUM(spent), 0), "
            "COALESCE(SUM(bought_tg), 0), COALESCE(SUM(bought_max), 0) FROM users"
        ) as cur:
            total, approved, pending, balances, spent, b_tg, b_max = await cur.fetchone()
        async with db.execute("SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE status = 'paid'") as cur:
            cb_sum = (await cur.fetchone())[0]
        async with db.execute("SELECT COALESCE(SUM(amount), 0) FROM xr_invoices WHERE status = 'paid'") as cur:
            xr_sum = (await cur.fetchone())[0]
    stock = await get_stock()
    text = (
        f"{ce(ID_STATS, '📊')} <b>Статистика бота</b>\n\n"
        f"{ce(ID_USER, '👤')} Пользователей: {total} (одобрено {approved}, в ожидании {pending})\n"
        f"{ce(ID_WALLET, '💰')} Сумма балансов: {money(balances)}\n"
        f"{ce(ID_PAY, '💸')} Пополнено всего: {money(cb_sum + xr_sum)}\n"
        f"{ce(ID_PRICE, '💵')} Потрачено на покупки: {money(spent)}\n\n"
        f"{ce(ID_BUY, '🛒')} Продано:\n"
        f"{ce(ID_TG, '💬')} Telegram — {b_tg} шт.\n"
        f"{ce(ID_MAX, '📲')} MAX — {b_max} шт.\n\n"
        f"{ce(ID_BOX, '📦')} Остаток:\n"
        f"{ce(ID_TG, '💬')} Telegram — {stock.get('tg', 0)} шт.\n"
        f"{ce(ID_MAX, '📲')} MAX — {stock.get('max', 0)} шт."
    )
    await call.answer()
    await call.message.edit_text(text, reply_markup=back_kb("adm"))


# ---------- каталог: цены, остаток, мин. количество ----------
async def admin_product_text(key: str) -> str:
    p = PRODUCTS[key]
    stock = (await get_stock()).get(key, 0)
    return (
        f"{p_icon(key)} <b>{p['name']}</b>\n\n"
        f"{ce(ID_PRICE, '💵')} Цена: {money(p['price'])} за шт.\n"
        f"{ce(ID_BOX, '📦')} Остаток: {stock} шт.\n"
        f"{ce(ID_WARN, '⚠️')} Мин. количество: {p['min']} шт."
    )


def admin_product_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Изменить цену", f"adm:set:price:{key}", ID_PRICE, "💵")],
            [btn("Изменить остаток", f"adm:set:stock:{key}", ID_BOX, "📦")],
            [btn("Изменить мин. кол-во", f"adm:set:min:{key}", ID_WARN, "⚠️")],
            [back_btn("adm:cat")],
        ]
    )


@router.callback_query(F.data == "adm:cat")
async def adm_catalog(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    stock = await get_stock()
    lines = [f"{ce(ID_SHOP, '🛍')} <b>Каталог</b>\n"]
    for k, p in PRODUCTS.items():
        lines.append(
            f"{p_icon(k)} <b>{p['name']}</b>\n"
            f"{money(p['price'])} · остаток {stock.get(k, 0)} шт. · мин. {p['min']} шт.\n"
        )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [btn(p["short"], f"adm:p:{k}", p["icon"]) for k, p in PRODUCTS.items()],
            [back_btn("adm")],
        ]
    )
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("adm:p:"))
async def adm_product(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":")[2]
    if not is_admin(call.from_user.id) or key not in PRODUCTS:
        await call.answer()
        return
    await state.clear()
    await call.answer()
    await call.message.edit_text(await admin_product_text(key), reply_markup=admin_product_kb(key))


@router.callback_query(F.data.startswith("adm:set:"))
async def adm_set(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    if not is_admin(call.from_user.id) or len(parts) != 4 or parts[2] not in ADM_FIELDS or parts[3] not in PRODUCTS:
        await call.answer()
        return
    field, key = parts[2], parts[3]
    st, hint = ADM_FIELDS[field]
    await state.set_state(st)
    await state.update_data(key=key)
    await call.answer()
    await call.message.edit_text(
        f"✏️ <b>{PRODUCTS[key]['name']}</b>\n\nОтправьте {hint}.",
        reply_markup=adm_cancel(f"adm:p:{key}"),
    )


@router.message(StateFilter(Admin.price, Admin.stock, Admin.minq), F.text)
async def adm_value(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    cur = await state.get_state()
    key = (await state.get_data()).get("key")
    if key not in PRODUCTS:
        await state.clear()
        return
    raw = message.text.strip()
    if cur == Admin.price.state:
        value = parse_amount(raw)
        if value is None or not 0.01 <= value <= 1000:
            await message.answer(err("Введите цену от 0.01 до 1000, например 0.65"))
            return
        PRODUCTS[key]["price"] = value
        await set_setting(f"price_{key}", str(value))
    elif cur == Admin.stock.state:
        if not raw.isdigit():
            await message.answer(err("Отправьте целое число"))
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO stock (platform, qty) VALUES (?, ?) "
                "ON CONFLICT(platform) DO UPDATE SET qty = excluded.qty",
                (key, int(raw)),
            )
            await db.commit()
    else:
        if not raw.isdigit() or int(raw) < 1:
            await message.answer(err("Отправьте целое число от 1"))
            return
        PRODUCTS[key]["min"] = int(raw)
        await set_setting(f"min_{key}", raw)
    await state.clear()
    await message.answer(
        f"{ce(ID_OK, '✔️')} <b>Сохранено</b>\n\n{await admin_product_text(key)}",
        reply_markup=admin_product_kb(key),
    )


# ---------- рассылка ----------
@router.callback_query(F.data == "adm:mail")
async def adm_mail(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.set_state(Admin.mail)
    await call.answer()
    await call.message.edit_text(
        f"{ce(ID_MAIL, '✉️')} <b>Рассылка</b>\n\n"
        "Отправьте сообщение, которое нужно разослать всем одобренным пользователям "
        "(текст, фото, видео — как есть).",
        reply_markup=adm_cancel("adm"),
    )


@router.message(Admin.mail)
async def adm_mail_message(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.update_data(mid=message.message_id, cid=message.chat.id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE status = 'approved'") as cur:
            total = (await cur.fetchone())[0]
    await message.answer(
        f"Отправить это сообщение {total} пользователям?\n<i>Чтобы заменить текст — просто отправьте другое сообщение.</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [btn("Отправить", "adm:mail:go", ID_OK, "✔️", "success")],
                [btn("Отменить", "adm", ID_DENIED, "❌", "danger")],
            ]
        ),
    )


@router.callback_query(F.data == "adm:mail:go")
async def adm_mail_go(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    data = await state.get_data()
    mid, cid = data.get("mid"), data.get("cid")
    if not mid:
        await call.answer("Сначала отправьте сообщение", show_alert=True)
        return
    await state.clear()
    await call.answer()
    await call.message.edit_text("Рассылка запущена…")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE status = 'approved'") as cur:
            ids = [r[0] for r in await cur.fetchall()]
    ok = fail = 0
    for uid in ids:
        for _ in range(2):
            try:
                await bot.copy_message(uid, cid, mid)
                ok += 1
                break
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
            except TelegramAPIError:
                fail += 1
                break
        await asyncio.sleep(0.05)
    await call.message.edit_text(
        f"{ce(ID_OK, '✔️')} <b>Рассылка завершена</b>\n\nДоставлено: {ok}\nНе доставлено: {fail}",
        reply_markup=back_kb("adm"),
    )


# ---------- канал для подписки ----------
async def admin_channel_screen(target: Message, edit: bool) -> None:
    ch = await get_setting("channel")
    text = (
        f"{ce(ID_NOTE, 'ℹ️')} <b>Канал подписки</b>\n\n"
        f"Сейчас: <b>{html.escape(ch) if ch else 'не задан'}</b>\n\n"
        "Если канал задан, пользователь не сможет подать заявку, пока не подпишется."
    )
    rows = [[btn("Задать / изменить", "adm:chan:set", ID_NOTE, "✏️")]]
    if ch:
        rows.append([btn("Отключить", "adm:chan:off", ID_DENIED, "❌", "danger")])
    rows.append([back_btn("adm")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "adm:chan")
async def adm_chan(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    await call.answer()
    await admin_channel_screen(call.message, edit=True)


@router.callback_query(F.data == "adm:chan:set")
async def adm_chan_set(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.set_state(Admin.channel)
    await call.answer()
    await call.message.edit_text(
        "✏️ <b>Канал подписки</b>\n\n"
        "Отправьте <code>@username</code> канала или его ID (<code>-100…</code>).\n"
        "Для приватного канала добавьте через пробел ссылку-приглашение.\n\n"
        f"{ce(ID_WARN, '⚠️')} Бот должен быть администратором канала.",
        reply_markup=adm_cancel("adm:chan"),
    )


@router.message(Admin.channel, F.text)
async def adm_chan_message(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    ref = parts[0]
    if not (ref.startswith("@") or re.fullmatch(r"-100\d+", ref)):
        await message.answer(err("Нужен @username или ID вида -1001234567890"))
        return
    try:
        chat = await bot.get_chat(ref if ref.startswith("@") else int(ref))
        me = await bot.me()
        member = await bot.get_chat_member(chat.id, me.id)
    except TelegramAPIError:
        await message.answer(err("Канал не найден или бот не добавлен в него"))
        return
    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        await message.answer(err("Сделайте бота администратором канала и повторите"))
        return
    url = parts[1] if len(parts) > 1 else (f"https://t.me/{chat.username}" if chat.username else None)
    await set_setting("channel", ref if ref.startswith("@") else str(chat.id))
    await set_setting("channel_url", url)
    await state.clear()
    await message.answer(f"{ce(ID_OK, '✔️')} Канал сохранён")
    await admin_channel_screen(message, edit=False)


@router.callback_query(F.data == "adm:chan:off")
async def adm_chan_off(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await set_setting("channel", None)
    await set_setting("channel_url", None)
    await call.answer("Проверка подписки отключена")
    await admin_channel_screen(call.message, edit=True)


# ---------- выдача баланса ----------
async def find_user(raw: str) -> aiosqlite.Row | None:
    raw = raw.strip().lstrip("@")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if raw.isdigit():
            q, args = "SELECT * FROM users WHERE user_id = ?", (int(raw),)
        else:
            q, args = "SELECT * FROM users WHERE LOWER(username) = ?", (raw.lower(),)
        async with db.execute(q, args) as cur:
            return await cur.fetchone()


def user_label(u: aiosqlite.Row) -> str:
    name = f"@{u['username']}" if u["username"] else (u["full_name"] or "без имени")
    return f"{html.escape(name)} (<code>{u['user_id']}</code>)"


@router.callback_query(F.data == "adm:bal")
async def adm_bal(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.set_state(Admin.bal_user)
    await call.answer()
    await call.message.edit_text(
        f"{ce(ID_WALLET, '💰')} <b>Выдача баланса</b>\n\n"
        "Отправьте ID или @username пользователя.",
        reply_markup=adm_cancel("adm"),
    )


@router.message(Admin.bal_user, F.text)
async def adm_bal_user(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    user = await find_user(message.text)
    if not user:
        await message.answer(err("Пользователь не найден. Он должен хотя бы раз запустить бота."))
        return
    await state.update_data(uid=user["user_id"])
    await state.set_state(Admin.bal_amount)
    await message.answer(
        f"{ce(ID_USER, '👤')} {user_label(user)}\n"
        f"{ce(ID_WALLET, '💰')} Баланс: {money(user['balance'])}\n\n"
        "Отправьте сумму в $ (например <code>5</code> или <code>2.5</code>). "
        "Отрицательное число спишет баланс.",
        reply_markup=adm_cancel("adm"),
    )


@router.message(Admin.bal_amount, F.text)
async def adm_bal_amount(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    user = await get_user((await state.get_data()).get("uid", 0))
    if not user:
        await state.clear()
        return
    amount = parse_amount(message.text)
    if amount is None or amount == 0 or abs(amount) > 100000:
        await message.answer(err("Введите ненулевую сумму, например 5 или -2.5"))
        return
    if round(user["balance"] + amount, 2) < 0:
        await message.answer(err(f"Нельзя списать больше баланса ({money(user['balance'])})"))
        return
    await state.update_data(amount=amount)
    sign = "Выдать" if amount > 0 else "Списать"
    await message.answer(
        f"{sign} <b>{money(abs(amount))}</b>\n"
        f"Пользователь: {user_label(user)}\n"
        f"Баланс: {money(user['balance'])} → {money(round(user['balance'] + amount, 2))}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [btn("Подтвердить", "adm:bal:ok", ID_OK, "✔️", "success")],
                [btn("Отменить", "adm", ID_DENIED, "❌", "danger")],
            ]
        ),
    )


@router.callback_query(F.data == "adm:bal:ok")
async def adm_bal_ok(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    data = await state.get_data()
    uid, amount = data.get("uid"), data.get("amount")
    if uid is None or amount is None:
        await call.answer("Сначала введите сумму", show_alert=True)
        return
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET balance = ROUND(balance + ?, 2) WHERE user_id = ? AND ROUND(balance + ?, 2) >= 0",
            (amount, uid, amount),
        )
        await db.commit()
    if cur.rowcount != 1:
        await call.answer("Не удалось изменить баланс", show_alert=True)
        return
    user = await get_user(uid)
    await call.answer()
    await call.message.edit_text(
        f"{ce(ID_OK, '✔️')} <b>Готово</b>\n\n{user_label(user)}\nНовый баланс: {money(user['balance'])}",
        reply_markup=back_kb("adm"),
    )
    note = (
        f"{ce(ID_OK, '✔️')} Администратор пополнил баланс на <b>{money(amount)}</b>"
        if amount > 0
        else f"{ce(ID_WARN, '⚠️')} Администратор списал с баланса <b>{money(-amount)}</b>"
    )
    try:
        await bot.send_message(uid, note)
    except TelegramAPIError:
        pass


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if BOT_TOKEN.startswith("ВСТАВЬТЕ"):
        raise SystemExit("Впишите BOT_TOKEN в начале main.py")
    await init_db()
    await load_settings()
    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    poller = asyncio.create_task(invoice_poller(bot))
    xr_poller = asyncio.create_task(xrocket_poller(bot))
    try:
        await dp.start_polling(bot)
    finally:
        poller.cancel()
        xr_poller.cancel()


if __name__ == "__main__":
    asyncio.run(main())
