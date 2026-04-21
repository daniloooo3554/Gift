import asyncio
import random
import re
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# ================= НАСТРОЙКИ =================
API_TOKEN = "8566175880:AAHA_MyUBVkZs_QSPAk0jcKoK-DAVvnG4Z8"
MAIN_PHOTO_URL = "https://i.ibb.co/JWDJrdD1/photo-2026-04-21-15-13-29.jpg"
ADMIN_ID = 7951599567
SECRET_PHRASE = "НАСА"
STATS_FILE = "bot_stats.json"

# === НАСТРОЙКИ ДЛЯ RENDER ===
# Замени 'YOUR_RENDER_APP_NAME' на имя твоего сервиса на Render
RENDER_APP_NAME = "YOUR_RENDER_APP_NAME" 
WEBHOOK_URL = f"https://{RENDER_APP_NAME}.onrender.com/webhook"
# =============================

class Form(StatesGroup):
    waiting_for_username = State()

GIFTS = {
    1: "Мишка",
    2: "Конфеты",
    3: "Машина",
    4: "Розы",
    5: "Торт",
    6: "Букет",
}

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)
user_results = {}

# --- Функции для статистики (без изменений) ---
def get_default_stats():
    return {
        "total_starts": 0,
        "total_dice_throws": 0,
        "total_claims": 0,
        "total_usernames_submitted": 0,
        "daily_stats": {},
        "gift_stats": {gift: 0 for gift in GIFTS.values()},
        "dice_value_stats": {str(i): 0 for i in range(1, 7)},
        "users": []
    }

stats = get_default_stats()

def load_stats():
    global stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                loaded_stats = json.load(f)
                for key in stats:
                    if key in loaded_stats:
                        stats[key] = loaded_stats[key]
        except:
            pass

def save_stats():
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except:
        pass

def update_daily_stats(event_type: str):
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in stats["daily_stats"]:
        stats["daily_stats"][today] = {
            "starts": 0,
            "throws": 0,
            "claims": 0,
            "usernames": 0
        }
    if event_type == "start":
        stats["daily_stats"][today]["starts"] += 1
    elif event_type == "throw":
        stats["daily_stats"][today]["throws"] += 1
    elif event_type == "claim":
        stats["daily_stats"][today]["claims"] += 1
    elif event_type == "username":
        stats["daily_stats"][today]["usernames"] += 1
# --- Конец функций статистики ---

def get_dice_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Бросить кубик", callback_data="throw_dice")
    return builder.as_markup()

def get_continue_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Забрать подарок", callback_data="claim_gift")
    return builder.as_markup()

def get_cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data="cancel_username")
    return builder.as_markup()

# === ВАЖНО: Эндпоинт для «будильника» ===
async def health_check(request):
    return web.Response(text="OK")
# ======================================

# --- Обработчики команд (без изменений, как в твоем коде) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # ... (весь код функции cmd_start из предыдущей версии) ...
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or ""
    
    stats["total_starts"] += 1
    update_daily_stats("start")
    
    user_exists = False
    for user in stats["users"]:
        if user["id"] == user_id:
            user_exists = True
            user["last_seen"] = datetime.now().isoformat()
            user["starts_count"] += 1
            break
    
    if not user_exists:
        stats["users"].append({
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "starts_count": 1,
            "throws_count": 0,
            "claims_count": 0
        })
    
    save_stats()
    
    caption = "Твой подарок\nБрось кубик и получи подарок"
    await message.answer_photo(
        photo=MAIN_PHOTO_URL,
        caption=caption,
        reply_markup=get_dice_keyboard()
    )

