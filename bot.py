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


# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в Variables!")

# Твой Telegram ID
ADMIN_IDS = {
    8558737152
}

# Бета-тест
BETA_INFINITE_BALANCE = True

# В бета-тесте игрок получает все NFT
BETA_ALL_NFTS = True

# OG: 0.0001%
OG_DROP_CHANCE = 0.0001

# Ресток каждые 4 часа
RESTOCK_SECONDS = 4 * 60 * 60


# =========================================================
# ЛОГИ
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =========================================================
# BOT
# =========================================================

bot = Bot(token=TOKEN)

dp = Dispatcher(
    storage=MemoryStorage()
)


# =========================================================
# ВРЕМЕННЫЕ ДАННЫЕ
# =========================================================

balances = defaultdict(int)

# user_id -> список NFT
owned_nfts = defaultdict(list)

# user_id -> активный NFT
equipped_nft = {}

# Магазин
stock = {}

# Промокоды
promo_codes = {}

# promo_code -> множество использовавших пользователей
promo_users = defaultdict(set)

# Игроки, которые запускали бота
known_users = set()


# =========================================================
# FSM
# =========================================================

class PromoCreate(StatesGroup):

    choosing_type = State()
    choosing_nft = State()
    choosing_activations = State()
    entering_stars = State()
    entering_code = State()
    confirmation = State()

    entering_promo = State()

    # Админ
    admin_give_nft_user = State()
    admin_give_nft_select = State()

    admin_give_stars_user = State()
    admin_give_stars_amount = State()

    admin_remove_nft_user = State()
    admin_remove_nft_select = State()

    admin_set_balance_user = State()
    admin_set_balance_amount = State()

    admin_user_info = State()

    admin_broadcast = State()


# =========================================================
# ПРОВЕРКА АДМИНА
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================================================
# БЕТА-ИНВЕНТАРЬ
# =========================================================

def initialize_beta_inventory(user_id: int):

    if not BETA_ALL_NFTS:
        return

    if owned_nfts[user_id]:
        return

    owned_nfts[user_id] = list(NFTS.keys())


# =========================================================
# АКТИВНЫЙ NFT
# =========================================================

def get_equipped_nft(user_id: int):

    nft_id = equipped_nft.get(user_id)

    if not nft_id:
        return None

    if nft_id not in NFTS:

        equipped_nft.pop(
            user_id,
            None
        )

        return None

    return NFTS[nft_id]


def get_total_bonus(user_id: int):

    nft = get_equipped_nft(user_id)

    if not nft:
        return 0

    return nft.get(
        "bonus",
        0
    )


# =========================================================
# РЕСТОК
# =========================================================

def make_restock():

    global stock

    stock = {}

    epic = [
        nft_id
        for nft_id, nft in NFTS.items()
        if nft.get("rarity") == "Epic"
    ]

    secret = [
        nft_id
        for nft_id, nft in NFTS.items()
        if nft.get("rarity") == "Secret"
    ]

    for nft_id in epic:

        if random.random() < 0.75:

            stock[nft_id] = random.randint(
                1,
                5
            )

    for nft_id in secret:

        if random.random() < 0.35:

            stock[nft_id] = random.randint(
                1,
                2
            )


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


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_menu(user_id: int):

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🖱 Кликнуть",
        callback_data="click"
    )

    kb.button(
        text="🎒 Инвентарь",
        callback_data="inventory"
    )

    kb.button(
        text="📖 Индекс NFT",
        callback_data="index"
    )

    kb.button(
        text="🛒 Магазин",
        callback_data="shop"
    )

    kb.button(
        text="🎟 Промокоды",
        callback_data="promos"
    )

    if is_admin(user_id):

        kb.button(
            text="🛠 Админ-панель",
            callback_data="admin"
        )

    kb.adjust(1)

    return kb.as_markup()


# =========================================================
# ИНДЕКС
# =========================================================

RARITY_ORDER = [
    "Common",
    "Uncommon",
    "Rare",
    "Epic",
    "Legendary",
    "Secret",
    "OG",
    "Friend"
]


RARITY_EMOJI = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟠",
    "Secret": "🟪",
    "OG": "👑",
    "Friend": "🤝"
}


def index_rarity_menu():

    kb = InlineKeyboardBuilder()

    existing_rarities = set(
        nft.get("rarity")
        for nft in NFTS.values()
    )

    for rarity in RARITY_ORDER:

        if rarity not in existing_rarities:
            continue

        count = sum(
            1
            for nft in NFTS.values()
            if nft.get("rarity") == rarity
        )

        emoji = RARITY_EMOJI.get(
            rarity,
            "⭐"
        )

        kb.button(
            text=f"{emoji} {rarity} ({count})",
            callback_data=f"index_rarity:{rarity}"
        )

    # На случай новой редкости в nfts.py
    for rarity in sorted(
        existing_rarities - set(RARITY_ORDER)
    ):

        count = sum(
            1
            for nft in NFTS.values()
            if nft.get("rarity") == rarity
        )

        kb.button(
            text=f"⭐ {rarity} ({count})",
            callback_data=f"index_rarity:{rarity}"
        )

    kb.button(
        text="◀️ Назад",
        callback_data="back_main"
    )

    kb.adjust(1)

    return kb.as_markup()


