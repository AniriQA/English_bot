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
TOKEN = os.getenv("BOT_TOKEN")  # токен задаётся в Render → Environment
WORDS_FILE = "words.json"

# ------------------ ЛОГИ ------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ ИНИЦИАЛИЗАЦИЯ ------------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------ ЗАГРУЗКА СЛОВАРЯ ------------------
def load_words():
    """Загрузка слов из файла с обработкой ошибок"""
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

# ------------------ СОХРАНЕНИЕ ------------------
def save_words():
    """Сохранение слов в файл с обработкой ошибок"""
    try:
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        logger.info(f"Словарь сохранен ({len(words)} слов)")
    except Exception as e:
        logger.error(f"Ошибка сохранения словаря: {e}")

# ------------------ СТАТЫ/СЛУЖЕБНЫЕ СЛОВАРИ ------------------
adding_word_users = set()  # user_id добавляет слово (ожидаем текст "eng-rus")
current_quiz: Dict[int, Tuple[str, str, bool]] = {}  # {user_id: (eng, rus, reverse)}

# Загружаем слова при старте
load_words()

# ------------------ УТИЛИТЫ ДЛЯ КЛАВИАТУР ------------------
def main_menu_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить слово", callback_data="cmd:add"),
            InlineKeyboardButton(text="📝 Посмотреть словарь", callback_data="cmd:list")
        ],
        [
            InlineKeyboardButton(text="❓ Квиз (англ → рус)", callback_data="cmd:quiz"),
            InlineKeyboardButton(text="❓ Квиз (рус → англ)", callback_data="cmd:quiz_reverse")
        ]
    ])
    return kb

def list_words_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    # добавляем по одной кнопке на слово (callback удаление)
    for eng, rus in list(words.items())[:50]:  # ограничиваем показ до 50 слов
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"{eng} → {rus}", callback_data=f"show:{eng}"),
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"del:{eng}")
        ])
    
    # Добавляем кнопку возврата в меню
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад в меню", callback_data="cmd:menu")
    ])
    return kb

def quiz_options_kb(options):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for opt in options:
        # Экранируем специальные символы в callback_data
        safe_opt = opt.replace(':', '|').replace(';', '|')
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=opt, callback_data=f"answer:{safe_opt}")
        ])
    return kb

def back_to_menu_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="cmd:menu")]
    ])
    return kb

# ------------------ КОМАНДЫ ------------------
@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    """Показываем красивое меню кнопок (inline)."""
    await message.answer(
        "Привет! Я бот для изучения английских слов.\nВыбирай действие кнопками ниже:",
        reply_markup=main_menu_kb()
    )

@dp.message(Command(commands=["add"]))
async def cmd_add(message: Message):
    adding_word_users.add(message.from_user.id)
    await message.answer(
        "Введите слово и перевод через дефис (пример: apple-яблоко):",
        reply_markup=back_to_menu_kb()
    )

@dp.message(Command(commands=["list"]))
async def cmd_list(message: Message):
    if not words:
        await message.answer(
            "Словарь пуст! Добавьте слова с помощью кнопки ниже:",
            reply_markup=main_menu_kb()
        )
        return
    await message.answer(
        f"Ваш словарь ({len(words)} слов):", 
        reply_markup=list_words_kb()
    )

@dp.message(Command(commands=["quiz"]))
async def cmd_quiz(message: Message):
    await send_quiz(message, reverse=False)

@dp.message(Command(commands=["quiz_reverse"]))
async def cmd_quiz_reverse(message: Message):
    await send_quiz(message, reverse=True)

