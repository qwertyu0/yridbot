import asyncio
import os
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7998832126

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не установлен")

session = AiohttpSession(proxy="socks5://127.0.0.1:10808")
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()

user_mode = {}


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
            [KeyboardButton(text="Рассылка")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


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
- Не выдумывай статьи, если данных недостаточно.
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


@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "menu"

    await message.answer(
        "Здарова да",
        reply_markup=main_menu()
    )


@dp.message()
async def handle(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    mode = user_mode.get(user_id, "menu")

    if text == "/admin" and user_id == ADMIN_ID:
        user_mode[user_id] = "admin"
        await message.answer("Админ панель", reply_markup=admin_menu())
        return

    if mode == "admin":
        if text == "Рассылка":
            user_mode[user_id] = "broadcast"
            await message.answer("Отправь сообщение для рассылки")
            return

        if text == "Назад":
            user_mode[user_id] = "menu"
            await message.answer("Меню", reply_markup=main_menu())
            return

    if mode == "broadcast" and user_id == ADMIN_ID:
        await message.answer(
            "Рассылка отключена в этой упрощённой версии.",
            reply_markup=admin_menu()
        )
        user_mode[user_id] = "admin"
        return

    if text == "Юридический помощник":
        user_mode[user_id] = "helper"
        await message.answer(
            "Режим юриста \nОпишите ситуацию:",
            reply_markup=helper_menu()
        )
        return

    if text == "Что-то мб будет хз":
        await message.answer("Ничо")
        return

    if text == "Назад":
        user_mode[user_id] = "menu"
        await message.answer("Меню", reply_markup=main_menu())
        return

    if mode == "helper":
        if text == "Пример":
            await message.answer("Пример:\nЧеловек украл телефон в магазине")
            return

        if text == "Помощь":
            await message.answer(
                "Опишите ситуацию словами.\n"
                "Например:\n"
                "- Человек украл телефон в магазине\n"
                "- Человек избил другого на улице"
            )
            return

        await message.answer("Анализирую...")

        result = analyze_with_ollama(text)
        result = clean_response(result)

        await message.answer(
            f"{result}\n\nбебебе."
        )
        return

    await message.answer("Выбери режим", reply_markup=main_menu())


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())