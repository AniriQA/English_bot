#!/usr/bin/env python3
"""
Telegram Bot для изучения английских слов
"""

import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = f"""
Привет, {user.first_name}! 👋

Я помогу тебе изучать английские слова!

📝 **Как добавлять слова:**
Просто напиши слово и перевод через дефис:
Пример: hello-привет
Пример: to learn-учить

🎯 **Доступные команды:**
/start - начать работу
/words - мой словарь  
/stats - статистика
/help - помощь

Просто напиши слово и перевод, и я его запомню!
    """
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
🆘 **Помощь по командам:**

/start - начать работу с ботом
/words - посмотреть все слова в вашем словаре
/stats - статистика вашего словаря
/help - показать эту справку

📝 **Формат добавления слов:**
• Через дефис: слово-перевод
• Пример: apple-яблоко
• Пример: to run-бегать

💡 **Совет:** Просто пишите слова в чат в формате "слово-перевод"!
    """
    await update.message.reply_text(help_text)

async def words_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /words - показать словарь"""
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)
    
    if not words:
        await update.message.reply_text("📝 **Ваш словарь пуст**\nДобавьте первые слова!")
        return
    
    word_list = "\n".join([f"• {word} - {trans}" for word, trans in words[:20]])
    stats = db.get_user_stats(user_id)
    
    response = f"📚 **Ваш словарь** ({stats['total_words']} слов)\n\n{word_list}"
    
    if len(words) > 20:
        response += f"\n\n... и ещё {len(words) - 20} слов"
    
    await update.message.reply_text(response)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats - статистика"""
    user_id = update.effective_user.id
    stats = db.get_user_stats(user_id)
    
    stats_text = f"""
📊 **Ваша статистика**

📝 Всего слов: **{stats['total_words']}**
🔤 Уникальных слов: **{stats['unique_words']}**

Продолжайте в том же духе! 💪
    """
    await update.message.reply_text(stats_text)

def clean_html(text: str) -> str:
    """Очистка текста от HTML тегов"""
    soup = BeautifulSoup(text, 'html.parser')
    return soup.get_text().strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обычных сообщений"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Проверяем формат "слово-перевод"
    if '-' in text:
        try:
            clean_text = clean_html(text)
            word, translation = clean_text.split('-', 1)
            word = word.strip()
            translation = translation.strip()
            
            if word and translation:
                success = db.add_word(user_id, word, translation)
                if success:
                    await update.message.reply_text(f"✅ **Слово добавлено!**\n{word} - {translation}")
                else:
                    await update.message.reply_text("❌ Ошибка при сохранении слова")
            else:
                await update.message.reply_text("❌ Пустое слово или перевод")
                
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            await update.message.reply_text("❌ Ошибка формата. Используйте: слово-перевод")

def main():
    """Основная функция"""
    # Получаем токен из переменных окружения
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    try:
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("words", words_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Запускаем бота
        logger.info("Бот запускается...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    main()
