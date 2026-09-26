import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

# ──────────────────────────────────────────────────────────────────────────
# НАСТРОЙКИ
# ──────────────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8651956926:AAG3ML1uGBPQOgrM5WAMl3kXaRLvVxTHCsw")
PARTNERSHIP_CONTACT = "@FAWT_TG_QAS_FO"  # контакт для сотрудничества, поддержки и оплаты

logging.basicConfig(level=logging.INFO)
router = Router()

# ──────────────────────────────────────────────────────────────────────────
# "БАЗА ДАННЫХ" (in-memory заглушка — на проде замените на реальную БД)
# ──────────────────────────────────────────────────────────────────────────

users_db: dict[int, dict] = {}


def get_user(user_id: int) -> dict:
    return users_db.setdefault(
        user_id, {"balance": 0.0, "purchases": 0, "total_spent": 0.0}
    )


# ──────────────────────────────────────────────────────────────────────────
# ТОВАР: РОССИЯ (аккаунты +7)
# ──────────────────────────────────────────────────────────────────────────

RUSSIA_STOCK = 145
RUSSIA_BASE_PRICE = 1.25
# (порог кол-ва, цена за штуку) — от большего порога к меньшему
RUSSIA_PRICE_TIERS = [
    (200, 0.95),
    (110, 1.00),
    (75, 1.15),
    (25, 1.20),
    (0, RUSSIA_BASE_PRICE),
]


def russia_price_per_unit(quantity: int) -> float:
    for threshold, price in RUSSIA_PRICE_TIERS:
        if quantity >= threshold:
            return price
    return RUSSIA_BASE_PRICE


class PurchaseFSM(StatesGroup):
    entering_quantity = State()


class PromoFSM(StatesGroup):
    entering_code = State()


# ──────────────────────────────────────────────────────────────────────────
# КАСТОМНЫЕ ЭМОДЗИ (Telegram Premium custom emoji)
# Работают только в ТЕКСТЕ сообщений (HTML), Bot API не позволяет
# использовать их на inline-кнопках — там всегда обычный юникод-эмодзи.
# icon_custom_emoji_id на кнопках работает только если у владельца бота
# есть Telegram Premium (либо куплен доп. юзернейм на Fragment).
# ──────────────────────────────────────────────────────────────────────────

EMOJI_WAVE = '<tg-emoji emoji-id="5413694143601842851">👋</tg-emoji>'
EMOJI_ROBOT = '<tg-emoji emoji-id="5287684458881756303">🤖</tg-emoji>'
EMOJI_SHOP = '<tg-emoji emoji-id="5920332557466997677">🏪</tg-emoji>'
EMOJI_PROFILE = '<tg-emoji emoji-id="5262690351969215936">📃</tg-emoji>'
EMOJI_SUPPORT = '<tg-emoji emoji-id="5447644880824181073">⚠️</tg-emoji>'
EMOJI_RULES = '<tg-emoji emoji-id="5397797168264260168">📜</tg-emoji>'
EMOJI_PLANE = '<tg-emoji emoji-id="5208888662451835014">✈️</tg-emoji>'
EMOJI_BOX = '<tg-emoji emoji-id="5258134813302332906">📦</tg-emoji>'
EMOJI_MONEY = '<tg-emoji emoji-id="5409048419211682843">💵</tg-emoji>'
EMOJI_BAG = '<tg-emoji emoji-id="5377660214096974712">🛍</tg-emoji>'
EMOJI_STAR = '<tg-emoji emoji-id="5438496463044752972">⭐️</tg-emoji>'
EMOJI_WALLET = '<tg-emoji emoji-id="5769126056262898415">👛</tg-emoji>'
EMOJI_CROSS = '<tg-emoji emoji-id="5210952531676504517">❌</tg-emoji>'
EMOJI_SMILE = '<tg-emoji emoji-id="6039496266180726678">🙂</tg-emoji>'
EMOJI_WHOLESALE_STAR = '<tg-emoji emoji-id="6034923938486684992">⭐️</tg-emoji>'
EMOJI_BACK = '<tg-emoji emoji-id="6039539366177541657">⬅️</tg-emoji>'
EMOJI_NUM1 = '<tg-emoji emoji-id="5830126888357468979">1️⃣</tg-emoji>'
EMOJI_NUM2 = '<tg-emoji emoji-id="5830254543375441108">2️⃣</tg-emoji>'
EMOJI_NUM3 = '<tg-emoji emoji-id="5827786453303696733">3️⃣</tg-emoji>'
EMOJI_NUM4 = '<tg-emoji emoji-id="5830434773088083875">4️⃣</tg-emoji>'
EMOJI_NUM5 = '<tg-emoji emoji-id="5827941630472100575">5️⃣</tg-emoji>'

