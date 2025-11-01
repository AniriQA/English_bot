import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- Настройки ---
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")  # Добавь BOT_TOKEN в Secrets Replit или .env
bot = Bot(token=TOKEN)
dp = Dispatcher()


# --- Клавиатуры ---
def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📘 Уроки", callback_data="lessons")
    kb.button(text="🎧 Аудио", callback_data="audio")
    kb.button(text="📝 Тесты", callback_data="tests")
    kb.button(text="⚙️ Настройки", callback_data="settings")
    kb.adjust(2)
    return kb.as_markup()


def lessons_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔤 Английский алфавит", callback_data="lesson_abc")
    kb.button(text="🕒 Время", callback_data="lesson_time")
    kb.button(text="🔙 Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def settings_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🌗 Тема интерфейса", callback_data="theme")
    kb.button(text="🌍 Сменить язык", callback_data="lang")
    kb.button(text="🔙 Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


# --- Обработчики ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я учебный бот по английскому языку.\n"
        "Выбери раздел:",
        reply_markup=main_menu_kb()
    )


# --- Главное меню ---
@dp.callback_query(F.data == "lessons")
async def cb_lessons(callback: types.CallbackQuery):
    await callback.message.edit_text("📘 Выбери урок:", reply_markup=lessons_kb())


@dp.callback_query(F.data == "audio")
async def cb_audio(callback: types.CallbackQuery):
    await callback.message.edit_text("🎧 Раздел аудио пока в разработке.", reply_markup=main_menu_kb())


@dp.callback_query(F.data == "tests")
async def cb_tests(callback: types.CallbackQuery):
    await callback.message.edit_text("📝 Раздел тестов в разработке.", reply_markup=main_menu_kb())


@dp.callback_query(F.data == "settings")
async def cb_settings(callback: types.CallbackQuery):
    await callback.message.edit_text("⚙️ Настройки:", reply_markup=settings_kb())


# --- Уроки ---
@dp.callback_query(F.data == "lesson_abc")
async def lesson_abc(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🔤 Английский алфавит:\n\nA B C D E F G H I J K L M\nN O P Q R S T U V W X Y Z",
        reply_markup=lessons_kb()
    )


@dp.callback_query(F.data == "lesson_time")
async def lesson_time(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🕒 Как сказать время по-английски:\n\nIt's 5 o'clock — Сейчас 5 часов.\n"
        "Half past six — Половина седьмого.",
        reply_markup=lessons_kb()
    )


# --- Настройки ---
@dp.callback_query(F.data == "theme")
async def theme_change(callback: types.CallbackQuery):
    await callback.message.edit_text("🌗 Выбор темы пока недоступен.", reply_markup=settings_kb())


@dp.callback_query(F.data == "lang")
async def lang_change(callback: types.CallbackQuery):
    await callback.message.edit_text("🌍 Переключение языка в разработке.", reply_markup=settings_kb())


# --- Кнопка «Назад» ---
@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())


# --- Обработка ошибок ---
@dp.errors()
async def errors_handler(update, exception):
    logging.error(f"Ошибка: {exception}")
    return True


# --- Запуск ---
async def main():
    print("✅ Бот запущен и готов к работе")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
