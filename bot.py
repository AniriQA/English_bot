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

# ------------------ ЛОГИ ------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ------------------ ИНИЦИАЛИЗАЦИЯ ------------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------ ЗАГРУЗКА СЛОВАРЯ ------------------
def load_words():
    global words
    try:
        if os.path.exists(WORDS_FILE):
            with open(WORDS_FILE, "r", encoding="utf-8") as f:
                words = json.load(f)
            logger.info(f"Загружено {len(words)} слов из словаря")
        else:
            words = {}
            logger.info("Создан новый пустой словарь")
    except Exception as e:
        logger.error(f"Ошибка загрузки словаря: {e}")
        words = {}

def save_words():
    try:
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения словаря: {e}")

# ------------------ СТАТЫ ------------------
adding_word_users = set()
current_quiz: Dict[int, Tuple[str, str, bool]] = {}

load_words()

# ------------------ КЛАВИАТУРЫ ------------------
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить слово", callback_data="cmd:add"),
            InlineKeyboardButton(text="📝 Словарь", callback_data="cmd:list")
        ],
        [
            InlineKeyboardButton(text="❓ Квиз (англ → рус)", callback_data="cmd:quiz"),
            InlineKeyboardButton(text="❓ Квиз (рус → англ)", callback_data="cmd:quiz_reverse")
        ]
    ])

def list_words_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for eng, rus in list(words.items())[:30]:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"{eng}", callback_data=f"show:{eng}"),
            InlineKeyboardButton(text="❌", callback_data=f"del:{eng}")
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="cmd:menu")
    ])
    return kb

def quiz_options_kb(options):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for opt in options:
        safe_opt = opt.replace(':', '|')
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=opt, callback_data=f"answer:{safe_opt}")
        ])
    return kb

# ------------------ КОМАНДЫ ------------------
@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для изучения английских слов.\nВыбирай действие:",
        reply_markup=main_menu_kb()
    )

@dp.message(Command(commands=["add"]))
async def cmd_add(message: Message):
    adding_word_users.add(message.from_user.id)
    await message.answer("Введите слово и перевод через дефис (пример: apple-яблоко):")

@dp.message(Command(commands=["list"]))
async def cmd_list(message: Message):
    if not words:
        await message.answer("Словарь пуст!", reply_markup=main_menu_kb())
        return
    await message.answer(f"Ваш словарь ({len(words)} слов):", reply_markup=list_words_kb())

