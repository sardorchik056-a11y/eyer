# bot.py — HOLIRY SKUP · финальная версия

import asyncio
import io
import json
import re
import zipfile
import logging
import hashlib
import sqlite3
import uuid
import html as html_lib
from datetime import datetime
from contextlib import closing

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

try:
    from aiorocket2 import xRocketClient
    XROCKET_AVAILABLE = True
except ImportError:
    XROCKET_AVAILABLE = False
    xRocketClient = None

# ═══════════════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════════════

BOT_TOKEN = "8666596729:AAH25vROxpHLEE7zv2Olifq9-uA07fbjBVM"
ADMIN_IDS = [8854740379]
SUPPORT_USERNAME = "@holiry_support"

XROCKET_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMwMDgzMiIsImp0aSI6ImFwcDozMDA4MzI6YzZlMTRkYWMtNzk4OC00YjU3LWFhYWQtODU1MmI5YzFmM2VkIiwiaWF0IjoxNzkxOTY5MDIxfQ.LsMEn1gMHcZOGdcMyQMoCxzt1VLSSi5NnV9yTgfb5DI"
XROCKET_CURRENCY = "USDT"

MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_TXT_FILES = 500
DB_PATH = "holiry.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

_xrocket = xRocketClient(api_key=XROCKET_API_KEY) if (XROCKET_AVAILABLE and XROCKET_API_KEY) else None

# ═══════════════════════════════════════════════
# ЭМОДЗИ (обычные — работают у всех)
# ═══════════════════════════════════════════════

E_LOGO     = "⚡️"
E_PROFILE  = "👤"
E_USERS    = "👥"
E_ID       = "🆔"
E_BALANCE  = "💰"
E_PAY      = "💵"
E_TOKEN    = "🔑"
E_FILE     = "📄"
E_ZIP      = "📦"
E_STUCK    = "✅"
E_DEAD     = "❌"
E_INVALID  = "⚠️"
E_PENDING  = "⏳"
E_APP      = "📌"
E_INBOX    = "📥"
E_STATS    = "📊"
E_REFS     = "💠"
E_SUPPORT  = "💬"
E_GUIDE    = "📖"
E_CHANNEL  = "📺"
E_BROADCAST= "📢"
E_WITHDRAW = "💸"
E_GIVE     = "🎁"
E_SETTINGS = "⚙️"
E_BACK     = "◀️"

SEP = "━━━━━━━━━━━━━━━━━━━━"


def btn(text, style="primary", callback_data=None, url=None):
    kw = {"text": text, "style": style}
    if callback_data: kw["callback_data"] = callback_data
    if url: kw["url"] = url
    return InlineKeyboardButton(**kw)


def back_btn(cb="menu"):
    return btn(f"{E_BACK} Назад", style="primary", callback_data=cb)


def split_message(text, limit=3800):
    if len(text) <= limit:
        return [text]
    parts, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > limit:
            parts.append(buf)
            buf = line
        else:
            buf = (buf + "\n" + line) if buf else line
    if buf:
        parts.append(buf)
    return parts


async def safe_edit(cb: CallbackQuery, text: str, kb=None):
    """Безопасное редактирование — не падает при 'message is not modified'."""
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return
        log.warning(f"safe_edit fallback: {e}")
        try:
            await cb.message.answer(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            log.exception("safe_edit: не смог отправить")
    except Exception:
        log.exception("safe_edit")


async def safe_send(chat_id, text, kb=None):
    """Безопасная отправка — режет на части."""
    for chunk in split_message(text, 3800):
        try:
            await bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=kb)
        except Exception:
            log.exception(f"safe_send: не смог отправить в {chat_id}")


# ═══════════════════════════════════════════════
# БД
# ═══════════════════════════════════════════════

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with closing(db()) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            joined_at TEXT,
            referrer_id INTEGER,
            ref_earned REAL DEFAULT 0,
            balance REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_app_number INTEGER,
            archive_name TEXT,
            status TEXT DEFAULT 'pending',
            amount REAL DEFAULT 0,
            created_at TEXT,
            processed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            file_name TEXT,
            device_id TEXT,
            viewer_id INTEGER,
            token_hash TEXT,
            token_full TEXT,
            raw_content TEXT,
            status TEXT DEFAULT 'pending',
            checked_by INTEGER,
            checked_at TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            username TEXT,
            title TEXT,
            is_required INTEGER DEFAULT 1,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rate_per_token', '0.5')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_bonus', '0.1')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('min_withdraw', '5.0')")
        c.commit()


# ── settings ──

