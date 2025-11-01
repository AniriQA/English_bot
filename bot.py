import json
import logging
import os
from gtts import gTTS
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# -----------------------
# Настройки
# -----------------------
TOKEN = os.getenv("BOT_TOKEN")  # помести токен в переменные окружения
WORDS_FILE = "words.json"
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# -----------------------
# Работа со словами
# -----------------------
def load_words():
    try:
        with open(WORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_words(words):
    with open(WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=4)

# -----------------------
# Команды
# -----------------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Добавить слово", callback_data="add"),
        InlineKeyboardButton("Удалить слово", callback_data="delete"),
        InlineKeyboardButton("Квиз", callback_data="quiz"),
        InlineKeyboardButton("TTS", callback_data="tts")
    )
    await message.answer("Выберите действие:", reply_markup=kb)

# -----------------------
# Добавление слова
# -----------------------
@dp.callback_query(lambda c: c.data == "add")
async def add_word_start(callback: types.CallbackQuery):
    await callback.message.answer("Введите слово и перевод через двоеточие, например:\nhello:привет")
    await callback.answer()
    dp.message.register(add_word_handler, F.text, state=None)

async def add_word_handler(message: types.Message):
    text = message.text.strip()
    if ":" not in text:
        await message.answer("Неверный формат. Используйте слово:перевод")
        return
    word, translation = map(str.strip, text.split(":", 1))
    words = load_words()
    words[word] = translation
    save_words(words)
    await message.answer(f"✅ Слово '{word}' добавлено!")

# -----------------------
# Удаление слова
# -----------------------
@dp.callback_query(lambda c: c.data == "delete")
async def delete_word_start(callback: types.CallbackQuery):
    words = load_words()
    if not words:
        await callback.message.answer("Словарь пуст!")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for w in words.keys():
        kb.button(text=w, callback_data=f"delete_{w}")
    await callback.message.answer("Выберите слово для удаления:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def delete_word(callback: types.CallbackQuery):
    word = callback.data[len("delete_"):]
    words = load_words()
    if word in words:
        words.pop(word)
        save_words(words)
        await callback.message.answer(f"✅ Слово '{word}' удалено!")
    else:
        await callback.message.answer("❌ Слово не найдено.")
    await callback.answer()

# -----------------------
# TTS
# -----------------------
@dp.callback_query(lambda c: c.data == "tts")
async def tts_start(callback: types.CallbackQuery):
    words = load_words()
    if not words:
        await callback.message.answer("Словарь пуст!")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for w in words.keys():
        kb.button(text=w, callback_data=f"tts_{w}")
    await callback.message.answer("Выберите слово для озвучки:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("tts_"))
async def tts_word(callback: types.CallbackQuery):
    word = callback.data[len("tts_"):]
    words = load_words()
    if word not in words:
        await callback.message.answer("Слово не найдено!")
        await callback.answer()
        return

    tts = gTTS(word, lang="en")
    filename = f"tts_{word}.mp3"
    tts.save(filename)
    await callback.message.answer_audio(open(filename, "rb"))
    os.remove(filename)
    await callback.answer()

# -----------------------
# Квиз
# -----------------------
@dp.callback_query(lambda c: c.data == "quiz")
async def quiz_start(callback: types.CallbackQuery):
    words = load_words()
    if not words:
        await callback.message.answer("Словарь пуст!")
        await callback.answer()
        return

    import random
    word, translation = random.choice(list(words.items()))
    kb = InlineKeyboardMarkup(row_width=2)
    options = list(words.values())
    if translation not in options:
        options.append(translation)
    random.shuffle(options)
    for opt in options[:4]:
        kb.add(InlineKeyboardButton(opt, callback_data=f"quiz_{word}_{opt}"))
    await callback.message.answer(f"Выберите правильный перевод для слова '{word}':", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("quiz_"))
async def quiz_answer(callback: types.CallbackQuery):
    _, word, answer = callback.data.split("_", 2)
    words = load_words()
    correct = words.get(word)
    if answer == correct:
        await callback.message.answer("✅ Правильно!")
    else:
        await callback.message.answer(f"❌ Неправильно! Правильный ответ: {correct}")
    await callback.answer()

# -----------------------
# Запуск бота
# -----------------------
if __name__ == "__main__":
    import asyncio
    from aiogram import exceptions

    async def main():
        try:
            await dp.start_polling(bot)
        except exceptions.TelegramRetryAfter as e:
            logging.error(f"TelegramRetryAfter: {e}")
        except Exception as e:
            logging.exception("Ошибка при запуске бота")

    asyncio.run(main())
