import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import Message


TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message()
async def get_sticker_id(message: Message):
    if message.sticker:
        sticker = message.sticker

        await message.answer(
            "✅ Стикер найден!\n\n"
            f"🆔 file_id:\n"
            f"<code>{sticker.file_id}</code>\n\n"
            f"📦 set_name:\n"
            f"<code>{sticker.set_name or 'Нет'}</code>\n\n"
            f"🎬 Тип: {sticker.type}",
            parse_mode="HTML"
        )

    else:
        await message.answer(
            "❌ Это не стикер.\n\n"
            "Отправь мне стикер из нужного набора."
        )


async def main():
    if not TOKEN:
        raise RuntimeError(
            "Переменная окружения BOT_TOKEN не установлена!"
        )

    print("🔎 Sticker ID Finder запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