# ──────────────────────────────────────────────────────────────────────────
# ТЕКСТЫ
# ──────────────────────────────────────────────────────────────────────────

def welcome_text(username: str) -> str:
    return (
        f"{EMOJI_WAVE} <b>Добро пожаловать в FETORYTO Shop</b> — {{name}}!\n\n"
        f"{EMOJI_ROBOT} <i>Автоматизированный бот по выдаче Telegram-аккаунтов.</i>\n\n"
        "<b>Выберите действие 👇</b>"
    ).format(name=username)


RULES_TEXT = (
    f"{EMOJI_RULES} <b>Правила магазина FETORYTO Shop</b>\n\n"
    f"{EMOJI_NUM1} <i>Оплата производится только через встроенный магазин.</i>\n\n"
    f"{EMOJI_NUM2} <i>После покупки аккаунт выдаётся автоматически.</i>\n\n"
    f"{EMOJI_NUM3} <i>Возврат средств возможен только по решению поддержки.</i>\n\n"
    f"{EMOJI_NUM4} <i>Перепродажа полученных аккаунтов — на ваш страх и риск.</i>\n\n"
    f"{EMOJI_NUM5} <i>Администрация не несёт ответственности за действия третьих лиц "
    "после выдачи товара.</i>"
)

SUPPORT_TEXT = (
    f"{EMOJI_SUPPORT} <b>Поддержка</b>\n\n"
    "Если у вас возникли вопросы или проблемы с заказом — "
    f"напишите нашему оператору: {PARTNERSHIP_CONTACT}"
)


def shop_text() -> str:
    return (
        f"{EMOJI_SHOP} <b>Магазин FETORYTO</b>\n\n"
        "🇷🇺 <b>РОССИЯ</b>\n\n"
        f"{EMOJI_PLANE} <i>Чистые аккаунты с российским номером (+7).\n"
        "Идеально подходят для рассылки и других целей.</i>\n\n"
        f"{EMOJI_BOX} В наличии: {RUSSIA_STOCK} шт.\n"
        f"{EMOJI_MONEY} Цена: ${RUSSIA_BASE_PRICE:.2f}/шт\n\n"
        f"{EMOJI_WHOLESALE_STAR} <b>Оптовые цены:</b>\n"
        "<i>• от 25 шт. — $1.20/шт\n"
        "• от 75 шт. — $1.15/шт\n"
        "• от 110 шт. — $1.00/шт\n"
        "• от 200 шт. — $0.95/шт</i>\n\n"
        f"<b>ИНДИВИДУАЛЬНОЕ СОТРУДНИЧЕСТВО {PARTNERSHIP_CONTACT}</b>\n\n"
        "<b>Выберите количество</b> 👇"
    )


def purchase_confirm_text(quantity: int, price_per_unit: float, balance: float) -> str:
    total = quantity * price_per_unit
    lines = [
        f"{EMOJI_BAG} <b>Покупка {quantity} шт. [ РОССИЯ ]</b>\n",
        f"{EMOJI_MONEY} Цена: ${price_per_unit:.2f}/шт",
        f"{EMOJI_STAR} Сумма: ${total:.2f}",
        f"{EMOJI_WALLET} Ваш баланс: ${balance:.2f}",
    ]
    if balance < total:
        lines.append(f"\n{EMOJI_CROSS} Недостаточно средств")
    return "\n".join(lines)


