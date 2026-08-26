import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)


TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ==================================================
# ВРЕМЕННЫЕ ДАННЫЕ
# ==================================================

players = {}


def get_player(user_id: int):
    if user_id not in players:
        players[user_id] = {
            "stars": 0,
            "per_click": 1,
            "nfts": [],
        }

    return players[user_id]


# ==================================================
# ГЛАВНОЕ МЕНЮ
# ==================================================

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
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💎 Коллекция",
                    callback_data="collection"
                ),
                InlineKeyboardButton(
                    text="👤 Профиль",
                    callback_data="profile"
                ),
            ],
        ]
    )


# ==================================================
# /START
# ==================================================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "⭐ <b>STAR CLICKER</b>\n\n"
        "Добро пожаловать!\n\n"
        "Кликай, собирай ⭐ Stars и собирай "
        "свою коллекцию NFT! 💎\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


# ==================================================
# КЛИКЕР
# ==================================================

def clicker_menu():
    return InlineKeyboardMarkup(
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
            ],
        ]
    )


@dp.callback_query(lambda call: call.data == "clicker")
async def clicker(callback: CallbackQuery):
    player = get_player(callback.from_user.id)

    await callback.message.edit_text(
        "⭐ <b>STAR CLICKER</b>\n\n"
        f"Баланс: <b>{player['stars']} ⭐</b>\n"
        f"За клик: <b>+{player['per_click']} ⭐</b>\n\n"
        "Нажимай кнопку! 👇",
        reply_markup=clicker_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ==================================================
# КЛИК
# ==================================================

@dp.callback_query(lambda call: call.data == "click")
async def click(callback: CallbackQuery):
    player = get_player(callback.from_user.id)

    player["stars"] += player["per_click"]

    await callback.message.edit_text(
        "⭐ <b>STAR CLICKER</b>\n\n"
        f"Баланс: <b>{player['stars']} ⭐</b>\n"
        f"За клик: <b>+{player['per_click']} ⭐</b>\n\n"
        "Нажимай кнопку! 👇",
        reply_markup=clicker_menu(),
        parse_mode="HTML",
    )

    await callback.answer(
        f"+{player['per_click']} ⭐"
    )


# ==================================================
# МАГАЗИН
# ==================================================

@dp.callback_query(lambda call: call.data == "shop")
async def shop(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛒 <b>NFT SHOP</b>\n\n"
        "💎 Здесь скоро появятся первые NFT!\n\n"
        "Каждый NFT будет иметь собственную "
        "редкость и бонус.",
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
        parse_mode="HTML",
    )

    await callback.answer()


# ==================================================
# КОЛЛЕКЦИЯ
# ==================================================

@dp.callback_query(lambda call: call.data == "collection")
async def collection(callback: CallbackQuery):
    player = get_player(callback.from_user.id)

    nft_count = len(player["nfts"])

    await callback.message.edit_text(
        "💎 <b>МОЯ КОЛЛЕКЦИЯ</b>\n\n"
        f"NFT: <b>{nft_count}</b>\n\n"
        "Твоя коллекция пока пуста.",
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
                ],
            ]
        ),
        parse_mode="HTML",
    )

    await callback.answer()


# ==================================================
# ПРОФИЛЬ
# ==================================================

@dp.callback_query(lambda call: call.data == "profile")
async def profile(callback: CallbackQuery):
    player = get_player(callback.from_user.id)
    user = callback.from_user

    await callback.message.edit_text(
        "👤 <b>ПРОФИЛЬ</b>\n\n"
        f"Игрок: <b>{user.first_name}</b>\n"
        f"ID: <code>{user.id}</code>\n\n"
        f"⭐ Stars: <b>{player['stars']}</b>\n"
        f"⚡ За клик: <b>+{player['per_click']} ⭐</b>\n"
        f"💎 NFT: <b>{len(player['nfts'])}</b>",
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
        parse_mode="HTML",
    )

    await callback.answer()


# ==================================================
# НАЗАД
# ==================================================

@dp.callback_query(lambda call: call.data == "back")
async def back(callback: CallbackQuery):
    await callback.message.edit_text(
        "⭐ <b>STAR CLICKER</b>\n\n"
        "Кликай, собирай ⭐ Stars и собирай "
        "свою коллекцию NFT! 💎\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ==================================================
# ЗАПУСК
# ==================================================

async def main():
    if not TOKEN:
        raise RuntimeError(
            "Переменная окружения BOT_TOKEN не установлена!"
        )

    print("⭐ Star Clicker запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