def get_setting(key, default):
    with closing(db()) as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_setting(key, value):
    with closing(db()) as c:
        c.execute("INSERT INTO settings (key,value) VALUES (?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        c.commit()


def get_rate(): return float(get_setting("rate_per_token", "0.5"))
def get_ref_bonus(): return float(get_setting("ref_bonus", "0.1"))
def get_min_withdraw(): return float(get_setting("min_withdraw", "5.0"))


# ── users ──

def get_user(tg_id):
    with closing(db()) as c:
        return c.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()


def ensure_user(tg_id, username, referrer_id=None) -> int:
    with closing(db()) as c:
        row = c.execute("SELECT id FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
        if row:
            if username:
                c.execute("UPDATE users SET username=? WHERE telegram_id=?", (username, tg_id))
                c.commit()
            return row["id"]
        cur = c.execute(
            "INSERT INTO users (telegram_id, username, joined_at, referrer_id) VALUES (?,?,?,?)",
            (tg_id, username, datetime.now().isoformat(), referrer_id)
        )
        c.commit()
        return cur.lastrowid


def credit_ref(referrer_tg_id, amount):
    with closing(db()) as c:
        c.execute("UPDATE users SET balance=balance+?, ref_earned=ref_earned+? WHERE telegram_id=?",
                  (amount, amount, referrer_tg_id))
        c.commit()


def credit_balance(tg_id, amount):
    with closing(db()) as c:
        c.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?", (amount, tg_id))
        c.commit()


def user_stats(tg_id):
    with closing(db()) as c:
        u = c.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
        if not u: return None
        uid = u["id"]
        total = c.execute("SELECT COUNT(*) c FROM applications WHERE user_id=?", (uid,)).fetchone()["c"]
        paid = c.execute("SELECT COUNT(*) c, COALESCE(SUM(amount),0) s FROM applications WHERE user_id=? AND status='paid'", (uid,)).fetchone()
        rej = c.execute("SELECT COUNT(*) c FROM applications WHERE user_id=? AND status='rejected'", (uid,)).fetchone()["c"]
        pend = c.execute("SELECT COUNT(*) c FROM applications WHERE user_id=? AND status='pending'", (uid,)).fetchone()["c"]
        return {
            "total": total, "paid_count": paid["c"], "earned": paid["s"],
            "rejected": rej, "pending": pend,
            "balance": u["balance"], "ref_earned": u["ref_earned"],
        }


def count_refs(tg_id):
    with closing(db()) as c:
        return c.execute("SELECT COUNT(*) c FROM users WHERE referrer_id=?", (tg_id,)).fetchone()["c"]


# ── applications ──

def create_application(user_id, archive_name):
    with closing(db()) as c:
        n = c.execute("SELECT COALESCE(MAX(user_app_number), 0) + 1 FROM applications WHERE user_id=?", (user_id,)).fetchone()[0]
        cur = c.execute(
            "INSERT INTO applications (user_id, user_app_number, archive_name, created_at) VALUES (?,?,?,?)",
            (user_id, n, archive_name, datetime.now().isoformat())
        )
        c.commit()
        return cur.lastrowid


def get_application(app_id):
    with closing(db()) as c:
        return c.execute(
            "SELECT a.*, u.telegram_id, u.username FROM applications a "
            "JOIN users u ON u.id=a.user_id WHERE a.id=?", (app_id,)
        ).fetchone()


def user_applications(tg_id, limit=20):
    with closing(db()) as c:
        return c.execute(
            "SELECT a.* FROM applications a JOIN users u ON u.id=a.user_id "
            "WHERE u.telegram_id=? ORDER BY a.id DESC LIMIT ?", (tg_id, limit)
        ).fetchall()


def pending_applications():
    with closing(db()) as c:
        return c.execute(
            "SELECT a.*, u.telegram_id, u.username FROM applications a "
            "JOIN users u ON u.id=a.user_id WHERE a.status='pending' ORDER BY a.id DESC"
        ).fetchall()


def set_app_status(app_id, status, amount=None):
    with closing(db()) as c:
        if amount is not None:
            c.execute("UPDATE applications SET status=?, amount=?, processed_at=? WHERE id=?",
                      (status, amount, datetime.now().isoformat(), app_id))
        else:
            c.execute("UPDATE applications SET status=?, processed_at=? WHERE id=?",
                      (status, datetime.now().isoformat(), app_id))
        c.commit()


# ── tokens ──

def add_token(app_id, file_name, device_id, viewer_id, token, raw_content):
    th = hashlib.sha256(token.encode()).hexdigest()
    with closing(db()) as c:
        cur = c.execute(
            "INSERT INTO tokens (application_id, file_name, device_id, viewer_id, token_hash, "
            "token_full, raw_content, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (app_id, file_name, device_id, viewer_id, th, token, raw_content, datetime.now().isoformat())
        )
        c.commit()
        return cur.lastrowid


def get_tokens(app_id):
    with closing(db()) as c:
        return c.execute("SELECT * FROM tokens WHERE application_id=? ORDER BY id", (app_id,)).fetchall()


def get_token(tid):
    with closing(db()) as c:
        return c.execute("SELECT * FROM tokens WHERE id=?", (tid,)).fetchone()


def set_token_status(tid, status, admin_id):
    with closing(db()) as c:
        c.execute("UPDATE tokens SET status=?, checked_by=?, checked_at=? WHERE id=?",
                  (status, admin_id, datetime.now().isoformat(), tid))
        c.commit()


def token_counts(app_id):
    with closing(db()) as c:
        rows = c.execute("SELECT status, COUNT(*) c FROM tokens WHERE application_id=? GROUP BY status", (app_id,)).fetchall()
        out = {"pending": 0, "stuck": 0, "dead": 0, "invalid": 0}
        for r in rows:
            out[r["status"]] = r["c"]
        return out


def token_exists(th):
    with closing(db()) as c:
        return c.execute("SELECT 1 FROM tokens WHERE token_hash=?", (th,)).fetchone() is not None


# ── channels ──

def get_channels():
    with closing(db()) as c:
        return c.execute("SELECT * FROM channels ORDER BY id").fetchall()


def add_channel(chat_id, username, title):
    with closing(db()) as c:
        c.execute("INSERT INTO channels (chat_id, username, title, created_at) VALUES (?,?,?,?)",
                  (str(chat_id), username, title, datetime.now().isoformat()))
        c.commit()


def del_channel(cid):
    with closing(db()) as c:
        c.execute("DELETE FROM channels WHERE id=?", (cid,))
        c.commit()


# ── stats ──

def get_today_stats():
    today = datetime.now().date().isoformat()
    with closing(db()) as c:
        apps = c.execute("SELECT COUNT(*) c FROM applications WHERE date(created_at)=?", (today,)).fetchone()["c"]
        paid = c.execute("SELECT COUNT(*) c, COALESCE(SUM(amount),0) s FROM applications WHERE status='paid' AND date(processed_at)=?", (today,)).fetchone()
        rej = c.execute("SELECT COUNT(*) c FROM applications WHERE status='rejected' AND date(processed_at)=?", (today,)).fetchone()["c"]
        pend = c.execute("SELECT COUNT(*) c FROM applications WHERE status='pending'").fetchone()["c"]
        new_users = c.execute("SELECT COUNT(*) c FROM users WHERE date(joined_at)=?", (today,)).fetchone()["c"]
        tok = c.execute(
            "SELECT t.status, COUNT(*) c FROM tokens t "
            "JOIN applications a ON a.id=t.application_id "
            "WHERE date(t.created_at)=? GROUP BY t.status", (today,)
        ).fetchall()
        t = {"stuck": 0, "dead": 0, "invalid": 0, "pending": 0}
        for r in tok: t[r["status"]] = r["c"]
        return {
            "apps": apps, "paid_count": paid["c"], "paid_sum": paid["s"],
            "rejected": rej, "pending": pend, "new_users": new_users, "tokens": t,
        }


def get_all_stats():
    with closing(db()) as c:
        users = c.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        apps = c.execute("SELECT COUNT(*) c FROM applications").fetchone()["c"]
        paid = c.execute("SELECT COUNT(*) c, COALESCE(SUM(amount),0) s FROM applications WHERE status='paid'").fetchone()
        rej = c.execute("SELECT COUNT(*) c FROM applications WHERE status='rejected'").fetchone()["c"]
        tok = c.execute("SELECT status, COUNT(*) c FROM tokens GROUP BY status").fetchall()
        t = {"stuck": 0, "dead": 0, "invalid": 0, "pending": 0}
        for r in tok: t[r["status"]] = r["c"]
        return {"users": users, "apps": apps, "paid_count": paid["c"], "paid_sum": paid["s"],
                "rejected": rej, "tokens": t}


# ═══════════════════════════════════════════════
# ПАРСЕР
# ═══════════════════════════════════════════════

RE_DEVICE = re.compile(r"__oneme_device_id',\s*'([^']+)'")
RE_AUTH = re.compile(r"__oneme_auth',\s*'([^']+)'")


def parse_token(content):
    r = {"device_id": None, "token": None, "viewer_id": None, "valid": False}
    m = RE_DEVICE.search(content)
    if m: r["device_id"] = m.group(1)
    m = RE_AUTH.search(content)
    if m:
        try:
            a = json.loads(m.group(1))
            r["token"] = a.get("token")
            r["viewer_id"] = a.get("viewerId")
        except json.JSONDecodeError:
            return r
    if r["device_id"] and r["viewer_id"] and r["token"]:
        r["valid"] = True
    return r


# ═══════════════════════════════════════════════
# xROCKET
# ═══════════════════════════════════════════════

async def xrocket_payout(tg_id, amount):
    if not _xrocket:
        log.warning("xRocket не настроен")
        return None
    tid = f"holiry-{tg_id}-{uuid.uuid4().hex[:12]}"
    try:
        return await _xrocket.create_transfer(
            tg_user_id=tg_id, currency=XROCKET_CURRENCY,
            amount=amount, transfer_id=tid, description="HOLIRY SKUP payout",
        )
    except Exception as e:
        log.error(f"xRocket payout: {e}")
        return None


# ═══════════════════════════════════════════════
# ПРОВЕРКА ПОДПИСКИ
# ═══════════════════════════════════════════════

async def check_subscriptions(user_id):
    chans = get_channels()
    if not chans:
        return True, []
    missing = []
    for ch in chans:
        if not ch["is_required"]:
            continue
        try:
            m = await bot.get_chat_member(ch["chat_id"], user_id)
            if m.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:
            missing.append(ch)
    return len(missing) == 0, missing


def sub_kb(missing):
    kb = InlineKeyboardBuilder()
    for ch in missing:
        if ch["username"]:
            kb.row(btn(f"{E_CHANNEL} {ch['title'] or ch['username']}", style="primary",
                       url=f"https://t.me/{ch['username']}"))
    kb.row(btn(f"{E_STUCK} Я подписался", style="success", callback_data="check_sub"))
    return kb.as_markup()


# ═══════════════════════════════════════════════
# МЕНЮ
# ═══════════════════════════════════════════════

def user_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        btn(f"{E_PROFILE} Профиль", style="primary", callback_data="profile"),
        btn(f"{E_GUIDE} Инфо", style="primary", callback_data="info"),
    )
    kb.row(btn(f"{E_ZIP} Сдать токен", style="success", callback_data="submit"))
    kb.row(btn(f"{E_TOKEN} Мои токены", style="primary", callback_data="my_tokens"))
    kb.row(btn(f"{E_REFS} Рефералы", style="primary", callback_data="refs"))
    kb.row(btn(f"{E_WITHDRAW} Вывести", style="success", callback_data="withdraw"))
    kb.row(btn(f"{E_SUPPORT} Поддержка", style="primary",
               url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"))
    return kb.as_markup()


def admin_menu():
    kb = InlineKeyboardBuilder()
    kb.row(btn(f"{E_INBOX} Заявки", style="primary", callback_data="a_apps"))
    kb.row(btn(f"{E_STATS} Статистика", style="primary", callback_data="a_stats"))
    kb.row(btn(f"{E_USERS} Пользователи", style="primary", callback_data="a_users"))
    kb.row(btn(f"{E_GIVE} Выдать баланс", style="success", callback_data="a_give"))
    kb.row(btn(f"{E_BROADCAST} Рассылка", style="primary", callback_data="a_broadcast"))
    kb.row(btn(f"{E_CHANNEL} Каналы", style="primary", callback_data="a_channels"))
    kb.row(btn(f"{E_SETTINGS} Настройки", style="primary", callback_data="a_settings"))
    return kb.as_markup()


def is_admin(uid): return uid in ADMIN_IDS


# ═══════════════════════════════════════════════
# FSM
# ═══════════════════════════════════════════════

class AdminFSM(StatesGroup):
    rate = State()
    ref_bonus = State()
    min_withdraw = State()
    broadcast = State()
    add_channel = State()
    give_find = State()
    give_amount = State()


class WithdrawFSM(StatesGroup):
    amount = State()


# ═══════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    try:
        await state.clear()
        args = m.text.split(maxsplit=1)
        ref_id = None
        if len(args) > 1 and args[1].startswith("ref_"):
            raw = args[1][4:]
            if raw.isdigit() and int(raw) != m.from_user.id and get_user(int(raw)):
                ref_id = int(raw)
        ensure_user(m.from_user.id, m.from_user.username, ref_id)

        ok, missing = await check_subscriptions(m.from_user.id)
        if not ok:
            await m.answer(
                f"{E_LOGO} <b>HOLIRY SKUP</b>\n\n"
                "Чтобы пользоваться ботом, подпишись на каналы:",
                parse_mode="HTML",
                reply_markup=sub_kb(missing),
            )
            return

        await m.answer(
            f"{E_LOGO} <b>HOLIRY SKUP</b>\n\n"
            "<b>АВТО-ПРИЁМ ТОКЕНОВ MAX</b>\n\n"
            f"{E_PAY} Оплата в течение дня\n"
            f"{E_PENDING} Работаем с 7:30 до 20:00\n"
            f"{E_DEAD} Сб и Вс — выходные\n\n"
            "👇 Выбери действие",
            parse_mode="HTML",
            reply_markup=user_menu(),
        )
    except Exception:
        log.exception("cmd_start")


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(cb: CallbackQuery):
    try:
        ok, missing = await check_subscriptions(cb.from_user.id)
        if ok:
            await safe_edit(cb,
                f"{E_LOGO} <b>HOLIRY SKUP</b>\n\n👇 Выбери действие",
                user_menu())
        else:
            await cb.answer("Ты ещё не подписался на все каналы", show_alert=True)
    except Exception:
        log.exception("cb_check_sub")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await safe_edit(cb,
            f"{E_LOGO} <b>HOLIRY SKUP</b>\n\n👇 Выбери действие",
            user_menu())
    except Exception:
        log.exception("cb_menu")
    finally:
        try: await cb.answer()
        except Exception: pass


# ═══════════════════════════════════════════════
# ЮЗЕР: ПРОФИЛЬ
# ═══════════════════════════════════════════════

@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery):
    try:
        ensure_user(cb.from_user.id, cb.from_user.username)
        s = user_stats(cb.from_user.id)
        u = get_user(cb.from_user.id)
        uname = f"@{u['username']}" if u["username"] else "—"
        text = (
            f"{E_PROFILE} <b>ПРОФИЛЬ</b>\n{SEP}\n\n"
            f"{E_ID} ID: <code>{cb.from_user.id}</code>\n"
            f"📛 Ник: {uname}\n"
            f"📅 В боте с: {u['joined_at'][:10]}\n\n"
            f"{E_STATS} <b>Статистика</b>\n"
            f"├ Сдано заявок: {s['total']}\n"
            f"├ {E_STUCK} Оплачено: {s['paid_count']}\n"
            f"├ {E_DEAD} Отклонено: {s['rejected']}\n"
            f"└ {E_PENDING} В ожидании: {s['pending']}\n\n"
            f"{E_BALANCE} Заработано: <b>{s['earned']:.2f} USDT</b>\n"
            f"{E_REFS} С рефералов: <b>{s['ref_earned']:.2f} USDT</b>\n"
            f"{E_PAY} Баланс: <b>{s['balance']:.2f} USDT</b>"
        )
        await safe_edit(cb, text,
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("menu")]]))
    except Exception:
        log.exception("cb_profile")
    finally:
        try: await cb.answer()
        except Exception: pass


