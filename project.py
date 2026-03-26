import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

import sqlite3

# --- БД ---
conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

def add_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def ban_user(user_id):
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def unban_user(user_id):
    cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

def is_banned(user_id):
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    is_banned INTEGER DEFAULT 0
)
""")

conn.commit()

TOKEN = "8652819384:AAG6aioB9qL2U-I5wnOoxDSnTMIhBeprQqY"
ADMIN_ID = 7998832126  # <-- ВСТАВЬ СВОЙ TELEGRAM ID

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_mode = {}
users = set()
banned_users = set()


# --- МЕНЮ ---
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Юридический помощник")],
            [KeyboardButton(text="Что-то мб будет хз")]
        ],
        resize_keyboard=True
    )


def helper_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пример")],
            [KeyboardButton(text="Помощь")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Список пользователей")],
            [KeyboardButton(text="Рассылка")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


# --- ИИ ---
def analyze_with_ollama(text):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": f"""
Ты юридический помощник РФ.

Описание: {text}

Ответ:
Статья:
Описание:
""",
                "stream": False
            }
        )
        return response.json()["response"]
    except:
        return "Ошибка ИИ"


# --- СТАРТ ---
@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id

    if user_id in banned_users:
        await message.answer("Ты заблокирован ❌")
        return

    add_user(user_id)
    user_mode[user_id] = "menu"

    await message.answer("Привет 👋", reply_markup=main_menu())


# --- ОБРАБОТКА ---
@dp.message()
async def handle(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # --- БАН ---
    if is_banned(user_id):
        await message.answer("Ты заблокирован ❌")
        return

    mode = user_mode.get(user_id, "menu")

    # --- ВХОД В АДМИНКУ ---
    if text == "/admin" and user_id == ADMIN_ID:
        user_mode[user_id] = "admin"
        await message.answer("Админ панель", reply_markup=admin_menu())
        return

    # --- АДМИНКА ---
    if mode == "admin":

        if text == "Список пользователей":
            await message.answer(f"Всего пользователей: {len(users)}")
            return

        if text.startswith("/ban"):
            try:
                uid = int(text.split()[1])
                ban_user(uid)
                await message.answer(f"Пользователь {uid} забанен")
            except:
                await message.answer("Используй: /ban user_id")
            return

        if text.startswith("/unban"):
            try:
                uid = int(text.split()[1])
                unban_user(uid)
                await message.answer(f"Пользователь {uid} разбанен")
            except:
                await message.answer("Используй: /unban user_id")
            return

        if text == "Рассылка":
            user_mode[user_id] = "broadcast"
            await message.answer("Отправь сообщение для рассылки")
            return

        if text == "Назад":
            user_mode[user_id] = "menu"
            await message.answer("Меню", reply_markup=main_menu())
            return

    # --- РАССЫЛКА ---
    if mode == "broadcast" and user_id == ADMIN_ID:
        for u in get_all_users():
            try:
                await bot.send_message(u, f"📢 {text}")
            except:
                pass

        user_mode[user_id] = "admin"
        await message.answer("Рассылка завершена", reply_markup=admin_menu())
        return

    # --- ПОЛЬЗОВАТЕЛЬ ---
    if text == "Юридический помощник":
        user_mode[user_id] = "helper"
        await message.answer("Режим юриста ⚖️", reply_markup=helper_menu())
        return

    if text == "Назад":
        user_mode[user_id] = "menu"
        await message.answer("Меню", reply_markup=main_menu())
        return

    if mode == "helper":
        await message.answer("Анализирую...")
        result = analyze_with_ollama(text)
        await message.answer(result)
        return

    await message.answer("Выбери режим", reply_markup=main_menu())


# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())