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

# ------------------ ИНИЦИАЛИЗАЦИЯ ------------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------ ЗАГРУЗКА СЛОВАРЯ ------------------
if os.path.exists(WORDS_FILE):
    try:
        with open(WORDS_FILE, "r", encoding="utf-8") as f:
            words: Dict[str, str] = json.load(f)
    except Exception:
        logging.exception("Can't load words.json, starting with empty dict")
        words = {}
else:
    words = {}  # структура: { "english": "русский" }

# ------------------ СОХРАНЕНИЕ ------------------
def save_words():
    try:
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
    except Exception:
        logging.exception("Failed to save words.json")

# ------------------ СТАТЫ/СЛУЖЕБНЫЕ СЛОВАРИ ------------------
adding_word_users = set()  # user_id добавляет слово (ожидаем текст "eng-rus")
current_quiz: Dict[int, Tuple[str, str, bool]] = {}  # {user_id: (eng, rus, reverse)}

# ------------------ УТИЛИТЫ ДЛЯ КЛАВИАТУР ------------------
def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text="➕ Добавить слово", callback_data="cmd:add"),
        InlineKeyboardButton(text="📝 Посмотреть словарь", callback_data="cmd:list"),
        InlineKeyboardButton(text="❓ Квиз (англ → рус)", callback_data="cmd:quiz"),
        InlineKeyboardButton(text="❓ Квиз (рус → англ)", callback_data="cmd:quiz_reverse"),
    )
    return kb

def list_words_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    # добавляем по одной кнопке на слово (callback удаление)
    for eng, rus in words.items():
        kb.add(
            InlineKeyboardButton(text=f"{eng} → {rus}", callback_data=f"show:{eng}"),
            InlineKeyboardButton(text="Удалить", callback_data=f"del:{eng}")
        )
    return kb

def quiz_options_kb(options):
    kb = InlineKeyboardMarkup(row_width=2)
    for opt in options:
        # callback_data экранируем двоеточие: используем префикс answer:
        kb.add(InlineKeyboardButton(text=opt, callback_data=f"answer:{opt}"))
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
    await message.answer("Введите слово и перевод через дефис (пример: apple-яблоко):")

@dp.message(Command(commands=["list"]))
async def cmd_list(message: Message):
    if not words:
        await message.answer("Словарь пуст! /add чтобы добавить слово.")
        return
    await message.answer("Ваш словарь (нажмите на слово, чтобы показать или удалить):", reply_markup=list_words_kb())

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
            await message.answer("Неверный формат. Используйте: английское-русский (пример: apple-яблоко)")
            return
        eng, rus = text.split("-", 1)
        eng = eng.strip()
        rus = rus.strip()
        if not eng or not rus:
            await message.answer("Пустая часть слова. Проверьте формат.")
            return
        words[eng] = rus
        save_words()
        adding_word_users.discard(user_id)
        await message.answer(f"✅ Слово '{eng}' → '{rus}' добавлено!", reply_markup=main_menu_kb())
        return

    # 2) если у пользователя открыт квиз и он ввёл текст вместо кнопки (поддерживаем оба варианта)
    if user_id in current_quiz:
        eng, rus, reverse = current_quiz[user_id]
        user_answer = text
        correct = rus if not reverse else eng
        if user_answer == correct:
            await message.answer(f"✅ Верно! '{eng}' → '{rus}'", reply_markup=main_menu_kb())
        else:
            await message.answer(f"❌ Неправильно. Правильный ответ: '{correct}'\nСлово удалено из словаря.", reply_markup=main_menu_kb())
            if not reverse and eng in words:
                del words[eng]
                save_words()
        del current_quiz[user_id]
        return

    # 3) никакой режим — игнор или подсказка
    await message.answer("Не понял. Используй меню /start или кнопки.", reply_markup=main_menu_kb())

