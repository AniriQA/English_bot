#!/usr/bin/env python3
"""
Telegram Bot для изучения английских слов
"""

import logging
import os
import random
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    ConversationHandler,
    CallbackQueryHandler
)
from bs4 import BeautifulSoup

from database import VocabularyDatabase

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = VocabularyDatabase()

# Состояния для ConversationHandler
ADDING_WORD, DELETING_WORD, QUIZ_EN_RU, QUIZ_RU_EN = range(4)

# Хранение состояний квизов
user_quiz_data = {}

# Клавиатура главного меню
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Добавить слово"), KeyboardButton("📚 Мой словарь")],
        [KeyboardButton("⏰ Квиз англ-рус"), KeyboardButton("⏰ Квиз рус-англ")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🗑️ Удалить слово")],
        [KeyboardButton("❓ Помощь")]
    ], resize_keyboard=True)

# Клавиатура возврата в меню
def back_to_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🏠 Главное меню")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = f"""
Привет, {user.first_name}! 👋

Я помогу тебе изучать английские слова!

🎯 **Доступные команды:**
➕ Добавить слово - добавить новое слово
📚 Мой словарь - посмотреть все слова  
⏰ Квиз англ-рус - проверить знания
⏰ Квиз рус-англ - проверить знания
📊 Статистика - ваша статистика
🗑️ Удалить слово - удалить слово из словаря
❓ Помощь - справка по командам

📝 **Формат добавления слов:**
Просто напиши: слово-перевод
Пример: hello-привет
    """
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
🆘 **Помощь по командам:**

➕ Добавить слово - добавить новое слово в формате "слово-перевод"
📚 Мой словарь - посмотреть все ваши слова
⏰ Квиз англ-рус - тест на перевод с английского на русский
⏰ Квиз рус-англ - тест на перевод с русского на английский
📊 Статистика - статистика вашего прогресса
🗑️ Удалить слово - удалить слово из словаря
🏠 Главное меню - вернуться в главное меню

💡 **Совет:** Для быстрого добавления слов просто пишите в чат в формате "слово-перевод"!
    """
    await update.message.reply_text(help_text, reply_markup=main_menu_keyboard())

async def add_word_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки Добавить слово"""
    await update.message.reply_text(
        "📝 Введите слово и перевод через дефис:\n\n"
        "Пример: <code>hello-привет</code>\n"
        "Пример: <code>to learn-учить</code>\n\n"
        "Или отправьте /cancel для отмены",
        parse_mode='HTML',
        reply_markup=back_to_menu_keyboard()
    )
    return ADDING_WORD

async def add_word_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик добавления слова"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "🏠 Главное меню":
        await update.message.reply_text("Возвращаемся в главное меню!", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    success, message = await process_word_addition(user_id, text)
    await update.message.reply_text(message, reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def process_word_addition(user_id: int, text: str):
    """Обработка добавления слова"""
    try:
        clean_text = clean_html(text)
        
        if '-' not in clean_text:
            return False, "❌ **Неверный формат!**\nИспользуйте: слово-перевод\nПример: hello-привет"
        
        word, translation = clean_text.split('-', 1)
        word = word.strip()
        translation = translation.strip()
        
        if not word or not translation:
            return False, "❌ **Пустое слово или перевод!**\nУбедитесь, что оба поля заполнены."
        
        success = db.add_word(user_id, word, translation)
        
        if success:
            return True, f"✅ **Слово добавлено!**\n{word} - {translation}"
        else:
            return False, "❌ **Ошибка при сохранении!**\nПопробуйте еще раз."
            
    except Exception as e:
        logger.error(f"Error processing word addition: {e}")
        return False, "❌ **Произошла ошибка!**\nПопробуйте другой формат."

async def show_vocabulary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать словарь пользователя"""
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)
    
    if not words:
        await update.message.reply_text(
            "📝 **Ваш словарь пуст**\nДобавьте первые слова!",
            reply_markup=main_menu_keyboard()
        )
        return
    
    word_list = "\n".join([f"• **{word}** - {trans}" for word, trans in words[:30]])
    stats = db.get_user_stats(user_id)
    
    response = f"📚 **Ваш словарь** ({stats['total_words']} слов)\n\n{word_list}"
    
    if len(words) > 30:
        response += f"\n\n... и ещё {len(words) - 30} слов"
    
    await update.message.reply_text(response, reply_markup=main_menu_keyboard())

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    user_id = update.effective_user.id
    stats = db.get_user_stats(user_id)
    
    stats_text = f"""
📊 **Ваша статистика**

📝 Всего слов: **{stats['total_words']}**
🔤 Уникальных слов: **{stats['unique_words']}**

Продолжайте в том же духе! 💪
    """
    await update.message.reply_text(stats_text, reply_markup=main_menu_keyboard())

