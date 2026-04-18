import telebot
from telebot import types
import json
import os
import requests
from datetime import datetime
import threading
import time

# ─── Конфиг ─────────────────────────────────────────────────────
BOT_TOKEN      = "8320997126:AAHyPYlfMWOOgYrTNPZMfF0GOrE_hh7gtcM"
CRYPTO_TOKEN   = "562214:AABJIaVpSkcIR7FvY7B8Oh3TszuqCUgi0Tk"
ADMIN_ID       = 8115654734
CRYPTO_BOT_URL = "https://pay.crypt.bot/api"

bot = telebot.TeleBot(BOT_TOKEN)

# ─── Custom Emoji IDs ────────────────────────────────────────────
EMOJI_AUTOREG  = "5258108352008823107"
EMOJI_LIVE     = "5260399854500191689"
EMOJI_JSON     = "5258185631355378853"
EMOJI_STREAM2  = "6030776052345737530"
EMOJI_TOPUP    = "5258204546391351475"
EMOJI_ORDERS   = "6039496266180726678"
EMOJI_INSTRUCT = "6030776052345737530"
EMOJI_RULES    = "5258185631355378853"
EMOJI_REF      = "5258513401784573443"
EMOJI_BACK     = "6039539366177541657"
EMOJI_PAY      = "5258204546391351475"
EMOJI_CHECK    = "6030776052345737530"
EMOJI_CONFIRM  = "5258215846450305872"
EMOJI_CANCEL   = "6039539366177541657"
EMOJI_MANUAL   = "6030776052345737530"

# ─── Crypto Bot API ─────────────────────────────────────────────
class CryptoPayAPI:
    def __init__(self, token, base_url):
        self.base_url = base_url.rstrip("/")
        self.headers  = {"Crypto-Pay-API-Token": token}

    def _get(self, method, **params):
        r    = requests.get(f"{self.base_url}/{method}",
                            headers=self.headers, params=params, timeout=10)
        data = r.json()
        if not data.get("ok"):
            raise Exception(data.get("error", {}).get("name", "API error"))
        return data["result"]

    def get_me(self):
        return self._get("getMe")

    def create_invoice(self, asset, amount, description="", payload="", expires_in=1800):
        return self._get("createInvoice",
                         asset=asset, amount=f"{amount:.2f}",
                         description=description[:1024],
                         payload=payload[:4096],
                         expires_in=expires_in)

    def check_invoice(self, invoice_id):
        items = self._get("getInvoices", invoice_ids=str(invoice_id), count=1).get("items", [])
        return items[0] if items else None

crypto = CryptoPayAPI(CRYPTO_TOKEN, CRYPTO_BOT_URL)

# ─── Товары (дефолтные) ─────────────────────────────────────────
DEFAULT_PRODUCTS = {
    "autoreg": {"name": "Авторег без 2FA",        "price": 4.0,  "stock": 136, "desc": "Авторег аккаунты без 2FA, фарм 7+ дней"},
    "live":    {"name": "Живые аккаунты",          "price": 4.5,  "stock": 256, "desc": "Живые аккаунты с историей 30+ дней"},
    "json":    {"name": "Код Android (эмулятор)", "price": 3.5,  "stock": 125, "desc": "JSON-файлы для LDPlayer, BlueStacks, MeMu"},
    "stream2": {"name": "Живые | Поток 2",         "price": 7.5,  "stock": 0,   "desc": "Премиум живые аккаунты второго потока"},
}

MIN_ORDER_QTY = 30   # минимальное количество штук
ASSET         = "USDT"

# ─── БД ─────────────────────────────────────────────────────────
DB_FILE        = "users_db.json"
INVOICES_FILE  = "invoices_db.json"
PRODUCTS_FILE  = "products_db.json"

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_products():
    """Загружает товары из файла или возвращает дефолтные."""
    db = load_json(PRODUCTS_FILE)
    if not db:
        save_json(PRODUCTS_FILE, DEFAULT_PRODUCTS)
        return DEFAULT_PRODUCTS
    return db

def save_products(data):
    save_json(PRODUCTS_FILE, data)

def get_user(uid):
    db  = load_json(DB_FILE)
    key = str(uid)
    if key not in db:
        db[key] = {"balance": 0.0, "orders": [], "ref": None, "ref_count": 0, "ref_earned": 0.0}
        save_json(DB_FILE, db)
    return db[key]

def save_user(uid, data):
    db = load_json(DB_FILE)
    db[str(uid)] = data
    save_json(DB_FILE, db)