@dp.callback_query(lambda c: c.data == "throw_dice")
async def process_throw_dice(callback: CallbackQuery):
    # ... (весь код функции process_throw_dice) ...
    await callback.answer()
    user_id = callback.from_user.id
    
    dice_msg = await bot.send_dice(
        chat_id=callback.message.chat.id,
        emoji="🎲"
    )
    
    await asyncio.sleep(4)
    dice_value = dice_msg.dice.value
    
    user_results[user_id] = dice_value
    gift_name = GIFTS[dice_value]
    
    stats["total_dice_throws"] += 1
    stats["dice_value_stats"][str(dice_value)] = stats["dice_value_stats"].get(str(dice_value), 0) + 1
    update_daily_stats("throw")
    
    for user in stats["users"]:
        if user["id"] == user_id:
            user["throws_count"] += 1
            break
    
    save_stats()
    
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"Ты выбросил: {dice_value}\nИ выиграл: {gift_name}!",
        reply_markup=get_continue_keyboard()
    )

@dp.callback_query(lambda c: c.data == "claim_gift")
async def process_claim_gift(callback: CallbackQuery, state: FSMContext):
    # ... (весь код функции process_claim_gift) ...
    user_id = callback.from_user.id
    dice_value = user_results.get(user_id, 1)
    gift_name = GIFTS[dice_value]
    
    stats["total_claims"] += 1
    stats["gift_stats"][gift_name] = stats["gift_stats"].get(gift_name, 0) + 1
    update_daily_stats("claim")
    
    for user in stats["users"]:
        if user["id"] == user_id:
            user["claims_count"] += 1
            break
    
    save_stats()
    
    await callback.answer()
    await state.update_data(gift_name=gift_name, dice_value=dice_value)
    await state.set_state(Form.waiting_for_username)
    
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"Ты выиграл: {gift_name}\n\nУкажи свой username:\nНапример: @username",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(Form.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    # ... (весь код функции process_username) ...
    user_id = message.from_user.id
    username_input = message.text.strip()
    
    pattern = r'^@[A-Za-z0-9_]{5,32}$'
    
    if not re.match(pattern, username_input):
        await message.answer(
            "Неверный формат username!\nUsername должен начинаться с @\nНапример: @username\n\nПопробуй ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    gift_name = data.get("gift_name", "подарок")
    
    stats["total_usernames_submitted"] += 1
    update_daily_stats("username")
    
    for user in stats["users"]:
        if user["id"] == user_id:
            user["submitted_username"] = username_input
            user["won_gift"] = gift_name
            user["submitted_time"] = datetime.now().isoformat()
            break
    
    save_stats()
    await state.clear()
    
    await message.answer(
        f"Отлично! Твой username: {username_input}\n\n"
        f"Твой подарок: {gift_name}\n\n"
        f"Подарок будет отправлен в течение 48 часов!\n"
        f"Мы свяжемся с тобой в Telegram.\n\n"
        f"Спасибо за участие!",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Новый выигрыш!\nПользователь: {username_input}\nПодарок: {gift_name}\nВыпало: {data.get('dice_value', '?')}"
    )

@dp.callback_query(lambda c: c.data == "cancel_username")
async def cancel_username(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Отменено")
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="Получение подарка отменено.\nНапиши /start чтобы сыграть снова!"
    )

@dp.message(lambda message: message.text and message.text.upper() == SECRET_PHRASE)
async def send_stats_to_admin(message: types.Message):
    # ... (весь код функции send_stats_to_admin) ...
    if message.from_user.id != ADMIN_ID:
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_stats = stats["daily_stats"].get(today, {
        "starts": 0, "throws": 0, "claims": 0, "usernames": 0
    })
    
    today_users = set()
    for user in stats["users"]:
        if user.get("first_seen", "").startswith(today):
            today_users.add(user["id"])
    
    top_gifts = sorted(stats["gift_stats"].items(), key=lambda x: x[1], reverse=True)[:3]
    top_gifts_text = "\n".join([f"{i+1}. {gift}: {count}" for i, (gift, count) in enumerate(top_gifts) if count > 0]) or "Нет данных"
    
    recent_users = sorted(stats["users"], key=lambda x: x.get("last_seen", ""), reverse=True)[:5]
    recent_text = ""
    for user in recent_users:
        username = user.get("username", "без username")
        gift = user.get("won_gift", "-")
        recent_text += f"@{username} -> {gift}\n"
    
    stats_text = (
        f"СТАТИСТИКА БОТА\n\n"
        f"ОБЩАЯ:\n"
        f"/start: {stats['total_starts']}\n"
        f"Бросков: {stats['total_dice_throws']}\n"
        f"Подарков: {stats['total_claims']}\n"
        f"Username: {stats['total_usernames_submitted']}\n"
        f"Пользователей: {len(stats['users'])}\n\n"
        f"ЗА СЕГОДНЯ ({today}):\n"
        f"Новых: {len(today_users)}\n"
        f"/start: {today_stats['starts']}\n"
        f"Бросков: {today_stats['throws']}\n"
        f"Подарков: {today_stats['claims']}\n"
        f"Username: {today_stats['usernames']}\n\n"
        f"ВЫПАДЕНИЕ:\n"
        f"1:{stats['dice_value_stats'].get('1',0)} 2:{stats['dice_value_stats'].get('2',0)} 3:{stats['dice_value_stats'].get('3',0)}\n"
        f"4:{stats['dice_value_stats'].get('4',0)} 5:{stats['dice_value_stats'].get('5',0)} 6:{stats['dice_value_stats'].get('6',0)}\n\n"
        f"ТОП ПОДАРКОВ:\n{top_gifts_text}\n\n"
        f"ПОСЛЕДНИЕ:\n{recent_text}"
    )
    
    await message.answer(stats_text)

# --- Функции для запуска вебхука ---
async def on_startup(bot: Bot):
    load_stats()
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Вебхук установлен на: {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()

def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app = web.Application()
    # Регистрируем эндпоинт для вебхука Telegram
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    # Регистрируем эндпоинт для «будильника» cron-job.org
    app.router.add_get("/", health_check)
    setup_application(app, dp, bot=bot)
    
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    main()import asyncio
import random
import re
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# ================= НАСТРОЙКИ =================
API_TOKEN = "8566175880:AAHA_MyUBVkZs_QSPAk0jcKoK-DAVvnG4Z8"
MAIN_PHOTO_URL = "https://i.ibb.co/JWDJrdD1/photo-2026-04-21-15-13-29.jpg"
ADMIN_ID = 7951599567
SECRET_PHRASE = "НАСА"
STATS_FILE = "bot_stats.json"

# === НАСТРОЙКИ ДЛЯ RENDER ===
# Замени 'YOUR_RENDER_APP_NAME' на имя твоего сервиса на Render
RENDER_APP_NAME = "YOUR_RENDER_APP_NAME" 
WEBHOOK_URL = f"https://{RENDER_APP_NAME}.onrender.com/webhook"
# =============================

class Form(StatesGroup):
    waiting_for_username = State()

GIFTS = {
    1: "Мишка",
    2: "Конфеты",
    3: "Машина",
    4: "Розы",
    5: "Торт",
    6: "Букет",
}

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)
user_results = {}

# --- Функции для статистики (без изменений) ---
def get_default_stats():
    return {
        "total_starts": 0,
        "total_dice_throws": 0,
        "total_claims": 0,
        "total_usernames_submitted": 0,
        "daily_stats": {},
        "gift_stats": {gift: 0 for gift in GIFTS.values()},
        "dice_value_stats": {str(i): 0 for i in range(1, 7)},
        "users": []
    }

stats = get_default_stats()

def load_stats():
    global stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                loaded_stats = json.load(f)
                for key in stats:
                    if key in loaded_stats:
                        stats[key] = loaded_stats[key]
        except:
            pass

def save_stats():
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except:
        pass

def update_daily_stats(event_type: str):
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in stats["daily_stats"]:
        stats["daily_stats"][today] = {
            "starts": 0,
            "throws": 0,
            "claims": 0,
            "usernames": 0
        }
    if event_type == "start":
        stats["daily_stats"][today]["starts"] += 1
    elif event_type == "throw":
        stats["daily_stats"][today]["throws"] += 1
    elif event_type == "claim":
        stats["daily_stats"][today]["claims"] += 1
    elif event_type == "username":
        stats["daily_stats"][today]["usernames"] += 1
# --- Конец функций статистики ---

def get_dice_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Бросить кубик", callback_data="throw_dice")
    return builder.as_markup()

def get_continue_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Забрать подарок", callback_data="claim_gift")
    return builder.as_markup()

def get_cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data="cancel_username")
    return builder.as_markup()

# === ВАЖНО: Эндпоинт для «будильника» ===
async def health_check(request):
    return web.Response(text="OK")
# ======================================

# --- Обработчики команд (без изменений, как в твоем коде) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # ... (весь код функции cmd_start из предыдущей версии) ...
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or ""
    
    stats["total_starts"] += 1
    update_daily_stats("start")
    
    user_exists = False
    for user in stats["users"]:
        if user["id"] == user_id:
            user_exists = True
            user["last_seen"] = datetime.now().isoformat()
            user["starts_count"] += 1
            break
    
    if not user_exists:
        stats["users"].append({
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "starts_count": 1,
            "throws_count": 0,
            "claims_count": 0
        })
    
    save_stats()
    
    caption = "Твой подарок\nБрось кубик и получи подарок"
    await message.answer_photo(
        photo=MAIN_PHOTO_URL,
        caption=caption,
        reply_markup=get_dice_keyboard()
    )

@dp.callback_query(lambda c: c.data == "throw_dice")
async def process_throw_dice(callback: CallbackQuery):
    # ... (весь код функции process_throw_dice) ...
    await callback.answer()
    user_id = callback.from_user.id
    
    dice_msg = await bot.send_dice(
        chat_id=callback.message.chat.id,
        emoji="🎲"
    )
    
    await asyncio.sleep(4)
    dice_value = dice_msg.dice.value
    
    user_results[user_id] = dice_value
    gift_name = GIFTS[dice_value]
    
    stats["total_dice_throws"] += 1
    stats["dice_value_stats"][str(dice_value)] = stats["dice_value_stats"].get(str(dice_value), 0) + 1
    update_daily_stats("throw")
    
    for user in stats["users"]:
        if user["id"] == user_id:
            user["throws_count"] += 1
            break
    
    save_stats()
    
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"Ты выбросил: {dice_value}\nИ выиграл: {gift_name}!",
        reply_markup=get_continue_keyboard()
    )