# ------------------ КВИЗ ------------------
async def send_quiz(message: Message, reverse: bool = False):
    if len(words) < 2:
        await message.answer("Добавьте хотя бы 2 слова для квиза! Используй /add.")
        return

    eng = random.choice(list(words.keys()))
    rus = words[eng]

    options = []
    correct = rus if not reverse else eng
    options.append(correct)
    # собираем варианты (строки)
    while len(options) < 4:
        w = random.choice(list(words.keys()))
        val = w if reverse else words[w]
        if val not in options:
            options.append(val)
    random.shuffle(options)

    question = eng if not reverse else rus

    # отправляем вопрос с inline-кнопками
    await message.answer(f"Выберите правильный перевод: <b>{question}</b>", reply_markup=quiz_options_kb(options))
    # озвучка английского (если прямой квиз)
    if not reverse:
        try:
            # используем уникальное имя файла на пользователя, чтобы избежать конфликтов
            filename = f"word_{message.from_user.id}.mp3"
            tts = gTTS(text=eng, lang='en')
            tts.save(filename)
            await message.answer_voice(InputFile(filename))
            try:
                os.remove(filename)
            except Exception:
                pass
        except Exception as e:
            logging.exception("TTS failed: %s", e)

    current_quiz[message.from_user.id] = (eng, rus, reverse)

# ------------------ CALLBACKS (кнопки) ------------------
@dp.callback_query(F.data.startswith("cmd:"))
async def cmd_buttons_handler(callback: CallbackQuery):
    cmd = callback.data.split(":", 1)[1]

    # для действий, которые ожидают "Message", мы НЕ передаём callback.message в качестве замены
    # а действуем от имени пользователя, использующего callback.from_user
    if cmd == "add":
        # пометить реального пользователя как добавляющего слово
        adding_word_users.add(callback.from_user.id)
        # отправляем подсказку в тот чат, где нажата кнопка (или в личку)
        try:
            # если это приватный чат — ответим там, иначе отправим пользователю в ЛС
            if callback.message.chat.type == "private":
                await callback.message.answer("Введите слово и перевод через дефис (пример: apple-яблоко):")
            else:
                # отправим лично пользователю (лучше — чтобы он писал в личке)
                await bot.send_message(callback.from_user.id, "Введите слово и перевод через дефис (пример: apple-яблоко):")
                await callback.message.answer("Я отправил тебе в личку инструкцию. Проверь сообщения.")
        except Exception:
            # fallback: отправим в тот же чат
            await callback.message.answer("Введите слово и перевод через дефис (пример: apple-яблоко):")
    elif cmd == "list":
        # покажем список слов в том же чате
        if not words:
            await callback.message.answer("Словарь пуст! /add чтобы добавить слово.")
        else:
            await callback.message.answer("Ваш словарь (нажмите на слово, чтобы показать или удалить):", reply_markup=list_words_kb())
    elif cmd == "quiz":
        # запустить квиз — создаём фейковое Message-like поведение? проще — отправляем запрос в тот же чат
        await send_quiz(callback.message, reverse=False)
    elif cmd == "quiz_reverse":
        await send_quiz(callback.message, reverse=True)

    await callback.answer()

@dp.callback_query(F.data.startswith("answer:"))
async def answer_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in current_quiz:
        await callback.answer("Сначала начните квиз командой /quiz или нажмите кнопку 'Квиз' в меню.", show_alert=True)
        return

    eng, rus, reverse = current_quiz[user_id]
    user_answer = callback.data.split(":", 1)[1]
    correct = rus if not reverse else eng

    if user_answer == correct:
        await callback.message.answer(f"✅ Верно! '{eng}' → '{rus}'", reply_markup=main_menu_kb())
    else:
        await callback.message.answer(f"❌ Неправильно. Правильный ответ: '{correct}'\nСлово удалено из словаря.", reply_markup=main_menu_kb())
        if not reverse and eng in words:
            del words[eng]
            save_words()

    del current_quiz[user_id]
    await callback.answer()

@dp.callback_query(F.data.startswith("show:"))
async def show_word_callback(callback: CallbackQuery):
    eng = callback.data.split(":", 1)[1]
    if eng in words:
        await callback.message.answer(f"{eng} → {words[eng]}")
    else:
        await callback.message.answer("Слово не найдено.")
    await callback.answer()

@dp.callback_query(F.data.startswith("del:"))
async def delete_word_callback(callback: CallbackQuery):
    eng = callback.data.split(":", 1)[1]
    if eng in words:
        del words[eng]
        save_words()
        await callback.message.answer(f"🗑️ Слово '{eng}' удалено.")
    else:
        await callback.message.answer("Слово не найдено.")
    await callback.answer()

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
    logging.info("Web server started on port %s", port)

# ------------------ ЗАПУСК ------------------
async def main():
    # Запускаем HTTP-заглушку и polling
    await start_web_server()
    logging.info("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        # корректное завершение бота
        try:
            await bot.session.close()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
