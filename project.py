import asyncio
import os
import requests

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

embedding = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

db = Chroma(
    persist_directory="db",
    embedding_function=embedding
)

docs = db.similarity_search(user_text, k=3)




TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не установлен")

bot = Bot(token=TOKEN)
dp = Dispatcher()

session = AiohttpSession(proxy="socks5://127.0.0.1:10808")
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()

# состояние
user_state = {}
user_last_message = {}  #чтобы редактировать одно сообщение

# КНОПКИ
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="УК РФ", callback_data="law_uk")],
        [InlineKeyboardButton(text="КоАП РФ", callback_data="law_koap")],
        [InlineKeyboardButton(text="ФЗ РФ", callback_data="law_fz")]
    ])


def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


# ИИ
def ask_ai(text: str, law: str) -> str:
    try:
        # поиск похожих фрагментов закона
        docs = db.similarity_search(text, k=3)
        context = "\n\n".join([d.page_content for d in docs])

        prompt = f"""
Ты юридический помощник РФ.

Работай только по:
{law}

Используй ТОЛЬКО информацию из контекста.

Контекст:
{context}

Правила:
- Только РФ
- Без лишнего текста
- Не пиши советы
- Не выдумывай статьи
- Если информации нет:
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
            timeout=60
        )

        r.raise_for_status()

        return r.json().get("response", "Ошибка ИИ")

    except Exception as e:
        return f"Ошибка ИИ: {e}"


# СТАРТ
@dp.message(CommandStart())
async def start(msg: types.Message):
    user_state[msg.from_user.id] = None

    sent = await msg.answer(
        "Привет \nВыбери раздел:",
        reply_markup=main_menu()
    )

    user_last_message[msg.from_user.id] = sent.message_id


#кнопки
@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    user_id = call.from_user.id
    message_id = user_last_message.get(user_id)

    if call.data == "back":
        user_state[user_id] = None

        await bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="Привет \nВыбери раздел:",
            reply_markup=main_menu()
        )
        return

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
            text=f"Выбран режим: {law}\n\nОпишите ситуацию:",
            reply_markup=back_menu()
        )



#ТЕКСТ
@dp.message()
async def handle(msg: types.Message):
    user_id = msg.from_user.id
    text = (msg.text or "").strip()

    law = user_state.get(user_id)

    # режим не выбран
    if not law:
        await msg.answer("Сначала выбери раздел выше 👆")
        return

    #вызов ии
    await msg.answer("Анализирую...")

    result = ask_ai(text, law)

    await msg.answer(
        f"{result}\n\n⚠️ Не является юридической консультацией"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