@dp.callback_query(lambda c: c.data == "claim_gift")
async def process_claim_gift(callback: CallbackQuery, state: FSMContext):
    # ... (весь код функции process_claim_gift) ...
    user_id = callback.from_user.id
    dice_value = user_results.get(user_id, 1)
    gift_name = GIFTS[dice_value]
    
    stats["total_claims"] += 1
    stats["gift_stats"][gift_name] = stats["gift_stats"].get(gift_name, 0) + 1
    update_daily_stats("claim")
    
    for user in stats["users"]:
        if user["id"] == user_id:
            user["claims_count"] += 1
            break
    
    save_stats()
    
    await callback.answer()
    await state.update_data(gift_name=gift_name, dice_value=dice_value)
    await state.set_state(Form.waiting_for_username)
    
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"Ты выиграл: {gift_name}\n\nУкажи свой username:\nНапример: @username",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(Form.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    # ... (весь код функции process_username) ...
    user_id = message.from_user.id
    username_input = message.text.strip()
    
    pattern = r'^@[A-Za-z0-9_]{5,32}$'
    
    if not re.match(pattern, username_input):
        await message.answer(
            "Неверный формат username!\nUsername должен начинаться с @\nНапример: @username\n\nПопробуй ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    gift_name = data.get("gift_name", "подарок")
    
    stats["total_usernames_submitted"] += 1
    update_daily_stats("username")
    
    for user in stats["users"]:
        if user["id"] == user_id:
            user["submitted_username"] = username_input
            user["won_gift"] = gift_name
            user["submitted_time"] = datetime.now().isoformat()
            break
    
    save_stats()
    await state.clear()
    
    await message.answer(
        f"Отлично! Твой username: {username_input}\n\n"
        f"Твой подарок: {gift_name}\n\n"
        f"Подарок будет отправлен в течение 48 часов!\n"
        f"Мы свяжемся с тобой в Telegram.\n\n"
        f"Спасибо за участие!",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Новый выигрыш!\nПользователь: {username_input}\nПодарок: {gift_name}\nВыпало: {data.get('dice_value', '?')}"
    )

@dp.callback_query(lambda c: c.data == "cancel_username")
async def cancel_username(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Отменено")
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="Получение подарка отменено.\nНапиши /start чтобы сыграть снова!"
    )

@dp.message(lambda message: message.text and message.text.upper() == SECRET_PHRASE)
async def send_stats_to_admin(message: types.Message):
    # ... (весь код функции send_stats_to_admin) ...
    if message.from_user.id != ADMIN_ID:
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_stats = stats["daily_stats"].get(today, {
        "starts": 0, "throws": 0, "claims": 0, "usernames": 0
    })
    
    today_users = set()
    for user in stats["users"]:
        if user.get("first_seen", "").startswith(today):
            today_users.add(user["id"])
    
    top_gifts = sorted(stats["gift_stats"].items(), key=lambda x: x[1], reverse=True)[:3]
    top_gifts_text = "\n".join([f"{i+1}. {gift}: {count}" for i, (gift, count) in enumerate(top_gifts) if count > 0]) or "Нет данных"
    
    recent_users = sorted(stats["users"], key=lambda x: x.get("last_seen", ""), reverse=True)[:5]
    recent_text = ""
    for user in recent_users:
        username = user.get("username", "без username")
        gift = user.get("won_gift", "-")
        recent_text += f"@{username} -> {gift}\n"
    
    stats_text = (
        f"СТАТИСТИКА БОТА\n\n"
        f"ОБЩАЯ:\n"
        f"/start: {stats['total_starts']}\n"
        f"Бросков: {stats['total_dice_throws']}\n"
        f"Подарков: {stats['total_claims']}\n"
        f"Username: {stats['total_usernames_submitted']}\n"
        f"Пользователей: {len(stats['users'])}\n\n"
        f"ЗА СЕГОДНЯ ({today}):\n"
        f"Новых: {len(today_users)}\n"
        f"/start: {today_stats['starts']}\n"
        f"Бросков: {today_stats['throws']}\n"
        f"Подарков: {today_stats['claims']}\n"
        f"Username: {today_stats['usernames']}\n\n"
        f"ВЫПАДЕНИЕ:\n"
        f"1:{stats['dice_value_stats'].get('1',0)} 2:{stats['dice_value_stats'].get('2',0)} 3:{stats['dice_value_stats'].get('3',0)}\n"
        f"4:{stats['dice_value_stats'].get('4',0)} 5:{stats['dice_value_stats'].get('5',0)} 6:{stats['dice_value_stats'].get('6',0)}\n\n"
        f"ТОП ПОДАРКОВ:\n{top_gifts_text}\n\n"
        f"ПОСЛЕДНИЕ:\n{recent_text}"
    )
    
    await message.answer(stats_text)

# --- Функции для запуска вебхука ---
async def on_startup(bot: Bot):
    load_stats()
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Вебхук установлен на: {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()

def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app = web.Application()
    # Регистрируем эндпоинт для вебхука Telegram
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    # Регистрируем эндпоинт для «будильника» cron-job.org
    app.router.add_get("/", health_check)
    setup_application(app, dp, bot=bot)
    
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    main()