def save_invoice(inv_id, meta):
    db = load_json(INVOICES_FILE)
    db[str(inv_id)] = meta
    save_json(INVOICES_FILE, db)

def get_inv_meta(inv_id):
    return load_json(INVOICES_FILE).get(str(inv_id))

def btn(text, cb=None, url=None, emoji_id=None):
    kwargs = {}
    if cb:       kwargs["callback_data"]        = cb
    if url:      kwargs["url"]                  = url
    if emoji_id: kwargs["icon_custom_emoji_id"] = emoji_id
    return types.InlineKeyboardButton(text=text, **kwargs)

# ─── Состояния админа ────────────────────────────────────────────
admin_states = {}   # uid -> {"action": ..., "key": ...}

# ─── Клавиатуры ─────────────────────────────────────────────────
def main_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(
        btn("Авторег без 2FA  •  4$",   cb="buy_autoreg",  emoji_id=EMOJI_AUTOREG),
        btn("Живые аккаунты  •  4.5$",    cb="buy_live",     emoji_id=EMOJI_LIVE),
    )
    kb.row(
        btn("Код Android  •  3.5$",    cb="buy_json",     emoji_id=EMOJI_JSON),
        btn("Живые | Поток 2  •  7.5$", cb="buy_stream2",  emoji_id=EMOJI_STREAM2),
    )
    kb.row(
        btn("Пополнить баланс",         cb="topup",        emoji_id=EMOJI_TOPUP),
        btn("Мои заказы",               cb="my_orders",    emoji_id=EMOJI_ORDERS),
    )
    kb.row(
        btn("Инструкция",               cb="instruction",  emoji_id=EMOJI_INSTRUCT),
        btn("Правила",                  cb="rules",        emoji_id=EMOJI_RULES),
    )
    kb.row(
        btn("Реферальная программа",    cb="referral",     emoji_id=EMOJI_REF),
    )
    return kb

def back_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(btn("Назад в меню", cb="main_menu", emoji_id=EMOJI_BACK))
    return kb

def admin_kb():
    """Главное меню админ-панели."""
    PRODUCTS = get_products()
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, p in PRODUCTS.items():
        stock_str = f"{p['stock']} шт" if p['stock'] > 0 else "❌ нет"
        kb.add(btn(
            f"✏️ {p['name']}  •  ${p['price']:.2f}  •  {stock_str}",
            cb=f"admin_edit_{key}"
        ))
    kb.add(btn("📊 Статистика",    cb="admin_stats"))
    kb.add(btn("📋 Все заказы",    cb="admin_orders"))
    kb.add(btn("👥 Все юзеры",     cb="admin_users"))
    kb.add(btn("🚪 Выйти из панели", cb="admin_exit"))
    return kb

def admin_product_kb(key):
    """Кнопки редактирования конкретного товара."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn("💲 Изменить цену",      cb=f"admin_price_{key}"),
        btn("📦 Изменить остаток",   cb=f"admin_stock_{key}"),
    )
    kb.add(btn("◀️ Назад к панели", cb="admin_main"))
    return kb

def main_text(uid):
    PRODUCTS = get_products()
    u = get_user(uid)
    lines = ""
    for key, p in PRODUCTS.items():
        if p["stock"] > 0:
            lines += f" {p['name']}  — <b>{p['stock']} шт</b>\n"
        else:
            lines += f" {p['name']}  — <b>❌ нет в наличии</b>\n"
    return (
        f"{'─'*28}\n"
        f"💰 Баланс: <b>${u['balance']:.2f}</b>   Заказов: <b>{len(u['orders'])}</b>\n"
        f"{'─'*28}\n\n"
        f"<b>Наличие на складе:</b>\n"
        f"{lines}\n"
        f"👇 Выберите товар или раздел:"
    )

def send_main(uid, cid, mid=None):
    t, k = main_text(uid), main_kb()
    if mid:
        bot.edit_message_text(t, cid, mid, parse_mode="HTML", reply_markup=k)
    else:
        bot.send_message(cid, t, parse_mode="HTML", reply_markup=k)

# ─── Тексты ─────────────────────────────────────────────────────
RULES_TEXT = """<tg-emoji emoji-id="5258185631355378853">🎯</tg-emoji> <b>ПРАВИЛА МАГАЗИНА</b>

<b>1. Общие положения</b>
• Покупая товар, вы соглашаетесь с данными правилами
• Минимальная сумма заказа: <b>$100</b>

