import logging
import os
import random
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from gtts import gTTS
from aiohttp import web

# ------------------ НАСТРОЙКА ------------------
TOKEN = os.getenv("BOT_TOKEN")
WORDS_FILE = "words.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------ СЛОВАРЬ ------------------
if os.path.exists(WORDS_FILE):
    with open(WORDS_FILE, "r", encoding="utf-8") as f:
        words = json.load(f)
else:
    words = {}

def save_words():
    with open(WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

adding_word_users = set()
current_quiz = {}  # {user_id: (eng, rus, reverse)}

# ------------------ START ------------------
@dp.message(Command(commands=["start"]))
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(text="➕ Добавить слово", callback_data="add"),
        InlineKeyboardButton(text="📖 Словарь", callback_data="list"),
        InlineKeyboardButton(text="📝 Квиз (англ→рус)", callback_data="quiz"),
        InlineKeyboardButton(text="📝 Квиз (рус→англ)", callback_data="quiz_reverse"),
    ]
    keyboard.add(*buttons)
    await message.answer("Привет! Выберите действие:", reply_markup=keyboard)

# ------------------ CALLBACKS ------------------
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    if data == "add":
        await bot.send_message(user_id, "Введите слово и перевод через дефис (пример: apple-яблоко):")
        adding_word_users.add(user_id)

    elif data == "list":
        if not words:
            await bot.send_message(user_id, "Словарь пуст!")
        else:
            reply = "\n".join([f"{eng} → {rus}" for eng, rus in words.items()])
            await bot.send_message(user_id, reply)

    elif data == "quiz":
        await send_quiz(user_id, reverse=False)

    elif data == "quiz_reverse":
        await send_quiz(user_id, reverse=True)

    await callback.answer()

# ------------------ ДОБАВЛЕНИЕ СЛОВ ------------------
@dp.message()
async def receive_word(message: Message):
    if message.from_user.id not in adding_word_users:
        return
    text = message.text.strip()
    if "-" not in text:
        await message.answer("Неверный формат. Используйте: английское-русский")
        return
    eng, rus = text.split("-", 1)
    eng = eng.strip()
    rus = rus.strip()
    words[eng] = rus
    save_words()
    await message.answer(f"Слово '{eng}' → '{rus}' добавлено!")
    adding_word_users.remove(message.from_user.id)

# ------------------ КВИЗ ------------------
async def send_quiz(user_id: int, reverse=False):
    if len(words) < 2:
        await bot.send_message(user_id, "Добавьте хотя бы 2 слова для квиза!")
        return

    eng = random.choice(list(words.keys()))
    rus = words[eng]

    options = []
    correct = rus if not reverse else eng
    options.append(correct)
    while len(options) < 4:
        w = random.choice(list(words.keys()))
        val = w if reverse else words[w]
        if val not in options:
            options.append(val)
    random.shuffle(options)

    keyboard = InlineKeyboardMarkup(row_width=2)
    for opt in options:
        keyboard.add(InlineKeyboardButton(text=opt, callback_data=f"answer:{opt}:{eng}:{rus}:{reverse}"))

    question = eng if not reverse else rus
    await bot.send_message(user_id, f"Выберите правильный перевод: {question}", reply_markup=keyboard)

    if not reverse:
        tts = gTTS(text=eng, lang='en')
        tts.save("word.mp3")
        await bot.send_voice(user_id, InputFile("word.mp3"))
        os.remove("word.mp3")

    current_quiz[user_id] = (eng, rus, reverse)

# ------------------ ПРОВЕРКА ОТВЕТОВ ------------------
@dp.callback_query(lambda c: c.data.startswith("answer:"))
async def answer_handler(callback: types.CallbackQuery):
    data = callback.data.split(":", 4)
    user_answer = data[1]
    eng = data[2]
    rus = data[3]
    reverse = data[4] == "True"
    user_id = callback.from_user.id

    correct = rus if not reverse else eng
    if user_answer == correct:
        await bot.send_message(user_id, f"✅ Верно! '{eng}' → '{rus}'")
    else:
        await bot.send_message(user_id, f"❌ Неправильно. Правильный ответ: '{correct}'\nСлово удалено из словаря.")
        if not reverse and eng in words:
            del words[eng]
            save_words()

    if user_id in current_quiz:
        del current_quiz[user_id]

    await callback.answer()

# ------------------ HTTP-заглушка ------------------
async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

# ------------------ ЗАПУСК ------------------
async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