# ═══════════════════════════════════════════════
# ЮЗЕР: ИНФО
# ═══════════════════════════════════════════════

@router.callback_query(F.data == "info")
async def cb_info(cb: CallbackQuery):
    try:
        text = (
            f"{E_GUIDE} <b>ИНФО</b>\n{SEP}\n\n"
            f"{E_LOGO} <b>HOLIRY SKUP</b> — авто-приём токенов MAX\n\n"
            f"{E_PAY} Оплата в течение дня\n"
            f"{E_PENDING} Работаем с 7:30 до 20:00\n"
            f"{E_DEAD} Сб и Вс — выходные\n\n"
            f"{E_ZIP} <b>Как сдать токен:</b>\n"
            "1. Нажми «Сдать токен»\n"
            "2. Отправь .zip архив с .txt файлами\n"
            "3. 1 .txt = 1 токен\n"
            "4. Дождись проверки и оплаты\n\n"
            f"{E_SUPPORT} Поддержка: {SUPPORT_USERNAME}"
        )
        await safe_edit(cb, text,
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("menu")]]))
    except Exception:
        log.exception("cb_info")
    finally:
        try: await cb.answer()
        except Exception: pass


# ═══════════════════════════════════════════════
# ЮЗЕР: СДАТЬ ТОКЕН
# ═══════════════════════════════════════════════