<b>2. Цены и товары</b>
• Авторег без 2FA — <b>$4/шт</b> (фарм 7+ дней)
• Живые аккаунты — <b>$4.5/шт</b> (активность 30+ дней)
• JSON Android — <b>$3.5/шт</b> (LDPlayer / BlueStacks / MeMu)
• Живые | Поток 2 — <b>$7.5/шт</b> (премиум)

<b>3. Гарантия и замены</b>
• Гарантия <b>24 часа</b> с момента выдачи
• Замена если аккаунт не работает при первой проверке
• Замена НЕ производится при: изменении данных, нарушении правил платформы, истечении 24ч

<b>4. Оплата</b>
• Только криптовалюта через @CryptoBot: USDT, TON, BTC, ETH
• После создания счёта — <b>30 минут</b> на оплату
• Возврат после выдачи товара — <b>невозможен</b>

<b>5. Запрещено</b>
• Чарджбэк / оспаривание платежей
• Перепродажа без разрешения администрации
• Любые формы мошенничества

....."""

INSTRUCTION_TEXT = """<tg-emoji emoji-id="6030776052345737530">🎯</tg-emoji> <b>ИНСТРУКЦИЯ</b>

<b>Шаг 1.</b> Выберите товар в главном меню

<b>Шаг 2.</b> Укажите количество аккаунтов
— Минимальный заказ: <b>$100</b>

<b>Шаг 3.</b> Нажмите <b>«Оплатить»</b>
— Оплатите в @CryptoBot (USDT / TON / BTC / ETH)
— Оплата фиксируется <b>автоматически</b>

<b>Шаг 4.</b> Аккаунты придут в течение нескольких минут

<b>Форматы выдачи:</b>
Авторег: <code>login:password</code>
Живые: <code>login:password:2fa</code>
Код:  <code>по коду</code> 
Поток 2: <code>login:password:cookies</code>

 Статус — раздел «Мои заказы»
....."""

REFERRAL_TEXT = """<tg-emoji emoji-id="5258513401784573443">🎯</tg-emoji> <b>РЕФЕРАЛЬНАЯ ПРОГРАММА</b>

Приглашайте друзей и получайте <b>5%</b> с каждой их покупки!

<b>Как работает:</b>
1- Скопируйте реферальную ссылку ниже
2- Друг переходит по ссылке и делает покупку
3- Вы получаете 5% на баланс автоматически

Минимум для вывода: <b>$10</b>

