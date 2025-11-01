import sqlite3
import logging
import random
from typing import List, Tuple

logger = logging.getLogger(__name__)

class VocabularyDatabase:
    def __init__(self, db_path: str = "vocabulary.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS words (
                    user_id INTEGER,
                    word TEXT,
                    translation TEXT,
                    PRIMARY KEY (user_id, word)
                )
            ''')
            conn.commit()
            conn.close()
            logger.info("✅ База данных готова")
        except Exception as e:
            logger.error(f"❌ Ошибка БД: {e}")
    
    def add_word(self, user_id: int, word: str, translation: str) -> bool:
        """Добавление слова"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO words (user_id, word, translation) VALUES (?, ?, ?)",
                (user_id, word.strip(), translation.strip())
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления: {e}")
            return False
    
    def get_user_words(self, user_id: int) -> List[Tuple[str, str]]:
        """Получение слов пользователя"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT word, translation FROM words WHERE user_id = ? ORDER BY word",
                (user_id,)
            )
            words = cursor.fetchall()
            conn.close()
            return words
        except Exception as e:
            logger.error(f"❌ Ошибка получения слов: {e}")
            return []
    
    def delete_word(self, user_id: int, word: str) -> bool:
        """Удаление слова"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM words WHERE user_id = ? AND word = ?",
                (user_id, word)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"❌ Ошибка удаления: {e}")
            return False
    
    def get_random_words(self, user_id: int, limit: int = 4) -> List[Tuple[str, str]]:
        """Случайные слова для квиза"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT word, translation FROM words WHERE user_id = ? ORDER BY RANDOM() LIMIT ?",
                (user_id, limit)
            )
            words = cursor.fetchall()
            conn.close()
            return words
        except Exception as e:
            logger.error(f"❌ Ошибка квиза: {e}")
            return []
    
    def get_word_count(self, user_id: int) -> int:
        """Количество слов"""
        words = self.get_user_words(user_id)
        return len(words)
