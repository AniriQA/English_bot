import logging
import os
import random
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InputFile
from gtts import gTTS
from aiohttp import web

# ------------------ НАСТРОЙКА ------------------
TOKEN = os.getenv("BOT_TOKEN")  # токен задаётся в Render → Environment
WORDS_FILE = "words.json"

# ------------------ ЛОГИ ------------------
logging.basicConfig(level=logging.INFO)

# ------------------ ИНИЦИАЛИЗАЦИЯ ------------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------ ЗАГРУЗКА СЛОВАРЯ ------------------
if os.path.exists(WORDS_FILE):
    with open(WORDS_FILE, "r", encoding="utf-8") as f:
        words = json.load(f)
else:
    words = {}  # структура: { "english": "русский" }

# ------------------ СОХРАНЕНИЕ ------------------
def save_words():
    with open(WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

# ------------------ ДОБАВЛЕНИЕ СЛОВ ------------------
adding_word_users = set()  # кто вводит слово

@dp.message(Command(commands=["add"]))
async def add(message: Message):
    await message.answer("Введите слово и перевод через дефис (пример: apple-яблоко):")
    adding_word_users.add(message.from_user.id)

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

# ------------------ ПРОСМОТР СЛОВАРЯ ------------------
@dp.message(Command(commands=["list"]))
async def list_words(message: Message):
    if not words:
        await message.answer("Словарь пуст!")
        return
    reply = "\n".join([f"{eng} → {rus}" for eng, rus in words.items()])
    await message.answer(reply)

# ------------------ КВИЗ ------------------
current_quiz = {}  # {user_id: (eng, rus, reverse)}

async def send_quiz(message: Message, reverse=False):
    if len(words) < 2:
        await message.answer("Добавьте хотя бы 2 слова для квиза!")
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

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for opt in options:
        keyboard.add(opt)

    question = eng if not reverse else rus
    await message.answer(f"Выберите правильный перевод: {question}", reply_markup=keyboard)

    # озвучка английского слова (только прямой квиз)
    if not reverse:
        tts = gTTS(text=eng, lang='en')
        tts.save("word.mp3")
        await message.answer_voice(InputFile("word.mp3"))
        os.remove("word.mp3")

    current_quiz[message.from_user.id] = (eng, rus, reverse)

@dp.message(Command(commands=["quiz"]))
async def quiz(message: Message):
    await send_quiz(message, reverse=False)

@dp.message(Command(commands=["quiz_reverse"]))
async def quiz_reverse(message: Message):
    await send_quiz(message, reverse=True)

# ------------------ ПРОВЕРКА ОТВЕТОВ ------------------
@dp.message()
async def check_answer(message: Message):
    user_id = message.from_user.id
    if user_id not in current_quiz:
        return  # нет активного квиза

    eng, rus, reverse = current_quiz[user_id]
    user_answer = message.text.strip()

    correct = rus if not reverse else eng
    if user_answer == correct:
        await message.answer(f"✅ Верно! '{eng}' → '{rus}'")
    else:
        await message.answer(f"❌ Неправильно. Правильный ответ: '{correct}'\nСлово удалено из словаря.")
        if not reverse and eng in words:
            del words[eng]
            save_words()

    del current_quiz[user_id]

# ------------------ СТАРТ ------------------
@dp.message(Command(commands=["start"]))
async def start(message: Message):
    await message.answer(
        "Привет! Я бот для изучения английских слов.\n\n"
        "Команды:\n"
        "/add - добавить слово\n"
        "/quiz - квиз (англ → рус)\n"
        "/quiz_reverse - квиз (рус → англ)\n"
        "/list - посмотреть словарь"
    )

# ------------------ HTTP-заглушка для Render ------------------
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
