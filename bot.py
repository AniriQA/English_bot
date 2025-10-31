import logging
import os
import random
import json
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from gtts import gTTS
from aiohttp import web

# ------------------ НАСТРОЙКА ------------------
TOKEN = os.getenv("BOT_TOKEN")  # токен из Render → Environment
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
async def add_word(message: Message):
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
    await message.answer(f"✅ Слово '{eng}' → '{rus}' добавлено!")
    adding_word_users.remove(message.from_user.id)

# ------------------ ПРОСМОТР СЛОВАРЯ ------------------
@dp.message(Command(commands=["list"]))
async def list_words(message: Message):
    if not words:
        await message.answer("Словарь пуст!")
        return

    # кнопки с буквами слов
    keyboard = InlineKeyboardMarkup(row_width=2, inline_keyboard=[])
    for eng, rus in words.items():
        keyboard.add(InlineKeyboardButton(text=f"{eng} → {rus}", callback_data="noop"))
    
    await message.answer("Ваш словарь:", reply_markup=keyboard)

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

    keyboard = InlineKeyboardMarkup(row_width=2, inline_keyboard=[])
    for opt in options:
        keyboard.add(InlineKeyboardButton(text=opt, callback_data=f"answer:{opt}"))

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
@dp.callback_query(F.data.startswith("answer:"))
async def check_answer_callback(callback):
    user_id = callback.from_user.id
    if user_id not in current_quiz:
        await callback.answer("Сначала начните квиз командой /quiz или /quiz_reverse")
        return

    eng, rus, reverse = current_quiz[user_id]
    user_answer = callback.data.split(":", 1)[1]

    correct = rus if not reverse else eng
    if user_answer == correct:
        await callback.message.answer(f"✅ Верно! '{eng}' → '{rus}'")
    else:
        await callback.message.answer(f"❌ Неправильно. Правильный ответ: '{correct}'\nСлово удалено из словаря.")
        if not reverse and eng in words:
            del words[eng]
            save_words()

    del current_quiz[user_id]
    await callback.answer()

# ------------------ СТАРТ ------------------
@dp.message(Command(commands=["start"]))
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(row_width=2, inline_keyboard=[
        [InlineKeyboardButton(text="Добавить слово", callback_data="cmd:add")],
        [InlineKeyboardButton(text="Квиз (англ → рус)", callback_data="cmd:quiz")],
        [InlineKeyboardButton(text="Квиз (рус → англ)", callback_data="cmd:quiz_reverse")],
        [InlineKeyboardButton(text="Посмотреть словарь", callback_data="cmd:list")]
    ])
    await message.answer(
        "Привет! Я бот для изучения английских слов.\nВыбирай действие кнопками ниже:",
        reply_markup=keyboard
    )

# ------------------ ОБРАБОТКА КНОПОК СТАРТА ------------------
@dp.callback_query(F.data.startswith("cmd:"))
async def handle_start_buttons(callback):
    cmd = callback.data.split(":", 1)[1]
    if cmd == "add":
        await add_word(callback.message)
    elif cmd == "quiz":
        await send_quiz(callback.message, reverse=False)
    elif cmd == "quiz_reverse":
        await send_quiz(callback.message, reverse=True)
    elif cmd == "list":
        await list_words(callback.message)
    await callback.answer()

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
