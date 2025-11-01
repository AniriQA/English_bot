#!/usr/bin/env python3
import logging
import os
import random
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from bs4 import BeautifulSoup

from database import VocabularyDatabase

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db = VocabularyDatabase()

# Состояния
ADDING_WORD, DELETING_WORD, QUIZ = range(3)
user_quiz = {}

# Клавиатуры
def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Добавить слово"), KeyboardButton("📚 Словарь")],
        [KeyboardButton("⏰ Квиз"), KeyboardButton("🗑️ Удалить слово")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("❓ Помощь")]
    ], resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🏠 Главное меню")]], resize_keyboard=True)

# Основные команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для изучения слов. Используй кнопки ниже!",
        reply_markup=main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Добавляй слова: слово-перевод\n"
        "📚 Словарь - все твои слова\n"
        "⏰ Квиз - проверить знания\n"
        "🗑️ Удалить - убрать слово\n"
        "📊 Статистика - твой прогресс",
        reply_markup=main_keyboard()
    )

# Добавление слов
async def add_word_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введи слово и перевод через дефис:\nПример: hello-привет",
        reply_markup=back_keyboard()
    )
    return ADDING_WORD

async def add_word_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🏠 Главное меню":
        await update.message.reply_text("Главное меню", reply_markup=main_keyboard())
        return ConversationHandler.END
    
    if '-' in text:
        try:
            word, trans = text.split('-', 1)
            user_id = update.effective_user.id
            if db.add_word(user_id, word.strip(), trans.strip()):
                await update.message.reply_text(f"✅ Добавлено: {word.strip()} - {trans.strip()}", reply_markup=main_keyboard())
            else:
                await update.message.reply_text("❌ Ошибка", reply_markup=main_keyboard())
        except:
            await update.message.reply_text("❌ Неверный формат", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("❌ Используй: слово-перевод", reply_markup=main_keyboard())
    
    return ConversationHandler.END

# Показать словарь
async def show_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)
    
    if not words:
        await update.message.reply_text("📝 Словарь пуст", reply_markup=main_keyboard())
        return
    
    word_list = "\n".join([f"• {w} - {t}" for w, t in words])
    await update.message.reply_text(f"📚 Твои слова:\n{word_list}", reply_markup=main_keyboard())

# Удаление слов
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)
    
    if not words:
        await update.message.reply_text("📝 Нечего удалять", reply_markup=main_keyboard())
        return ConversationHandler.END
    
    word_list = "\n".join([f"• {w}" for w, t in words[:10]])
    await update.message.reply_text(
        f"🗑️ Какое слово удалить?\n{word_list}\n\nНапиши слово на английском:",
        reply_markup=back_keyboard()
    )
    return DELETING_WORD

async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🏠 Главное меню":
        await update.message.reply_text("Главное меню", reply_markup=main_keyboard())
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    if db.delete_word(user_id, text.strip()):
        await update.message.reply_text(f"✅ Удалено: {text}", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("❌ Слово не найдено", reply_markup=main_keyboard())
    
    return ConversationHandler.END

# Квиз
async def quiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if db.get_word_count(user_id) < 2:
        await update.message.reply_text("❌ Нужно минимум 2 слова", reply_markup=main_keyboard())
        return ConversationHandler.END
    
    words = db.get_random_words(user_id, 4)
    if len(words) < 2:
        await update.message.reply_text("❌ Недостаточно слов", reply_markup=main_keyboard())
        return ConversationHandler.END
    
    # Создаем вопрос
    question_word, answer = random.choice(words)
    user_quiz[user_id] = answer
    
    # Создаем варианты
    options = [t for w, t in words]
    random.shuffle(options)
    
    keyboard = [[KeyboardButton(opt)] for opt in options] + [[KeyboardButton("🏠 Главное меню")]]
    
    await update.message.reply_text(
        f"📝 Переведи: {question_word}",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return QUIZ

async def quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "🏠 Главное меню":
        user_quiz.pop(user_id, None)
        await update.message.reply_text("Главное меню", reply_markup=main_keyboard())
        return ConversationHandler.END
    
    if user_id in user_quiz:
        correct = user_quiz[user_id]
        if text == correct:
            await update.message.reply_text("✅ Верно! 🎉")
        else:
            await update.message.reply_text(f"❌ Неверно! Правильно: {correct}")
        
        # Новый вопрос
        return await quiz_start(update, context)
    
    await update.message.reply_text("❌ Ошибка квиза", reply_markup=main_keyboard())
    return ConversationHandler.END

# Статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    count = db.get_word_count(user_id)
    await update.message.reply_text(f"📊 Слов в словаре: {count}", reply_markup=main_keyboard())

# Прямое добавление слов
async def direct_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if '-' in text and len(text.split('-')) == 2:
        word, trans = text.split('-', 1)
        if db.add_word(user_id, word.strip(), trans.strip()):
            await update.message.reply_text(f"✅ Добавлено: {word.strip()} - {trans.strip()}", reply_markup=main_keyboard())

# Главное меню
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 Главное меню", reply_markup=main_keyboard())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено", reply_markup=main_keyboard())
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
        states={ADDING_WORD: [MessageHandler(filters.TEXT, add_word_handler)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    del_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑️ Удалить слово$"), delete_start)],
        states={DELETING_WORD: [MessageHandler(filters.TEXT, delete_handler)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    quiz_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⏰ Квиз$"), quiz_start)],
        states={QUIZ: [MessageHandler(filters.TEXT, quiz_handler)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.Regex("^📚 Словарь$"), show_words))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), stats))
    app.add_handler(MessageHandler(filters.Regex("^🏠 Главное меню$"), main_menu))
    app.add_handler(add_conv)
    app.add_handler(del_conv)
    app.add_handler(quiz_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, direct_message))
    
    logger.info("🤖 Бот запускается...")
    app.run_polling()

if __name__ == "__main__":
    main()