@router.callback_query(F.data == "submit")
async def cb_submit(cb: CallbackQuery):
    try:
        ok, missing = await check_subscriptions(cb.from_user.id)
        if not ok:
            await safe_edit(cb, f"{E_INVALID} Сначала подпишись на каналы:", sub_kb(missing))
            return
        await safe_edit(cb,
            f"{E_ZIP} <b>СДАТЬ ТОКЕН</b>\n{SEP}\n\n"
            "Кидай <b>.zip</b> архив.\n"
            "Внутри — <b>.txt</b> файлы, 1 файл = 1 токен.",
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("menu")]]))
    except Exception:
        log.exception("cb_submit")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.message(F.document)
async def handle_zip(m: Message):
    try:
        doc = m.document
        if not doc.file_name or not doc.file_name.lower().endswith(".zip"):
            await m.answer(f"{E_DEAD} Нужен .zip файл")
            return
        if doc.file_size and doc.file_size > MAX_FILE_SIZE:
            await m.answer(f"{E_DEAD} Файл слишком большой")
            return

        ok, missing = await check_subscriptions(m.from_user.id)
        if not ok:
            await m.answer(f"{E_INVALID} Сначала подпишись на каналы:", reply_markup=sub_kb(missing))
            return

        await m.answer(f"{E_PENDING} Скачиваю архив...")
        try:
            f = await bot.download(doc.file_id)
            data = f.read()
        except Exception as e:
            await m.answer(f"{E_DEAD} Ошибка: {e}")
            return

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                txts = [n for n in z.namelist() if n.lower().endswith(".txt") and not n.endswith("/")]
        except zipfile.BadZipFile:
            await m.answer(f"{E_DEAD} Битый zip")
            return

        if not txts or len(txts) > MAX_TXT_FILES:
            await m.answer(f"{E_DEAD} Нет .txt или слишком много")
            return

        uid = ensure_user(m.from_user.id, m.from_user.username)
        app_id = create_application(uid, doc.file_name)

        added = []
        not_added = []

        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in txts:
                try:
                    raw = z.read(name).decode("utf-8", errors="ignore").strip()
                except Exception:
                    not_added.append(name)
                    continue

                p = parse_token(raw)
                if not p["valid"]:
                    not_added.append(name)
                    continue

                th = hashlib.sha256(p["token"].encode()).hexdigest()
                if token_exists(th):
                    not_added.append(name)
                    continue

                add_token(app_id, name, p["device_id"], int(p["viewer_id"]), p["token"], raw)
                added.append(name)

        if not added:
            set_app_status(app_id, "rejected", 0)
            lines = [f"{E_DEAD} <b>НЕ ДОБАВЛЕНО</b>\n{SEP}\n"]
            for i, name in enumerate(not_added, 1):
                lines.append(f"{i}. {E_FILE} <code>{name}</code>\n   └ {E_DEAD} Отказ: не токен веб")
            await safe_send(m.chat.id, "\n".join(lines))
            return

        lines = [f"{E_STUCK} <b>ДОБАВЛЕНЫ:</b>\n{SEP}\n"]
        for i, name in enumerate(added, 1):
            lines.append(f"{i}. {E_FILE} <code>{name}</code>")

        if not_added:
            lines.append(f"\n{E_DEAD} <b>НЕ ДОБАВЛЕНЫ:</b>\n{SEP}")
            for i, name in enumerate(not_added, 1):
                lines.append(f"{i}. {E_FILE} <code>{name}</code>\n   └ {E_DEAD} Отказ: не токен веб")

        app = get_application(app_id)
        lines.append(f"\n{E_APP} Заявка: <b>#{app['user_app_number']}</b>")
        lines.append(f"{E_PENDING} На проверке")

        await safe_send(m.chat.id, "\n".join(lines))

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"{E_INBOX} <b>НОВАЯ ЗАЯВКА #{app_id}</b>\n"
                    f"👤 @{m.from_user.username or '—'} · ID {m.from_user.id}\n"
                    f"{E_TOKEN} Токенов: {len(added)}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [btn(f"{E_APP} Открыть", style="primary", callback_data=f"app_open:{app_id}")]
                    ]),
                )
            except Exception:
                pass
    except Exception:
        log.exception("handle_zip")
        try: await m.answer(f"{E_DEAD} Ошибка при обработке")
        except Exception: pass


# ═══════════════════════════════════════════════
# ЮЗЕР: МОИ ТОКЕНЫ
# ═══════════════════════════════════════════════

@router.callback_query(F.data == "my_tokens")
async def cb_my_tokens(cb: CallbackQuery):
    try:
        apps = user_applications(cb.from_user.id)
        if not apps:
            text = f"{E_TOKEN} У тебя пока нет заявок."
        else:
            sm = {"pending": f"{E_PENDING} на проверке", "paid": f"{E_STUCK} оплачено", "rejected": f"{E_DEAD} отклонено"}
            lines = [f"{E_TOKEN} <b>МОИ ТОКЕНЫ</b>\n{SEP}\n"]
            for a in apps:
                amount = f" · {a['amount']:.2f} USDT" if a["status"] == "paid" else ""
                lines.append(f"#{a['user_app_number']} — {sm.get(a['status'], a['status'])}{amount}")
            text = "\n".join(lines)
        await safe_edit(cb, text,
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("menu")]]))
    except Exception:
        log.exception("cb_my_tokens")
    finally:
        try: await cb.answer()
        except Exception: pass