async def delete_word_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки Удалить слово"""
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)
    
    if not words:
        await update.message.reply_text(
            "📝 **Ваш словарь пуст**\nНечего удалять!",
            reply_markup=main_menu_keyboard()
        )
        return
    
    word_list = "\n".join([f"• {word}" for word, trans in words[:20]])
    await update.message.reply_text(
        f"🗑️ **Выберите слово для удаления:**\n\n{word_list}\n\n"
        "Просто напишите слово на английском, которое хотите удалить:",
        reply_markup=back_to_menu_keyboard()
    )
    return DELETING_WORD

async def delete_word_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик удаления слова"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "🏠 Главное меню":
        await update.message.reply_text("Возвращаемся в главное меню!", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    word_to_delete = text.strip()
    success = db.delete_word(user_id, word_to_delete)
    
    if success:
        await update.message.reply_text(f"✅ **Слово удалено!**\n{word_to_delete}", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(f"❌ **Слово не найдено!**\nПроверьте правильность написания.", reply_markup=main_menu_keyboard())
    
    return ConversationHandler.END

async def start_quiz_en_ru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать квиз английский-русский"""
    user_id = update.effective_user.id
    
    if db.get_word_count(user_id) < 4:
        await update.message.reply_text(
            "❌ **Недостаточно слов для квиза!**\nДобавьте хотя бы 4 слова в словарь.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    await send_quiz_question(update, user_id, "en_ru")
    return QUIZ_EN_RU

async def start_quiz_ru_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать квиз русский-английский"""
    user_id = update.effective_user.id
    
    if db.get_word_count(user_id) < 4:
        await update.message.reply_text(
            "❌ **Недостаточно слов для квиза!**\nДобавьте хотя бы 4 слова в словарь.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    await send_quiz_question(update, user_id, "ru_en")
    return QUIZ_RU_EN

async def send_quiz_question(update: Update, user_id: int, quiz_type: str):
    """Отправить вопрос квиза"""
    words = db.get_random_words_for_quiz(user_id, 4)
    
    if len(words) < 4:
        await update.message.reply_text(
            "❌ **Недостаточно слов для квиза!**",
            reply_markup=main_menu_keyboard()
        )
        return
    
    correct_word, correct_translation = random.choice(words)
    
    if quiz_type == "en_ru":
        question = f"📝 **Как переводится слово:**\n**{correct_word}**"
        options = [trans for _, trans in words]
        correct_answer = correct_translation
    else:  # ru_en
        question = f"📝 **Как переводится слово:**\n**{correct_translation}**"
        options = [word for word, _ in words]
        correct_answer = correct_word
    
    # Перемешиваем варианты ответов
    random.shuffle(options)
    
    # Сохраняем правильный ответ
    user_quiz_data[user_id] = {
        'correct_answer': correct_answer,
        'quiz_type': quiz_type
    }
    
    # Создаем клавиатуру с вариантами
    keyboard = []
    for option in options:
        keyboard.append([KeyboardButton(option)])
    keyboard.append([KeyboardButton("🏠 Главное меню")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(question, reply_markup=reply_markup)

async def quiz_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, quiz_state: int):
    """Обработчик ответов в квизе"""
    user_id = update.effective_user.id
    user_answer = update.message.text
    
    if user_answer == "🏠 Главное меню":
        if user_id in user_quiz_data:
            del user_quiz_data[user_id]
        await update.message.reply_text("Возвращаемся в главное меню!", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    if user_id not in user_quiz_data:
        await update.message.reply_text("❌ Ошибка квиза. Начните заново.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    correct_answer = user_quiz_data[user_id]['correct_answer']
    quiz_type = user_quiz_data[user_id]['quiz_type']
    
    if user_answer == correct_answer:
        response = "✅ **Верно!** 🎉"
    else:
        if quiz_type == "en_ru":
            response = f"❌ **Неверно!**\nПравильный ответ: **{correct_answer}**"
        else:
            response = f"❌ **Неверно!**\nПравильный ответ: **{correct_answer}**"
    
    await update.message.reply_text(response)
    
    # Следующий вопрос
    await send_quiz_question(update, user_id, quiz_type)
    return quiz_state

async def quiz_en_ru_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для квиза англ-рус"""
    return await quiz_answer_handler(update, context, QUIZ_EN_RU)

async def quiz_ru_en_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для квиза рус-англ"""
    return await quiz_answer_handler(update, context, QUIZ_RU_EN)

async def handle_direct_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик прямых сообщений (слово-перевод)"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Если сообщение в формате слово-перевод
    if '-' in text and len(text.split('-')) == 2:
        success, message = await process_word_addition(user_id, text)
        await update.message.reply_text(message, reply_markup=main_menu_keyboard())

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки Главное меню"""
    await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu_keyboard())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены"""
    user_id = update.effective_user.id
    if user_id in user_quiz_data:
        del user_quiz_data[user_id]
    
    await update.message.reply_text("Действие отменено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

def clean_html(text: str) -> str:
    """Очистка текста от HTML тегов"""
    soup = BeautifulSoup(text, 'html.parser')
    return soup.get_text().strip()

def main():
    """Основная функция"""
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # ConversationHandler для добавления слов
        add_conversation = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^➕ Добавить слово$"), add_word_button)],
            states={
                ADDING_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_word_handler)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        
        # ConversationHandler для удаления слов
        delete_conversation = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^🗑️ Удалить слово$"), delete_word_button)],
            states={
                DELETING_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_word_handler)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        
        # ConversationHandler для квиза англ-рус
        quiz_en_ru_conversation = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^⏰ Квиз англ-рус$"), start_quiz_en_ru)],
            states={
                QUIZ_EN_RU: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_en_ru_handler)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        
        # ConversationHandler для квиза рус-англ
        quiz_ru_en_conversation = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^⏰ Квиз рус-англ$"), start_quiz_ru_en)],
            states={
                QUIZ_RU_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_ru_en_handler)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        
        # Обычные обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.Regex("^📚 Мой словарь$"), show_vocabulary))
        application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), show_stats))
        application.add_handler(MessageHandler(filters.Regex("^🏠 Главное меню$"), handle_main_menu))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_direct_message))
        
        # Conversation handlers
        application.add_handler(add_conversation)
        application.add_handler(delete_conversation)
        application.add_handler(quiz_en_ru_conversation)
        application.add_handler(quiz_ru_en_conversation)
        
        logger.info("Бот запускается...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    main()
