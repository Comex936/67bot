import os
import asyncio
import random
import logging
from collections import defaultdict

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from nfts import NFTS


# =========================
# НАСТРОЙКИ
# =========================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в Variables!")

BETA_INFINITE_BALANCE = True

OG_DROP_CHANCE = 0.001  # 0.001%

RESTOCK_SECONDS = 4 * 60 * 60


# =========================
# ЛОГИ
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


bot = Bot(token=TOKEN)
dp = Dispatcher()


# =========================
# ВРЕМЕННЫЕ ДАННЫЕ БЕТЫ
# =========================

# В реальной версии это будет БД.
balances = defaultdict(int)
inventories = defaultdict(list)

# Текущий сток магазина.
stock = {}

# Созданные промокоды.
promo_codes = {}

# NFT, которые игроки уже получили.
# Пока хранится только в памяти.
owned_nfts = defaultdict(list)


# =========================
# РЕСТОК
# =========================

def make_restock():
    global stock

    stock = {}

    epic = [
        nft_id
        for nft_id, nft in NFTS.items()
        if nft["rarity"] == "Epic"
    ]

    secret = [
        nft_id
        for nft_id, nft in NFTS.items()
        if nft["rarity"] == "Secret"
    ]

    # Epic
    for nft_id in epic:
        if random.random() < 0.75:
            stock[nft_id] = random.randint(1, 5)

    # Secret
    for nft_id in secret:
        if random.random() < 0.35:
            stock[nft_id] = random.randint(1, 2)


make_restock()


async def restock_loop():
    while True:
        await asyncio.sleep(RESTOCK_SECONDS)

        make_restock()

        logging.info("🔄 Выполнен новый ресток!")


# =========================
# КЛАВИАТУРЫ
# =========================

def main_menu():
    kb = InlineKeyboardBuilder()

    kb.button(text="Кликнуть", callback_data="click")
    kb.button(text="Магазин", callback_data="shop")
    kb.button(text="Промокоды", callback_data="promos")
    kb.button(text="Создать промокод", callback_data="create_promo")

    kb.adjust(1)

    return kb.as_markup()


def shop_menu():
    kb = InlineKeyboardBuilder()

    epic_count = sum(
        amount
        for nft_id, amount in stock.items()
        if NFTS[nft_id]["rarity"] == "Epic"
    )

    secret_count = sum(
        amount
        for nft_id, amount in stock.items()
        if NFTS[nft_id]["rarity"] == "Secret"
    )

    kb.button(
        text=f"🟣 Купить Epic ({epic_count})",
        callback_data="shop_epic"
    )

    kb.button(
        text=f"🟪 Купить Secret ({secret_count})",
        callback_data="shop_secret"
    )

    kb.button(
        text="👑 Как получить OG-NFT?",
        callback_data="og_info"
    )

    kb.button(
        text="◀️ Назад",
        callback_data="back_main"
    )

    kb.adjust(1)

    return kb.as_markup()


def nft_list_menu(rarity):
    kb = InlineKeyboardBuilder()

    available = [
        nft_id
        for nft_id, amount in stock.items()
        if amount > 0 and NFTS[nft_id]["rarity"] == rarity
    ]

    for nft_id in available:
        nft = NFTS[nft_id]

        kb.button(
            text=nft["name"],
            callback_data=f"nft:{nft_id}"
        )

    kb.button(
        text="◀️ Назад",
        callback_data="shop"
    )

    kb.adjust(1)

    return kb.as_markup()


def nft_card_menu(nft_id):
    kb = InlineKeyboardBuilder()

    nft = NFTS[nft_id]

    kb.button(
        text=f"⭐ {nft['price']:,}".replace(",", " "),
        callback_data=f"buy:{nft_id}"
    )

    kb.button(
        text="◀️ Назад",
        callback_data=f"list:{nft['rarity']}"
    )

    kb.adjust(1)

    return kb.as_markup()


def confirm_menu(nft_id):
    kb = InlineKeyboardBuilder()

    kb.button(
        text="✅ Да, купить",
        callback_data=f"confirm:{nft_id}"
    )

    kb.button(
        text="❌ Отмена",
        callback_data=f"nft:{nft_id}"
    )

    kb.adjust(2)

    return kb.as_markup()


# =========================
# СТАРТ
# =========================

