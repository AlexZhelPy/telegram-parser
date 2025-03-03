import sqlite3
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("parser.log"),
        logging.StreamHandler()
    ]
)

class Database:
    def __init__(self, db_name='telegram_parser.db'):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        try:
            # Таблица для хранения полных сообщений
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_name TEXT,
                    message_text TEXT,
                    message_date DATETIME
                )
            ''')

            # Таблица для хранения преобразованных библиотек
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS transformed_libraries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_name TEXT,
                    original_description TEXT,
                    transformed_description TEXT,
                    image_path TEXT
                )
            ''')

            # Таблица для хранения последней даты сканирования
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS last_scan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_name TEXT UNIQUE,
                    last_message_date DATETIME
                )
            ''')

            # Таблица для хранения промтов (с тремя полями)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    message_prompt TEXT,
                    image_prompt TEXT,
                    name_prompt TEXT
                )
            ''')

            self.conn.commit()
            logging.info("Таблицы в базе данных успешно созданы.")
        except Exception as e:
            logging.error(f"Ошибка при создании таблиц: {e}")

    def save_message(self, channel_name, message_text, message_date):
        try:
            self.cursor.execute('''
                INSERT INTO messages (channel_name, message_text, message_date)
                VALUES (?, ?, ?)
            ''', (channel_name, message_text, message_date))
            self.conn.commit()
            logging.info(f"Сообщение сохранено: {message_text[:50]}...")
        except Exception as e:
            logging.error(f"Ошибка при сохранении сообщения: {e}")

    def delete_message(self, message_id):
        try:
            self.cursor.execute('''
                DELETE FROM messages WHERE id = ?
            ''', (message_id,))
            self.conn.commit()
            logging.info(f"Сообщение с ID {message_id} удалено.")
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")

    def get_last_scan_date(self, channel_name):
        self.cursor.execute('''
            SELECT last_message_date FROM last_scan WHERE channel_name = ?
        ''', (channel_name,))
        row = self.cursor.fetchone()
        if row:
            # Преобразуем строку даты в объект datetime
            return datetime.fromisoformat(row[0])
        logging.info(f"Для канала {channel_name} последняя дата сканирования не найдена.")
        return None

    def update_last_scan_date(self, channel_name, last_message_date):
        self.cursor.execute('''
            INSERT OR REPLACE INTO last_scan (channel_name, last_message_date)
            VALUES (?, ?)
        ''', (channel_name, last_message_date))
        self.conn.commit()

    def save_transformed_library(self, library_name, original_description, transformed_description, image_path):
        try:
            self.cursor.execute('''
                INSERT INTO transformed_libraries (library_name, original_description, transformed_description, image_path)
                VALUES (?, ?, ?, ?)
            ''', (library_name, original_description, transformed_description, image_path))
            self.conn.commit()
            logging.info(f"Преобразованная библиотека сохранена")
        except Exception as e:
            logging.error(f"Ошибка при сохранении преобразованной библиотеки: {e}")

    def get_messages(self, limit=None):
        """
            Возвращает историю сканирования с ограничением по количеству записей.
            """
        try:
            query = '''
                    SELECT channel_name, message_text, message_date FROM messages
                    ORDER BY id DESC
                '''
            if limit:
                query += f' LIMIT {limit}'

            self.cursor.execute(query)
            history = self.cursor.fetchall()
            logging.info(f"Получено {len(history)} записей истории сканирования.")
            return history
        except Exception as e:
            logging.error(f"Ошибка при получении истории сканирования: {e}")
            return []

    def get_last_scan_messages(self):
        try:
            self.cursor.execute('''
                SELECT id, message_text, message_date FROM messages
                ORDER BY id DESC
                LIMIT 5
            ''')
            messages = self.cursor.fetchall()
            logging.info(f"Получено {len(messages)} сообщений для канала.")
            return messages
        except Exception as e:
            logging.error(f"Ошибка при получении сообщений: {e}")
            return []

    def get_transformed_libraries(self):
        """
        Возвращает все преобразованные сообщения из таблицы transformed_libraries.
        """
        try:
            self.cursor.execute('''
                SELECT library_name, transformed_description, image_path FROM transformed_libraries
            ''')
            libraries = self.cursor.fetchall()
            logging.info(f"Получено {len(libraries)} преобразованных библиотек.")
            return libraries
        except Exception as e:
            logging.error(f"Ошибка при получении преобразованных библиотек: {e}")
            return []

    # Методы для работы с промтами
    def save_prompt(self, name, message_prompt, image_prompt, name_prompt):
        try:
            self.cursor.execute('''
                INSERT INTO prompts (name, message_prompt, image_prompt, name_prompt)
                VALUES (?, ?, ?, ?)
            ''', (name, message_prompt, image_prompt, name_prompt))
            self.conn.commit()
            logging.info(f"Промт '{name}' сохранен.")
        except Exception as e:
            logging.error(f"Ошибка при сохранении промта: {e}")

    def get_prompts(self):
        try:
            self.cursor.execute('''
                SELECT id, name, message_prompt, image_prompt, name_prompt FROM prompts
            ''')
            prompts = self.cursor.fetchall()
            logging.info(f"Получено {len(prompts)} промтов.")
            return prompts
        except Exception as e:
            logging.error(f"Ошибка при получении промтов: {e}")
            return []

    def update_prompt(self, prompt_id, message_prompt, image_prompt, name_prompt):
        try:
            self.cursor.execute('''
                UPDATE prompts
                SET message_prompt = ?, image_prompt = ?, name_prompt = ?
                WHERE id = ?
            ''', (message_prompt, image_prompt, name_prompt, prompt_id))
            self.conn.commit()
            logging.info(f"Промт с ID {prompt_id} обновлен.")
        except Exception as e:
            logging.error(f"Ошибка при обновлении промта: {e}")

    def delete_prompt(self, prompt_id):
        try:
            self.cursor.execute('''
                DELETE FROM prompts WHERE id = ?
            ''', (prompt_id,))
            self.conn.commit()
            logging.info(f"Промт с ID {prompt_id} удален.")
        except Exception as e:
            logging.error(f"Ошибка при удалении промта: {e}")

    def close(self):
        self.conn.close()
        logging.info("Соединение с базой данных закрыто.")