# ------------------ ДОБАВЛЕНИЕ СЛОВ ------------------
@dp.message(F.text)
async def text_router(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # 1) если пользователь сейчас добавляет слово
    if user_id in adding_word_users:
        if "-" not in text:
            await message.answer(
                "Неверный формат. Используйте: английское-русский (пример: apple-яблоко)\nПопробуйте еще раз:",
                reply_markup=back_to_menu_kb()
            )
            return
        
        eng, rus = text.split("-", 1)
        eng = eng.strip().lower()
        rus = rus.strip().lower()
        
        if not eng or not rus:
            await message.answer(
                "Пустая часть слова. Проверьте формат.\nПопробуйте еще раз:",
                reply_markup=back_to_menu_kb()
            )
            return
        
        words[eng] = rus
        save_words()
        adding_word_users.discard(user_id)  # используем discard вместо remove для безопасности
        await message.answer(
            f"✅ Слово '{eng}' → '{rus}' добавлено!\nВсего слов в словаре: {len(words)}", 
            reply_markup=main_menu_kb()
        )
        return

    # 2) если у пользователя открыт квиз и он ввёл текст вместо кнопки
    if user_id in current_quiz:
        eng, rus, reverse = current_quiz[user_id]
        user_answer = text.strip().lower()
        correct = rus.lower() if not reverse else eng.lower()
        
        if user_answer == correct:
            response = f"✅ Верно! '{eng}' → '{rus}'"
        else:
            response = f"❌ Неправильно. Правильный ответ: '{correct}'"
            # Удаляем слово только если ответ неверный
            if not reverse and eng in words:
                del words[eng]
                save_words()
                response += f"\nСлово '{eng}' удалено из словаря."
        
        del current_quiz[user_id]
        await message.answer(response, reply_markup=main_menu_kb())
        return

    # 3) никакой режим — отправляем меню
    await message.answer("Используйте меню для навигации:", reply_markup=main_menu_kb())

# ------------------ КВИЗ ------------------
async def send_quiz(message: Message, reverse: bool = False):
    if len(words) < 2:
        await message.answer(
            "Добавьте хотя бы 2 слова для квиза!", 
            reply_markup=main_menu_kb()
        )
        return

    # Создаем копию ключей для избежания изменения во время итерации
    word_keys = list(words.keys())
    eng = random.choice(word_keys)
    rus = words[eng]

    options = []
    correct = rus if not reverse else eng
    options.append(correct)
    
    # собираем варианты (строки)
    while len(options) < 4:
        w = random.choice(word_keys)
        val = words[w] if not reverse else w
        if val not in options and val != correct:
            options.append(val)
    
    random.shuffle(options)

    question = eng if not reverse else rus
    question_type = "английского" if reverse else "русского"

    # отправляем вопрос с inline-кнопками
    await message.answer(
        f"Выберите правильный перевод {question_type} слова: <b>{question}</b>", 
        reply_markup=quiz_options_kb(options)
    )
    
    # озвучка английского (если прямой квиз)
    if not reverse:
        try:
            tts = gTTS(text=eng, lang='en')
            tts.save("word.mp3")
            await message.answer_voice(InputFile("word.mp3"))
            os.remove("word.mp3")
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            # Не прерываем выполнение если TTS не работает

    current_quiz[message.from_user.id] = (eng, rus, reverse)

# ------------------ CALLBACKS (кнопки) ------------------
@dp.callback_query(F.data.startswith("cmd:"))
async def cmd_buttons_handler(callback: CallbackQuery):
    cmd = callback.data.split(":", 1)[1]
    user_msg = callback.message
    
    if cmd == "add":
        adding_word_users.add(callback.from_user.id)
        await user_msg.edit_text(
            "Введите слово и перевод через дефис (пример: apple-яблоко):",
            reply_markup=back_to_menu_kb()
        )
    elif cmd == "list":
        if not words:
            await user_msg.edit_text(
                "Словарь пуст! Добавьте слова с помощью кнопки ниже:",
                reply_markup=main_menu_kb()
            )
        else:
            await user_msg.edit_text(
                f"Ваш словарь ({len(words)} слов):", 
                reply_markup=list_words_kb()
            )
    elif cmd == "quiz":
        await user_msg.delete()  # Удаляем старое сообщение
        await send_quiz(user_msg, reverse=False)
    elif cmd == "quiz_reverse":
        await user_msg.delete()  # Удаляем старое сообщение
        await send_quiz(user_msg, reverse=True)
    elif cmd == "menu":
        await user_msg.edit_text(
            "Главное меню:",
            reply_markup=main_menu_kb()
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("answer:"))
async def answer_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in current_quiz:
        await callback.answer("Квиз устарел. Начните новый!", show_alert=True)
        return

    eng, rus, reverse = current_quiz[user_id]
    user_answer = callback.data.split(":", 1)[1].replace('|', ':')
    correct = rus if not reverse else eng

    if user_answer == correct:
        response = f"✅ Верно! '{eng}' → '{rus}'"
    else:
        response = f"❌ Неправильно. Правильный ответ: '{correct}'"
        # Удаляем слово только если ответ неверный
        if not reverse and eng in words:
            del words[eng]
            save_words()
            response += f"\nСлово '{eng}' удалено из словаря."

    await callback.message.edit_text(response, reply_markup=main_menu_kb())
    del current_quiz[user_id]
    await callback.answer()

@dp.callback_query(F.data.startswith("show:"))
async def show_word_callback(callback: CallbackQuery):
    eng = callback.data.split(":", 1)[1]
    if eng in words:
        await callback.answer(f"{eng} → {words[eng]}", show_alert=True)
    else:
        await callback.answer("Слово не найдено.", show_alert=True)

@dp.callback_query(F.data.startswith("del:"))
async def delete_word_callback(callback: CallbackQuery):
    eng = callback.data.split(":", 1)[1]
    if eng in words:
        del words[eng]
        save_words()
        # Обновляем сообщение со списком слов
        if words:
            await callback.message.edit_text(
                f"🗑️ Слово '{eng}' удалено. Осталось слов: {len(words)}", 
                reply_markup=list_words_kb()
            )
        else:
            await callback.message.edit_text(
                "Словарь теперь пуст!",
                reply_markup=main_menu_kb()
            )
    else:
        await callback.answer("Слово уже было удалено.", show_alert=True)

# ------------------ HTTP-заглушка для Render ------------------
async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

# ------------------ ЗАПУСК ------------------
async def main():
    # Загружаем слова при старте
    load_words()
    
    # Запускаем HTTP-заглушку и polling
    await start_web_server()
    logger.info("Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