@dp.message(CommandStart())
async def start(message: Message):

    if BETA_INFINITE_BALANCE:
        balance_text = "-0 [∞]"
    else:
        balance_text = f"{balances[message.from_user.id]:,}".replace(",", " ")

    await message.answer(
        "⭐ <b>Star Clicker</b>\n\n"
        f"Ваш баланс: <b>{balance_text} ⭐</b>\n\n"
        "Добро пожаловать в бета-тест!",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================
# КЛИК
# =========================

@dp.callback_query(F.data == "click")
async def click(callback: CallbackQuery):

    user_id = callback.from_user.id

    # Даже при бесконечном балансе считаем клики.
    balances[user_id] += 1

    # =========================
    # ШАНС OG
    # =========================

    if random.random() < OG_DROP_CHANCE / 100:

        og_nfts = [
            nft_id
            for nft_id, nft in NFTS.items()
            if nft["rarity"] == "OG"
        ]

        if og_nfts:

            nft_id = random.choice(og_nfts)
            nft = NFTS[nft_id]

            owned_nfts[user_id].append(nft_id)

            await callback.message.answer_sticker(
                nft["file_id"]
            )

            await callback.message.answer(
                "👑 <b>НЕВЕРОЯТНАЯ УДАЧА!</b>\n\n"
                f"Вы получили OG-NFT:\n"
                f"<b>{nft['name']}</b>\n\n"
                "🎲 Шанс: <b>0.0001%</b>",
                parse_mode="HTML"
            )

    await callback.answer("+1 ⭐")


# =========================
# МАГАЗИН
# =========================

@dp.callback_query(F.data == "shop")
async def shop(callback: CallbackQuery):

    epic_count = sum(
        amount
        for nft_id, amount in stock.items()
        if NFTS[nft_id]["rarity"] == "Epic"
    )

    secret_count = sum(
        amount
        for nft_id, amount in stock.items()
        if NFTS[nft_id]["rarity"] == "Secret"
    )

    await callback.message.edit_text(
        "🛒 <b>МАРКЕТ</b>\n\n"
        f"Сейчас в маркете:\n"
        f"🟣 Epic — <b>{epic_count}</b>\n"
        f"🟪 Secret — <b>{secret_count}</b>\n\n"
        "⏰ Следующий ресток через <b>4 часа</b>",
        reply_markup=shop_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# СПИСОК NFT
# =========================

@dp.callback_query(F.data == "shop_epic")
async def shop_epic(callback: CallbackQuery):

    available = [
        nft_id
        for nft_id, amount in stock.items()
        if amount > 0 and NFTS[nft_id]["rarity"] == "Epic"
    ]

    if not available:

        text = (
            "🟣 <b>EPIC</b>\n\n"
            "Сейчас в стоке ничего нет.\n\n"
            "⏰ Ожидайте рестока."
        )

    else:

        text = (
            "🟣 <b>EPIC NFT</b>\n\n"
            "Сейчас в стоке имеются:"
        )

    await callback.message.edit_text(
        text,
        reply_markup=nft_list_menu("Epic"),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data == "shop_secret")
async def shop_secret(callback: CallbackQuery):

    available = [
        nft_id
        for nft_id, amount in stock.items()
        if amount > 0 and NFTS[nft_id]["rarity"] == "Secret"
    ]

    if not available:

        text = (
            "🟪 <b>SECRET</b>\n\n"
            "Сейчас в стоке ничего нет.\n\n"
            "⏰ Ожидайте рестока."
        )

    else:

        text = (
            "🟪 <b>SECRET NFT</b>\n\n"
            "Сейчас в стоке имеются:"
        )

    await callback.message.edit_text(
        text,
        reply_markup=nft_list_menu("Secret"),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# КАРТОЧКА NFT
# =========================

@dp.callback_query(F.data.startswith("nft:"))
async def nft_card(callback: CallbackQuery):

    nft_id = callback.data.split(":", 1)[1]

    if nft_id not in NFTS:
        await callback.answer(
            "NFT не найден!",
            show_alert=True
        )
        return

    nft = NFTS[nft_id]

    current_stock = stock.get(nft_id, 0)

    await callback.message.delete()

    await callback.message.answer_sticker(
        nft["file_id"]
    )

    await callback.message.answer(
        f"<b>{nft['name']}</b>\n\n"
        f"Редкость: <b>{nft['rarity']}</b>\n"
        f"📦 Сейчас в стоке: <b>{current_stock}</b>\n"
        f"⚡ Бонус: <b>+{nft['bonus']} ⭐/клик</b>",
        reply_markup=nft_card_menu(nft_id),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ПОКУПКА
# =========================

@dp.callback_query(F.data.startswith("buy:"))
async def buy_nft(callback: CallbackQuery):

    nft_id = callback.data.split(":", 1)[1]

    if nft_id not in NFTS:
        await callback.answer(
            "NFT не найден!",
            show_alert=True
        )
        return

    nft = NFTS[nft_id]

    await callback.message.edit_text(
        f"⚠️ <b>Вы точно уверены, что хотите купить "
        f"{nft['name']}?</b>\n\n"
        f"⭐ Стоимость: <b>{nft['price']:,}</b>".replace(",", " "),
        reply_markup=confirm_menu(nft_id),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ПОДТВЕРЖДЕНИЕ
# =========================

@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_buy(callback: CallbackQuery):

    user_id = callback.from_user.id
    nft_id = callback.data.split(":", 1)[1]

    if nft_id not in NFTS:
        await callback.answer(
            "NFT не найден!",
            show_alert=True
        )
        return

    nft = NFTS[nft_id]

    # Проверяем сток прямо в момент покупки.
    current_stock = stock.get(nft_id, 0)

    if current_stock <= 0:

        await callback.message.edit_text(
            "❌ <b>Этот NFT уже был продан!</b>\n\n"
            "⏰ Ожидайте рестока.",
            reply_markup=shop_menu(),
            parse_mode="HTML"
        )

        await callback.answer(
            "NFT уже продан!",
            show_alert=True
        )

        return

    # В будущем здесь будет настоящая проверка баланса.
    if not BETA_INFINITE_BALANCE:

        if balances[user_id] < nft["price"]:

            await callback.message.edit_text(
                "❌ <b>У вас недостаточно звёзд "
                "для покупки данного NFT.</b>\n\n"
                f"⭐ Баланс: <b>{balances[user_id]}</b>\n"
                f"💎 Стоимость NFT: <b>{nft['price']}</b>",
                parse_mode="HTML"
            )

            return

        balances[user_id] -= nft["price"]

    # Уменьшаем сток.
    stock[nft_id] -= 1

    # Выдаём NFT.
    owned_nfts[user_id].append(nft_id)

    await callback.message.edit_text(
        "✅ <b>Покупка успешно совершена!</b>\n\n"
        f"🎁 NFT: <b>{nft['name']}</b>\n"
        f"🟣 Редкость: <b>{nft['rarity']}</b>\n"
        f"⚡ Бонус: <b>+{nft['bonus']} ⭐/клик</b>",
        reply_markup=shop_menu(),
        parse_mode="HTML"
    )

    await callback.message.answer_sticker(
        nft["file_id"]
    )

    await callback.answer("Покупка совершена!")


# =========================
# НАЗАД
# =========================

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):

    user_id = callback.from_user.id

    if BETA_INFINITE_BALANCE:
        balance_text = "-0 [∞]"
    else:
        balance_text = str(balances[user_id])

    await callback.message.edit_text(
        "⭐ <b>Star Clicker</b>\n\n"
        f"Ваш баланс: <b>{balance_text} ⭐</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("list:"))
async def back_to_list(callback: CallbackQuery):

    rarity = callback.data.split(":", 1)[1]

    await callback.message.edit_text(
        f"{'🟣' if rarity == 'Epic' else '🟪'} "
        f"<b>{rarity.upper()} NFT</b>\n\n"
        "Сейчас в стоке имеются:",
        reply_markup=nft_list_menu(rarity),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# OG
# =========================

@dp.callback_query(F.data == "og_info")
async def og_info(callback: CallbackQuery):

    await callback.message.edit_text(
        "👑 <b>Как получить OG-NFT?</b>\n\n"
        "Чтобы получить OG-NFT, вам нужна удача "
        "или промокод.\n\n"
        "🎲 С шансом <b>0.0001%</b> при клике "
        "у вас может появиться сообщение "
        "с получением NFT.\n\n"
        "🎟️ Второй способ — получить специальный "
        "промокод.",
        reply_markup=shop_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ПРОМОКОДЫ
# =========================

@dp.callback_query(F.data == "promos")
async def promos(callback: CallbackQuery):

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🎟️ Ввести промокод",
        callback_data="enter_promo"
    )

    kb.button(
        text="◀️ Назад",
        callback_data="back_main"
    )

    kb.adjust(1)

    await callback.message.edit_text(
        "🎟️ <b>ПРОМОКОДЫ</b>\n\n"
        "Введите промокод, чтобы получить награду.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# СОЗДАНИЕ ПРОМОКОДА
# =========================

@dp.callback_query(F.data == "create_promo")
async def create_promo(callback: CallbackQuery):

    await callback.message.edit_text(
        "🛠️ <b>Создание промокода</b>\n\n"
        "Для бета-теста система создания промокодов "
        "пока находится в разработке.\n\n"
        "Следующим этапом добавим создание кода "
        "прямо через диалог с ботом.",
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ЗАПУСК
# =========================

async def main():

    logging.info("⭐ Star Clicker запущен!")

    asyncio.create_task(restock_loop())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