# ------------------ ОБРАБОТКА ТЕКСТА ------------------
@dp.message(F.text)
async def text_router(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id in adding_word_users:
        if "-" not in text:
            await message.answer("Неверный формат. Пример: apple-яблоко\nПопробуйте еще раз:")
            return
        
        eng, rus = text.split("-", 1)
        eng, rus = eng.strip().lower(), rus.strip().lower()
        
        if eng and rus:
            words[eng] = rus
            save_words()
            adding_word_users.discard(user_id)
            await message.answer(f"✅ '{eng}' → '{rus}' добавлено! Всего: {len(words)}", 
                               reply_markup=main_menu_kb())
        return

    if user_id in current_quiz:
        eng, rus, reverse = current_quiz[user_id]
        user_answer = text.strip().lower()
        correct = rus.lower() if not reverse else eng.lower()
        
        if user_answer == correct:
            response = f"✅ Верно! '{eng}' → '{rus}'"
        else:
            response = f"❌ Неправильно. Правильно: '{correct}'"
            if not reverse and eng in words:
                del words[eng]
                save_words()
                response += f"\nСлово '{eng}' удалено."
        
        del current_quiz[user_id]
        await message.answer(response, reply_markup=main_menu_kb())
        return

    await message.answer("Используйте меню:", reply_markup=main_menu_kb())

# ------------------ КВИЗ ------------------
async def send_quiz(message: Message, reverse: bool = False):
    if len(words) < 2:
        await message.answer("Добавьте хотя бы 2 слова!", reply_markup=main_menu_kb())
        return

    word_keys = list(words.keys())
    eng = random.choice(word_keys)
    rus = words[eng]

    options = [rus if not reverse else eng]
    while len(options) < 4:
        w = random.choice(word_keys)
        val = words[w] if not reverse else w
        if val not in options and val != options[0]:
            options.append(val)
    
    random.shuffle(options)
    question = eng if not reverse else rus

    await message.answer(f"Выберите перевод: <b>{question}</b>", reply_markup=quiz_options_kb(options))
    
    if not reverse:
        try:
            tts = gTTS(text=eng, lang='en')
            tts.save("word.mp3")
            await message.answer_voice(InputFile("word.mp3"))
            os.remove("word.mp3")
        except Exception as e:
            logger.error(f"TTS error: {e}")

    current_quiz[message.from_user.id] = (eng, rus, reverse)

# ------------------ CALLBACKS ------------------
@dp.callback_query(F.data.startswith("cmd:"))
async def cmd_handler(callback: CallbackQuery):
    cmd = callback.data.split(":", 1)[1]
    
    if cmd == "add":
        adding_word_users.add(callback.from_user.id)
        await callback.message.edit_text("Введите слово и перевод через дефис (пример: apple-яблоко):")
    elif cmd == "list":
        if not words:
            await callback.message.edit_text("Словарь пуст!", reply_markup=main_menu_kb())
        else:
            await callback.message.edit_text(f"Ваш словарь ({len(words)} слов):", reply_markup=list_words_kb())
    elif cmd == "quiz":
        await callback.message.delete()
        await send_quiz(callback.message, False)
    elif cmd == "quiz_reverse":
        await callback.message.delete()
        await send_quiz(callback.message, True)
    elif cmd == "menu":
        await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    
    await callback.answer()

@dp.callback_query(F.data.startswith("answer:"))
async def answer_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in current_quiz:
        await callback.answer("Начните новый квиз!", show_alert=True)
        return

    eng, rus, reverse = current_quiz[user_id]
    user_answer = callback.data.split(":", 1)[1].replace('|', ':')
    correct = rus if not reverse else eng

    if user_answer == correct:
        response = f"✅ Верно! '{eng}' → '{rus}'"
    else:
        response = f"❌ Неправильно. Правильно: '{correct}'"
        if not reverse and eng in words:
            del words[eng]
            save_words()
            response += f"\nСлово '{eng}' удалено."

    await callback.message.edit_text(response, reply_markup=main_menu_kb())
    del current_quiz[user_id]
    await callback.answer()

@dp.callback_query(F.data.startswith("show:"))
async def show_handler(callback: CallbackQuery):
    eng = callback.data.split(":", 1)[1]
    if eng in words:
        await callback.answer(f"{eng} → {words[eng]}", show_alert=True)
    else:
        await callback.answer("Слово не найдено", show_alert=True)

@dp.callback_query(F.data.startswith("del:"))
async def delete_handler(callback: CallbackQuery):
    eng = callback.data.split(":", 1)[1]
    if eng in words:
        del words[eng]
        save_words()
        if words:
            await callback.message.edit_text(f"🗑️ '{eng}' удалено. Осталось: {len(words)}", reply_markup=list_words_kb())
        else:
            await callback.message.edit_text("Словарь пуст!", reply_markup=main_menu_kb())
    await callback.answer()

# ------------------ WEB SERVER ------------------
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server on port {port}")

# ------------------ ЗАПУСК ------------------
async def reset_bot():
    """Принудительный сброс перед запуском"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook reset successfully")
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Reset error: {e}")

async def main():
    # Сначала сбрасываем вебхук
    await reset_bot()
    
    # Запускаем веб-сервер
    await start_web_server()
    
    # Запускаем бота
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Polling failed: {e}")
        # Пробуем еще раз через 10 секунд
        await asyncio.sleep(10)
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
