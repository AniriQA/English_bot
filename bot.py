import logging
import os
import random
import json
import asyncio
from typing import Dict, Tuple

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, InputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from gtts import gTTS
from aiohttp import web

# ------------------ НАСТРОЙКА ------------------
TOKEN = os.getenv("BOT_TOKEN")
WORDS_FILE = "words.json"

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

# ------------------ ЛОГИ ------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ ИНИЦИАЛИЗАЦИЯ ------------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------ СЛОВАРЬ ------------------
def load_words():
    global words
    try:
        if os.path.exists(WORDS_FILE):
            with open(WORDS_FILE, "r", encoding="utf-8") as f:
                words = json.load(f)
            logger.info(f"📚 Слов в словаре: {len(words)}")
        else:
            words = {
                "hello": "привет",
                "task": "задача", 
                "project": "проект",
                "team": "команда"
            }
            with open(WORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(words, f, ensure_ascii=False, indent=2)
            logger.info("📚 Создан новый словарь")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки: {e}")
        words = {}

def save_words():
    try:
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {e}")

# ------------------ СОСТОЯНИЯ ------------------
adding_word_users = set()
current_quiz: Dict[int, Tuple[str, str, bool]] = {}

load_words()

# ------------------ КЛАВИАТУРЫ ------------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить слово", callback_data="add"),
            InlineKeyboardButton(text="📚 Словарь", callback_data="list")
        ],
        [
            InlineKeyboardButton(text="🎯 Квиз англ→рус", callback_data="quiz"),
            InlineKeyboardButton(text="🎯 Квиз рус→англ", callback_data="quiz_reverse")
        ]
    ])

# ------------------ КОМАНДЫ ------------------
@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "🇬🇧 Английский бот\nВыбирайте действие:",
        reply_markup=main_menu()
    )

@dp.message(Command("status"))  
async def status_cmd(message: Message):
    await message.answer(f"✅ Бот активен\n📚 Слов в словаре: {len(words)}")

# ------------------ ТЕКСТ ------------------
@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id in adding_word_users:
        if "-" in text:
            eng, rus = text.split("-", 1)
            eng, rus = eng.strip().lower(), rus.strip().lower()
            if eng and rus:
                words[eng] = rus
                save_words()
                adding_word_users.discard(user_id)
                await message.answer(
                    f"✅ '{eng}' → '{rus}'\n📚 Всего слов: {len(words)}",
                    reply_markup=main_menu()
                )
                return
        await message.answer("❌ Формат: apple-яблоко\nПопробуйте:")
        return

    await message.answer("ℹ️ Используйте меню:", reply_markup=main_menu())

# ------------------ CALLBACKS ------------------
@dp.callback_query(F.data == "add")
async def add_callback(callback: CallbackQuery):
    adding_word_users.add(callback.from_user.id)
    await callback.message.edit_text(
        "📝 Введите слово и перевод:\nПример: <code>database-база данных</code>"
    )
    await callback.answer()

@dp.callback_query(F.data == "list")
async def list_callback(callback: CallbackQuery):
    if not words:
        await callback.message.edit_text("📚 Словарь пуст!")
        await callback.answer()
        return
    
    text = "📚 Ваш словарь:\n\n"
    for eng, rus in list(words.items())[:15]:
        text += f"• <b>{eng}</b> - {rus}\n"
    
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("quiz"))
async def quiz_callback(callback: CallbackQuery):
    if len(words) < 2:
        await callback.message.edit_text("❌ Нужно минимум 2 слова!")
        await callback.answer()
        return
    
    reverse = callback.data == "quiz_reverse"
    eng = random.choice(list(words.keys()))
    rus = words[eng]
    
    correct = rus if not reverse else eng
    options = [correct]
    
    while len(options) < 4:
        word = random.choice(list(words.keys()))
        option = words[word] if not reverse else word
        if option not in options and option != correct:
            options.append(option)
    
    random.shuffle(options)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for opt in options:
        kb.inline_keyboard.append([InlineKeyboardButton(text=opt, callback_data=f"ans:{opt}")])
    
    question = eng if not reverse else rus
    await callback.message.edit_text(
        f"🎯 Выберите перевод:\n<b>{question}</b>",
        reply_markup=kb
    )
    
    current_quiz[callback.from_user.id] = (eng, rus, reverse)
    await callback.answer()

@dp.callback_query(F.data.startswith("ans:"))
async def answer_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in current_quiz:
        await callback.answer("❌ Квиз устарел")
        return
    
    user_ans = callback.data.split(":", 1)[1]
    eng, rus, reverse = current_quiz[user_id]
    correct = rus if not reverse else eng
    
    if user_ans == correct:
        response = f"✅ Верно!\n<b>{eng}</b> - {rus}"
    else:
        response = f"❌ Неправильно!\n✅ <b>{eng}</b> - {rus}"
    
    del current_quiz[user_id]
    await callback.message.edit_text(response, reply_markup=main_menu())
    await callback.answer()

# ------------------ WEB SERVER ------------------
async def health_check(request):
    return web.Response(text="🤖 Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # 🔥 ВАЖНО: Используем порт 8080 для Render
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    logger.info(f"🌐 Web server started on port {port}")
    return app

# ------------------ ЗАПУСК ------------------
async def main():
    logger.info("🚀 Starting bot...")
    
    # Сброс вебхука
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook reset")
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
    
    # Запуск веб-сервера
    await start_web_server()
    
    # Запуск бота
    logger.info("✅ Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