# ═══════════════════════════════════════════════
# ЮЗЕР: РЕФЕРАЛЫ
# ═══════════════════════════════════════════════

@router.callback_query(F.data == "refs")
async def cb_refs(cb: CallbackQuery):
    try:
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{cb.from_user.id}"
        u = get_user(cb.from_user.id)
        refs = count_refs(cb.from_user.id)
        text = (
            f"{E_REFS} <b>РЕФЕРАЛЫ</b>\n{SEP}\n\n"
            f"Приглашай друзей и получай <b>{get_ref_bonus():.2f} USDT</b> "
            f"за каждый их валидный токен.\n\n"
            f"{E_STATS} Приглашено: <b>{refs}</b>\n"
            f"{E_BALANCE} Заработано: <b>{u['ref_earned']:.2f} USDT</b>\n\n"
            f"{E_LINK if False else '🔗'} Твоя ссылка:\n<code>{link}</code>"
        )
        await safe_edit(cb, text,
            InlineKeyboardMarkup(inline_keyboard=[
                [btn("Поделиться", style="success",
                     url=f"https://t.me/share/url?url={link}")],
                [back_btn("menu")],
            ]))
    except Exception:
        log.exception("cb_refs")
    finally:
        try: await cb.answer()
        except Exception: pass


# ═══════════════════════════════════════════════
# ЮЗЕР: ВЫВОД БАЛАНСА
# ═══════════════════════════════════════════════

@router.callback_query(F.data == "withdraw")
async def cb_withdraw(cb: CallbackQuery, state: FSMContext):
    try:
        u = get_user(cb.from_user.id)
        if not u:
            await cb.answer("Сначала /start", show_alert=True)
            return
        mn = get_min_withdraw()
        if u["balance"] < mn:
            await cb.answer(f"Минимум для вывода: {mn:.2f} USDT. Баланс: {u['balance']:.2f}", show_alert=True)
            return
        await state.set_state(WithdrawFSM.amount)
        text = (
            f"{E_WITHDRAW} <b>ВЫВОД БАЛАНСА</b>\n{SEP}\n\n"
            f"{E_BALANCE} Доступно: <b>{u['balance']:.2f} USDT</b>\n"
            f"Минимум: {mn:.2f} USDT\n\n"
            "Отправь сумму для вывода:"
        )
        await safe_edit(cb, text,
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("menu")]]))
    except Exception:
        log.exception("cb_withdraw")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.message(WithdrawFSM.amount, F.text)
async def msg_withdraw(m: Message, state: FSMContext):
    try:
        try:
            amount = round(float(m.text.replace(",", ".").strip()), 2)
        except ValueError:
            await m.answer(f"{E_DEAD} Введи число")
            return
        u = get_user(m.from_user.id)
        mn = get_min_withdraw()
        if amount < mn or amount > u["balance"]:
            await m.answer(f"{E_DEAD} Неверная сумма (мин. {mn:.2f}, макс. {u['balance']:.2f})")
            return
        await state.clear()

        result = await xrocket_payout(m.from_user.id, amount)
        if not result:
            await m.answer(f"{E_DEAD} Ошибка выплаты. Попробуй позже или напиши в поддержку.")
            return

        credit_balance(m.from_user.id, -amount)
        await m.answer(
            f"{E_STUCK} <b>ВЫПЛАТА ОТПРАВЛЕНА</b>\n\n"
            f"{E_BALANCE} {amount:.2f} USDT\n"
            f"🧾 <code>{result.get('transferId', '—')}</code>",
            parse_mode="HTML",
        )
    except Exception:
        log.exception("msg_withdraw")


# ═══════════════════════════════════════════════
# АДМИНКА
# ═══════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(m: Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id):
            await m.answer(f"{E_DEAD} Нет доступа")
            return
        await state.clear()
        await m.answer(
            f"{E_LOGO} <b>HOLIRY SKUP · АДМИН</b>\n{SEP}\n\n👇 Выбери раздел",
            parse_mode="HTML",
            reply_markup=admin_menu(),
        )
    except Exception:
        log.exception("cmd_admin")


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        await safe_edit(cb,
            f"{E_LOGO} <b>HOLIRY SKUP · АДМИН</b>\n{SEP}\n\n👇 Выбери раздел",
            admin_menu())
    except Exception:
        log.exception("cb_admin_panel")
    finally:
        try: await cb.answer()
        except Exception: pass


# ── ЗАЯВКИ ──

@router.callback_query(F.data == "a_apps")
async def cb_a_apps(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        apps = pending_applications()
        if not apps:
            await cb.answer("Нет новых заявок", show_alert=True)
            return
        await safe_edit(cb, f"{E_INBOX} <b>НОВЫХ ЗАЯВОК: {len(apps)}</b>")
        for a in apps:
            c = token_counts(a["id"])
            await bot.send_message(
                cb.from_user.id,
                f"{E_APP} <b>#{a['id']}</b> · @{a['username'] or '—'}\n"
                f"🕐 {a['created_at'][11:16]}\n"
                f"{E_TOKEN} {sum(c.values())} · {E_STUCK} {c['stuck']} · {E_DEAD} {c['dead']} · {E_INVALID} {c['invalid']} · {E_PENDING} {c['pending']}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [btn(f"{E_APP} Открыть", style="primary", callback_data=f"app_open:{a['id']}")]
                ]),
            )
    except Exception:
        log.exception("cb_a_apps")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.callback_query(F.data.startswith("app_open:"))
async def cb_app_open(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id):
            await cb.answer("Нет доступа", show_alert=True)
            return
        app_id = int(cb.data.split(":")[1])
        await cb.answer()
        await send_app_card(cb.message.chat.id, app_id)
    except Exception:
        log.exception("cb_app_open")


