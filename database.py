"""
Модуль для работы с базой данных SQLite
Хранит словари пользователей
"""

import sqlite3
import logging
import random
from typing import List, Tuple, Dict, Any
import os

# Настройка логирования
logger = logging.getLogger(__name__)

class VocabularyDatabase:
    def __init__(self, db_path: str = "vocabulary.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_vocabulary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        word TEXT NOT NULL,
                        translation TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
            logger.info("База данных инициализирована успешно")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    def add_word(self, user_id: int, word: str, translation: str) -> bool:
        """Добавление слова в словарь пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO user_vocabulary (user_id, word, translation)
                    VALUES (?, ?, ?)
                ''', (user_id, word.strip(), translation.strip()))
                conn.commit()
            logger.info(f"Добавлено слово для user_id {user_id}: {word} - {translation}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления слова: {e}")
            return False
    
    def get_user_words(self, user_id: int) -> List[Tuple[str, str]]:
        """Получение всех слов пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT word, translation FROM user_vocabulary 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC
                ''', (user_id,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка получения слов пользователя {user_id}: {e}")
            return []
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM user_vocabulary WHERE user_id = ?
                ''', (user_id,))
                total_words = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(DISTINCT word) FROM user_vocabulary WHERE user_id = ?
                ''', (user_id,))
                unique_words = cursor.fetchone()[0]
                
                return {
                    'total_words': total_words,
                    'unique_words': unique_words
                }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {'total_words': 0, 'unique_words': 0}
    
    def delete_word(self, user_id: int, word: str) -> bool:
        """Удаление слова из словаря пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM user_vocabulary 
                    WHERE user_id = ? AND word = ?
                ''', (user_id, word))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Удалено слово для user_id {user_id}: {word}")
                return deleted
        except Exception as e:
            logger.error(f"Ошибка удаления слова: {e}")
            return False
    
    def get_random_words_for_quiz(self, user_id: int, limit: int = 4) -> List[Tuple[str, str]]:
        """Получение случайных слов для квиза"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT word, translation FROM user_vocabulary 
                    WHERE user_id = ? 
                    ORDER BY RANDOM() 
                    LIMIT ?
                ''', (user_id, limit))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка получения слов для квиза: {e}")
            return []
    
    def get_word_count(self, user_id: int) -> int:
        """Получение количества слов пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM user_vocabulary WHERE user_id = ?
                ''', (user_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Ошибка получения количества слов: {e}")
            return 0
