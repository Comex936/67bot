import os
import asyncio
import random
import logging
from collections import defaultdict

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from nfts import NFTS


# =========================
# НАСТРОЙКИ
# =========================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в Variables!")

# Во время бета-теста баланс отображается как бесконечный.
BETA_INFINITE_BALANCE = True

# 0.0001% = 1 шанс из 1 000 000
OG_DROP_CHANCE = 0.0001

# Ресток каждые 4 часа.
RESTOCK_SECONDS = 4 * 60 * 60


# =========================
# ЛОГИ
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =========================
# BOT / DISPATCHER
# =========================

bot = Bot(token=TOKEN)

dp = Dispatcher(
    storage=MemoryStorage()
)


# =========================
# ВРЕМЕННЫЕ ДАННЫЕ БЕТЫ
# =========================

# В будущем заменим это на БД.
balances = defaultdict(int)

# Инвентарь игроков.
owned_nfts = defaultdict(list)

# Текущий сток магазина.
stock = {}

# Созданные промокоды.
promo_codes = {}

# Пользователи, которые уже активировали конкретный промокод.
#
# Например:
# {
#     "STAR2026": {123456789, 987654321}
# }
promo_users = defaultdict(set)


# =========================
# FSM СОЗДАНИЯ ПРОМОКОДА
# =========================

class PromoCreate(StatesGroup):

    # Выбор типа награды.
    choosing_type = State()

    # Выбор NFT.
    choosing_nft = State()

    # Выбор количества активаций.
    choosing_activations = State()

    # Ввод количества звёзд.
    entering_stars = State()

    # Ввод названия промокода.
    entering_code = State()

    # Подтверждение создания.
    confirmation = State()

    # Ввод готового промокода пользователем.
    entering_promo = State()


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

        await asyncio.sleep(
            RESTOCK_SECONDS
        )

        make_restock()

        logging.info(
            "🔄 Выполнен новый ресток!"
        )


# =========================
# ГЛАВНОЕ МЕНЮ
# =========================

def main_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🖱 Кликнуть",
        callback_data="click"
    )

    kb.button(
        text="🛒 Магазин",
        callback_data="shop"
    )

    kb.button(
        text="🎟 Промокоды",
        callback_data="promos"
    )

    kb.button(
        text="🛠 Создать промокод",
        callback_data="create_promo"
    )

    kb.adjust(1)

    return kb.as_markup()


# =========================
# МЕНЮ МАГАЗИНА
# =========================

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


# =========================
# СПИСОК NFT
# =========================

def nft_list_menu(rarity):

    kb = InlineKeyboardBuilder()

    available = [
        nft_id
        for nft_id, amount in stock.items()
        if amount > 0
        and NFTS[nft_id]["rarity"] == rarity
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


# =========================
# КАРТОЧКА NFT
# =========================

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


# =========================
# ПОДТВЕРЖДЕНИЕ ПОКУПКИ
# =========================

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
# МЕНЮ ТИПА ПРОМОКОДА
# =========================

def promo_type_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🖼 NFT",
        callback_data="promo_type:nft"
    )

    kb.button(
        text="⭐ Звёзды",
        callback_data="promo_type:stars"
    )

    kb.button(
        text="◀️ Назад",
        callback_data="back_main"
    )

    kb.adjust(1)

    return kb.as_markup()


# =========================
# СПИСОК NFT ДЛЯ ПРОМОКОДА
# =========================

def promo_nft_menu():

    kb = InlineKeyboardBuilder()

    for nft_id, nft in NFTS.items():

        kb.button(
            text=nft["name"],
            callback_data=f"promo_nft:{nft_id}"
        )

    kb.button(
        text="❌ Отмена",
        callback_data="promo_cancel"
    )

    kb.adjust(1)

    return kb.as_markup()


# =========================
# КОЛИЧЕСТВО АКТИВАЦИЙ
# =========================

def promo_activation_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="1",
        callback_data="promo_activations:1"
    )

    kb.button(
        text="10",
        callback_data="promo_activations:10"
    )

    kb.button(
        text="50",
        callback_data="promo_activations:50"
    )

    kb.button(
        text="100",
        callback_data="promo_activations:100"
    )

    kb.button(
        text="♾ Бесконечно",
        callback_data="promo_activations:infinite"
    )

    kb.button(
        text="❌ Отмена",
        callback_data="promo_cancel"
    )

    kb.adjust(2, 2, 1, 1)

    return kb.as_markup()