async def send_app_card(chat_id, app_id):
    try:
        app = get_application(app_id)
        if not app:
            await bot.send_message(chat_id, "Не найдено")
            return
        tokens = get_tokens(app_id)
        c = token_counts(app_id)

        await bot.send_message(
            chat_id,
            f"{E_APP} <b>ЗАЯВКА #{app_id}</b>\n{SEP}\n\n"
            f"👤 @{app['username'] or '—'} · ID {app['telegram_id']}\n"
            f"🕐 {app['created_at'][:16]}\n"
            f"{E_ZIP} {app['archive_name']}\n"
            f"{E_TOKEN} Токенов: {len(tokens)}\n"
            f"{E_PENDING} Проверено: {len(tokens)-c['pending']} из {len(tokens)}",
            parse_mode="HTML",
        )

        icons = {"pending": f"{E_PENDING} не проверен", "stuck": f"{E_STUCK} встал",
                 "dead": f"{E_DEAD} сдох", "invalid": f"{E_INVALID} не валид"}

        for i, t in enumerate(tokens, 1):
            # .txt файл
            try:
                fb = io.BytesIO(t["raw_content"].encode("utf-8"))
                fb.name = t["file_name"]
                await bot.send_document(chat_id, document=fb, caption=f"{i}/{len(tokens)} · {t['file_name']}")
            except Exception:
                log.exception(f"send_document {t['file_name']}")

            # кнопки статусов
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                btn(f"{E_STUCK} Встал", style="success", callback_data=f"tok:stuck:{t['id']}"),
                btn(f"{E_DEAD} Сдох", style="danger", callback_data=f"tok:dead:{t['id']}"),
                btn(f"{E_INVALID} Не валид", style="danger", callback_data=f"tok:invalid:{t['id']}"),
            ]])

            raw_safe = html_lib.escape(t["raw_content"] or "")
            text = (
                f"{E_TOKEN} <b>ТОКЕН #{i}</b>\n"
                f"{E_FILE} {t['file_name']}\n"
                f"🤖 {icons[t['status']]}\n\n"
                f"<b>СОДЕРЖИМОЕ ФАЙЛА:</b>\n"
                f"<code>{raw_safe}</code>"
            )

            chunks = split_message(text, 3800)
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    await bot.send_message(
                        chat_id, chunk, parse_mode="HTML",
                        reply_markup=kb if is_last else None,
                    )
                except Exception:
                    log.exception("send token text")

        amount = c["stuck"] * get_rate()
        rows = []
        if c["pending"] == 0:
            rows.append([btn(f"{E_PAY} Оплатить {amount:.2f} USDT", style="success",
                             callback_data=f"app_pay:{app_id}")])
        rows.append([btn(f"{E_DEAD} Отклонить", style="danger", callback_data=f"app_reject:{app_id}")])
        rows.append([btn("🔄 Обновить", style="primary", callback_data=f"app_open:{app_id}")])
        await bot.send_message(
            chat_id,
            f"{SEP}\n{E_STUCK} {c['stuck']} · {E_DEAD} {c['dead']} · {E_INVALID} {c['invalid']} · {E_PENDING} {c['pending']}\n\n"
            f"{E_BALANCE} К оплате: <b>{amount:.2f} USDT</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
    except Exception:
        log.exception("send_app_card")


@router.callback_query(F.data.startswith("tok:"))
async def cb_tok(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id):
            await cb.answer("Нет доступа", show_alert=True)
            return
        _, status, tid = cb.data.split(":")
        tid = int(tid)
        t = get_token(tid)
        if not t:
            await cb.answer("Не найдено")
            return
        old = t["status"]
        set_token_status(tid, status, cb.from_user.id)

        if status == "stuck" and old != "stuck":
            app = get_application(t["application_id"])
            if app:
                u = get_user(app["telegram_id"])
                if u and u["referrer_id"]:
                    bonus = get_ref_bonus()
                    credit_ref(u["referrer_id"], bonus)
                    try:
                        await bot.send_message(
                            u["referrer_id"],
                            f"{E_REFS} <b>+{bonus:.2f} USDT</b> за валидный токен реферала!",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

        icon = {"stuck": f"{E_STUCK} встал", "dead": f"{E_DEAD} сдох",
                "invalid": f"{E_INVALID} не валид"}[status]
        await cb.answer(f"Статус: {icon}")

        try:
            old_text = cb.message.html_text
            if "<b>СОДЕРЖИМОЕ ФАЙЛА:</b>" in old_text:
                head, rest = old_text.split("<b>СОДЕРЖИМОЕ ФАЙЛА:</b>", 1)
                head = re.sub(r"🤖 .+", f"🤖 {icon}", head)
                await cb.message.edit_text(
                    f"{head}<b>СОДЕРЖИМОЕ ФАЙЛА:</b>{rest}",
                    parse_mode="HTML",
                    reply_markup=cb.message.reply_markup,
                )
        except Exception:
            pass
    except Exception:
        log.exception("cb_tok")


@router.callback_query(F.data.startswith("app_pay:"))
async def cb_app_pay(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        app_id = int(cb.data.split(":")[1])
        c = token_counts(app_id)
        amount = c["stuck"] * get_rate()
        if c["pending"] > 0:
            await cb.answer("Сначала проверь все токены", show_alert=True)
            return
        if amount <= 0:
            await cb.answer("Нет встал-токенов", show_alert=True)
            return

        app = get_application(app_id)
        await cb.answer("Отправляю...")
        result = await xrocket_payout(app["telegram_id"], amount)
        if not result:
            await safe_edit(cb,
                f"{E_DEAD} <b>ОШИБКА ВЫПЛАТЫ</b>\n\n"
                f"Заявка #{app_id}\nСумма: {amount:.2f} USDT\n\n"
                "Проверь: юзер в @xRocket, баланс, ключ.")
            return
        set_app_status(app_id, "paid", amount)
        try:
            await bot.send_message(
                app["telegram_id"],
                f"{E_STUCK} <b>ЗАЯВКА ОПЛАЧЕНА</b>\n\n"
                f"#{app_id} · {amount:.2f} USDT",
                parse_mode="HTML",
            )
        except Exception:
            pass
        await safe_edit(cb,
            f"{E_STUCK} Заявка #{app_id} оплачена\n"
            f"{E_BALANCE} {amount:.2f} USDT\n"
            f"🧾 <code>{result.get('transferId', '—')}</code>")
    except Exception:
        log.exception("cb_app_pay")


@router.callback_query(F.data.startswith("app_reject:"))
async def cb_app_reject(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        app_id = int(cb.data.split(":")[1])
        set_app_status(app_id, "rejected", 0)
        app = get_application(app_id)
        try:
            await bot.send_message(app["telegram_id"],
                f"{E_DEAD} Заявка #{app_id} отклонена", parse_mode="HTML")
        except Exception:
            pass
        await safe_edit(cb, f"{E_DEAD} Заявка #{app_id} отклонена")
    except Exception:
        log.exception("cb_app_reject")
    finally:
        try: await cb.answer()
        except Exception: pass


# ── СТАТИСТИКА ──

@router.callback_query(F.data == "a_stats")
async def cb_a_stats(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        d = get_today_stats()
        a = get_all_stats()
        text = (
            f"{E_STATS} <b>СТАТИСТИКА</b>\n{SEP}\n\n"
            f"📅 <b>СЕГОДНЯ</b> ({datetime.now().strftime('%d.%m.%Y')})\n"
            f"├ {E_INBOX} Заявок: {d['apps']}\n"
            f"├ {E_STUCK} Оплачено: {d['paid_count']} · {d['paid_sum']:.2f} USDT\n"
            f"├ {E_DEAD} Отклонено: {d['rejected']}\n"
            f"└ {E_PENDING} В ожидании: {d['pending']}\n\n"
            f"{E_TOKEN} <b>Токены сегодня</b>\n"
            f"├ {E_STUCK} встал: {d['tokens']['stuck']}\n"
            f"├ {E_DEAD} сдох: {d['tokens']['dead']}\n"
            f"├ {E_INVALID} не валид: {d['tokens']['invalid']}\n"
            f"└ {E_PENDING} ожидает: {d['tokens']['pending']}\n\n"
            f"👥 Новых юзеров: {d['new_users']}\n\n"
            f"{E_STATS} <b>ЗА ВСЁ ВРЕМЯ</b>\n"
            f"├ Юзеров: {a['users']}\n"
            f"├ Заявок: {a['apps']}\n"
            f"├ Оплачено: {a['paid_count']} · {a['paid_sum']:.2f} USDT\n"
            f"└ Отклонено: {a['rejected']}"
        )
        await safe_edit(cb, text,
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("admin_panel")]]))
    except Exception:
        log.exception("cb_a_stats")
    finally:
        try: await cb.answer()
        except Exception: pass


# ── ПОЛЬЗОВАТЕЛИ ──

@router.callback_query(F.data == "a_users")
async def cb_a_users(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        with closing(db()) as c:
            total = c.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            banned = c.execute("SELECT COUNT(*) c FROM users WHERE is_banned=1").fetchone()["c"]
            today = c.execute("SELECT COUNT(*) c FROM users WHERE date(joined_at)=?",
                              (datetime.now().date().isoformat(),)).fetchone()["c"]
        text = (
            f"{E_USERS} <b>ПОЛЬЗОВАТЕЛИ</b>\n{SEP}\n\n"
            f"Всего: <b>{total}</b>\n"
            f"Новых сегодня: <b>{today}</b>\n"
            f"Забанено: <b>{banned}</b>"
        )
        await safe_edit(cb, text,
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("admin_panel")]]))
    except Exception:
        log.exception("cb_a_users")
    finally:
        try: await cb.answer()
        except Exception: pass


