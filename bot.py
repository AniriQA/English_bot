#!/usr/bin/env python3
import logging
import os
import random
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from database import VocabularyDatabase

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = VocabularyDatabase()

# Состояния
ADDING_WORD, DELETING_WORD, QUIZ_EN_RU, QUIZ_RU_EN = range(4)
user_quiz = {}

# Красивые клавиатуры
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Добавить слово"), KeyboardButton("📚 Мой словарь")],
        [KeyboardButton("⏰ Квиз англ → рус"), KeyboardButton("⏰ Квиз рус → англ")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🗑️ Удалить слово")],
        [KeyboardButton("ℹ️ Помощь")]
    ], resize_keyboard=True)

def back_to_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🏠 Главное меню")]
    ], resize_keyboard=True)

def quiz_keyboard(options):
    """Клавиатура для квиза с вариантами ответов"""
    keyboard = []
    for option in options:
        keyboard.append([KeyboardButton(option)])
    keyboard.append([KeyboardButton("🏠 Главное меню")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Основные команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я твой помощник в изучении английских слов! 

✨ <b>Что я умею:</b>
• Сохранять твои слова в словарь
• Проверять знания через квизы
• Показывать статистику прогресса
• Работать с несколькими пользователями

🎯 <b>Используй кнопки ниже чтобы начать!</b>
    """
    await update.message.reply_html(welcome_text, reply_markup=main_menu_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
ℹ️ <b>Помощь по командам:</b>

<b>➕ Добавить слово</b> - добавить новое слово в формате "слово-перевод"
<b>📚 Мой словарь</b> - посмотреть все ваши слова
<b>⏰ Квиз англ → рус</b> - тест на перевод с английского на русский
<b>⏰ Квиз рус → англ</b> - тест на перевод с русского на английский
<b>📊 Статистика</b> - статистика вашего прогресса
<b>🗑️ Удалить слово</b> - удалить слово из словаря
<b>🏠 Главное меню</b> - вернуться в главное меню

💡 <b>Совет:</b> Для быстрого добавления слов просто пишите в чат в формате "слово-перевод"!
    """
    await update.message.reply_html(help_text, reply_markup=main_menu_keyboard())

# Добавление слов
async def add_word_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "📝 <b>Добавление слова</b>\n\n"
        "Введите слово и перевод через дефис:\n\n"
        "📌 <b>Примеры:</b>\n"
        "<code>hello-привет</code>\n"
        "<code>to learn-учить</code>\n"
        "<code>computer-компьютер</code>",
        reply_markup=back_to_menu_keyboard()
    )
    return ADDING_WORD

async def add_word_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🏠 Главное меню":
        await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    if '-' in text:
        try:
            word, trans = text.split('-', 1)
            word = word.strip()
            trans = trans.strip()
            
            if word and trans:
                user_id = update.effective_user.id
                if db.add_word(user_id, word, trans):
                    await update.message.reply_html(
                        f"✅ <b>Слово добавлено!</b>\n\n"
                        f"<b>🇬🇧 Английский:</b> {word}\n"
                        f"<b>🇷🇺 Русский:</b> {trans}",
                        reply_markup=main_menu_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при сохранении", reply_markup=main_menu_keyboard())
            else:
                await update.message.reply_text("❌ Пустое слово или перевод", reply_markup=main_menu_keyboard())
        except Exception as e:
            await update.message.reply_text("❌ Неверный формат", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("❌ Используйте формат: слово-перевод", reply_markup=main_menu_keyboard())
    
    return ConversationHandler.END

# Показать словарь
async def show_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)
    
    if not words:
        await update.message.reply_html(
            "📝 <b>Ваш словарь пуст</b>\n\n"
            "Добавьте первые слова используя кнопку <b>➕ Добавить слово</b> или "
            "написав в чат в формате <code>слово-перевод</code>",
            reply_markup=main_menu_keyboard()
        )
        return
    
    word_list = "\n".join([f"• <b>{word}</b> - {trans}" for word, trans in words])
    count = len(words)
    
    await update.message.reply_html(
        f"📚 <b>Ваш словарь</b> ({count} слов)\n\n{word_list}",
        reply_markup=main_menu_keyboard()
    )

# Удаление слов
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)
    
    if not words:
        await update.message.reply_html(
            "📝 <b>Словарь пуст</b>\n\nНечего удалять!",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    
    word_list = "\n".join([f"• {word}" for word, trans in words[:15]])
    await update.message.reply_html(
        f"🗑️ <b>Удаление слова</b>\n\n"
        f"Выберите слово для удаления:\n\n{word_list}\n\n"
        f"<i>Напишите слово на английском:</i>",
        reply_markup=back_to_menu_keyboard()
    )
    return DELETING_WORD

async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🏠 Главное меню":
        await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    if db.delete_word(user_id, text.strip()):
        await update.message.reply_html(
            f"✅ <b>Слово удалено!</b>\n\n<b>{text}</b>",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_html(
            f"❌ <b>Слово не найдено!</b>\n\nПроверьте правильность написания слова <b>{text}</b>",
            reply_markup=main_menu_keyboard()
        )
    
    return ConversationHandler.END

# Квизы
async def quiz_en_ru_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if db.get_word_count(user_id) < 4:
        await update.message.reply_html(
            "❌ <b>Недостаточно слов для квиза!</b>\n\n"
            "Добавьте как минимум <b>4 слова</b> в словарь чтобы начать квиз.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    
    await send_quiz_question(update, user_id, "en_ru")
    return QUIZ_EN_RU

async def quiz_ru_en_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if db.get_word_count(user_id) < 4:
        await update.message.reply_html(
            "❌ <b>Недостаточно слов для квиза!</b>\n\n"
            "Добавьте как минимум <b>4 слова</b> в словарь чтобы начать квиз.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    
    await send_quiz_question(update, user_id, "ru_en")
    return QUIZ_RU_EN

async def send_quiz_question(update: Update, user_id: int, quiz_type: str):
    """Отправка вопроса квиза с 4 вариантами ответов"""
    words = db.get_random_words(user_id, 4)
    
    if len(words) < 4:
        await update.message.reply_text("❌ Недостаточно слов", reply_markup=main_menu_keyboard())
        return
    
    correct_word, correct_translation = random.choice(words)
    
    if quiz_type == "en_ru":
        question = f"🇬🇧 <b>Переведи слово:</b>\n\n<code>{correct_word}</code>"
        options = [trans for _, trans in words]
        correct_answer = correct_translation
    else:  # ru_en
        question = f"🇷🇺 <b>Переведи слово:</b>\n\n<code>{correct_translation}</code>"
        options = [word for word, _ in words]
        correct_answer = correct_word
    
    # Перемешиваем варианты ответов
    random.shuffle(options)
    
    # Сохраняем правильный ответ
    user_quiz[user_id] = {
        'correct_answer': correct_answer,
        'quiz_type': quiz_type
    }
    
    await update.message.reply_html(question, reply_markup=quiz_keyboard(options))

async def quiz_en_ru_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ответов для квиза англ-рус"""
    return await handle_quiz_answer(update, context, QUIZ_EN_RU)

async def quiz_ru_en_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ответов для квиза рус-англ"""
    return await handle_quiz_answer(update, context, QUIZ_RU_EN)

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, quiz_state: int):
    """Обработка ответов в квизе"""
    user_id = update.effective_user.id
    user_answer = update.message.text
    
    if user_answer == "🏠 Главное меню":
        user_quiz.pop(user_id, None)
        await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    if user_id not in user_quiz:
        await update.message.reply_text("❌ Ошибка квиза", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    correct_answer = user_quiz[user_id]['correct_answer']
    quiz_type = user_quiz[user_id]['quiz_type']
    
    if user_answer == correct_answer:
        response = "✅ <b>Верно!</b> 🎉\n\n"
    else:
        if quiz_type == "en_ru":
            response = f"❌ <b>Неверно!</b>\n\nПравильный ответ: <b>{correct_answer}</b>\n\n"
        else:
            response = f"❌ <b>Неверно!</b>\n\nПравильный ответ: <b>{correct_answer}</b>\n\n"
    
    await update.message.reply_html(response)
    
    # Следующий вопрос
    await send_quiz_question(update, user_id, quiz_type)
    return quiz_state

# Статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    count = db.get_word_count(user_id)
    
    if count == 0:
        await update.message.reply_html(
            "📊 <b>Статистика</b>\n\n"
            "📝 <b>Слов в словаре:</b> 0\n\n"
            "💡 <b>Совет:</b> Добавьте первые слова чтобы начать обучение!",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_html(
            f"📊 <b>Статистика</b>\n\n"
            f"📝 <b>Слов в словаре:</b> {count}\n\n"
            f"🎯 <b>Продолжайте в том же духе!</b> 💪",
            reply_markup=main_menu_keyboard()
        )

# Прямое добавление слов (ИСПРАВЛЕННАЯ ФУНКЦИЯ)
async def direct_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик прямых сообщений (слово-перевод)"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Игнорируем сообщения, которые являются ответами в квизе
    if user_id in user_quiz:
        return
    
    # Игнорируем кнопки меню
    menu_buttons = [
        "➕ Добавить слово", "📚 Мой словарь", "⏰ Квиз англ → рус",
        "⏰ Квиз рус → англ", "📊 Статистика", "🗑️ Удалить слово",
        "ℹ️ Помощь", "🏠 Главное меню"
    ]
    if text in menu_buttons:
        return
    
    # Обрабатываем только сообщения в формате слово-перевод
    if '-' in text and len(text.split('-')) == 2:
        word, trans = text.split('-', 1)
        word = word.strip()
        trans = trans.strip()
        
        if word and trans:
            if db.add_word(user_id, word, trans):
                await update.message.reply_html(
                    f"✅ <b>Слово добавлено!</b>\n\n"
                    f"<b>🇬🇧 Английский:</b> {word}\n"
                    f"<b>🇷🇺 Русский:</b> {trans}",
                    reply_markup=main_menu_keyboard()
                )

# Главное меню
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu_keyboard())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_quiz.pop(user_id, None)
    await update.message.reply_text("❌ Действие отменено", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

def main():
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("❌ Нет токена!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handlers
    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить слово$"), add_word_start)],
        states={ADDING_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_word_handler)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    del_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑️ Удалить слово$"), delete_start)],
        states={DELETING_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_handler)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    quiz_en_ru_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⏰ Квиз англ → рус$"), quiz_en_ru_start)],
        states={QUIZ_EN_RU: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_en_ru_handler)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    quiz_ru_en_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⏰ Квиз рус → англ$"), quiz_ru_en_start)],
        states={QUIZ_RU_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_ru_en_handler)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Обычные обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.Regex("^📚 Мой словарь$"), show_words))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), stats))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Помощь$"), help_command))
    app.add_handler(MessageHandler(filters.Regex("^🏠 Главное меню$"), main_menu))
    
    # Conversation handlers
    app.add_handler(add_conv)
    app.add_handler(del_conv)
    app.add_handler(quiz_en_ru_conv)
    app.add_handler(quiz_ru_en_conv)
    
    # Прямые сообщения (исправленные)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, direct_message))
    
    logger.info("🤖 Бот запускается...")
    app.run_polling()

if __name__ == "__main__":
    main()
