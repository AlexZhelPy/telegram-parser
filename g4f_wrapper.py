import g4f
import os
import requests
import logging
import re
import random
import string
from g4f.client import Client
from PIL import Image

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("transform_library.log"),
        logging.StreamHandler()
    ]
)

# Создаем папку для изображений, если она не существует
if not os.path.exists('generated_images'):
    os.makedirs('generated_images')

def extract_library_name(message_text, name_prompt=None):
    """
    Извлекает название сообщения из текста с помощью нейросети.
    """
    try:
        # Если промт не задан, используем стандартный
        if not name_prompt:
            name_prompt = (f"Извлеки название сообщения из следующего текста. "
                           f"Ответ должен содержать только название сообщения: {message_text}")

        # Запрос к нейросети для извлечения названия сообщения
        response = g4f.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": (name_prompt + " " + message_text)}],
        )
        return response.strip()  # Убираем лишние пробелы
    except Exception as e:
        logging.error(f"Ошибка при извлечении названия сообщения: {e}")
        return None

def generate_image_name(library_name):
    """
    Генерирует имя файла для изображения на основе названия сообщения.
    - Имя должно быть не длиннее 10 символов.
    - Используются только латинские буквы (без пробелов и специальных знаков).
    - Если в названии нет латинских букв, генерируется случайное имя.
    """
    # Убираем все нелатинские символы и пробелы
    cleaned_name = re.sub(r'[^a-zA-Z]', '', library_name)

    # Если в названии есть латинские буквы, обрезаем до 10 символов
    if cleaned_name:
        return cleaned_name[:10].lower()  # Приводим к нижнему регистру

    # Если латинских букв нет, генерируем случайное имя из 10 символов
    random_name = ''.join(random.choices(string.ascii_lowercase, k=10))
    return random_name

def generate_image(library_name, image_prompt=None):
    """
    Генерирует изображение с использованием названия сообщения.
    """
    try:
        client = Client()
        # Если промт не задан, используем стандартный
        if not image_prompt:
            image_prompt = (f"сгенерируйте изображение с текстом '{library_name}'. "
                            f"Текст должен быть крупным и ярким")

        response = client.images.generate(
            model="dall-e-3",
            prompt=(image_prompt + " " + library_name),
            response_format="url"
        )
        image_url = response.data[0].url

        # Генерируем имя файла
        image_name = generate_image_name(library_name)
        filename = f"generated_images/{image_name}_image.png"

        # Сохраняем изображение
        response = requests.get(image_url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)

            # Уменьшаем размер изображения
            image = Image.open(filename)
            image.thumbnail((300, 300))  # Устанавливаем максимальный размер 300x300
            image.save(filename)

            logging.info(f"Изображение сохранено: {filename}")
            return filename
        else:
            logging.error(f"Не удалось загрузить изображение: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Ошибка при генерации изображения: {e}")
        return None

def transform_library_description(message_text, message_prompt=None, image_prompt=None, name_prompt=None):
    """
    Преобразует описание сообщения и генерирует изображение.
    """
    try:
        # Если промт не задан, используем стандартный
        if not message_prompt:
            message_prompt = (f"Перепиши другими словами, но чтобы смысл остался прежним. Убери все лишнее, оставь "
                              f"только название библиотеки, описание, установку, допиши не большой код использования библиотеки до 200 символов"
                              f"и ссылку на документацию: {message_text}.")

        # Извлекаем название сообщения
        library_name = extract_library_name(message_text, name_prompt)
        if not library_name:
            logging.error("Не удалось извлечь название сообщения.")
            return None, None

        # Преобразуем текст
        transformed_text = g4f.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": (message_prompt + " " + message_text)}],
        )

        # Генерируем изображение
        image_path = generate_image(library_name, image_prompt)
        if not image_path:
            logging.error("Не удалось сгенерировать изображение.")
            return transformed_text, None

        return transformed_text, image_path
    except Exception as e:
        logging.error(f"Ошибка при преобразовании описания: {e}")
        return None, None