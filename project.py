import asyncio
import os
import requests

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не установлен")
#PROXY
session = AiohttpSession(
    proxy="socks5://127.0.0.1:10808"
)

bot = Bot(
    token=TOKEN,
    session=session
)

dp = Dispatcher()


#БАЗА ЗАКОНОВ

embedding = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

db = Chroma(
    persist_directory="db",
    embedding_function=embedding
)


user_state = {}
user_last_message = {}

# КНОПКИ
def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="УК РФ",
                    callback_data="law_uk"
                )
            ],
            [
                InlineKeyboardButton(
                    text="КоАП РФ",
                    callback_data="law_koap"
                )
            ],
            [
                InlineKeyboardButton(
                    text="ФЗ РФ",
                    callback_data="law_fz"
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹИнформация",
                    callback_data="info"
                )
            ]
        ]
    )


def back_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅ Назад",
                    callback_data="back"
                )
            ]
        ]
    )


# ИИ
def ask_ai(text: str, law: str) -> str:
    try:
        docs = db.similarity_search(text, k=3)

        context = "\n\n".join(
            [d.page_content for d in docs]
        )

        prompt = f"""
Ты юридический помощник РФ.

Работай ТОЛЬКО по:
{law}

Используй только информацию из контекста.

Контекст:
{context}

Правила:
- Только РФ
- Без лишнего текста
- Не пиши советы
- Не выдумывай статьи

Если информации недостаточно:
Статья: Не определено
Описание: Недостаточно данных

Формат ответа строго такой:

Статья: ...
Описание: ...

Ситуация:
{text}
"""

        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        r.raise_for_status()

        return r.json().get(
            "response",
            "Ошибка ИИ"
        )

    except Exception as e:
        return f"Ошибка ИИ: {e}"


# СТАРТ
@dp.message(CommandStart())
async def start(msg: types.Message):
    user_id = msg.from_user.id

    user_state[user_id] = None

    sent = await msg.answer(
        "Привет\n\nВыбери раздел:",
        reply_markup=main_menu()
    )

    user_last_message[user_id] = sent.message_id

# CALLBACK
@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    user_id = call.from_user.id

    message_id = user_last_message.get(user_id)

    # назад
    if call.data == "back":
        user_state[user_id] = None

        await bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="Привет\n\nВыбери раздел:",
            reply_markup=main_menu()
        )

        await call.answer()
        return

    # информация
    if call.data == "info":
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="""
ℹ️ Информация о боте

Версия: 1.0

ИИ:
Llama 3 через Ollama

Поддержка:
• УК РФ
• КоАП РФ
• ФЗ РФ

Поиск:
RAG + ChromaDB

База:
Текстовые документы законов РФ
""",
            reply_markup=back_menu()
        )

        await call.answer()
        return

    # режимы
    if call.data.startswith("law_"):
        law_map = {
            "law_uk": "УК РФ",
            "law_koap": "КоАП РФ",
            "law_fz": "ФЗ РФ"
        }

        law = law_map.get(call.data)

        user_state[user_id] = law

        await bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=f"""
Выбран режим:
{law}

Опишите ситуацию:
""",
            reply_markup=back_menu()
        )

        await call.answer()
        return

# ТЕКСТ
@dp.message()
async def handle(msg: types.Message):
    user_id = msg.from_user.id

    text = (msg.text or "").strip()

    law = user_state.get(user_id)

    if not law:
        await msg.answer(
            "Сначала выбери раздел выше"
        )
        return

    wait = await msg.answer(
        "Анализирую..."
    )

    result = ask_ai(text, law)

    await wait.delete()

    await msg.answer(
        f"""
{result}

Не является юридической консультацией
"""
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