# ── ВЫДАТЬ БАЛАНС ──

@router.callback_query(F.data == "a_give")
async def cb_a_give(cb: CallbackQuery, state: FSMContext):
    try:
        if not is_admin(cb.from_user.id): return
        await state.set_state(AdminFSM.give_find)
        await safe_edit(cb,
            f"{E_GIVE} <b>ВЫДАТЬ БАЛАНС</b>\n{SEP}\n\n"
            "Введи ID или @username пользователя:",
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("admin_panel")]]))
    except Exception:
        log.exception("cb_a_give")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.message(AdminFSM.give_find, F.text)
async def msg_give_find(m: Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id): return
        raw = m.text.strip().lstrip("@")
        with closing(db()) as c:
            if raw.isdigit():
                u = c.execute("SELECT * FROM users WHERE telegram_id=?", (int(raw),)).fetchone()
            else:
                u = c.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (raw,)).fetchone()
        if not u:
            await m.answer(f"{E_DEAD} Не найден. Попробуй ещё раз:")
            return
        await state.update_data(target=u["telegram_id"])
        await state.set_state(AdminFSM.give_amount)
        await m.answer(
            f"{E_GIVE} <b>ВЫДАТЬ БАЛАНС</b>\n\n"
            f"👤 @{u['username'] or '—'} · ID {u['telegram_id']}\n"
            f"{E_BALANCE} Текущий баланс: {u['balance']:.2f} USDT\n\n"
            "Отправь сумму:",
            parse_mode="HTML",
        )
    except Exception:
        log.exception("msg_give_find")


@router.message(AdminFSM.give_amount, F.text)
async def msg_give_amount(m: Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id): return
        try:
            amount = round(float(m.text.replace(",", ".").strip()), 2)
        except ValueError:
            await m.answer(f"{E_DEAD} Введи число")
            return
        if amount <= 0 or amount > 100000:
            await m.answer(f"{E_DEAD} Неверная сумма")
            return
        data = await state.get_data()
        tg_id = data["target"]
        credit_balance(tg_id, amount)
        u = get_user(tg_id)
        await state.clear()
        await m.answer(
            f"{E_STUCK} Выдано <b>{amount:.2f} USDT</b>\n"
            f"Новый баланс @{u['username'] or '—'}: <b>{u['balance']:.2f} USDT</b>",
            parse_mode="HTML",
        )
        try:
            await bot.send_message(
                tg_id,
                f"{E_BALANCE} <b>Вам начислено {amount:.2f} USDT</b>\n"
                f"Баланс: {u['balance']:.2f} USDT",
                parse_mode="HTML",
            )
        except Exception:
            pass
    except Exception:
        log.exception("msg_give_amount")


# ── РАССЫЛКА ──

@router.callback_query(F.data == "a_broadcast")
async def cb_a_broadcast(cb: CallbackQuery, state: FSMContext):
    try:
        if not is_admin(cb.from_user.id): return
        await state.set_state(AdminFSM.broadcast)
        with closing(db()) as c:
            total = c.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        await safe_edit(cb,
            f"{E_BROADCAST} <b>РАССЫЛКА</b>\n{SEP}\n\n"
            f"Получателей: <b>{total}</b>\n\n"
            "Отправь текст рассылки:",
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("admin_panel")]]))
    except Exception:
        log.exception("cb_a_broadcast")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.message(AdminFSM.broadcast, F.text)
async def msg_broadcast(m: Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id): return
        text = m.text
        await state.clear()
        with closing(db()) as c:
            users = c.execute("SELECT telegram_id FROM users").fetchall()
        sent, failed = 0, 0
        msg = await m.answer(f"{E_PENDING} Рассылаю...")
        for i, u in enumerate(users, 1):
            try:
                await bot.send_message(u["telegram_id"], text)
                sent += 1
            except Exception:
                failed += 1
            if i % 25 == 0:
                try:
                    await msg.edit_text(f"{E_PENDING} {i}/{len(users)} · {E_STUCK} {sent} · {E_DEAD} {failed}")
                except Exception:
                    pass
            await asyncio.sleep(0.05)
        await msg.edit_text(
            f"{E_STUCK} <b>РАССЫЛКА ЗАВЕРШЕНА</b>\n\n"
            f"{E_STUCK} Доставлено: {sent}\n{E_DEAD} Ошибок: {failed}",
            parse_mode="HTML",
        )
    except Exception:
        log.exception("msg_broadcast")


# ── КАНАЛЫ ──

