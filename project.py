import asyncio
import sqlite3
import requests
import re

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession

# =========================
# НАСТРОЙКИ
# =========================
TOKEN = "8652819384:AAG6aioB9qL2U-I5wnOoxDSnTMIhBeprQqY"
ADMIN_ID = 7998832126

# Xray SOCKS5 proxy
session = AiohttpSession(proxy="socks5://127.0.0.1:10808")
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()

# =========================
# БАЗА ДАННЫХ
# =========================
conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    is_banned INTEGER DEFAULT 0
)
""")
conn.commit()


def add_user(user_id: int) -> None:
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )
    conn.commit()


def ban_user(user_id: int) -> None:
    cursor.execute(
        "UPDATE users SET is_banned = 1 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()


def unban_user(user_id: int) -> None:
    cursor.execute(
        "UPDATE users SET is_banned = 0 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()


def is_banned(user_id: int) -> bool:
    cursor.execute(
        "SELECT is_banned FROM users WHERE user_id = ?",
        (user_id,)
    )
    result = cursor.fetchone()
    return bool(result and result[0] == 1)


def get_all_users() -> list[int]:
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]


def get_users_count() -> int:
    cursor.execute("SELECT COUNT(*) FROM users")
    result = cursor.fetchone()
    return result[0] if result else 0


# =========================
# СОСТОЯНИЕ ПОЛЬЗОВАТЕЛЕЙ
# =========================
user_mode = {}


# =========================
# КЛАВИАТУРЫ
# =========================
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


ARTICLES = {
    "105": "Статья: 105 УК РФ\nОписание: Убийство.",
    "111": "Статья: 111 УК РФ\nОписание: Умышленное причинение тяжкого вреда здоровью.",
    "112": "Статья: 112 УК РФ\nОписание: Умышленное причинение средней тяжести вреда здоровью.",
    "115": "Статья: 115 УК РФ\nОписание: Умышленное причинение легкого вреда здоровью.",
    "116": "Статья: 116 УК РФ\nОписание: Побои.",
    "158": "Статья: 158 УК РФ\nОписание: Кража.",
    "159": "Статья: 159 УК РФ\nОписание: Мошенничество.",
    "161": "Статья: 161 УК РФ\nОписание: Грабеж.",
    "162": "Статья: 162 УК РФ\nОписание: Разбой.",
    "163": "Статья: 163 УК РФ\nОписание: Вымогательство.",
    "167": "Статья: 167 УК РФ\nОписание: Умышленные уничтожение или повреждение имущества.",
    "228": "Статья: 228 УК РФ\nОписание: Незаконные приобретение, хранение, перевозка, изготовление, переработка наркотических средств, психотропных веществ или их аналогов.",
    "264": "Статья: 264 УК РФ\nОписание: Нарушение правил дорожного движения и эксплуатации транспортных средств."
}


def find_article_by_number(text: str) -> str | None:
    text = text.lower().strip()

    match = re.search(r"(?:статья\s*)?(\d{2,3}(?:\.\d+)?)", text)
    if not match:
        return None

    article_number = match.group(1)

    if article_number in ARTICLES:
        return ARTICLES[article_number]

    return f"Статья: {article_number}\nОписание: Нет в локальной базе. Нужна ручная проверка."


def clean_response(result: str) -> str:
    lines = result.splitlines()
    filtered = []

    for line in lines:
        line = line.strip()
        if line.startswith("Статья:") or line.startswith("Описание:"):
            filtered.append(line)

    if not filtered:
        return "Статья: Не определено\nОписание: Недостаточно данных для точного определения статьи."

    return "\n".join(filtered)



# =========================
# OLLAMA
# =========================

def analyze_with_ollama(text: str) -> str:
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": f"""
Ты юридический помощник по законодательству РФ.

Правила:
- Отвечай только на русском языке.
- Отвечай только по законодательству РФ.
- Не добавляй лишний текст.
- Не пиши вступления, выводы и советы.
- Если пользователь прислал просто номер статьи, не выдумывай содержание.
- Если данных недостаточно, пиши:
Статья: Не определено
Описание: Недостаточно данных для точного определения статьи.

Формат ответа строго такой:
Статья: ...
Описание: ...

Описание ситуации:
{text}
""",
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "Ошибка: пустой ответ от ИИ")
    except Exception as e:
        return f"Ошибка ИИ: {e}"

def clean_response(result: str) -> str:
    lines = result.splitlines()
    filtered = []

    for line in lines:
        line = line.strip()
        if line.startswith("Статья:") or line.startswith("Описание:"):
            filtered.append(line)

    if not filtered:
        return "Статья: Не определено\nОписание: Недостаточно данных для точного определения статьи."

    return "\n".join(filtered)

# =========================
# СТАРТ
# =========================
@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id

    add_user(user_id)

    if is_banned(user_id):
        await message.answer("Ты заблокирован ❌")
        return

    user_mode[user_id] = "menu"
    await message.answer("Привет 👋", reply_markup=main_menu())


# =========================
# ОБРАБОТКА СООБЩЕНИЙ
# =========================
@dp.message()
async def handle(message: types.Message):
    user_id = message.from_user.id
    text = message.text or ""

    add_user(user_id)

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
            await message.answer(f"Всего пользователей: {get_users_count()}")
            return

        if text.startswith("/ban"):
            try:
                uid = int(text.split()[1])
                ban_user(uid)
                await message.answer(f"Пользователь {uid} забанен")
            except Exception:
                await message.answer("Используй: /ban user_id")
            return

        if text.startswith("/unban"):
            try:
                uid = int(text.split()[1])
                unban_user(uid)
                await message.answer(f"Пользователь {uid} разбанен")
            except Exception:
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
        sent_count = 0

        for u in get_all_users():
            try:
                await bot.send_message(u, f"📢 {text}")
                sent_count += 1
            except Exception:
                pass

        user_mode[user_id] = "admin"
        await message.answer(
            f"Рассылка завершена. Отправлено: {sent_count}",
            reply_markup=admin_menu()
        )
        return

    # --- ПОЛЬЗОВАТЕЛЬСКИЕ РЕЖИМЫ ---
    if text == "Юридический помощник":
        user_mode[user_id] = "helper"
        await message.answer(
            "Режим юриста ⚖️\nОпиши ситуацию:",
            reply_markup=helper_menu()
        )
        return

    if text == "Что-то мб будет хз":
        await message.answer("Этот раздел пока в разработке 🚧")
        return

    if text == "Назад":
        user_mode[user_id] = "menu"
        await message.answer("Меню", reply_markup=main_menu())
        return

    # --- РЕЖИМ ЮРИСТА ---
    if mode == "helper":
        if text == "Пример":
            await message.answer("Пример:\nЧеловек украл телефон в магазине")
            return

        if text == "Помощь":
            await message.answer(
                "Можно написать либо описание ситуации, либо номер статьи.\n"
                "Например:\n"
                "- Человек украл телефон в магазине\n"
                "- 228 УК РФ"
            )
            return

        await message.answer("Анализирую...")

        article_result = find_article_by_number(text)
        if article_result:
            await message.answer(
                f"{article_result}\n\n⚠️ Это не является юридической консультацией."
            )
            return

        result = analyze_with_ollama(text)
        result = clean_response(result)

        await message.answer(
            f"{result}\n\n⚠️ Это не является юридической консультацией."
        )
        return

    await message.answer("Выбери режим", reply_markup=main_menu())


# =========================
# ЗАПУСК
# =========================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())