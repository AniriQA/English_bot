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

# РЕЗЕРВНЫЙ СЛОВАРЬ (восстановится при сбросе)
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
    """Восстановить словарь из резервной копии"""
    global words
    words = BACKUP_WORDS.copy()
    save_words()
    await message.answer("✅ Словарь восстановлен из резервной копии!")

@dp.message(Command("count"))
async def count_cmd(message: Message):
    """Показать статистику"""
    await message.answer(f"📊 Слов в словаре: {len(words)}")

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
                    f"✅ Добавлено!\n{eng} → {rus}\n\n"
                    f"📚 Всего слов: {len(words)}",
                    reply_markup=main_menu()
                )
                return
        
        await message.answer(
            "❌ Неверный формат\n\n"
            "Правильно: слово-перевод\n"
            "Пример: computer-компьютер\n\n"
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
        "Пример: database-база данных\n"
        "Пример: to learn-учить",
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
    
    # Создаем клавиатуру со словами и кнопками удаления
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Добавляем слова с кнопками удаления
    for eng, rus in list(words.items())[:15]:  # Показываем первые 15 слов
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"🗑️ {eng}", callback_data=f"delete:{eng}"),
            InlineKeyboardButton(text=rus, callback_data=f"show:{eng}")
        ])
    
    # Кнопка возврата
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    ])
    
    await callback.message.edit_text(
        f"📚 Словарь ({len(words)} слов)\n\nНажмите 🗑️ чтобы удалить слово:",
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
        
        await callback.answer(f"✅ Удалено: {eng} → {rus_translation}")
        
        # Обновляем сообщение со словарем
        if words:
            # Создаем обновленную клавиатуру
            kb = InlineKeyboardMarkup(inline_keyboard=[])
            
            for eng_word, rus_word in list(words.items())[:15]:
                kb.inline_keyboard.append([
                    InlineKeyboardButton(text=f"🗑️ {eng_word}", callback_data=f"delete:{eng_word}"),
                    InlineKeyboardButton(text=rus_word, callback_data=f"show:{eng_word}")
                ])
            
            kb.inline_keyboard.append([
                InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
            ])
            
            await callback.message.edit_text(
                f"📚 Словарь ({len(words)} слов)\n\nНажмите 🗑️ чтобы удалить слово:",
                reply_markup=kb
            )
        else:
            await callback.message.edit_text(
                "📚 Словарь теперь пуст!",
                reply_markup=main_menu()
            )
    else:
        await callback.answer("❌ Слово уже удалено", show_alert=True)

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
        f"🎯 Выберите перевод {question_type} слова:\n\n{question}",
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
        response = f"✅ Верно!\n\n{eng} → {rus}"
    else:
        response = f"❌ Неправильно!\n\n✅ {eng} → {rus}"
    
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