def index_nft_menu(rarity):

    kb = InlineKeyboardBuilder()

    for nft_id, nft in NFTS.items():

        if nft.get("rarity") != rarity:
            continue

        bonus = nft.get(
            "bonus",
            0
        )

        kb.button(
            text=f"{nft['name']} (+{bonus} ⭐)",
            callback_data=f"index_nft:{nft_id}"
        )

    kb.button(
        text="◀️ К редкостям",
        callback_data="index"
    )

    kb.adjust(1)

    return kb.as_markup()


@dp.callback_query(F.data == "index")
async def index_menu_handler(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        "📖 <b>ИНДЕКС NFT</b>\n\n"
        "Здесь собраны все NFT игры.\n\n"
        "Выберите редкость:",
        reply_markup=index_rarity_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("index_rarity:")
)
async def index_rarity_handler(
    callback: CallbackQuery
):

    rarity = callback.data.split(
        ":",
        1
    )[1]

    if not any(
        nft.get("rarity") == rarity
        for nft in NFTS.values()
    ):

        await callback.answer(
            "Редкость не найдена!",
            show_alert=True
        )

        return

    emoji = RARITY_EMOJI.get(
        rarity,
        "⭐"
    )

    await callback.message.edit_text(
        f"{emoji} <b>{rarity.upper()}</b>\n\n"
        "Выберите NFT:",
        reply_markup=index_nft_menu(rarity),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("index_nft:")
)
async def index_nft_handler(
    callback: CallbackQuery
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

    bonus = nft.get(
        "bonus",
        0
    )

    rarity = nft.get(
        "rarity",
        "Unknown"
    )

    price = nft.get(
        "price"
    )

    if price is None:
        price_text = "Нельзя купить"
    else:
        price_text = (
            f"{price:,}"
            .replace(",", " ")
            + " ⭐"
        )

    emoji = RARITY_EMOJI.get(
        rarity,
        "⭐"
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="◀️ Назад",
        callback_data=f"index_rarity:{rarity}"
    )

    kb.adjust(1)

    await callback.message.edit_text(
        f"{emoji} <b>{nft['name']}</b>\n\n"
        f"Редкость: <b>{rarity}</b>\n"
        f"⚡ За клик: <b>+{bonus} ⭐</b>\n"
        f"💰 Цена: <b>{price_text}</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ИНВЕНТАРЬ
# =========================================================

def inventory_menu(user_id: int):

    kb = InlineKeyboardBuilder()

    initialize_beta_inventory(user_id)

    nft_ids = list(
        dict.fromkeys(
            owned_nfts[user_id]
        )
    )

    for nft_id in nft_ids:

        if nft_id not in NFTS:
            continue

        nft = NFTS[nft_id]

        if equipped_nft.get(user_id) == nft_id:

            text = (
                f"🟢 {nft['name']} — АКТИВЕН"
            )

        else:

            text = nft["name"]

        kb.button(
            text=text,
            callback_data=f"equip:{nft_id}"
        )

    kb.button(
        text="◀️ Назад",
        callback_data="back_main"
    )

    kb.adjust(1)

    return kb.as_markup()


@dp.callback_query(F.data == "inventory")
async def inventory_handler(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    initialize_beta_inventory(user_id)

    active_nft = get_equipped_nft(
        user_id
    )

    if active_nft:

        active_text = (
            f"🟢 <b>{active_nft['name']}</b>\n"
            f"⚡ Бонус: "
            f"<b>+{active_nft.get('bonus', 0)} ⭐/клик</b>"
        )

    else:

        active_text = (
            "🔴 <b>Нет активного NFT</b>"
        )

    nft_count = len(
        set(
            owned_nfts[user_id]
        )
    )

    await callback.message.edit_text(
        "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
        f"Всего NFT: <b>{nft_count}</b>\n\n"
        "Активный NFT:\n"
        f"{active_text}\n\n"
        "👇 Нажмите на NFT, чтобы "
        "применить его:",
        reply_markup=inventory_menu(
            user_id
        ),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("equip:")
)
async def equip_nft(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    nft_id = callback.data.split(
        ":",
        1
    )[1]

    initialize_beta_inventory(user_id)

    if nft_id not in NFTS:

        await callback.answer(
            "❌ NFT не найден!",
            show_alert=True
        )

        return

    if nft_id not in owned_nfts[user_id]:

        await callback.answer(
            "❌ У вас нет этого NFT!",
            show_alert=True
        )

        return

    if equipped_nft.get(user_id) == nft_id:

        await callback.answer(
            "Этот NFT уже активен!"
        )

        return

    nft = NFTS[nft_id]

    equipped_nft[user_id] = nft_id

    await callback.message.edit_text(
        "✅ <b>NFT применён!</b>\n\n"
        f"🎁 <b>{nft['name']}</b>\n"
        f"🟣 Редкость: <b>{nft['rarity']}</b>\n"
        f"⚡ Бонус: "
        f"<b>+{nft.get('bonus', 0)} ⭐/клик</b>\n\n"
        "Теперь этот NFT активен.",
        reply_markup=inventory_menu(
            user_id
        ),
        parse_mode="HTML"
    )

    await callback.answer(
        "NFT применён!"
    )


# =========================================================
# ГЛАВНАЯ
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    user_id = message.from_user.id

    known_users.add(user_id)

    initialize_beta_inventory(
        user_id
    )

    if BETA_INFINITE_BALANCE:

        balance_text = "-0 [∞]"

    else:

        balance_text = (
            f"{balances[user_id]:,}"
            .replace(",", " ")
        )

    active_nft = get_equipped_nft(
        user_id
    )

    if active_nft:

        active_text = (
            f"{active_nft['name']} "
            f"(+{active_nft.get('bonus', 0)} ⭐/клик)"
        )

    else:

        active_text = "Нет"

    await message.answer(
        "⭐ <b>NFT CLICKER</b>\n\n"
        f"Ваш баланс: <b>{balance_text} ⭐</b>\n"
        f"🎒 Активный NFT: <b>{active_text}</b>\n\n"
        "Добро пожаловать в бета-тест!",
        reply_markup=main_menu(user_id),
        parse_mode="HTML"
    )


# =========================================================
# КЛИК
# =========================================================

@dp.callback_query(F.data == "click")
async def click(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    known_users.add(user_id)

    initialize_beta_inventory(user_id)

    bonus = get_total_bonus(
        user_id
    )

    click_reward = 1 + bonus

    balances[user_id] += click_reward

    # OG DROP
    if random.random() < OG_DROP_CHANCE / 100:

        og_nfts = [
            nft_id
            for nft_id, nft in NFTS.items()
            if nft.get("rarity") == "OG"
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
        f"+{click_reward} ⭐"
    )


# =========================================================
# МАГАЗИН
# =========================================================

def shop_menu():

    kb = InlineKeyboardBuilder()

    epic_count = sum(
        amount
        for nft_id, amount in stock.items()
        if NFTS[nft_id].get("rarity") == "Epic"
    )

    secret_count = sum(
        amount
        for nft_id, amount in stock.items()
        if NFTS[nft_id].get("rarity") == "Secret"
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
        if amount > 0
        and NFTS[nft_id].get("rarity") == rarity
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


@dp.callback_query(F.data == "shop")
async def shop(
    callback: CallbackQuery
):

    epic_count = sum(
        amount
        for nft_id, amount in stock.items()
        if NFTS[nft_id].get("rarity") == "Epic"
    )

    secret_count = sum(
        amount
        for nft_id, amount in stock.items()
        if NFTS[nft_id].get("rarity") == "Secret"
    )

    await callback.message.edit_text(
        "🛒 <b>МАРКЕТ</b>\n\n"
        "Сейчас в маркете:\n"
        f"🟣 Epic — <b>{epic_count}</b>\n"
        f"🟪 Secret — <b>{secret_count}</b>\n\n"
        "⏰ Следующий ресток через "
        "<b>4 часа</b>",
        reply_markup=shop_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data == "shop_epic")
async def shop_epic(
    callback: CallbackQuery
):

    available = [
        nft_id
        for nft_id, amount in stock.items()
        if amount > 0
        and NFTS[nft_id].get("rarity") == "Epic"
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
async def shop_secret(
    callback: CallbackQuery
):

    available = [
        nft_id
        for nft_id, amount in stock.items()
        if amount > 0
        and NFTS[nft_id].get("rarity") == "Secret"
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


# =========================================================
# КАРТОЧКА NFT
# =========================================================

def nft_card_menu(nft_id):

    kb = InlineKeyboardBuilder()

    nft = NFTS[nft_id]

    price = nft.get("price")

    if price is not None:

        kb.button(
            text=(
                f"⭐ {price:,}"
                .replace(",", " ")
            ),
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


@dp.callback_query(F.data.startswith("nft:"))
async def nft_card(
    callback: CallbackQuery
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

    current_stock = stock.get(
        nft_id,
        0
    )

    await callback.message.delete()

    await callback.message.answer_sticker(
        nft["file_id"]
    )

    price = nft.get("price")

    if price is None:
        price_text = "Нельзя купить"
    else:
        price_text = (
            f"{price:,}"
            .replace(",", " ")
        )

    await callback.message.answer(
        f"<b>{nft['name']}</b>\n\n"
        f"Редкость: <b>{nft['rarity']}</b>\n"
        f"📦 Сейчас в стоке: <b>{current_stock}</b>\n"
        f"⚡ Бонус: "
        f"<b>+{nft.get('bonus', 0)} ⭐/клик</b>\n"
        f"💰 Цена: <b>{price_text}</b>",
        reply_markup=nft_card_menu(nft_id),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ПОКУПКА
# =========================================================

@dp.callback_query(F.data.startswith("buy:"))
async def buy_nft(
    callback: CallbackQuery
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

    if nft.get("price") is None:

        await callback.answer(
            "Этот NFT нельзя купить!",
            show_alert=True
        )

        return

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


@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_buy(
    callback: CallbackQuery
):

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

    if nft.get("price") is None:

        await callback.answer(
            "Этот NFT нельзя купить!",
            show_alert=True
        )

        return

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

    if not BETA_INFINITE_BALANCE:

        if balances[user_id] < nft["price"]:

            await callback.message.edit_text(
                "❌ <b>Недостаточно звёзд.</b>\n\n"
                f"⭐ Баланс: "
                f"<b>{balances[user_id]}</b>\n"
                f"💎 Стоимость: "
                f"<b>{nft['price']}</b>",
                reply_markup=shop_menu(),
                parse_mode="HTML"
            )

            return

        balances[user_id] -= nft["price"]

    stock[nft_id] -= 1

    owned_nfts[user_id].append(
        nft_id
    )

    await callback.message.edit_text(
        "✅ <b>Покупка успешно совершена!</b>\n\n"
        f"🎁 NFT: <b>{nft['name']}</b>\n"
        f"🟣 Редкость: <b>{nft['rarity']}</b>\n"
        f"⚡ Бонус: "
        f"<b>+{nft.get('bonus', 0)} ⭐/клик</b>",
        reply_markup=shop_menu(),
        parse_mode="HTML"
    )

    await callback.message.answer_sticker(
        nft["file_id"]
    )

    await callback.answer(
        "Покупка совершена!"
    )


# =========================================================
# НАЗАД
# =========================================================

@dp.callback_query(F.data == "back_main")
async def back_main(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    if BETA_INFINITE_BALANCE:

        balance_text = "-0 [∞]"

    else:

        balance_text = (
            f"{balances[user_id]:,}"
            .replace(",", " ")
        )

    active_nft = get_equipped_nft(
        user_id
    )

    if active_nft:

        active_text = (
            f"{active_nft['name']} "
            f"(+{active_nft.get('bonus', 0)} ⭐/клик)"
        )

    else:

        active_text = "Нет"

    await callback.message.edit_text(
        "⭐ <b>NFT CLICKER</b>\n\n"
        f"Ваш баланс: <b>{balance_text} ⭐</b>\n"
        f"🎒 Активный NFT: <b>{active_text}</b>",
        reply_markup=main_menu(user_id),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("list:"))
async def back_to_list(
    callback: CallbackQuery
):

    rarity = callback.data.split(
        ":",
        1
    )[1]

    emoji = RARITY_EMOJI.get(
        rarity,
        "⭐"
    )

    await callback.message.edit_text(
        f"{emoji} <b>{rarity.upper()} NFT</b>\n\n"
        "Сейчас в стоке имеются:",
        reply_markup=nft_list_menu(rarity),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# OG
# =========================================================

@dp.callback_query(F.data == "og_info")
async def og_info(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        "👑 <b>Как получить OG-NFT?</b>\n\n"
        "OG-NFT можно получить только "
        "особыми способами.\n\n"
        "🎲 При клике существует шанс "
        "<b>0.0001%</b> получить OG-NFT.\n\n"
        "🎟️ Также OG-NFT может быть выдан "
        "через специальный промокод.",
        reply_markup=shop_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ПРОМОКОДЫ
# =========================================================

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
        callback_data="admin"
    )

    kb.adjust(1)

    return kb.as_markup()


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

    kb.adjust(
        2,
        2,
        1,
        1
    )

    return kb.as_markup()


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


# =========================================================
# ПРОМОКОДЫ — МЕНЮ
# =========================================================

@dp.callback_query(F.data == "promos")
async def promos(
    callback: CallbackQuery
):

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

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    await state.clear()

    await state.set_state(
        PromoCreate.choosing_type
    )

    await callback.message.edit_text(
        "🛠️ <b>Создание промокода</b>\n\n"
        "Выберите награду:",
        reply_markup=promo_type_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


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
        "Выберите NFT, который будет "
        "выдаваться за промокод:",
        reply_markup=promo_nft_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


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
        "Напишите количество ⭐ звёзд "
        "за одну активацию.\n\n"
        "Например:\n"
        "<code>1000</code>",
        parse_mode="HTML"
    )

    await callback.answer()


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


@dp.message(PromoCreate.entering_stars)
async def promo_stars_entered(
    message: Message,
    state: FSMContext
):

    if not message.text or not message.text.strip().isdigit():

        await message.answer(
            "❌ Введите количество звёзд числом.\n\n"
            "Например: <code>1000</code>",
            parse_mode="HTML"
        )

        return

    stars = int(
        message.text.strip()
    )

    if stars <= 0:

        await message.answer(
            "❌ Количество должно быть больше нуля."
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
        "Сколько активаций нужно?",
        reply_markup=promo_activation_menu(),
        parse_mode="HTML"
    )


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
        activation_text = str(value)

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
        "Можно использовать английские "
        "буквы и цифры.\n\n"
        "Например:\n"
        "<code>STAR2026</code>",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(PromoCreate.entering_code)
async def promo_code_entered(
    message: Message,
    state: FSMContext
):

    if not message.text:

        await message.answer(
            "❌ Напишите промокод."
        )

        return

    code = message.text.strip()

    if (
        not code
        or len(code) > 32
        or not code.isascii()
        or not code.isalnum()
    ):

        await message.answer(
            "❌ Промокод должен содержать "
            "только английские буквы и цифры.\n\n"
            "Максимум 32 символа."
        )

        return

    if code.lower() in (
        existing_code.lower()
        for existing_code in promo_codes
    ):

        await message.answer(
            "❌ Такой промокод уже существует."
        )

        return

    await state.update_data(
        code=code
    )

    data = await state.get_data()

    await state.set_state(
        PromoCreate.confirmation
    )

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
        f"🎁 На что промокод: "
        f"<b>{reward_text}</b>\n"
        f"🔢 На сколько активаций: "
        f"<b>{data['activation_text']}</b>",
        reply_markup=promo_confirm_menu(),
        parse_mode="HTML"
    )


@dp.callback_query(
    PromoCreate.confirmation,
    F.data == "promo_confirm"
)
async def promo_confirm(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await state.clear()

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    data = await state.get_data()

    code = data["code"]

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


@dp.callback_query(F.data == "promo_cancel")
async def promo_cancel(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    if is_admin(callback.from_user.id):

        await callback.message.edit_text(
            "❌ <b>Операция отменена.</b>",
            reply_markup=admin_menu(),
            parse_mode="HTML"
        )

    else:

        await callback.message.edit_text(
            "❌ <b>Операция отменена.</b>",
            reply_markup=main_menu(
                callback.from_user.id
            ),
            parse_mode="HTML"
        )

    await callback.answer()


# =========================================================
# ВВОД ПРОМОКОДА
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

    real_code = next(
        (
            promo_code
            for promo_code in promo_codes
            if promo_code.lower() == code.lower()
        ),
        None
    )

    if real_code is None:

        await message.answer(
            "❌ <b>Промокод не найден!</b>",
            parse_mode="HTML"
        )

        return

    promo = promo_codes[real_code]

    user_id = message.from_user.id

    known_users.add(user_id)

    if user_id in promo_users[real_code]:

        await message.answer(
            "❌ <b>Вы уже активировали "
            "этот промокод!</b>",
            parse_mode="HTML"
        )

        await state.clear()

        return

    if promo["activations"] != "infinite":

        if promo["used"] >= promo["activations"]:

            await message.answer(
                "❌ <b>Все активации этого "
                "промокода уже использованы!</b>",
                parse_mode="HTML"
            )

            await state.clear()

            return

    promo_users[real_code].add(
        user_id
    )

    if promo["activations"] != "infinite":

        promo["used"] += 1

    # ЗВЁЗДЫ
    if promo["type"] == "STARS":

        stars = promo["stars"]

        balances[user_id] += stars

        reward_text = (
            f"⭐ +{stars:,}"
            .replace(",", " ")
        )

    # NFT
    elif promo["type"] == "NFT":

        nft_id = promo["nft_id"]

        if nft_id not in NFTS:

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

    else:

        await message.answer(
            "❌ Неизвестный тип промокода."
        )

        await state.clear()

        return

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
        f"🎟 Активации: "
        f"<b>{activation_text}</b>",
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# 🛠 АДМИН-ПАНЕЛЬ
# =========================================================

def admin_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🎟 Создать промокод",
        callback_data="create_promo"
    )

    kb.button(
        text="🗑 Удалить промокод",
        callback_data="admin_delete_promo"
    )

    kb.button(
        text="📋 Список промокодов",
        callback_data="admin_promo_list"
    )

    kb.button(
        text="🎁 Выдать NFT",
        callback_data="admin_give_nft"
    )

    kb.button(
        text="⭐ Выдать звёзды",
        callback_data="admin_give_stars"
    )

    kb.button(
        text="🗑 Забрать NFT",
        callback_data="admin_remove_nft"
    )

    kb.button(
        text="💰 Изменить баланс",
        callback_data="admin_set_balance"
    )

    kb.button(
        text="👤 Информация об игроке",
        callback_data="admin_user_info"
    )

    kb.button(
        text="🔄 Сделать ресток",
        callback_data="admin_restock"
    )

    kb.button(
        text="📊 Статистика",
        callback_data="admin_stats"
    )

    kb.button(
        text="📢 Рассылка",
        callback_data="admin_broadcast"
    )

    kb.button(
        text="◀️ Назад",
        callback_data="back_main"
    )

    kb.adjust(1)

    return kb.as_markup()


@dp.callback_query(F.data == "admin")
async def admin_panel(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    await state.clear()

    await callback.message.edit_text(
        "🛠 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# АДМИН — СПИСОК ПРОМОКОДОВ
# =========================================================

@dp.callback_query(F.data == "admin_promo_list")
async def admin_promo_list(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    if not promo_codes:

        text = (
            "📋 <b>ПРОМОКОДЫ</b>\n\n"
            "Промокодов пока нет."
        )

    else:

        lines = []

        for code, promo in promo_codes.items():

            if promo["type"] == "STARS":

                reward = (
                    f"{promo['stars']:,}"
                    .replace(",", " ")
                    + " ⭐"
                )

            else:

                nft_id = promo["nft_id"]

                if nft_id in NFTS:
                    reward = NFTS[nft_id]["name"]
                else:
                    reward = "Удалённый NFT"

            if promo["activations"] == "infinite":
                activation = "♾"
            else:
                activation = (
                    f"{promo['used']}/"
                    f"{promo['activations']}"
                )

            lines.append(
                f"🎟 <code>{code}</code>\n"
                f"🎁 {reward}\n"
                f"🔢 {activation}"
            )

        text = (
            "📋 <b>СПИСОК ПРОМОКОДОВ</b>\n\n"
            + "\n\n".join(lines)
        )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="◀️ Назад",
        callback_data="admin"
    )

    await callback.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# АДМИН — УДАЛЕНИЕ ПРОМОКОДА
# =========================================================

@dp.callback_query(F.data == "admin_delete_promo")
async def admin_delete_promo(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    if not promo_codes:

        await callback.answer(
            "Промокодов пока нет!",
            show_alert=True
        )

        return

    kb = InlineKeyboardBuilder()

    for code in promo_codes:

        kb.button(
            text=f"🗑 {code}",
            callback_data=f"delete_promo:{code}"
        )

    kb.button(
        text="◀️ Назад",
        callback_data="admin"
    )

    kb.adjust(1)

    await callback.message.edit_text(
        "🗑 <b>Удаление промокода</b>\n\n"
        "Выберите промокод:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("delete_promo:")
)
async def delete_promo(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    code = callback.data.split(
        ":",
        1
    )[1]

    if code not in promo_codes:

        await callback.answer(
            "Промокод уже удалён!",
            show_alert=True
        )

        return

    promo_codes.pop(
        code,
        None
    )

    promo_users.pop(
        code,
        None
    )

    await callback.message.edit_text(
        f"✅ Промокод <code>{code}</code> удалён.",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

    await callback.answer(
        "Промокод удалён!"
    )


# =========================================================
# АДМИН — ВЫДАТЬ NFT
# =========================================================

@dp.callback_query(F.data == "admin_give_nft")
async def admin_give_nft(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    await state.clear()

    await state.set_state(
        PromoCreate.admin_give_nft_user
    )

    await callback.message.edit_text(
        "🎁 <b>Выдать NFT</b>\n\n"
        "Введите Telegram ID игрока:",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(PromoCreate.admin_give_nft_user)
async def admin_give_nft_user(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():

        await message.answer(
            "❌ Telegram ID должен быть числом."
        )

        return

    user_id = int(
        message.text.strip()
    )

    await state.update_data(
        target_user=user_id
    )

    await state.set_state(
        PromoCreate.admin_give_nft_select
    )

    kb = InlineKeyboardBuilder()

    for nft_id, nft in NFTS.items():

        kb.button(
            text=nft["name"],
            callback_data=f"admingive:{nft_id}"
        )

    kb.button(
        text="❌ Отмена",
        callback_data="admin"
    )

    kb.adjust(1)

    await message.answer(
        "🎁 <b>Выберите NFT:</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@dp.callback_query(
    PromoCreate.admin_give_nft_select,
    F.data.startswith("admingive:")
)
async def admin_give_nft_selected(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await state.clear()
        return

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

    data = await state.get_data()

    user_id = data["target_user"]

    owned_nfts[user_id].append(
        nft_id
    )

    nft = NFTS[nft_id]

    known_users.add(user_id)

    await state.clear()

    await callback.message.edit_text(
        "✅ <b>NFT выдан!</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"🎁 NFT: <b>{nft['name']}</b>",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

    await callback.answer(
        "NFT выдан!"
    )


# =========================================================
# АДМИН — ВЫДАТЬ ЗВЁЗДЫ
# =========================================================

@dp.callback_query(F.data == "admin_give_stars")
async def admin_give_stars(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    await state.clear()

    await state.set_state(
        PromoCreate.admin_give_stars_user
    )

    await callback.message.edit_text(
        "⭐ <b>Выдать звёзды</b>\n\n"
        "Введите Telegram ID игрока:",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(PromoCreate.admin_give_stars_user)
async def admin_give_stars_user(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    user_id = int(
        message.text.strip()
    )

    await state.update_data(
        target_user=user_id
    )

    await state.set_state(
        PromoCreate.admin_give_stars_amount
    )

    await message.answer(
        "⭐ <b>Введите количество звёзд:</b>",
        parse_mode="HTML"
    )


@dp.message(PromoCreate.admin_give_stars_amount)
async def admin_give_stars_amount(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():

        await message.answer(
            "❌ Количество должно быть числом."
        )

        return

    amount = int(
        message.text.strip()
    )

    if amount <= 0:

        await message.answer(
            "❌ Количество должно быть больше нуля."
        )

        return

    data = await state.get_data()

    user_id = data["target_user"]

    balances[user_id] += amount

    known_users.add(user_id)

    await state.clear()

    await message.answer(
        "✅ <b>Звёзды выданы!</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"⭐ Выдано: <b>+{amount:,}</b>".replace(",", " "),
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )


# =========================================================
# АДМИН — ЗАБРАТЬ NFT
# =========================================================

@dp.callback_query(F.data == "admin_remove_nft")
async def admin_remove_nft(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    await state.clear()

    await state.set_state(
        PromoCreate.admin_remove_nft_user
    )

    await callback.message.edit_text(
        "🗑 <b>Забрать NFT</b>\n\n"
        "Введите Telegram ID игрока:",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(PromoCreate.admin_remove_nft_user)
async def admin_remove_nft_user(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    user_id = int(
        message.text.strip()
    )

    await state.update_data(
        target_user=user_id
    )

    await state.set_state(
        PromoCreate.admin_remove_nft_select
    )

    kb = InlineKeyboardBuilder()

    nft_ids = list(
        dict.fromkeys(
            owned_nfts[user_id]
        )
    )

    for nft_id in nft_ids:

        if nft_id not in NFTS:
            continue

        kb.button(
            text=f"🗑 {NFTS[nft_id]['name']}",
            callback_data=f"adminremove:{nft_id}"
        )

    kb.button(
        text="❌ Отмена",
        callback_data="admin"
    )

    kb.adjust(1)

    if not nft_ids:

        await state.clear()

        await message.answer(
            "❌ У этого игрока нет NFT.",
            reply_markup=admin_menu()
        )

        return

    await message.answer(
        "🗑 <b>Выберите NFT, который забрать:</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@dp.callback_query(
    PromoCreate.admin_remove_nft_select,
    F.data.startswith("adminremove:")
)
async def admin_remove_nft_selected(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await state.clear()
        return

    nft_id = callback.data.split(
        ":",
        1
    )[1]

    data = await state.get_data()

    user_id = data["target_user"]

    if nft_id not in owned_nfts[user_id]:

        await callback.answer(
            "У игрока нет этого NFT!",
            show_alert=True
        )

        return

    owned_nfts[user_id].remove(
        nft_id
    )

    if equipped_nft.get(user_id) == nft_id:

        equipped_nft.pop(
            user_id,
            None
        )

    nft = NFTS[nft_id]

    await state.clear()

    await callback.message.edit_text(
        "✅ <b>NFT забран!</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"🗑 NFT: <b>{nft['name']}</b>",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

    await callback.answer(
        "NFT забран!"
    )


# =========================================================
# АДМИН — ИЗМЕНИТЬ БАЛАНС
# =========================================================

@dp.callback_query(F.data == "admin_set_balance")
async def admin_set_balance(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    await state.clear()

    await state.set_state(
        PromoCreate.admin_set_balance_user
    )

    await callback.message.edit_text(
        "💰 <b>Изменение баланса</b>\n\n"
        "Введите Telegram ID игрока:",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(PromoCreate.admin_set_balance_user)
async def admin_set_balance_user(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    user_id = int(
        message.text.strip()
    )

    await state.update_data(
        target_user=user_id
    )

    await state.set_state(
        PromoCreate.admin_set_balance_amount
    )

    await message.answer(
        "💰 <b>Введите новый баланс:</b>",
        parse_mode="HTML"
    )


@dp.message(PromoCreate.admin_set_balance_amount)
async def admin_set_balance_amount(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():

        await message.answer(
            "❌ Баланс должен быть числом."
        )

        return

    amount = int(
        message.text.strip()
    )

    data = await state.get_data()

    user_id = data["target_user"]

    balances[user_id] = amount

    known_users.add(user_id)

    await state.clear()

    await message.answer(
        "✅ <b>Баланс изменён!</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"⭐ Новый баланс: <b>{amount:,}</b>".replace(",", " "),
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )


# =========================================================
# АДМИН — ИНФОРМАЦИЯ ОБ ИГРОКЕ
# =========================================================

@dp.callback_query(F.data == "admin_user_info")
async def admin_user_info(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    await state.clear()

    await state.set_state(
        PromoCreate.admin_user_info
    )

    await callback.message.edit_text(
        "👤 <b>Информация об игроке</b>\n\n"
        "Введите Telegram ID:",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(PromoCreate.admin_user_info)
async def admin_user_info_result(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    user_id = int(
        message.text.strip()
    )

    initialize_beta_inventory(
        user_id
    )

    nft_ids = list(
        dict.fromkeys(
            owned_nfts[user_id]
        )
    )

    active = get_equipped_nft(
        user_id
    )

    if active:

        active_text = (
            f"{active['name']} "
            f"(+{active.get('bonus', 0)} ⭐)"
        )

    else:

        active_text = "Нет"

    nft_names = []

    for nft_id in nft_ids:

        if nft_id in NFTS:

            nft_names.append(
                NFTS[nft_id]["name"]
            )

    if not nft_names:

        nft_text = "Нет NFT"

    else:

        nft_text = "\n".join(
            f"• {name}"
            for name in nft_names
        )

    await state.clear()

    await message.answer(
        "👤 <b>ИНФОРМАЦИЯ ОБ ИГРОКЕ</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"⭐ Баланс: <b>{balances[user_id]:,}</b>\n"
        f"🟢 Активный NFT: <b>{active_text}</b>\n\n"
        f"🎒 <b>NFT:</b>\n{nft_text}",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )


# =========================================================
# АДМИН — РЕСТОК
# =========================================================

@dp.callback_query(F.data == "admin_restock")
async def admin_restock(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    make_restock()

    await callback.message.edit_text(
        "🔄 <b>Ресток выполнен!</b>\n\n"
        "Новый сток магазина создан.",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

    await callback.answer(
        "Ресток выполнен!"
    )


# =========================================================
# АДМИН — СТАТИСТИКА
# =========================================================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    total_nfts = sum(
        len(
            set(
                nfts
            )
        )
        for nfts in owned_nfts.values()
    )

    total_promo = len(
        promo_codes
    )

    stock_count = sum(
        stock.values()
    )

    await callback.message.edit_text(
        "📊 <b>СТАТИСТИКА NFT CLICKER</b>\n\n"
        f"👥 Известных игроков: "
        f"<b>{len(known_users)}</b>\n"
        f"🎁 NFT у игроков: "
        f"<b>{total_nfts}</b>\n"
        f"🎟 Промокодов: "
        f"<b>{total_promo}</b>\n"
        f"🛒 NFT в магазине: "
        f"<b>{stock_count}</b>\n"
        f"📖 NFT в индексе: "
        f"<b>{len(NFTS)}</b>",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# АДМИН — РАССЫЛКА
# =========================================================

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "⛔ Доступ запрещён!",
            show_alert=True
        )

        return

    await state.clear()

    await state.set_state(
        PromoCreate.admin_broadcast
    )

    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Напишите сообщение, которое "
        "нужно отправить всем известным "
        "игрокам.",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(PromoCreate.admin_broadcast)
async def admin_broadcast_send(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    if not message.text:

        await message.answer(
            "❌ Сообщение пустое."
        )

        return

    text = message.text

    success = 0
    failed = 0

    for user_id in list(known_users):

        try:

            await bot.send_message(
                user_id,
                text
            )

            success += 1

        except Exception as error:

            failed += 1

            logging.warning(
                "Не удалось отправить сообщение %s: %s",
                user_id,
                error
            )

        await asyncio.sleep(
            0.05
        )

    await state.clear()

    await message.answer(
        "📢 <b>Рассылка завершена!</b>\n\n"
        f"✅ Отправлено: <b>{success}</b>\n"
        f"❌ Не доставлено: <b>{failed}</b>",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logging.info(
        "⭐ NFT CLICKER запущен!"
    )

    asyncio.create_task(
        restock_loop()
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
