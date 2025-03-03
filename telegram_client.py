import re
import asyncio
import logging
from telethon import TelegramClient

class TelegramClientWrapper:
    def __init__(self, api_id, api_hash):
        self.client = None
        self.api_id = api_id
        self.api_hash = api_hash
        self.is_connected = False
        self.loop = asyncio.get_event_loop()  # Получаем текущий цикл событий

    async def connect(self):
        if not self.is_connected:
            self.client = TelegramClient('session_name', self.api_id, self.api_hash)
            await self.client.start()
            self.is_connected = True
            logging.info("Подключение к Telegram успешно установлено")

    async def disconnect(self):
        if self.is_connected:
            await self.client.disconnect()
            self.is_connected = False

    def contains_keywords(self, text, keywords):
        """
        Проверяет, есть ли в тексте хотя бы одно из ключевых слов.
        """
        if not keywords:
            return True  # Если ключевые слова не заданы, считаем, что условие выполнено
        return any(keyword.strip().lower() in text.lower() for keyword in keywords)

    def contains_exclude_words(self, text, exclude_words):
        """
        Проверяет, есть ли в тексте хотя бы одно из исключаемых слов.
        """
        if not exclude_words or exclude_words == ['']:
            return False  # Если исключаемые слова не заданы, считаем, что условие не выполнено
        return any(exclude_word.strip().lower() in text.lower() for exclude_word in exclude_words)

    def is_message_valid(self, text, keywords, exclude_words):
        """
        Проверяет, соответствует ли сообщение условиям:
        - Если ключевые слова заданы, сообщение должно содержать хотя бы одно из них.
        - Если исключаемые слова заданы, сообщение не должно содержать ни одного из них.
        - Если оба поля пусты, сообщение считается валидным.
        """
        # Проверяем, есть ли в сообщении ключевые слова (если они заданы)
        if keywords and not self.contains_keywords(text, keywords):
            return False

        # Проверяем, есть ли в сообщении исключаемые слова (если они заданы)
        if exclude_words and exclude_words != '' and self.contains_exclude_words(text, exclude_words):
            return False

        # Если все условия выполнены, сообщение валидно
        return True

    async def scan_channel(self, channel_name, last_message_date=None, keywords=None, exclude_words=None, limit=5):

        await self.connect()

        try:
            channel = await self.client.get_entity(channel_name)
            messages_found = []
            count = 0  # Добавляем счетчик

            # Сканируем сообщения
            async for message in self.client.iter_messages(channel, offset_date=last_message_date, reverse=True):
                if count >= limit:  # Проверяем, не достигли ли лимита
                    break

                if message.text:
                    # Проверяем, соответствует ли сообщение условиям
                    if self.is_message_valid(message.text, keywords, exclude_words):
                        # Сохраняем всё сообщение
                        messages_found.append((message.text, message.date))
                        print(f"Сообщение сохранено: {message.text[:500]}... (дата: {message.date})")
                        count += 1  # Увеличиваем счетчик

                # Добавляем задержку, чтобы не нарушать лимиты Telegram API
                await asyncio.sleep(1)

            return messages_found
        except Exception as e:
            logging.error(f"Ошибка при сканировании канала: {e}")
            raise
        finally:
            await self.disconnect()

    # def contains_library_keyword(self, text):
    #     # Проверяем, есть ли в тексте слово "библиотека"
    #     return bool(re.search(r'\bбиблиотека?\b', text, re.IGNORECASE))
    #
    # def extract_libraries(self, text):
    #     # Паттерн для поиска библиотек
    #     pattern = r'\b(?:pip install|pip3 install)\s+([a-zA-Z0-9_-]+)\b|\b([A-Z][a-zA-Z0-9_-]+)\b'
    #     matches = re.findall(pattern, text)
    #
    #     # Фильтруем результаты и удаляем пустые строки
    #     libraries = [match[0] or match[1] for match in matches if match[0] or match[1]]
    #     return libraries

    async def upload_message(self, channel_name, text, image_path):
        """
        Выгружает сообщение с изображением в Telegram.
        """
        try:
            await self.connect()  # Убедитесь, что клиент подключен
            channel = await self.client.get_entity(channel_name)
            # Отправляем изображение с текстом
            await self.client.send_file(
                channel,
                image_path,
                caption=text,
                parse_mode="html"  # Поддержка HTML-разметки в тексте
            )
            logging.info(f"Сообщение выгружено в канал: {channel_name}")
        except Exception as e:
            logging.error(f"Ошибка при выгрузке в Telegram: {e}")
        finally:
            await self.disconnect()