def profile_text(user_id: int) -> str:
    user = get_user(user_id)
    return (
        f"{EMOJI_PROFILE} <b>Профиль</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"{EMOJI_WALLET} Баланс: ${user['balance']:.2f}\n"
        f"{EMOJI_BAG} Покупок: {user['purchases']}\n"
        f"{EMOJI_STAR} Всего потрачено: ${user['total_spent']:.2f}"
    )


# ──────────────────────────────────────────────────────────────────────────
# КЛАВИАТУРЫ
# ──────────────────────────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="МАГАЗИН",
                    callback_data="menu_shop",
                    icon_custom_emoji_id="5208888662451835014",
                )
            ],
            [
                InlineKeyboardButton(
                    text="ПРОФИЛЬ",
                    callback_data="menu_profile",
                    icon_custom_emoji_id="5323442290708985472",
                ),
                InlineKeyboardButton(
                    text="ПОДДЕРЖКА",
                    callback_data="menu_support",
                    icon_custom_emoji_id="5420323339723881652",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="ПРАВИЛА",
                    callback_data="menu_rules",
                    icon_custom_emoji_id="6050643982646513651",
                )
            ],
        ]
    )


def reply_menu_kb() -> ReplyKeyboardMarkup:
    # style="primary" — синий цвет кнопок реплай-клавиатуры.
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="Меню",
                    style="primary",
                    icon_custom_emoji_id="5249231689695115145",
                ),
                KeyboardButton(
                    text="Сотрудничество",
                    style="primary",
                    icon_custom_emoji_id="5258501105293205250",
                ),
            ]
        ],
        resize_keyboard=True,
    )


def back_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text="Назад",
        callback_data="menu_back",
        icon_custom_emoji_id="6039539366177541657",
    )


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[back_button()]])


def shop_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Ввести количество",
                    callback_data="shop_enter_qty",
                    icon_custom_emoji_id="5197269100878907942",
                )
            ],
            [back_button()],
        ]
    )


def purchase_kb(enough_balance: bool) -> InlineKeyboardMarkup:
    cancel_button = InlineKeyboardButton(
        text="ОТМЕНА",
        callback_data="purchase_cancel",
        icon_custom_emoji_id="5210952531676504517",
    )
    if enough_balance:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить", callback_data="purchase_confirm")],
                [cancel_button],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ПОПОЛНИТЬ БАЛАНС",
                    callback_data="profile_topup",
                    icon_custom_emoji_id="5879814368572478751",
                )
            ],
            [cancel_button],
        ]
    )


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ПОПОЛНИТЬ",
                    callback_data="profile_topup",
                    icon_custom_emoji_id="5879814368572478751",
                ),
                InlineKeyboardButton(
                    text="ВВЕСТИ ПРОМОКОД",
                    callback_data="profile_promo",
                    icon_custom_emoji_id="6037175527846975726",
                ),
            ],
            [back_button()],
        ]
    )


# ──────────────────────────────────────────────────────────────────────────
# ХЕНДЛЕРЫ: старт / реплай-меню
# ──────────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    get_user(message.from_user.id)
    username = message.from_user.full_name or message.from_user.username or "Гость"
    await message.answer(EMOJI_WAVE, reply_markup=reply_menu_kb())
    await message.answer(welcome_text(username), reply_markup=main_menu_kb())


@router.message(F.text == "Меню")
async def on_reply_menu(message: Message) -> None:
    username = message.from_user.full_name or message.from_user.username or "Гость"
    await message.answer(welcome_text(username), reply_markup=main_menu_kb())


@router.message(F.text == "Сотрудничество")
async def on_partnership(message: Message) -> None:
    await message.answer(
        f"<i>Для прямого сотрудничества обращайтесь: {PARTNERSHIP_CONTACT}</i>"
    )


