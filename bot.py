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

# РЕЗЕРВНЫЙ СЛОВАРЬ
BACKUP_WORDS = {
    "task": "задача", "project": "проект", "deadline": "крайний срок", "report": "отчет",
    "to fix a bug": "исправить ошибку", "solution": "решение", "team": "команда", 
    "review": "отзыв", "meeting": "созвон, совещание", "request": "запрос", 
    "access": "доступ", "respond": "отвечать", "check": "проверять", "apple": "яблоко", 
    "book": "книга", "work on": "работать над", "solve problems": "решать проблемы/задачи",
    "communicate": "общаться, связываться", "work remotely": "работать удаленно", 
    "write code": "писать код", "attend meetings": "посещать совещания", 
    "design": "проектировать", "analyze": "анализировать", "fix": "исправлять", 
    "test": "тестировать", "develop": "разрабатывать", "collaborate with": "сотрудничать с"
}

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

# ------------------ ЛОГИ ------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ ИНИЦИАЛИЗАЦИЯ ------------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------ СЛОВАРЬ С РЕЗЕРВНОЙ КОПИЕЙ ------------------
def load_words():
    global words
    try:
        if os.path.exists(WORDS_FILE):
            with open(WORDS_FILE, "r", encoding="utf-8") as f:
                words = json.load(f)
            logger.info(f"📚 Слов в словаре: {len(words)}")
        else:
            # ВОССТАНОВЛЕНИЕ ИЗ РЕЗЕРВНОЙ КОПИИ
            words = BACKUP_WORDS.copy()
            with open(WORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(words, f, ensure_ascii=False, indent=2)
            logger.info("🔄 Словарь восстановлен из резервной копии")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки: {e}")
        words = BACKUP_WORDS.copy()

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

# ... остальной код без изменений (ваш существующий функционал) ...

# ДОБАВЬТЕ ЭТИ КОМАНДЫ
@dp.message(Command("backup"))
async def backup_cmd(message: Message):
    """Скачать бэкап словаря"""
    try:
        with open(WORDS_FILE, "rb") as f:
            await message.answer_document(
                types.BufferedInputFile(f.read(), filename="words_backup.json"),
                caption="📦 Резервная копия вашего словаря"
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка создания бэкапа: {e}")

@dp.message(Command("restore"))
async def restore_cmd(message: Message):
    """Восстановить словарь"""
    global words
    words = BACKUP_WORDS.copy()
    save_words()
    await message.answer("✅ Словарь восстановлен из резервной копии!")

@dp.message(Command("count"))
async def count_cmd(message: Message):
    """Показать статистику"""
    await message.answer(f"📊 Слов в словаре: {len(words)}")

# ------------------ WEB SERVER ------------------
async def health_check(request):
    return web.Response(text="🤖 Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
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
