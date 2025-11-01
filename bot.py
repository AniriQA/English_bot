import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from gtts import gTTS

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()


# === Клавиатура ===
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎧 Озвучить", callback_data="tts")
    kb.button(text="📘 Уроки", callback_data="lessons")
    kb.adjust(2)
    return kb.as_markup()


# === Команда /start ===
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Привет 👋 Я бот для изучения английского языка!\nВыбери действие:",
        reply_markup=main_menu()
    )


@dp.callback_query(lambda c: c.data == "lessons")
async def lessons(callback: types.CallbackQuery):
    await callback.message.answer("📘 Уроки скоро появятся!")


@dp.callback_query(lambda c: c.data == "tts")
async def tts_menu(callback: types.CallbackQuery):
    await callback.message.answer("🎧 Отправь мне текст, и я озвучу его на английском!")


@dp.message()
async def voice_generator(message: types.Message):
    if not message.text:
        return
    try:
        tts = gTTS(message.text, lang="en")
        file_path = f"voice_{message.from_user.id}.mp3"
        tts.save(file_path)
        await message.reply_audio(audio=open(file_path, "rb"))
        os.remove(file_path)
    except Exception as e:
        await message.answer(f"Ошибка при озвучивании: {e}")


async def main():
    logging.info("✅ Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
