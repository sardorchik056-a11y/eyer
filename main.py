import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ──────────────────────────────────────────────────────────────────────────
# НАСТРОЙКИ
# ──────────────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬТЕ_СЮДА_ТОКЕН_БОТА")

logging.basicConfig(level=logging.INFO)
router = Router()

# ──────────────────────────────────────────────────────────────────────────
# КАСТОМНЫЕ ЭМОДЗИ (Telegram Premium custom emoji)
# Работают только в ТЕКСТЕ сообщений (HTML), Bot API не позволяет
# использовать их на inline-кнопках — там всегда обычный юникод-эмодзи.
# ──────────────────────────────────────────────────────────────────────────

EMOJI_SHOP = '<tg-emoji emoji-id="5920332557466997677">🏪</tg-emoji>'
EMOJI_PROFILE = '<tg-emoji emoji-id="5262690351969215936">📃</tg-emoji>'
EMOJI_SUPPORT = '<tg-emoji emoji-id="5447644880824181073">⚠️</tg-emoji>'
EMOJI_RULES = '<tg-emoji emoji-id="5397797168264260168">📜</tg-emoji>'

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
    f"{EMOJI_RULES} <b>Правила магазина FETORYTO Shop</b>\n\n"
    "1. Оплата производится только через встроенный магазин.\n"
    "2. После покупки аккаунт выдаётся автоматически.\n"
    "3. Возврат средств возможен только по решению поддержки.\n"
    "4. Перепродажа полученных аккаунтов — на ваш страх и риск.\n"
    "5. Администрация не несёт ответственности за действия третьих лиц "
    "после выдачи товара."
)

SUPPORT_TEXT = (
    f"{EMOJI_SUPPORT} <b>Поддержка</b>\n\n"
    "Если у вас возникли вопросы или проблемы с заказом — "
    "напишите нашему оператору: @your_support_username"
)

SHOP_TEXT = (
    f"{EMOJI_SHOP} <b>Магазин FETORYTO</b>\n\n"
    "Здесь скоро появится каталог доступных Telegram-аккаунтов.\n"
    "Раздел находится в разработке."
)


def profile_text(user_id: int, username: str) -> str:
    return (
        f"{EMOJI_PROFILE} <b>Ваш профиль</b>\n\n"
        f"👤 Ник: {username}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: 0 ₽\n"
        f"📦 Куплено аккаунтов: 0"
    )


# ──────────────────────────────────────────────────────────────────────────
# КЛАВИАТУРЫ
# ──────────────────────────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    # icon_custom_emoji_id рисует кастомный эмодзи ПЕРЕД текстом кнопки.
    # Требование Telegram Bot API: работает только если у владельца бота
    # есть Telegram Premium (либо у бота куплен доп. юзернейм на Fragment).
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="МАГАЗИН",
                    callback_data="menu_shop",
                    icon_custom_emoji_id="5920332557466997677",
                )
            ],
            [
                InlineKeyboardButton(
                    text="ПРОФИЛЬ",
                    callback_data="menu_profile",
                    icon_custom_emoji_id="5262690351969215936",
                ),
                InlineKeyboardButton(
                    text="ПОДДЕРЖКА",
                    callback_data="menu_support",
                    icon_custom_emoji_id="5447644880824181073",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="ПРАВИЛА",
                    callback_data="menu_rules",
                    icon_custom_emoji_id="5397797168264260168",
                )
            ],
        ]
    )


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ]
    )


# ──────────────────────────────────────────────────────────────────────────
# ХЕНДЛЕРЫ
# ──────────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    username = message.from_user.full_name or message.from_user.username or "Гость"
    await message.answer(welcome_text(username), reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu_shop")
async def on_shop(callback: CallbackQuery) -> None:
    await callback.message.edit_text(SHOP_TEXT, reply_markup=back_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_profile")
async def on_profile(callback: CallbackQuery) -> None:
    username = callback.from_user.username or callback.from_user.full_name
    await callback.message.edit_text(
        profile_text(callback.from_user.id, username), reply_markup=back_kb()
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
async def on_back(callback: CallbackQuery) -> None:
    username = callback.from_user.full_name or callback.from_user.username or "Гость"
    await callback.message.edit_text(welcome_text(username), reply_markup=main_menu_kb())
    await callback.answer()


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