# =========================
# ПОДТВЕРЖДЕНИЕ ПРОМОКОДА
# =========================

def promo_confirm_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="✅ Подтвердить",
        callback_data="promo_confirm"
    )

    kb.button(
        text="❌ Отмена",
        callback_data="promo_cancel"
    )

    kb.adjust(1)

    return kb.as_markup()


# =========================
# СТАРТ
# =========================

@dp.message(CommandStart())
async def start(message: Message):

    user_id = message.from_user.id

    if BETA_INFINITE_BALANCE:

        balance_text = "-0 [∞]"

    else:

        balance_text = (
            f"{balances[user_id]:,}"
            .replace(",", " ")
        )

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

    # Считаем клики даже при бесконечном балансе.
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

            nft_id = random.choice(
                og_nfts
            )

            nft = NFTS[nft_id]

            owned_nfts[user_id].append(
                nft_id
            )

            await callback.message.answer_sticker(
                nft["file_id"]
            )

            await callback.message.answer(
                "👑 <b>НЕВЕРОЯТНАЯ УДАЧА!</b>\n\n"
                "Вы получили OG-NFT:\n"
                f"<b>{nft['name']}</b>\n\n"
                "🎲 Шанс: <b>0.0001%</b>",
                parse_mode="HTML"
            )

    await callback.answer(
        "+1 ⭐"
    )


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
        "Сейчас в маркете:\n"
        f"🟣 Epic — <b>{epic_count}</b>\n"
        f"🟪 Secret — <b>{secret_count}</b>\n\n"
        "⏰ Следующий ресток через <b>4 часа</b>",
        reply_markup=shop_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# EPIC
# =========================

