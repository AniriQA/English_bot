#!/usr/bin/env python3
"""
Telegram Bot для изучения английских слов
Хранит словари пользователей в SQLite базе данных
"""

import logging
import re
from html import escape
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    ConversationHandler
)
from bs4 import BeautifulSoup

from database import VocabularyDatabase

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
ADDING_WORD = 1

# Инициализация базы данных
db = VocabularyDatabase()

class VocabularyBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        
        # Обработчик команды /start
        start_handler = CommandHandler('start', self.start_command)
        
        # Обработчик команды /words - показать словарь
        words_handler = CommandHandler('words', self.words_command)
        
        # Обработчик команды /stats - статистика
        stats_handler = CommandHandler('stats', self.stats_command)
        
        # Обработчик команды /add - добавить слово (с клавиатурой)
        add_handler = CommandHandler('add', self.add_command)
        
        # Обработчик команды /help
        help_handler = CommandHandler('help', self.help_command)
        
        # Обработчик команды /cancel - отмена
        cancel_handler = CommandHandler('cancel', self.cancel_command)
        
        # ConversationHandler для добавления слов
        add_conversation = ConversationHandler(
            entry_points=[CommandHandler('addword', self.addword_command)],
            states={
                ADDING_WORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.addword_handler)
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_command)],
        )
        
        # Обработчик обычных сообщений (слово-перевод)
        message_handler = MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.message_handler
        )
        
        # Добавляем все обработчики
        handlers = [
            start_handler, words_handler, stats_handler, 
            add_handler, help_handler, cancel_handler,
            add_conversation, message_handler
        ]
        
        for handler in handlers:
            self.application.add_handler(handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_text = f"""
Привет, {user.first_name}! 👋

Я помогу тебе изучать английские слова!

📝 **Как добавлять слова:**
• Напиши слово и перевод через дефис
• Пример: `hello-привет`
• Пример: `to learn-учить`

🎯 **Доступные команды:**
/start - начать работу
/addword - добавить слово
/words - мой словарь
/stats - статистика
/help - помощь

Просто напиши слово и перевод, и я его запомню!
        """
        await update.message.reply_text(welcome_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🆘 **Помощь по командам:**

/start - начать работу с ботом
/addword - добавить новое слово (пошагово)
/words - посмотреть все слова в вашем словаре
/stats - статистика вашего словаря
/help - показать эту справку

📝 **Формат добавления слов:**
• Через дефис: `word-перевод`
• Пример: `apple-яблоко`
• Пример: `to run-бегать`

💡 **Совет:** Вы можете просто писать слова в чат в формате "слово-перевод", и бот автоматически их добавит!
        """
        await update.message.reply_text(help_text)
    
    async def addword_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса добавления слова"""
        await update.message.reply_text(
            "Введите слово и перевод через дефис:\n"
            "Пример: computer-компьютер\n\n"
            "Или отправьте /cancel для отмены"
        )
        return ADDING_WORD
    
    async def addword_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик добавления слова в режиме Conversation"""
        user_id = update.effective_user.id
        text = update.message.text
        
        success, message = await self.process_word_addition(user_id, text)
        await update.message.reply_text(message)
        
        return ConversationHandler.END
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик обычных сообщений (автоматическое добавление слов)"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Проверяем формат "слово-перевод"
        if '-' in text and len(text.split('-')) == 2:
            success, message = await self.process_word_addition(user_id, text)
            await update.message.reply_text(message)
    
    async def process_word_addition(self, user_id: int, text: str):
        """Обработка добавления слова"""
        try:
            # Очищаем текст от HTML тегов
            clean_text = self.clean_html(text)
            
            if '-' not in clean_text:
                return False, "❌ **Неверный формат!**\nИспользуйте: слово-перевод\nПример: hello-привет"
            
            word, translation = clean_text.split('-', 1)
            word = word.strip()
            translation = translation.strip()
            
            if not word or not translation:
                return False, "❌ **Пустое слово или перевод!**\nУбедитесь, что оба поля заполнены."
            
            # Добавляем в базу данных
            success = db.add_word(user_id, word, translation)
            
            if success:
                return True, f"✅ **Слово добавлено!**\n{word} - {translation}"
            else:
                return False, "❌ **Ошибка при сохранении!**\nПопробуйте еще раз."
                
        except Exception as e:
            logger.error(f"Error processing word addition: {e}")
            return False, "❌ **Произошла ошибка!**\nПопробуйте другой формат."
    
    async def words_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /words - показать словарь"""
        user_id = update.effective_user.id
        
        words = db.get_user_words(user_id)
        
        if not words:
            await update.message.reply_text("📝 **Ваш словарь пуст**\nДобавьте первые слова!")
            return
        
        # Формируем список слов (максимум 50 для избежания переполнения)
        word_list = "\n".join([f"• **{word}** - {trans}" for word, trans in words[:50]])
        
        stats = db.get_user_stats(user_id)
        
        response = f"""
📚 **Ваш словарь** ({stats['total_words']} слов)

{word_list}
        """
        
        if len(words) > 50:
            response += f"\n\n... и еще {len(words) - 50} слов"
        
        await update.message.reply_text(response)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    async def add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /add (устаревшая)"""
        await update.message.reply_text(
            "Команда /add устарела. Используйте /addword для пошагового добавления "
            "или просто пишите слова в формате 'слово-перевод' в чат!"
        )
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /cancel"""
        await update.message.reply_text(
            "Действие отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    def clean_html(self, text: str) -> str:
        """Очистка текста от HTML тегов"""
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text().strip()
    
    def run(self):
        """Запуск бота"""
        logger.info("Бот запущен...")
        self.application.run_polling()

def main():
    """Основная функция"""
    
    # Токен бота (замените на свой)
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ← ЗАМЕНИТЕ НА ВАШ ТОКЕН!
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ОШИБКА: Замените BOT_TOKEN на ваш реальный токен бота!")
        print("1. Получите токен у @BotFather в Telegram")
        print("2. Откройте файл bot.py")
        print("3. Замените 'YOUR_BOT_TOKEN_HERE' на ваш токен")
        return
    
    try:
        bot = VocabularyBot(BOT_TOKEN)
        bot.run()
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    main()