"""

# ─── /start ─────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    uid  = msg.from_user.id
    args = msg.text.split()
    if len(args) > 1 and args[1] != str(uid):
        user = get_user(uid)
        if not user["ref"]:
            user["ref"] = args[1]
            save_user(uid, user)
    send_main(uid, msg.chat.id)

# ─── /admin ─────────────────────────────────────────────────────
@bot.message_handler(commands=["admin"])
def cmd_admin(msg):
    uid = msg.from_user.id
    if uid != ADMIN_ID:
        bot.send_message(msg.chat.id, "❌ Нет доступа.")
        return
    bot.send_message(
        msg.chat.id,
        "<b>🔧 АДМИН-ПАНЕЛЬ</b>\n\nВыберите товар для редактирования:",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )

# ─── Callbacks ──────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: True)
def on_cb(call):
    uid  = call.from_user.id
    cid  = call.message.chat.id
    mid  = call.message.message_id
    data = call.data
    bot.answer_callback_query(call.id)

    # ── Админ-панель ────────────────────────────────────────────
    if data == "admin_main":
        if uid != ADMIN_ID: return
        bot.edit_message_text(
            "<b>🔧 АДМИН-ПАНЕЛЬ</b>\n\nВыберите товар для редактирования:",
            cid, mid, parse_mode="HTML", reply_markup=admin_kb()
        )

    elif data == "admin_exit":
        if uid != ADMIN_ID: return
        bot.edit_message_text("✅ Вышли из панели.", cid, mid)

    elif data.startswith("admin_edit_"):
        if uid != ADMIN_ID: return
        key      = data[11:]
        PRODUCTS = get_products()
        p        = PRODUCTS.get(key)
        if not p: return
        bot.edit_message_text(
            f"<b>✏️ Редактирование: {p['name']}</b>\n{'─'*28}\n"
            f"💲 Цена: <b>${p['price']:.2f}/шт</b>\n"
            f"📦 Остаток: <b>{p['stock']} шт</b>\n"
            f"📝 Описание: {p['desc']}",
            cid, mid, parse_mode="HTML", reply_markup=admin_product_kb(key)
        )

    elif data.startswith("admin_price_"):
        if uid != ADMIN_ID: return
        key = data[12:]
        admin_states[uid] = {"action": "set_price", "key": key}
        PRODUCTS = get_products()
        p = PRODUCTS[key]
        m = bot.edit_message_text(
            f"💲 Введите новую цену для <b>{p['name']}</b>\n"
            f"Текущая цена: <b>${p['price']:.2f}</b>\n\nВведите число (например: 5.5):",
            cid, mid, parse_mode="HTML", reply_markup=admin_back_kb()
        )

    elif data.startswith("admin_stock_"):
        if uid != ADMIN_ID: return
        key = data[12:]
        admin_states[uid] = {"action": "set_stock", "key": key}
        PRODUCTS = get_products()
        p = PRODUCTS[key]
        m = bot.edit_message_text(
            f"📦 Введите новый остаток для <b>{p['name']}</b>\n"
            f"Текущий остаток: <b>{p['stock']} шт</b>\n\nВведите число (например: 500):",
            cid, mid, parse_mode="HTML", reply_markup=admin_back_kb()
        )

    elif data == "admin_stats":
        if uid != ADMIN_ID: return
        db       = load_json(DB_FILE)
        inv_db   = load_json(INVOICES_FILE)
        total_users  = len(db)
        paid_orders  = sum(1 for v in inv_db.values() if v.get("status") == "paid" and v.get("type") == "order")
        total_revenue = sum(v.get("total", 0) for v in inv_db.values() if v.get("status") == "paid")
        PRODUCTS = get_products()
        stock_text = "\n".join(
            f"  • {p['name']}: <b>{p['stock']} шт</b>"
            for p in PRODUCTS.values()
        )
        bot.edit_message_text(
            f"<b>📊 СТАТИСТИКА</b>\n{'─'*28}\n"
            f"👥 Пользователей: <b>{total_users}</b>\n"
            f"🛒 Оплаченных заказов: <b>{paid_orders}</b>\n"
            f"💰 Общая выручка: <b>${total_revenue:.2f}</b>\n\n"
            f"<b>Остатки на складе:</b>\n{stock_text}",
            cid, mid, parse_mode="HTML", reply_markup=admin_back_kb()
        )

    elif data == "admin_orders":
        if uid != ADMIN_ID: return
        inv_db = load_json(INVOICES_FILE)
        paid   = [(k, v) for k, v in inv_db.items() if v.get("status") == "paid" and v.get("type") == "order"]
        paid   = sorted(paid, key=lambda x: x[1].get("created", ""), reverse=True)[:15]
        if not paid:
            text = "<b>📋 Заказы</b>\n\nЗаказов пока нет."
        else:
            text = f"<b>📋 ПОСЛЕДНИЕ ЗАКАЗЫ</b>\n{'─'*28}\n\n"
            PRODUCTS = get_products()
            for inv_id, v in paid:
                p_name = PRODUCTS.get(v.get("key", ""), {}).get("name", v.get("key", "?"))
                text += (
                    f"🆔 {v.get('order_id','?')}\n"
                    f"👤 UID: <code>{v.get('uid','?')}</code>\n"
                    f"📋 {p_name} × {v.get('qty',0)} шт\n"
                    f"💰 ${v.get('total',0):.2f}\n"
                    f"{'─'*20}\n"
                )
        bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=admin_back_kb())

    elif data == "admin_users":
        if uid != ADMIN_ID: return
        db = load_json(DB_FILE)
        text = f"<b>👥 ВСЕ ПОЛЬЗОВАТЕЛИ</b>\n{'─'*28}\n\n"
        for u_id, u_data in list(db.items())[-20:]:
            text += (
                f"👤 <code>{u_id}</code>  "
                f"💰${u_data.get('balance', 0):.2f}  "
                f"🛒{len(u_data.get('orders', []))} заказов\n"
            )
        bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=admin_back_kb())

    # ── Обычные кнопки ──────────────────────────────────────────
    elif data == "main_menu":
        send_main(uid, cid, mid)

    elif data.startswith("buy_"):
        key      = data[4:]
        PRODUCTS = get_products()
        p        = PRODUCTS.get(key)
        if not p: return

        if p["stock"] == 0:
            kb = types.InlineKeyboardMarkup()
            kb.add(btn("Назад", cb="main_menu", emoji_id=EMOJI_BACK))
            bot.edit_message_text(
                f"❌ <b>Нет в наличии</b>\n\n{p['name']} — временно недоступен.",
                cid, mid, parse_mode="HTML", reply_markup=kb
            )
            return

        min_qty = MIN_ORDER_QTY
        kb      = types.InlineKeyboardMarkup(row_width=2)
        btns    = []
        for mult in [1, 2, 5, 10]:
            q = min_qty * mult
            if q <= p["stock"]:
                btns.append(btn(f"{q} шт → ${q * p['price']:.0f}",
                                cb=f"order_{key}_{q}", emoji_id=EMOJI_CONFIRM))
        if btns: kb.add(*btns[:4])
        kb.add(btn("Ввести вручную", cb=f"manual_{key}", emoji_id=EMOJI_MANUAL))
        kb.add(btn("Назад",          cb="main_menu",     emoji_id=EMOJI_BACK))

        bot.edit_message_text(
            f"<b>{p['name']}</b>\n{'─'*28}\n"
            f"💲 Цена: <b>${p['price']:.2f}/шт</b>\n"
            f"📦 На складе: <b>{p['stock']} шт</b>\n"
            f"📌 Мин. заказ: <b>{MIN_ORDER_QTY} шт</b>\n\n"
            f"📝 {p['desc']}\n\nВыберите количество:",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif data.startswith("manual_"):
        key      = data[7:]
        PRODUCTS = get_products()
        p        = PRODUCTS[key]
        m = bot.edit_message_text(
            f"✏️ Введите количество аккаунтов:\n\n"
            f"Мин: <b>{MIN_ORDER_QTY} шт</b>\n"
            f"Макс: <b>{p['stock']} шт</b>",
            cid, mid, parse_mode="HTML", reply_markup=back_kb()
        )
        bot.register_next_step_handler(m, step_qty, key, cid)

    elif data.startswith("order_"):
        _, key, qty_s = data.split("_", 2)
        qty      = int(qty_s)
        PRODUCTS = get_products()
        p        = PRODUCTS[key]
        kb       = types.InlineKeyboardMarkup()
        kb.add(
            btn("Создать счёт", cb=f"pay_{key}_{qty}", emoji_id=EMOJI_CONFIRM),
            btn("Отмена",       cb="main_menu",        emoji_id=EMOJI_CANCEL),
        )
        bot.edit_message_text(
            f"<b>✅ ПОДТВЕРЖДЕНИЕ</b>\n{'─'*28}\n"
            f"Товар: <b>{p['name']}</b>\n"
            f"Кол-во: <b>{qty} шт</b>\n"
            f"Цена: <b>${p['price']:.2f}/шт</b>\n{'─'*28}\n"
            f"💰 Итого: <b>${qty * p['price']:.2f} {ASSET}</b>",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif data.startswith("pay_"):
        _, key, qty_s = data.split("_", 2)
        qty      = int(qty_s)
        PRODUCTS = get_products()
        p        = PRODUCTS[key]
        total    = qty * p["price"]
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        bot.edit_message_text("⏳ Создаю счёт...", cid, mid)

        try:
            invoice = crypto.create_invoice(
                asset=ASSET, amount=total,
                description=f"{p['name']} × {qty} шт",
                payload=f"{uid}:{key}:{qty}:{order_id}",
                expires_in=1800,
            )
        except Exception as e:
            bot.edit_message_text(
                f"❌ Ошибка CryptoBot API: <code>{e}</code>\n\nПопробуйте позже.",
                cid, mid, parse_mode="HTML", reply_markup=back_kb()
            )
            return

        inv_id  = invoice["invoice_id"]
        pay_url = invoice["pay_url"]

        save_invoice(inv_id, {
            "uid": str(uid), "key": key, "qty": qty, "total": total,
            "order_id": order_id, "cid": cid, "mid": mid,
            "status": "active", "type": "order",
            "created": datetime.now().isoformat()
        })

        user = get_user(uid)
        user["orders"].append({
            "id": order_id, "invoice_id": inv_id,
            "product": p["name"], "quantity": qty,
            "total": total, "status": "⏳ Ожидает оплаты",
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        })
        save_user(uid, user)

        kb = types.InlineKeyboardMarkup()
        kb.add(btn("Оплатить",          url=pay_url,            emoji_id=EMOJI_PAY))
        kb.add(btn("Проверить оплату",  cb=f"check_{inv_id}",   emoji_id=EMOJI_CHECK))
        kb.add(btn("В меню",            cb="main_menu",         emoji_id=EMOJI_BACK))

        bot.edit_message_text(
            f"<b>🎯 СЧЁТ СОЗДАН</b>\n{'─'*28}\n"
            f"Заказ: <code>{order_id}</code>\n"
            f"{p['name']} × {qty} шт\n"
            f"💰 К оплате: <b>${total:.2f} {ASSET}</b>\n"
            f"🔖 Invoice: <code>{inv_id}</code>\n{'─'*28}\n\n"
            f"⚡ Оплата фиксируется <b>автоматически</b>\n"
            f"⏱ Счёт действителен <b>30 минут</b>",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif data.startswith("check_"):
        inv_id = int(data[6:])
        meta   = get_inv_meta(inv_id)
        if not meta:
            bot.answer_callback_query(call.id, "❌ Инвойс не найден", show_alert=True)
            return
        if meta.get("status") == "paid":
            bot.answer_callback_query(call.id, "✅ Уже оплачен!", show_alert=True)
            return
        bot.answer_callback_query(call.id, "⏳ Проверяю...")
        try:
            inv = crypto.check_invoice(inv_id)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)
            return
        status = inv.get("status") if inv else "not_found"
        if status == "paid":
            _on_paid(inv_id, meta, cid, mid)
        elif status == "expired":
            bot.edit_message_text("❌ <b>Счёт истёк</b>\n\nСоздайте новый заказ.",
                                  cid, mid, parse_mode="HTML", reply_markup=back_kb())
        else:
            bot.answer_callback_query(call.id, "⏳ Оплата ещё не поступила", show_alert=True)

    elif data == "topup":
        kb = types.InlineKeyboardMarkup(row_width=3)
        kb.add(
            btn("$50",   cb="topup_50",   emoji_id=EMOJI_TOPUP),
            btn("$100",  cb="topup_100",  emoji_id=EMOJI_TOPUP),
            btn("$200",  cb="topup_200",  emoji_id=EMOJI_TOPUP),
            btn("$500",  cb="topup_500",  emoji_id=EMOJI_TOPUP),
            btn("$1000", cb="topup_1000", emoji_id=EMOJI_TOPUP),
        )
        kb.add(btn("Другая сумма", cb="topup_custom", emoji_id=EMOJI_MANUAL))
        kb.add(btn("Назад",        cb="main_menu",    emoji_id=EMOJI_BACK))
        bot.edit_message_text(
            f"<b>💳 ПОПОЛНЕНИЕ БАЛАНСА</b>\n{'─'*28}\n"
            f"Оплата в {ASSET} через @CryptoBot\n\nВыберите сумму:",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif data.startswith("topup_"):
        val = data[6:]
        if val == "custom":
            m = bot.edit_message_text("✏️ Введите сумму пополнения (мин. $10):",
                                      cid, mid, reply_markup=back_kb())
            bot.register_next_step_handler(m, step_topup, cid)
        else:
            _create_topup(uid, cid, mid, float(val))

    elif data == "my_orders":
        user   = get_user(uid)
        orders = user["orders"]
        if not orders:
            bot.edit_message_text("<b>📦 Мои заказы</b>\n\nЗаказов пока нет.",
                                  cid, mid, parse_mode="HTML", reply_markup=back_kb())
            return
        text = f"<b>📦 МОИ ЗАКАЗЫ</b>\n{'─'*28}\n\n"
        for o in reversed(orders[-10:]):
            text += (
                f"🆔 <code>{o['id']}</code>\n"
                f"📋 {o['product']}\n"
                f"📦 {o['quantity']} шт  ${o['total']:.2f}\n"
                f"📅 {o['date']}  {o['status']}\n"
                f"{'─'*20}\n"
            )
        bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=back_kb())

    elif data == "instruction":
        bot.edit_message_text(INSTRUCTION_TEXT, cid, mid, parse_mode="HTML", reply_markup=back_kb())

    elif data == "rules":
        bot.edit_message_text(RULES_TEXT, cid, mid, parse_mode="HTML", reply_markup=back_kb())

    elif data == "referral":
        user = get_user(uid)
        link = f"https://t.me/{bot.get_me().username}?start={uid}"
        text = (
            REFERRAL_TEXT +
            f'<tg-emoji emoji-id="5260730055880876557">🎯</tg-emoji> <b>Ваша ссылка:</b>\n<code>{link}</code>\n\n'
            f"{'─'*28}\n"
            f" Приглашено: <b>{user.get('ref_count', 0)} чел.</b>\n"
            f" Заработано: <b>${user.get('ref_earned', 0.0):.2f}</b>"
        )
        bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=back_kb())

# ─── Вспомогательные клавиатуры ─────────────────────────────────
def admin_back_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(btn("◀️ Назад к панели", cb="admin_main"))
    return kb

# ─── Обработка текстовых сообщений от админа ────────────────────
@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and msg.from_user.id in admin_states)
def admin_text_handler(msg):
    uid   = msg.from_user.id
    state = admin_states.get(uid)
    if not state:
        return

    action = state["action"]
    key    = state["key"]
    text   = msg.text.strip()

    PRODUCTS = get_products()
    p        = PRODUCTS.get(key)
    if not p:
        del admin_states[uid]
        return

    if action == "set_price":
        try:
            new_price = float(text.replace(",", "."))
            if new_price <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ Некорректная цена. Введите число > 0 (например: 5.5)")
            return
        old_price         = p["price"]
        PRODUCTS[key]["price"] = new_price
        save_products(PRODUCTS)
        del admin_states[uid]
        bot.send_message(
            uid,
            f"✅ Цена на <b>{p['name']}</b> обновлена!\n"
            f"${old_price:.2f} → <b>${new_price:.2f}</b>",
            parse_mode="HTML",
            reply_markup=admin_kb()
        )

    elif action == "set_stock":
        try:
            new_stock = int(text)
            if new_stock < 0: raise ValueError
        except:
            bot.send_message(uid, "❌ Некорректный остаток. Введите целое число ≥ 0")
            return
        old_stock              = p["stock"]
        PRODUCTS[key]["stock"] = new_stock
        save_products(PRODUCTS)
        del admin_states[uid]
        bot.send_message(
            uid,
            f"✅ Остаток для <b>{p['name']}</b> обновлён!\n"
            f"{old_stock} шт → <b>{new_stock} шт</b>",
            parse_mode="HTML",
            reply_markup=admin_kb()
        )

# ─── Оплата подтверждена ────────────────────────────────────────
def _on_paid(inv_id, meta, cid, mid):
    db = load_json(INVOICES_FILE)
    if db.get(str(inv_id), {}).get("status") == "paid":
        return
    db[str(inv_id)]["status"] = "paid"
    save_json(INVOICES_FILE, db)

    uid      = meta["uid"]
    inv_type = meta.get("type", "order")
    total    = meta["total"]

    if inv_type == "topup":
        user = get_user(uid)
        user["balance"] = round(user["balance"] + total, 2)
        save_user(uid, user)
        text = (
            f"✅ <b>Баланс пополнен!</b>\n{'─'*28}\n"
            f"💰 +${total:.2f} {ASSET}\n"
            f"Ваш баланс: <b>${user['balance']:.2f}</b>"
        )
        if mid:
            try: bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=back_kb())
            except: bot.send_message(cid, text, parse_mode="HTML", reply_markup=back_kb())
        else:
            bot.send_message(cid, text, parse_mode="HTML", reply_markup=back_kb())
        return

    key      = meta["key"]
    qty      = meta["qty"]
    order_id = meta["order_id"]
    PRODUCTS = get_products()
    p        = PRODUCTS.get(key, {})

    user = get_user(uid)
    for o in user["orders"]:
        if o.get("invoice_id") == inv_id:
            o["status"] = "✅ Оплачен"
    save_user(uid, user)

    # Реферальный бонус
    ref_uid = user.get("ref")
    if ref_uid:
        ru    = get_user(ref_uid)
        bonus = round(total * 0.05, 2)
        ru["balance"]    = round(ru["balance"] + bonus, 2)
        ru["ref_earned"] = round(ru.get("ref_earned", 0) + bonus, 2)
        ru["ref_count"]  = ru.get("ref_count", 0) + 1
        save_user(ref_uid, ru)
        try:
            bot.send_message(int(ref_uid),
                f"🎉 Реферальный бонус <b>+${bonus:.2f}</b>!\n"
                f"Баланс: <b>${ru['balance']:.2f}</b>", parse_mode="HTML")
        except: pass

    text = (
        f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА</b>\n{'─'*28}\n"
        f"Заказ: <code>{order_id}</code>\n"
        f"{p.get('name', key)} × {qty} шт\n"
        f"Оплачено: <b>${total:.2f} {ASSET}</b>\n{'─'*28}\n\n"
        f"📦 Аккаунты будут выданы в ближайшее время."
    )
    if mid:
        try: bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=back_kb())
        except: bot.send_message(int(uid), text, parse_mode="HTML", reply_markup=back_kb())
    else:
        bot.send_message(int(uid), text, parse_mode="HTML", reply_markup=back_kb())

    try:
        bot.send_message(ADMIN_ID,
            f"🛒 <b>НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ</b>\n{'─'*28}\n"
            f"👤 UID: <code>{uid}</code>\n"
            f"🆔 {order_id}\n"
            f"📋 {p.get('name', key)} × {qty} шт\n"
            f"💰 ${total:.2f} {ASSET}\n"
            f"🔖 Invoice: <code>{inv_id}</code>", parse_mode="HTML")
    except: pass

# ─── Next step handlers ─────────────────────────────────────────
def step_qty(msg, key, cid):
    uid      = msg.from_user.id
    PRODUCTS = get_products()
    p        = PRODUCTS[key]
    min_qty  = MIN_ORDER_QTY
    try:
        qty = int(msg.text.strip())
        assert min_qty <= qty <= p["stock"]
    except:
        m = bot.send_message(cid,
            f"❌ Введите число от {min_qty} до {p['stock']}:",
            reply_markup=back_kb())
        bot.register_next_step_handler(m, step_qty, key, cid)
        return
    total = qty * p["price"]
    kb = types.InlineKeyboardMarkup()
    kb.add(
        btn("Создать счёт", cb=f"pay_{key}_{qty}", emoji_id=EMOJI_CONFIRM),
        btn("Отмена",       cb="main_menu",        emoji_id=EMOJI_CANCEL),
    )
    bot.send_message(cid,
        f"<b>✅ ПОДТВЕРЖДЕНИЕ</b>\n{'─'*28}\n"
        f"Товар: <b>{p['name']}</b>\n"
        f"Кол-во: <b>{qty} шт</b>\n"
        f"Итого: <b>${total:.2f} {ASSET}</b>",
        parse_mode="HTML", reply_markup=kb)

def step_topup(msg, cid):
    try:
        amount = float(msg.text.strip().replace("$", "").replace(",", "."))
        if amount < 10: raise ValueError
    except:
        m = bot.send_message(cid, "❌ Введите корректную сумму (мин. $10):", reply_markup=back_kb())
        bot.register_next_step_handler(m, step_topup, cid)
        return
    _create_topup(msg.from_user.id, cid, None, amount)

def _create_topup(uid, cid, mid, amount):
    try:
        invoice = crypto.create_invoice(
            asset=ASSET, amount=amount,
            description="Пополнение баланса",
            payload=f"topup:{uid}:{amount}",
            expires_in=1800,
        )
    except Exception as e:
        text = f"❌ Ошибка API: <code>{e}</code>"
        if mid: bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=back_kb())
        else:   bot.send_message(cid, text, parse_mode="HTML", reply_markup=back_kb())
        return

    inv_id  = invoice["invoice_id"]
    pay_url = invoice["pay_url"]

    save_invoice(inv_id, {
        "uid": str(uid), "key": "topup", "qty": 0, "total": amount,
        "order_id": f"TOP-{inv_id}", "cid": cid, "mid": mid,
        "status": "active", "type": "topup",
        "created": datetime.now().isoformat()
    })

    kb = types.InlineKeyboardMarkup()
    kb.add(btn("Оплатить",          url=pay_url,            emoji_id=EMOJI_PAY))
    kb.add(btn("Проверить оплату",  cb=f"check_{inv_id}",   emoji_id=EMOJI_CHECK))
    kb.add(btn("В меню",            cb="main_menu",         emoji_id=EMOJI_BACK))

    text = (
        f"<b>💳 СЧЁТ НА ПОПОЛНЕНИЕ</b>\n{'─'*28}\n"
        f"Сумма: <b>${amount:.2f} {ASSET}</b>\n"
        f"🔖 Invoice: <code>{inv_id}</code>\n{'─'*28}\n\n"
        f"⚡ Оплата фиксируется <b>автоматически</b>\n"
        f"⏱ Счёт действителен <b>30 минут</b>"
    )
    if mid: bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=kb)
    else:   bot.send_message(cid, text, parse_mode="HTML", reply_markup=kb)

# ─── Фоновый поллинг ────────────────────────────────────────────
def poll_loop():
    while True:
        time.sleep(2)
        db = load_json(INVOICES_FILE)
        for inv_id_s, meta in list(db.items()):
            if meta.get("status") != "active":
                continue
            try:
                inv = crypto.check_invoice(int(inv_id_s))
                if inv and inv.get("status") == "paid":
                    cid = int(meta.get("cid", 0))
                    mid = meta.get("mid", 0)
                    _on_paid(int(inv_id_s), meta, cid, mid)
            except:
                pass

# ─── Запуск ─────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        me = crypto.get_me()
        print(f"✅ CryptoBot API: {me.get('name')}")
    except Exception as e:
        print(f"⚠️  CryptoBot: {e}")

    threading.Thread(target=poll_loop, daemon=True).start()
    print("✅ Бот запущен...")
    bot.infinity_polling()
