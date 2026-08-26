import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# =========================
# КЛАВИАТУРА ГЛАВНОГО МЕНЮ
# =========================

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ Кликер",
                    callback_data="clicker"
                ),
                InlineKeyboardButton(
                    text="🛒 Магазин",
                    callback_data="shop"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 Коллекция",
                    callback_data="collection"
                ),
                InlineKeyboardButton(
                    text="👤 Профиль",
                    callback_data="profile"
                )
            ]
        ]
    )


# =========================
# /start
# =========================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "⭐ <b>STAR CLICKER</b>\n\n"
        "Добро пожаловать!\n\n"
        "Здесь тебя ждут ⭐ Stars, коллекционные NFT "
        "и различные бонусы.\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================
# КНОПКА КЛИКЕРА
# =========================

@dp.callback_query(lambda call: call.data == "clicker")
async def clicker(callback: CallbackQuery):
    await callback.message.edit_text(
        "⭐ <b>STAR CLICKER</b>\n\n"
        "Баланс: <b>0 ⭐</b>\n\n"
        "Нажимай кнопку, чтобы получать Stars!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⭐ КЛИК!",
                        callback_data="click"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="back"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# САМИЙ КЛИК
# =========================

@dp.callback_query(lambda call: call.data == "click")
async def click(callback: CallbackQuery):
    await callback.answer("⭐ +1 Star!")


# =========================
# МАГАЗИН
# =========================

@dp.callback_query(lambda call: call.data == "shop")
async def shop(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛒 <b>NFT SHOP</b>\n\n"
        "Здесь будут находиться коллекционные NFT.\n\n"
        "Скоро здесь появятся первые предметы! 💎",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="back"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# КОЛЛЕКЦИЯ
# =========================

@dp.callback_query(lambda call: call.data == "collection")
async def collection(callback: CallbackQuery):
    await callback.message.edit_text(
        "💎 <b>МОЯ КОЛЛЕКЦИЯ</b>\n\n"
        "У тебя пока нет NFT.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 В магазин",
                        callback_data="shop"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="back"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ПРОФИЛЬ
# =========================

@dp.callback_query(lambda call: call.data == "profile")
async def profile(callback: CallbackQuery):
    user = callback.from_user

    await callback.message.edit_text(
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"Игрок: <b>{user.first_name}</b>\n"
        f"ID: <code>{user.id}</code>\n\n"
        f"⭐ Stars: <b>0</b>\n"
        f"💎 NFT: <b>0</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="back"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# НАЗАД
# =========================

@dp.callback_query(lambda call: call.data == "back")
async def back(callback: CallbackQuery):
    await callback.message.edit_text(
        "⭐ <b>STAR CLICKER</b>\n\n"
        "Добро пожаловать!\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ЗАПУСК
# =========================

async def main():
    if not TOKEN:
        raise RuntimeError(
            "Переменная окружения BOT_TOKEN не установлена!"
        )

    print("⭐ Star Clicker запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