# ──────────────────────────────────────────────────────────────────────────
# ХЕНДЛЕРЫ: главное inline-меню
# ──────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_shop")
async def on_shop(callback: CallbackQuery) -> None:
    await callback.message.edit_text(shop_text(), reply_markup=shop_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_profile")
async def on_profile(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        profile_text(callback.from_user.id), reply_markup=profile_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_support")
async def on_support(callback: CallbackQuery) -> None:
    await callback.message.edit_text(SUPPORT_TEXT, reply_markup=back_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_rules")
async def on_rules(callback: CallbackQuery) -> None:
    await callback.message.edit_text(RULES_TEXT, reply_markup=back_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_back")
async def on_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    username = callback.from_user.full_name or callback.from_user.username or "Гость"
    await callback.message.edit_text(welcome_text(username), reply_markup=main_menu_kb())
    await callback.answer()


# ──────────────────────────────────────────────────────────────────────────
# ХЕНДЛЕРЫ: покупка (ввод количества → подтверждение)
# ──────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "shop_enter_qty")
async def on_shop_enter_qty(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PurchaseFSM.entering_quantity)
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="5197269100878907942">✍️</tg-emoji> <i>Введите количество (от 1 до {RUSSIA_STOCK} шт.):</i>',
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="ОТМЕНА",
                    callback_data="purchase_cancel",
                    icon_custom_emoji_id="5210952531676504517",
                )
            ]]
        ),
    )
    await callback.answer()


@router.message(StateFilter(PurchaseFSM.entering_quantity))
async def on_quantity_entered(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if not raw.isdigit() or not (1 <= int(raw) <= RUSSIA_STOCK):
        await message.answer(f"⚠️ Введите число от 1 до {RUSSIA_STOCK}.")
        return

    quantity = int(raw)
    price = russia_price_per_unit(quantity)
    balance = get_user(message.from_user.id)["balance"]
    enough = balance >= quantity * price

    await state.update_data(quantity=quantity, price=price)
    await message.answer(
        purchase_confirm_text(quantity, price, balance),
        reply_markup=purchase_kb(enough),
    )
    if not enough:
        await state.clear()


@router.callback_query(F.data == "purchase_cancel")
async def on_purchase_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(shop_text(), reply_markup=shop_kb())
    await callback.answer("Отменено")


@router.callback_query(F.data == "purchase_confirm")
async def on_purchase_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    quantity = data.get("quantity")
    price = data.get("price")
    if not quantity or not price:
        await callback.answer("Сессия покупки истекла, начните заново.", show_alert=True)
        await state.clear()
        return

    user = get_user(callback.from_user.id)
    total = quantity * price
    if user["balance"] < total:
        await callback.answer("Недостаточно средств", show_alert=True)
        return

    user["balance"] -= total
    user["purchases"] += 1
    user["total_spent"] += total
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Покупка успешна!</b>\n\n"
        f"Товар: РОССИЯ, {quantity} шт.\n"
        f"Списано: ${total:.2f}\n"
        f"Остаток баланса: ${user['balance']:.2f}\n\n"
        "Аккаунты будут высланы в ближайшее время.",
        reply_markup=back_kb(),
    )
    await callback.answer()


# ──────────────────────────────────────────────────────────────────────────
# ХЕНДЛЕРЫ: профиль (пополнение / промокод)
# ──────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile_topup")
async def on_profile_topup(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "💵 <b>Пополнение баланса</b>\n\n"
        f"Раздел оплаты в разработке. Для пополнения обратитесь: {PARTNERSHIP_CONTACT}",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "profile_promo")
async def on_profile_promo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromoFSM.entering_code)
    await callback.message.edit_text(
        "🎁 Введите промокод:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="ОТМЕНА",
                    callback_data="menu_profile",
                    icon_custom_emoji_id="5210952531676504517",
                )
            ]]
        ),
    )
    await callback.answer()


@router.message(StateFilter(PromoFSM.entering_code))
async def on_promo_entered(message: Message, state: FSMContext) -> None:
    await state.clear()
    # Заглушка: реальная проверка промокодов подключается здесь.
    await message.answer(
        "❌ Промокод не найден или уже использован.",
        reply_markup=profile_kb(),
    )


# ──────────────────────────────────────────────────────────────────────────
# ЗАПУСК
# ──────────────────────────────────────────────────────────────────────────

async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
