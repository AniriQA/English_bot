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
                "team": "команда",
                "deadline": "крайний срок",
                "report": "отчет",
                "solution": "решение",
                "meeting": "совещание",
                "request": "запрос",
                "access": "доступ",
                "apple": "яблоко",
                "book": "книга"
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

def back_to_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])

# ------------------ КОМАНДЫ ------------------
@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "🇬🇧 Английский бот\n\nВыбирайте действие:",
        reply_markup=main_menu()
    )

@dp.message(Command("status"))  
async def status_cmd(message: Message):
    await message.answer(f"✅ Бот активен\n📚 Слов в словаре: {len(words)}")

@dp.message(Command("words"))
async def words_cmd(message: Message):
    if not words:
        await message.answer("📚 Словарь пуст!")
        return
    
    text = "📚 Ваш словарь:\n\n"
    for eng, rus in words.items():
        text += f"• {eng} → {rus}\n"
    
    text += f"\nВсего слов: {len(words)}"
    await message.answer(text)

# ------------------ ОБРАБОТКА ТЕКСТА ------------------
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
                    f"✅ Добавлено!\n<code>{eng}</code> → <code>{rus}</code>\n\n"
                    f"📚 Всего слов: {len(words)}",
                    reply_markup=main_menu()
                )
                return
        
        await message.answer(
            "❌ Неверный формат\n\n"
            "Правильно: <code>слово-перевод</code>\n"
            "Пример: <code>computer-компьютер</code>\n\n"
            "Попробуйте еще раз:",
            reply_markup=back_to_menu()
        )
        return

    await message.answer("ℹ️ Используйте меню:", reply_markup=main_menu())

# ------------------ CALLBACKS ------------------
@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "🇬🇧 Английский бот\n\nВыбирайте действие:",
        reply_markup=main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "add")
async def add_callback(callback: CallbackQuery):
    adding_word_users.add(callback.from_user.id)
    await callback.message.edit_text(
        "📝 Введите слово и перевод через дефис:\n\n"
        "Пример: <code>database-база данных</code>\n"
        "Пример: <code>to learn-учить</code>",
        reply_markup=back_to_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "list")
async def list_callback(callback: CallbackQuery):
    if not words:
        await callback.message.edit_text(
            "📚 Словарь пуст!\nДобавьте слова с помощью кнопки ниже:",
            reply_markup=main_menu()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру со словами
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Добавляем слова с кнопками удаления
    for eng, rus in list(words.items())[:20]:  # Показываем первые 20 слов
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"🗑️ {eng}", callback_data=f"delete:{eng}"),
            InlineKeyboardButton(text=rus, callback_data=f"show:{eng}")
        ])
    
    # Кнопка возврата
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    ])
    
    await callback.message.edit_text(
        f"📚 Словарь ({len(words)} слов)\n\n"
        "Нажмите 🗑️ чтобы удалить слово:",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("delete:"))
async def delete_callback(callback: CallbackQuery):
    eng = callback.data.split(":", 1)[1]
    
    if eng in words:
        # Сохраняем перевод для сообщения
        rus_translation = words[eng]
        
        # Удаляем слово
        del words[eng]
        save_words()
        
        # Обновляем сообщение со словарем
        if words:
            # Создаем обновленную клавиатуру
            kb = InlineKeyboardMarkup(inline_keyboard=[])
            
            for eng_word, rus_word in list(words.items())[:20]:
                kb.inline_keyboard.append([
                    InlineKeyboardButton(text=f"🗑️ {eng_word}", callback_data=f"delete:{eng_word}"),
                    InlineKeyboardButton(text=rus_word, callback_data=f"show:{eng_word}")
                ])
            
            kb.inline_keyboard.append([
                InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
            ])
            
            await callback.message.edit_text(
                f"✅ Удалено: <code>{eng}</code> → <code>{rus_translation}</code>\n\n"
                f"📚 Осталось слов: {len(words)}\n\n"
                "Нажмите 🗑️ чтобы удалить слово:",
                reply_markup=kb
            )
        else:
            await callback.message.edit_text(
                f"✅ Удалено: <code>{eng}</code> → <code>{rus_translation}</code>\n\n"
                "📚 Словарь теперь пуст!",
                reply_markup=main_menu()
            )
    else:
        await callback.answer("❌ Слово уже удалено", show_alert=True)
    
    await callback.answer()

@dp.callback_query(F.data.startswith("show:"))
async def show_callback(callback: CallbackQuery):
    eng = callback.data.split(":", 1)[1]
    if eng in words:
        await callback.answer(f"🔍 {eng} → {words[eng]}", show_alert=True)
    else:
        await callback.answer("❌ Слово не найдено", show_alert=True)

@dp.callback_query(F.data.startswith("quiz"))
async def quiz_callback(callback: CallbackQuery):
    if len(words) < 2:
        await callback.message.edit_text(
            "❌ Нужно минимум 2 слова для квиза!\nДобавьте слова в словарь.",
            reply_markup=main_menu()
        )
        await callback.answer()
        return
    
    reverse = callback.data == "quiz_reverse"
    eng = random.choice(list(words.keys()))
    rus = words[eng]
    
    # Создаем варианты ответов
    correct = rus if not reverse else eng
    options = [correct]
    
    # Добавляем случайные неправильные варианты
    while len(options) < 4:
        random_word = random.choice(list(words.keys()))
        wrong_option = words[random_word] if not reverse else random_word
        if wrong_option not in options and wrong_option != correct:
            options.append(wrong_option)
    
    random.shuffle(options)
    
    # Создаем клавиатуру с вариантами
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for option in options:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=option, callback_data=f"answer:{option}")
        ])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu")
    ])
    
    question = eng if not reverse else rus
    question_type = "английского" if reverse else "русского"
    
    await callback.message.edit_text(
        f"🎯 Выберите перевод {question_type} слова:\n\n<b>{question}</b>",
        reply_markup=kb
    )
    
    current_quiz[callback.from_user.id] = (eng, rus, reverse)
    await callback.answer()

@dp.callback_query(F.data.startswith("answer:"))
async def answer_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in current_quiz:
        await callback.answer("❌ Квиз устарел", show_alert=True)
        return
    
    user_answer = callback.data.split(":", 1)[1]
    eng, rus, reverse = current_quiz[user_id]
    correct = rus if not reverse else eng
    
    if user_answer == correct:
        response = f"✅ Верно!\n\n<b>{eng}</b> → <i>{rus}</i>"
    else:
        response = f"❌ Неправильно!\n\n✅ <b>{eng}</b> → <i>{rus}</i>"
    
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