@router.callback_query(F.data == "a_channels")
async def cb_a_channels(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        chans = get_channels()
        lines = [f"{E_CHANNEL} <b>КАНАЛЫ</b>\n{SEP}\n"]
        if not chans:
            lines.append("Нет каналов.")
        else:
            for ch in chans:
                lines.append(f"@{ch['username']} · {ch['title']}")
        kb = InlineKeyboardBuilder()
        kb.row(btn("➕ Добавить", style="success", callback_data="a_add_channel"))
        if chans:
            kb.row(btn("🗑 Удалить все", style="danger", callback_data="a_del_channels"))
        kb.row(back_btn("admin_panel"))
        await safe_edit(cb, "\n".join(lines), kb.as_markup())
    except Exception:
        log.exception("cb_a_channels")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.callback_query(F.data == "a_add_channel")
async def cb_a_add_channel(cb: CallbackQuery, state: FSMContext):
    try:
        if not is_admin(cb.from_user.id): return
        await state.set_state(AdminFSM.add_channel)
        await safe_edit(cb,
            f"{E_CHANNEL} Отправь @username или ID канала (-100...):",
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("a_channels")]]))
    except Exception:
        log.exception("cb_a_add_channel")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.message(AdminFSM.add_channel, F.text)
async def msg_add_channel(m: Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id): return
        raw = m.text.strip()
        try:
            chat = await bot.get_chat(raw)
            add_channel(chat.id, chat.username, chat.title or "")
            await state.clear()
            await m.answer(f"{E_STUCK} Канал @{chat.username} добавлен")
        except Exception as e:
            await m.answer(f"{E_DEAD} Ошибка: {e}")
    except Exception:
        log.exception("msg_add_channel")


@router.callback_query(F.data == "a_del_channels")
async def cb_a_del_channels(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        for ch in get_channels():
            del_channel(ch["id"])
        await cb.answer("Удалено")
        await cb_a_channels(cb)
    except Exception:
        log.exception("cb_a_del_channels")


# ── НАСТРОЙКИ ──

@router.callback_query(F.data == "a_settings")
async def cb_a_settings(cb: CallbackQuery):
    try:
        if not is_admin(cb.from_user.id): return
        kb = InlineKeyboardBuilder()
        kb.row(btn(f"{E_PAY} Ставка: {get_rate():.2f} USDT", style="primary", callback_data="set_rate"))
        kb.row(btn(f"{E_REFS} Рефка: {get_ref_bonus():.2f} USDT", style="primary", callback_data="set_ref"))
        kb.row(btn(f"{E_BALANCE} Мин. вывод: {get_min_withdraw():.2f} USDT", style="primary", callback_data="set_min"))
        kb.row(back_btn("admin_panel"))
        text = (
            f"{E_SETTINGS} <b>НАСТРОЙКИ</b>\n{SEP}\n\n"
            f"{E_PAY} Ставка за «встал»: <b>{get_rate():.2f} USDT</b>\n"
            f"{E_REFS} Рефка за токен: <b>{get_ref_bonus():.2f} USDT</b>\n"
            f"{E_BALANCE} Мин. вывод: <b>{get_min_withdraw():.2f} USDT</b>\n\n"
            "Выбери, что изменить 👇"
        )
        await safe_edit(cb, text, kb.as_markup())
    except Exception:
        log.exception("cb_a_settings")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.callback_query(F.data == "set_rate")
async def cb_set_rate(cb: CallbackQuery, state: FSMContext):
    try:
        if not is_admin(cb.from_user.id): return
        await state.set_state(AdminFSM.rate)
        await safe_edit(cb,
            f"{E_PAY} <b>ИЗМЕНЕНИЕ СТАВКИ</b>\n\n"
            f"Текущая: <b>{get_rate():.2f} USDT</b>\n\n"
            "Отправь новое значение (0.01 – 100):",
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("a_settings")]]))
    except Exception:
        log.exception("cb_set_rate")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.message(AdminFSM.rate, F.text)
async def msg_set_rate(m: Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id): return
        try:
            v = round(float(m.text.replace(",", ".").strip()), 2)
        except ValueError:
            await m.answer(f"{E_DEAD} Введи число")
            return
        if not (0.01 <= v <= 100):
            await m.answer(f"{E_DEAD} 0.01 – 100")
            return
        set_setting("rate_per_token", v)
        await state.clear()
        await m.answer(f"{E_STUCK} Ставка: <b>{v:.2f} USDT</b>", parse_mode="HTML")
    except Exception:
        log.exception("msg_set_rate")


@router.callback_query(F.data == "set_ref")
async def cb_set_ref(cb: CallbackQuery, state: FSMContext):
    try:
        if not is_admin(cb.from_user.id): return
        await state.set_state(AdminFSM.ref_bonus)
        await safe_edit(cb,
            f"{E_REFS} <b>ИЗМЕНЕНИЕ РЕФКИ</b>\n\n"
            f"Текущая: <b>{get_ref_bonus():.2f} USDT</b>\n\n"
            "Отправь новое значение (0 – 100):",
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("a_settings")]]))
    except Exception:
        log.exception("cb_set_ref")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.message(AdminFSM.ref_bonus, F.text)
async def msg_set_ref(m: Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id): return
        try:
            v = round(float(m.text.replace(",", ".").strip()), 2)
        except ValueError:
            await m.answer(f"{E_DEAD} Введи число")
            return
        if not (0 <= v <= 100):
            await m.answer(f"{E_DEAD} 0 – 100")
            return
        set_setting("ref_bonus", v)
        await state.clear()
        await m.answer(f"{E_STUCK} Рефка: <b>{v:.2f} USDT</b>", parse_mode="HTML")
    except Exception:
        log.exception("msg_set_ref")


@router.callback_query(F.data == "set_min")
async def cb_set_min(cb: CallbackQuery, state: FSMContext):
    try:
        if not is_admin(cb.from_user.id): return
        await state.set_state(AdminFSM.min_withdraw)
        await safe_edit(cb,
            f"{E_BALANCE} <b>МИН. ВЫВОД</b>\n\n"
            f"Текущий: <b>{get_min_withdraw():.2f} USDT</b>\n\n"
            "Отправь новое значение:",
            InlineKeyboardMarkup(inline_keyboard=[[back_btn("a_settings")]]))
    except Exception:
        log.exception("cb_set_min")
    finally:
        try: await cb.answer()
        except Exception: pass


@router.message(AdminFSM.min_withdraw, F.text)
async def msg_set_min(m: Message, state: FSMContext):
    try:
        if not is_admin(m.from_user.id): return
        try:
            v = round(float(m.text.replace(",", ".").strip()), 2)
        except ValueError:
            await m.answer(f"{E_DEAD} Введи число")
            return
        if not (0.01 <= v <= 10000):
            await m.answer(f"{E_DEAD} 0.01 – 10000")
            return
        set_setting("min_withdraw", v)
        await state.clear()
        await m.answer(f"{E_STUCK} Мин. вывод: <b>{v:.2f} USDT</b>", parse_mode="HTML")
    except Exception:
        log.exception("msg_set_min")


# ═══════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════

async def main():
    init_db()
    if _xrocket:
        log.info("xRocket OK")
    else:
        log.warning("xRocket НЕ настроен")
    print("HOLIRY SKUP запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