@dp.callback_query(F.data == "shop_epic")
async def shop_epic(callback: CallbackQuery):

    available = [
        nft_id
        for nft_id, amount in stock.items()
        if amount > 0
        and NFTS[nft_id]["rarity"] == "Epic"
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


# =========================
# SECRET
# =========================

@dp.callback_query(F.data == "shop_secret")
async def shop_secret(callback: CallbackQuery):

    available = [
        nft_id
        for nft_id, amount in stock.items()
        if amount > 0
        and NFTS[nft_id]["rarity"] == "Secret"
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

    nft_id = callback.data.split(
        ":", 1
    )[1]

    if nft_id not in NFTS:

        await callback.answer(
            "NFT не найден!",
            show_alert=True
        )

        return

    nft = NFTS[nft_id]

    current_stock = stock.get(
        nft_id,
        0
    )

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

    nft_id = callback.data.split(
        ":",
        1
    )[1]

    if nft_id not in NFTS:

        await callback.answer(
            "NFT не найден!",
            show_alert=True
        )

        return

    nft = NFTS[nft_id]

    price_text = (
        f"{nft['price']:,}"
        .replace(",", " ")
    )

    await callback.message.edit_text(
        "⚠️ <b>Вы точно уверены, что хотите "
        f"купить {nft['name']}?</b>\n\n"
        f"⭐ Стоимость: <b>{price_text}</b>",
        reply_markup=confirm_menu(nft_id),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ПОДТВЕРЖДЕНИЕ ПОКУПКИ
# =========================

@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_buy(callback: CallbackQuery):

    user_id = callback.from_user.id

    nft_id = callback.data.split(
        ":",
        1
    )[1]

    if nft_id not in NFTS:

        await callback.answer(
            "NFT не найден!",
            show_alert=True
        )

        return

    nft = NFTS[nft_id]

    current_stock = stock.get(
        nft_id,
        0
    )

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

    # Реальная проверка баланса будет использоваться
    # после окончания бета-теста.
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
    owned_nfts[user_id].append(
        nft_id
    )

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

    await callback.answer(
        "Покупка совершена!"
    )


# =========================
# НАЗАД В ГЛАВНОЕ МЕНЮ
# =========================

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):

    user_id = callback.from_user.id

    if BETA_INFINITE_BALANCE:

        balance_text = "-0 [∞]"

    else:

        balance_text = str(
            balances[user_id]
        )

    await callback.message.edit_text(
        "⭐ <b>Star Clicker</b>\n\n"
        f"Ваш баланс: <b>{balance_text} ⭐</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# НАЗАД К СПИСКУ NFT
# =========================

@dp.callback_query(F.data.startswith("list:"))
async def back_to_list(
    callback: CallbackQuery
):

    rarity = callback.data.split(
        ":",
        1
    )[1]

    emoji = (
        "🟣"
        if rarity == "Epic"
        else "🟪"
    )

    await callback.message.edit_text(
        f"{emoji} <b>{rarity.upper()} NFT</b>\n\n"
        "Сейчас в стоке имеются:",
        reply_markup=nft_list_menu(rarity),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# OG INFO
# =========================

@dp.callback_query(F.data == "og_info")
async def og_info(callback: CallbackQuery):

    await callback.message.edit_text(
        "👑 <b>Как получить OG-NFT?</b>\n\n"
        "Чтобы получить OG-NFT, вам нужна удача "
        "или специальный промокод.\n\n"
        "🎲 С шансом <b>0.0001%</b> при клике "
        "у вас может появиться сообщение "
        "с получением NFT.\n\n"
        "🎟️ Второй способ — получить специальный "
        "промокод.",
        reply_markup=shop_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ПРОМОКОДЫ
# =========================================================

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


# =========================================================
# СОЗДАНИЕ ПРОМОКОДА
# =========================================================

@dp.callback_query(F.data == "create_promo")
async def create_promo(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await state.set_state(
        PromoCreate.choosing_type
    )

    await callback.message.edit_text(
        "🛠️ <b>Создание промокода</b>\n\n"
        "Выберите награду, которую будет "
        "выдавать промокод:",
        reply_markup=promo_type_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# NFT
# =========================

@dp.callback_query(
    PromoCreate.choosing_type,
    F.data == "promo_type:nft"
)
async def promo_choose_nft(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.update_data(
        reward_type="NFT"
    )

    await state.set_state(
        PromoCreate.choosing_nft
    )

    await callback.message.edit_text(
        "🖼 <b>Выбор NFT</b>\n\n"
        "Выберите NFT, который вы хотите "
        "получить за промокод:",
        reply_markup=promo_nft_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ЗВЁЗДЫ
# =========================

@dp.callback_query(
    PromoCreate.choosing_type,
    F.data == "promo_type:stars"
)
async def promo_choose_stars(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.update_data(
        reward_type="STARS"
    )

    await state.set_state(
        PromoCreate.entering_stars
    )

    await callback.message.edit_text(
        "⭐ <b>Промокод на звёзды</b>\n\n"
        "Напишите количество ⭐ звёзд, "
        "которое будет выдаваться за одну "
        "активацию.\n\n"
        "Например:\n"
        "<code>1000</code>",
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ВЫБОР NFT
# =========================

@dp.callback_query(
    PromoCreate.choosing_nft,
    F.data.startswith("promo_nft:")
)
async def promo_nft_selected(
    callback: CallbackQuery,
    state: FSMContext
):

    nft_id = callback.data.split(
        ":",
        1
    )[1]

    if nft_id not in NFTS:

        await callback.answer(
            "NFT не найден!",
            show_alert=True
        )

        return

    nft = NFTS[nft_id]

    await state.update_data(
        nft_id=nft_id,
        nft_name=nft["name"]
    )

    await state.set_state(
        PromoCreate.choosing_activations
    )

    await callback.message.edit_text(
        "🔢 <b>Количество активаций</b>\n\n"
        "Сколько активаций нужно для "
        "этого промокода?",
        reply_markup=promo_activation_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# КОЛИЧЕСТВО ЗВЁЗД
# =========================

@dp.message(PromoCreate.entering_stars)
async def promo_stars_entered(
    message: Message,
    state: FSMContext
):

    if not message.text:

        await message.answer(
            "❌ Напишите количество звёзд числом."
        )

        return

    text = message.text.strip()

    if not text.isdigit():

        await message.answer(
            "❌ Количество звёзд должно быть "
            "указано числом.\n\n"
            "Например: <code>1000</code>",
            parse_mode="HTML"
        )

        return

    stars = int(text)

    if stars <= 0:

        await message.answer(
            "❌ Количество звёзд должно быть "
            "больше нуля."
        )

        return

    if stars > 1_000_000_000:

        await message.answer(
            "❌ Максимальная награда — "
            "<b>1 000 000 000 ⭐</b>.",
            parse_mode="HTML"
        )

        return

    await state.update_data(
        stars=stars
    )

    await state.set_state(
        PromoCreate.choosing_activations
    )

    await message.answer(
        "🔢 <b>Количество активаций</b>\n\n"
        "Сколько активаций нужно для "
        "этого промокода?",
        reply_markup=promo_activation_menu(),
        parse_mode="HTML"
    )


# =========================
# ВЫБОР АКТИВАЦИЙ
# =========================

@dp.callback_query(
    PromoCreate.choosing_activations,
    F.data.startswith("promo_activations:")
)
async def promo_activations_selected(
    callback: CallbackQuery,
    state: FSMContext
):

    value = callback.data.split(
        ":",
        1
    )[1]

    if value == "infinite":

        activations = "infinite"
        activation_text = "Бесконечно"

    else:

        activations = int(value)
        activation_text = str(
            activations
        )

    await state.update_data(
        activations=activations,
        activation_text=activation_text
    )

    await state.set_state(
        PromoCreate.entering_code
    )

    await callback.message.edit_text(
        "✏️ <b>Создание промокода</b>\n\n"
        "Напишите свой промокод "
        "<b>на английском языке</b>.\n\n"
        "Например:\n"
        "<code>STAR2026</code>",
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ВВОД ПРОМОКОДА
# =========================

@dp.message(PromoCreate.entering_code)
async def promo_code_entered(
    message: Message,
    state: FSMContext
):

    if not message.text:

        await message.answer(
            "❌ Пожалуйста, напишите промокод текстом."
        )

        return

    code = message.text.strip()

    # Только английские буквы и цифры.
    if not code.isascii() or not code.isalnum():

        await message.answer(
            "❌ Промокод должен содержать только "
            "английские буквы и цифры.\n\n"
            "Например: <code>STAR2026</code>",
            parse_mode="HTML"
        )

        return

    # Не даём создать одинаковый код.
    if code.lower() in (
        existing_code.lower()
        for existing_code in promo_codes
    ):

        await message.answer(
            "❌ Такой промокод уже существует.\n\n"
            "Придумайте другой."
        )

        return

    await state.update_data(
        code=code
    )

    data = await state.get_data()

    await state.set_state(
        PromoCreate.confirmation
    )

    # Текст награды.
    if data["reward_type"] == "NFT":

        reward_text = data["nft_name"]

    else:

        reward_text = (
            f"{data['stars']:,}"
            .replace(",", " ")
            + " ⭐"
        )

    await message.answer(
        "⚠️ <b>Вы подтверждаете создание "
        "промокода?</b>\n\n"
        "📋 <b>Данные:</b>\n\n"
        f"🏷 Название: <code>{code}</code>\n"
        f"🎁 На что промокод: <b>{reward_text}</b>\n"
        f"🔢 На сколько активаций: "
        f"<b>{data['activation_text']}</b>",
        reply_markup=promo_confirm_menu(),
        parse_mode="HTML"
    )


# =========================
# ПОДТВЕРЖДЕНИЕ СОЗДАНИЯ
# =========================

@dp.callback_query(
    PromoCreate.confirmation,
    F.data == "promo_confirm"
)
async def promo_confirm(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    code = data["code"]

    # -------------------------
    # ПРОМОКОД НА ЗВЁЗДЫ
    # -------------------------

    if data["reward_type"] == "STARS":

        promo_codes[code] = {
            "type": "STARS",
            "stars": data["stars"],
            "activations": data["activations"],
            "used": 0,
            "creator_id": callback.from_user.id
        }

        reward_text = (
            f"{data['stars']:,}"
            .replace(",", " ")
            + " ⭐"
        )

    # -------------------------
    # ПРОМОКОД НА NFT
    # -------------------------

    else:

        promo_codes[code] = {
            "type": "NFT",
            "nft_id": data["nft_id"],
            "activations": data["activations"],
            "used": 0,
            "creator_id": callback.from_user.id
        }

        reward_text = data["nft_name"]

    await state.clear()

    await callback.message.edit_text(
        "✅ <b>Промокод успешно создан!</b>\n\n"
        f"🎟 Промокод: <code>{code}</code>\n"
        f"🎁 Награда: <b>{reward_text}</b>\n"
        f"🔢 Активаций: "
        f"<b>{data['activation_text']}</b>",
        parse_mode="HTML"
    )

    await callback.answer(
        "Промокод создан!"
    )


# =========================
# ОТМЕНА СОЗДАНИЯ
# =========================

@dp.callback_query(
    F.data == "promo_cancel"
)
async def promo_cancel(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Создание промокода отменено.</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# АКТИВАЦИЯ ПРОМОКОДА
# =========================================================

@dp.callback_query(F.data == "enter_promo")
async def enter_promo(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await state.set_state(
        PromoCreate.entering_promo
    )

    await callback.message.edit_text(
        "🎟️ <b>Активация промокода</b>\n\n"
        "Напишите промокод:",
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ОБРАБОТКА ПРОМОКОДА
# =========================

@dp.message(PromoCreate.entering_promo)
async def activate_promo(
    message: Message,
    state: FSMContext
):

    if not message.text:

        await message.answer(
            "❌ Пожалуйста, напишите промокод."
        )

        return

    code = message.text.strip()

    # Ищем код без учёта регистра.
    real_code = next(
        (
            promo_code
            for promo_code in promo_codes
            if promo_code.lower() == code.lower()
        ),
        None
    )

    # -------------------------
    # КОД НЕ НАЙДЕН
    # -------------------------

    if real_code is None:

        await message.answer(
            "❌ <b>Промокод не найден!</b>\n\n"
            "Проверьте правильность написания.",
            parse_mode="HTML"
        )

        return

    promo = promo_codes[real_code]

    user_id = message.from_user.id

    # -------------------------
    # ПОВТОРНАЯ АКТИВАЦИЯ
    # -------------------------

    if user_id in promo_users[real_code]:

        await message.answer(
            "❌ <b>Вы уже активировали "
            "этот промокод!</b>",
            parse_mode="HTML"
        )

        await state.clear()

        return

    # -------------------------
    # ПРОВЕРКА ЛИМИТА
    # -------------------------

    if promo["activations"] != "infinite":

        if promo["used"] >= promo["activations"]:

            await message.answer(
                "❌ <b>Все активации этого "
                "промокода уже использованы!</b>",
                parse_mode="HTML"
            )

            await state.clear()

            return

    # -------------------------
    # ЗАСЧИТЫВАЕМ АКТИВАЦИЮ
    # -------------------------

    promo_users[real_code].add(
        user_id
    )

    if promo["activations"] != "infinite":

        promo["used"] += 1

    # =====================================================
    # НАГРАДА: ЗВЁЗДЫ
    # =====================================================

    if promo["type"] == "STARS":

        stars = promo["stars"]

        balances[user_id] += stars

        reward_text = (
            f"⭐ +{stars:,}"
            .replace(",", " ")
        )

    # =====================================================
    # НАГРАДА: NFT
    # =====================================================

    elif promo["type"] == "NFT":

        nft_id = promo["nft_id"]

        if nft_id not in NFTS:

            # Откатываем использование,
            # если NFT больше нет.
            promo_users[real_code].discard(
                user_id
            )

            if promo["activations"] != "infinite":
                promo["used"] -= 1

            await message.answer(
                "❌ NFT этого промокода "
                "больше не существует."
            )

            await state.clear()

            return

        nft = NFTS[nft_id]

        owned_nfts[user_id].append(
            nft_id
        )

        await message.answer_sticker(
            nft["file_id"]
        )

        reward_text = (
            f"🎁 {nft['name']}"
        )

    # =====================================================
    # НЕИЗВЕСТНЫЙ ТИП
    # =====================================================

    else:

        promo_users[real_code].discard(
            user_id
        )

        if promo["activations"] != "infinite":
            promo["used"] -= 1

        await message.answer(
            "❌ Неизвестный тип промокода."
        )

        await state.clear()

        return

    # -------------------------
    # ТЕКСТ АКТИВАЦИЙ
    # -------------------------

    if promo["activations"] == "infinite":

        activation_text = "♾ Бесконечно"

    else:

        activation_text = (
            f"{promo['used']} / "
            f"{promo['activations']}"
        )

    await message.answer(
        "🎉 <b>Промокод успешно активирован!</b>\n\n"
        f"🎁 Награда: <b>{reward_text}</b>\n"
        f"🎟 Активации: <b>{activation_text}</b>",
        parse_mode="HTML"
    )

    await state.clear()


# =========================
# ЗАПУСК
# =========================

async def main():

    logging.info(
        "⭐ Star Clicker запущен!"
    )

    asyncio.create_task(
        restock_loop()
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
