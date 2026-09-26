import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

# ──────────────────────────────────────────────────────────────────────────
# НАСТРОЙКИ
# ──────────────────────────────────────────────────────────────────────────

BOT_TOKEN = "ВСТАВЬТЕ_СЮДА_ТОКЕН_БОТА"

logging.basicConfig(level=logging.INFO)
router = Router()

# ──────────────────────────────────────────────────────────────────────────
# ТЕКСТЫ
# ──────────────────────────────────────────────────────────────────────────

def welcome_text(username: str) -> str:
    return (
        "🎁 <b>Добро пожаловать в FETORYTO Shop</b> — {name}!\n\n"
        "🤖 Автоматизированный бот по выдаче Telegram-аккаунтов.\n\n"
        "Выберите действие 👇"
    ).format(name=username)


RULES_TEXT = (
    "🖥 <b>Правила магазина FETORYTO Shop</b>\n\n"
    "1. Оплата производится только через встроенный магазин.\n"
    "2. После покупки аккаунт выдаётся автоматически.\n"
    "3. Возврат средств возможен только по решению поддержки.\n"
    "4. Перепродажа полученных аккаунтов — на ваш страх и риск.\n"
    "5. Администрация не несёт ответственности за действия третьих лиц "
    "после выдачи товара."
)

SUPPORT_TEXT = (
    "🚀 <b>Поддержка</b>\n\n"
    "Если у вас возникли вопросы или проблемы с заказом — "
    "напишите нашему оператору: @your_support_username"
)

SHOP_TEXT = (
    "👉 <b>Магазин FETORYTO</b>\n\n"
    "Здесь скоро появится каталог доступных Telegram-аккаунтов.\n"
    "Раздел находится в разработке."
)


def profile_text(user_id: int, username: str) -> str:
    return (
        "⌛ <b>Ваш профиль</b>\n\n"
        f"👤 Ник: {username}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: 0 ₽\n"
        f"📦 Куплено аккаунтов: 0"
    )


# ──────────────────────────────────────────────────────────────────────────
# КЛАВИАТУРА
# ──────────────────────────────────────────────────────────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👉МАГАЗИН")],
            [KeyboardButton(text="⌛ПРОФИЛЬ"), KeyboardButton(text="🚀ПОДДЕРЖКА")],
            [KeyboardButton(text="🖥ПРАВИЛА")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие в меню…",
    )


# ──────────────────────────────────────────────────────────────────────────
# ХЕНДЛЕРЫ
# ──────────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    username = message.from_user.full_name or message.from_user.username or "Гость"
    await message.answer(welcome_text(username), reply_markup=main_menu_kb())


@router.message(F.text == "👉МАГАЗИН")
async def on_shop(message: Message) -> None:
    await message.answer(SHOP_TEXT)


@router.message(F.text == "⌛ПРОФИЛЬ")
async def on_profile(message: Message) -> None:
    username = message.from_user.username or message.from_user.full_name
    await message.answer(profile_text(message.from_user.id, username))


@router.message(F.text == "🚀ПОДДЕРЖКА")
async def on_support(message: Message) -> None:
    await message.answer(SUPPORT_TEXT)


@router.message(F.text == "🖥ПРАВИЛА")
async def on_rules(message: Message) -> None:
    await message.answer(RULES_TEXT)


# ──────────────────────────────────────────────────────────────────────────
# ЗАПУСК
# ──────────────────────────────────────────────────────────────────────────

async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
