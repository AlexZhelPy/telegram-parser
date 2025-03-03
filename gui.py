import tkinter as tk
import os
import asyncio
import logging
from dotenv import load_dotenv
from tkinter import messagebox, simpledialog, ttk
from database import Database
from telegram_client import TelegramClientWrapper
from g4f_wrapper import transform_library_description, extract_library_name, generate_image
from PIL import Image, ImageTk
from datetime import datetime


# Загружаем переменные из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("parser.log"),
        logging.StreamHandler()
    ]
)

class TelegramParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram Parser")
        self.root.geometry("1000x600")  # Устанавливаем размер окна

        # Инициализация базы данных
        self.db = Database()
        logging.info("База данных инициализирована.")

        # Инициализация Telegram клиента
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        if not api_id or not api_hash:
            logging.error("Не удалось загрузить API_ID или API_HASH из .env файла.")
            raise ValueError("API_ID и API_HASH должны быть указаны в .env файле.")
        self.telegram_client = TelegramClientWrapper(api_id, api_hash)
        logging.info("Telegram клиент инициализирован.")

        # Создаем меню
        self.create_menu()

        # Создаем контейнер для библиотек с прокруткой
        self.create_library_container()

        # Обновляем интерфейс
        self.update_library_list()

        # Запускаем цикл событий asyncio
        self.loop = asyncio.get_event_loop()

        # Обработка закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    async def initialize_telegram_client(self):
        """
        Асинхронный метод для подключения Telegram клиента.
        """
        try:
            await self.telegram_client.connect()
            logging.info("Telegram клиент успешно подключен.")
        except Exception as e:
            logging.error(f"Ошибка при подключении Telegram клиента: {e}")
            messagebox.showerror("Ошибка", f"Не удалось подключить Telegram клиент: {e}")

    def create_menu(self):
        # Создаем меню
        menubar = tk.Menu(self.root)

        # Меню "Сканировать"
        scan_menu = tk.Menu(menubar, tearoff=0)
        scan_menu.add_command(label="Сканировать телеграм канал", command=self.show_scan_input)
        menubar.add_cascade(label="Сканировать", menu=scan_menu)

        # Меню "История сканирования"
        history_menu = tk.Menu(menubar, tearoff=0)
        history_menu.add_command(label="Последние 5", command=lambda: self.show_history(5))
        history_menu.add_command(label="Последние 10", command=lambda: self.show_history(10))
        history_menu.add_command(label="Вся история", command=lambda: self.show_history())
        menubar.add_cascade(label="История сканирования", menu=history_menu)

        # Меню "Показать преобразованные"
        transformed_menu = tk.Menu(menubar, tearoff=0)
        transformed_menu.add_command(label="Показать преобразованные", command=self.show_transformed_libraries_all)
        menubar.add_cascade(label="Показать преобразованные", menu=transformed_menu)

        # Меню "Промты"
        prompt_menu = tk.Menu(menubar, tearoff=0)
        prompt_menu.add_command(label="Управление промтами", command=self.manage_prompts)
        menubar.add_cascade(label="Промты", menu=prompt_menu)

        self.root.config(menu=menubar)

    def create_library_container(self):
        # Создаем контейнер с прокруткой
        self.container = tk.Frame(self.root)
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Создаем Canvas для прокрутки
        self.canvas = tk.Canvas(self.container)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Добавляем Scrollbar
        scrollbar = ttk.Scrollbar(self.container, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Настраиваем Canvas для работы с Scrollbar
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Создаем фрейм для библиотек внутри Canvas
        self.library_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.library_frame, anchor="nw")

        # Настраиваем прокрутку колесиком мыши
        self.library_frame.bind(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        )

    def show_scan_input(self):
        # Окно для ввода канала и выбора режима сканирования.
        scan_window = tk.Toplevel(self.root)
        scan_window.title("Сканирование канала")

        # Поле для ввода названия канала
        tk.Label(scan_window, text="Название канала:").grid(row=0, column=0, padx=5, pady=5)
        channel_entry = tk.Entry(scan_window)
        channel_entry.grid(row=0, column=1, padx=5, pady=5)

        # Поле для ввода ключевых слов
        tk.Label(scan_window, text="Ключевые слова (через запятую):").grid(row=1, column=0, padx=5, pady=5)
        keywords_entry = tk.Entry(scan_window)
        keywords_entry.grid(row=1, column=1, padx=5, pady=5)

        # Поле для ввода слов, которых не должно быть
        tk.Label(scan_window, text="Слова, которых не должно быть (через запятую):").grid(row=2, column=0, padx=5,
                                                                                          pady=5)
        exclude_words_entry = tk.Entry(scan_window)
        exclude_words_entry.grid(row=2, column=1, padx=5, pady=5)

        # Переменная для хранения выбранного режима сканирования
        self.scan_mode = tk.StringVar(value="start")  # По умолчанию "Сканировать с начала канала"

        # Радио-кнопки для выбора режима сканирования
        tk.Radiobutton(scan_window, text="Сканировать с начала канала", variable=self.scan_mode, value="start").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        tk.Radiobutton(scan_window, text="Продолжить с последней даты", variable=self.scan_mode, value="continue").grid(
            row=4, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        tk.Radiobutton(scan_window, text="Сканировать с конкретной даты", variable=self.scan_mode,
                       value="specific_date").grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        # Поле для ввода конкретной даты (скрыто по умолчанию)
        self.date_entry = tk.Entry(scan_window, state=tk.DISABLED)
        self.date_entry.grid(row=6, column=1, padx=5, pady=5)

        # Обработчик изменения выбора радио-кнопок
        def on_scan_mode_change():
            if self.scan_mode.get() == "specific_date":
                self.date_entry.config(state=tk.NORMAL)  # Активируем поле для ввода даты
            else:
                self.date_entry.config(state=tk.DISABLED)  # Деактивируем поле для ввода даты

        # Привязываем обработчик к изменению выбора радио-кнопок
        self.scan_mode.trace_add("write", lambda *args: on_scan_mode_change())

        # Кнопка "Сканировать"
        def on_scan():
            channel_name = channel_entry.get()
            keywords = keywords_entry.get().split(',')
            exclude_words = exclude_words_entry.get().split(',')

            scan_mode = self.scan_mode.get()
            specific_date = None

            if scan_mode == "specific_date":
                specific_date = self.date_entry.get()
                if not specific_date:
                    messagebox.showwarning("Ошибка", "Пожалуйста, введите дату.")
                    return
                try:
                    # Преобразуем строку даты в объект datetime
                    specific_date = datetime.strptime(specific_date, "%Y-%m-%d")
                except ValueError:
                    messagebox.showwarning("Ошибка", "Неверный формат даты. Используйте формат ГГГГ-ММ-ДД.")
                    return

            if channel_name and keywords:
                self.scan_channel(channel_name, keywords, exclude_words, scan_mode, specific_date)
                scan_window.destroy()
            else:
                messagebox.showwarning("Ошибка", "Пожалуйста, заполните все поля.")

        tk.Button(scan_window, text="Сканировать", command=on_scan).grid(row=8, column=0, columnspan=2, pady=10)

    def scan_channel(self, channel_name, keywords, exclude_words, scan_mode, specific_date):
        logging.info(f"Начато сканирование канала: {channel_name}")

        async def run_scan():
            try:
                last_message_date = None

                # Определяем дату начала сканирования
                if scan_mode == "continue":
                    last_message_date = self.db.get_last_scan_date(channel_name)
                    logging.info(f"Продолжение сканирования с последней даты: {last_message_date}")
                elif scan_mode == "specific_date":
                    last_message_date = specific_date
                    logging.info(f"Сканирование с конкретной даты: {last_message_date}")

                # Преобразуем ключевые и исключаемые слова в списки (если они переданы как строки)
                keywords_list = [keyword.strip() for keyword in keywords.split(',')] if isinstance(keywords,
                                                                                                   str) else keywords
                exclude_words_list = [word.strip() for word in exclude_words.split(',')] if isinstance(exclude_words,
                                                                                                       str) else exclude_words

                # Сканируем канал (не более 5 сообщений за раз)
                messages_found = await self.telegram_client.scan_channel(channel_name, last_message_date, keywords_list,
                                                                         exclude_words_list)
                logging.info(f"Найдено {len(messages_found)} сообщений.")

                if messages_found:
                    # Сохраняем найденные сообщения
                    for message_text, message_date in messages_found:
                        self.db.save_message(channel_name, message_text, message_date)

                    # Обновляем последнюю дату сканирования
                    last_message_date = messages_found[-1][1]
                    self.db.update_last_scan_date(channel_name, last_message_date)

                    messagebox.showinfo("Сканирование", f"Найдено {len(messages_found)} сообщений.")
                    self.update_library_list()
                else:
                    messagebox.showinfo("Сканирование", "Новые сообщения не найдены.")
            except Exception as e:
                logging.error(f"Ошибка при сканировании канала: {e}")
                messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")

        asyncio.run(run_scan())

    def show_history(self, limit=None):
        """
           Отображает историю сканирования с ограничением по количеству записей.
           """
        logging.info(f"Загрузка истории сканирования (limit={limit}).")
        # Очищаем фрейм
        for widget in self.library_frame.winfo_children():
            widget.destroy()

        # Получаем историю сканирования
        history = self.db.get_messages(limit)
        logging.info(f"Получено {len(history)} записей истории сканирования.")

        # Отображаем каждую запись
        for record in history:
            channel_name, message_text, message_date = record
            self.add_history_record_to_frame(channel_name, message_text, message_date)

        # Обновляем область прокрутки
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def add_history_record_to_frame(self, channel_name, message_text, message_date):
        """
        Добавляет запись истории сканирования в интерфейс.
        """
        # Фрейм для одной записи
        frame = tk.Frame(self.library_frame, bd=2, relief=tk.GROOVE)
        frame.pack(fill=tk.X, pady=5, padx=5)

        # Метка с текстом сообщения (без обрезки)
        label = tk.Label(frame, text=f"{message_text} (канал: {channel_name}, дата: {message_date})", wraplength=700,
                         justify=tk.LEFT)
        label.pack(side=tk.LEFT, padx=5, pady=5)

        # Кнопка "Преобразовать"
        transform_button = tk.Button(frame, text="Преобразовать",
                                     command=lambda text=message_text: self.transform_library(text))
        transform_button.pack(side=tk.RIGHT, padx=5)

        # Разделительная линия
        separator = ttk.Separator(self.library_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=5)

    def update_library_list(self):
        logging.info("Обновление списка библиотек (последнее сканирование).")
        # Очищаем фрейм
        for widget in self.library_frame.winfo_children():
            widget.destroy()

        # Получаем сообщения из базы данных (только данные последнего сканирования)
        messages = self.db.get_last_scan_messages()
        logging.info(f"Получено {len(messages)} сообщений для отображения (последнее сканирование).")

        # Отображаем каждое сообщение с кнопками
        for i, message in enumerate(messages):
            message_id, message_text, message_date = message
            self.add_library_to_frame(message_id, message_text, message_date)
            # Добавляем разделительную линию, кроме последней записи
            if i < len(messages) - 1:
                separator = ttk.Separator(self.library_frame, orient=tk.HORIZONTAL)
                separator.pack(fill=tk.X, pady=5)

        # Обновляем область прокрутки
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def add_library_to_frame(self, message_id, message_text, message_date):
        # Фрейм для одной библиотеки
        frame = tk.Frame(self.library_frame, bd=2, relief=tk.GROOVE)
        frame.pack(fill=tk.X, pady=5, padx=5)

        # Метка с текстом сообщения (без обрезки)
        label = tk.Label(frame, text=f"{message_text} (дата: {message_date})", wraplength=700, justify=tk.LEFT)
        label.pack(side=tk.LEFT, padx=5, pady=5)

        # Кнопка "Удалить"
        delete_button = tk.Button(frame, text="Удалить", command=lambda id=message_id: self.delete_library(id))
        delete_button.pack(side=tk.RIGHT, padx=5)

        # Кнопка "Преобразовать"
        transform_button = tk.Button(frame, text="Преобразовать",
                                     command=lambda text=message_text: self.transform_library(text))
        transform_button.pack(side=tk.RIGHT, padx=5)

        # Разделительная линия
        separator = ttk.Separator(self.library_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=5)

    def delete_library(self, message_id):
        logging.info(f"Удаление библиотеки с ID {message_id}.")
        self.db.delete_message(message_id)
        self.update_library_list()

    def transform_library(self, message_text):
        """
        Преобразует текст сообщения с использованием выбранного промта.
        """
        # Окно для выбора промта
        prompt_window = tk.Toplevel(self.root)
        prompt_window.title("Выберите промт")

        tk.Label(prompt_window, text="Выберите промт:").grid(row=0, column=0, padx=5, pady=5)
        self.prompt_listbox = tk.Listbox(prompt_window, width=50, height=10)
        self.prompt_listbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        # Загружаем список промтов
        self.load_prompts()

        def on_transform():
            selected = self.prompt_listbox.curselection()
            if not selected:
                messagebox.showwarning("Ошибка", "Пожалуйста, выберите промт.")
                return

            #prompt_id = int(self.prompt_listbox.get(selected[0]).split("(ID: ")[1].rstrip(")"))
            prompt = self.db.get_prompts()[selected[0]]
            # Преобразуем текст и генерируем изображение
            transformed_text, image_path = transform_library_description(message_text, prompt[2], prompt[3], prompt[4])
            if transformed_text and image_path:
                # Отображаем преобразованный текст и изображение
                self.show_transformed_library(transformed_text, image_path, message_text)
                prompt_window.destroy()
            else:
                messagebox.showerror("Ошибка", "Не удалось преобразовать текст или сгенерировать изображение.")

        tk.Button(prompt_window, text="Преобразовать", command=on_transform).grid(row=2, column=0, columnspan=2,
                                                                                  pady=10)

    def show_transformed_library(self, transformed_text, image_path, original_text):
        # Окно для отображения преобразованного текста и изображения
        transformed_window = tk.Toplevel(self.root)
        transformed_window.title("Преобразованная библиотека")

        # Отображаем преобразованный текст (редактируемый)
        text_frame = tk.Frame(transformed_window)
        text_frame.pack(pady=10)

        text_label = tk.Label(text_frame, text="Преобразованный текст:")
        text_label.pack()

        text_edit = tk.Text(text_frame, wrap=tk.WORD, height=10, width=50)
        text_edit.insert(tk.END, transformed_text)
        text_edit.pack()

        # Отображаем изображение
        image_frame = tk.Frame(transformed_window)
        image_frame.pack(pady=10)

        try:
            image = Image.open(image_path)
            photo = ImageTk.PhotoImage(image)
            image_label = tk.Label(image_frame, image=photo)
            image_label.image = photo  # Сохраняем ссылку на изображение
            image_label.pack()
        except Exception as e:
            logging.error(f"Ошибка при загрузке изображения: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить изображение: {e}")

        # Кнопки
        button_frame = tk.Frame(transformed_window)
        button_frame.pack(pady=10)

        # Кнопка "Сохранить"
        save_button = tk.Button(button_frame, text="Сохранить", command=lambda: self.save_transformed_library(
            text_edit.get("1.0", tk.END).strip(), image_path, original_text
        ))
        save_button.pack(side=tk.LEFT, padx=5)

        # Кнопка "Повторно преобразовать текст"
        retry_text_button = tk.Button(button_frame, text="Повторно преобразовать текст",
                                      command=lambda: self.retry_transform_text(
                                          text_edit, original_text
                                      ))
        retry_text_button.pack(side=tk.LEFT, padx=5)

        # Кнопка "Повторно сгенерировать изображение"
        retry_image_button = tk.Button(button_frame, text="Повторно сгенерировать изображение",
                                       command=lambda: self.retry_generate_image(
                                           text_edit.get("1.0", tk.END).strip(), image_label, image_frame
                                       ))
        retry_image_button.pack(side=tk.LEFT, padx=5)

    def show_transformed_libraries_all(self):
        """
        Отображает все преобразованные сообщения.
        """
        logging.info("Загрузка преобразованных библиотек.")
        # Очищаем фрейм
        for widget in self.library_frame.winfo_children():
            widget.destroy()

        # Получаем преобразованные сообщения из базы данных
        libraries = self.db.get_transformed_libraries()
        logging.info(f"Получено {len(libraries)} преобразованных библиотек.")

        # Отображаем каждое преобразованное сообщение
        for library in libraries:
            library_name, transformed_text, image_path = library
            self.add_transformed_library_to_frame(library_name, transformed_text, image_path)

        # Обновляем область прокрутки
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def add_transformed_library_to_frame(self, library_name, transformed_text, image_path):
        """
        Добавляет преобразованное сообщение в интерфейс.
        """
        # Фрейм для одной библиотеки
        frame = tk.Frame(self.library_frame, bd=2, relief=tk.GROOVE)
        frame.pack(fill=tk.X, pady=5, padx=5)

        # Метка с текстом сообщения (без обрезки)
        label = tk.Label(frame, text=f"{transformed_text} (библиотека: {library_name})", wraplength=700,
                         justify=tk.LEFT)
        label.pack(side=tk.LEFT, padx=5, pady=5)

        # Кнопка "Выгрузить в Telegram"
        upload_button = tk.Button(frame, text="Выгрузить в Telegram",
                                  command=lambda text=transformed_text, img=image_path: self.upload_to_telegram(text,
                                                                                                                img))
        upload_button.pack(side=tk.RIGHT, padx=5)

        # Разделительная линия
        separator = ttk.Separator(self.library_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=5)

    def upload_to_telegram(self, text, image_path):
        """
        Выгружает преобразованное сообщение в Telegram.
        """
        # Окно для ввода названия канала
        channel_name = simpledialog.askstring("Выгрузить в Telegram", "Введите название канала:")
        if channel_name:
            async def run_upload():
                try:
                    await self.telegram_client.upload_message(channel_name, text, image_path)
                    messagebox.showinfo("Успех", "Сообщение успешно выгружено в Telegram.")
                except Exception as e:
                    logging.error(f"Ошибка при выгрузке в Telegram: {e}")
                    messagebox.showerror("Ошибка", f"Не удалось выгрузить сообщение: {e}")

            asyncio.run(run_upload())

    def save_transformed_library(self, transformed_text, image_path, original_text):
        """
        Сохраняет преобразованный текст и изображение.
        """
        try:
            # Извлекаем название сообщения
            library_name = extract_library_name(transformed_text)
            if not library_name:
                logging.error("Не удалось извлечь название сообщения.")
                return

            # Сохраняем в базу данных
            self.db.save_transformed_library(library_name, original_text, transformed_text, image_path)
            logging.info(f"Преобразованный текст и изображение сохранены для сообщения: {library_name}")
            messagebox.showinfo("Сохранено", "Преобразованный текст и изображение сохранены.")
        except Exception as e:
            logging.error(f"Ошибка при сохранении: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")

    def retry_transform_text(self, text_edit, original_text):
        """
        Повторно преобразует текст.
        """
        try:
            transformed_text = transform_library_description(original_text)
            if transformed_text:
                text_edit.delete("1.0", tk.END)
                text_edit.insert(tk.END, transformed_text)
            else:
                messagebox.showerror("Ошибка", "Не удалось преобразовать текст.")
        except Exception as e:
            logging.error(f"Ошибка при повторном преобразовании текста: {e}")
            messagebox.showerror("Ошибка", f"Не удалось преобразовать текст: {e}")

    def manage_prompts(self):
        """
        Окно для управления промтами (добавление, редактирование, удаление).
        """
        prompt_window = tk.Toplevel(self.root)
        prompt_window.title("Управление промтами")

        # Список промтов
        tk.Label(prompt_window, text="Список промтов:").grid(row=0, column=0, padx=5, pady=5)
        self.prompt_listbox = tk.Listbox(prompt_window, width=50, height=10)
        self.prompt_listbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        # Кнопки для управления промтами
        tk.Button(prompt_window, text="Добавить промт", command=self.add_prompt).grid(row=2, column=0, padx=5, pady=5)
        tk.Button(prompt_window, text="Редактировать промт", command=self.edit_prompt).grid(row=2, column=1, padx=5,
                                                                                            pady=5)
        tk.Button(prompt_window, text="Удалить промт", command=self.delete_prompt).grid(row=3, column=0, columnspan=2,
                                                                                        pady=5)

        # Загружаем список промтов
        self.load_prompts()

    def load_prompts(self):
        """
        Загружает список промтов из базы данных.
        """
        self.prompt_listbox.delete(0, tk.END)
        prompts = self.db.get_prompts()
        for prompt in prompts:
            self.prompt_listbox.insert(tk.END, f"{prompt[1]} (ID: {prompt[0]})")

    def add_prompt(self):
        """
        Окно для добавления нового промта.
        """
        add_window = tk.Toplevel(self.root)
        add_window.title("Добавить промт")

        tk.Label(add_window, text="Название промта:").grid(row=0, column=0, padx=5, pady=5)
        name_entry = tk.Entry(add_window)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(add_window, text="Промт для сообщения:").grid(row=1, column=0, padx=5, pady=5)
        message_prompt_entry = tk.Text(add_window, height=5, width=40)
        message_prompt_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(add_window, text="Промт для генерации изображения:").grid(row=2, column=0, padx=5, pady=5)
        image_prompt_entry = tk.Text(add_window, height=5, width=40)
        image_prompt_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(add_window, text="Промт для названия сообщения:").grid(row=3, column=0, padx=5, pady=5)
        name_prompt_entry = tk.Text(add_window, height=5, width=40)
        name_prompt_entry.grid(row=3, column=1, padx=5, pady=5)

        def on_save():
            name = name_entry.get()
            message_prompt = message_prompt_entry.get("1.0", tk.END).strip()
            image_prompt = image_prompt_entry.get("1.0", tk.END).strip()
            name_prompt = name_prompt_entry.get("1.0", tk.END).strip()
            if name and message_prompt and image_prompt and name_prompt:
                self.db.save_prompt(name, message_prompt, image_prompt, name_prompt)
                self.load_prompts()
                add_window.destroy()
            else:
                messagebox.showwarning("Ошибка", "Пожалуйста, заполните все поля.")

        tk.Button(add_window, text="Сохранить", command=on_save).grid(row=4, column=0, columnspan=2, pady=10)

    def edit_prompt(self):
        """
        Окно для редактирования выбранного промта.
        """
        selected = self.prompt_listbox.curselection()
        if not selected:
            messagebox.showwarning("Ошибка", "Пожалуйста, выберите промт для редактирования.")
            return

        prompt_id = int(self.prompt_listbox.get(selected[0]).split("(ID: ")[1].rstrip(")"))
        prompt = self.db.get_prompts()[selected[0]]

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Редактировать промт")

        tk.Label(edit_window, text="Название промта:").grid(row=0, column=0, padx=5, pady=5)
        name_entry = tk.Entry(edit_window)
        name_entry.insert(0, prompt[1])
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(edit_window, text="Промт для сообщения:").grid(row=1, column=0, padx=5, pady=5)
        message_prompt_entry = tk.Text(edit_window, height=5, width=40)
        message_prompt_entry.insert(tk.END, prompt[2])
        message_prompt_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(edit_window, text="Промт для генерации изображения:").grid(row=2, column=0, padx=5, pady=5)
        image_prompt_entry = tk.Text(edit_window, height=5, width=40)
        image_prompt_entry.insert(tk.END, prompt[3])
        image_prompt_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(edit_window, text="Промт для названия библиотеки:").grid(row=3, column=0, padx=5, pady=5)
        name_prompt_entry = tk.Text(edit_window, height=5, width=40)
        name_prompt_entry.insert(tk.END, prompt[4])
        name_prompt_entry.grid(row=3, column=1, padx=5, pady=5)

        def on_save():
            name = name_entry.get()
            message_prompt = message_prompt_entry.get("1.0", tk.END).strip()
            image_prompt = image_prompt_entry.get("1.0", tk.END).strip()
            name_prompt = name_prompt_entry.get("1.0", tk.END).strip()
            if name and message_prompt and image_prompt and name_prompt:
                self.db.update_prompt(prompt_id, message_prompt, image_prompt, name_prompt)
                self.load_prompts()
                edit_window.destroy()
            else:
                messagebox.showwarning("Ошибка", "Пожалуйста, заполните все поля.")

        tk.Button(edit_window, text="Сохранить", command=on_save).grid(row=4, column=0, columnspan=2, pady=10)

    def delete_prompt(self):
        """
        Удаляет выбранный промт.
        """
        selected = self.prompt_listbox.curselection()
        if not selected:
            messagebox.showwarning("Ошибка", "Пожалуйста, выберите промт для удаления.")
            return

        prompt_id = int(self.prompt_listbox.get(selected[0]).split("(ID: ")[1].rstrip(")"))
        self.db.delete_prompt(prompt_id)
        self.load_prompts()

    def retry_generate_image(self, transformed_text, image_label, image_frame):
        """
        Повторно генерирует изображение.
        """
        try:
            library_name = extract_library_name(transformed_text)
            if not library_name:
                messagebox.showerror("Ошибка", "Не удалось извлечь название сообщения.")
                return

            image_path = generate_image(library_name)
            if image_path:
                # Обновляем изображение
                image = Image.open(image_path)
                photo = ImageTk.PhotoImage(image)
                image_label.config(image=photo)
                image_label.image = photo  # Сохраняем ссылку на изображение
            else:
                messagebox.showerror("Ошибка", "Не удалось сгенерировать изображение.")
        except Exception as e:
            logging.error(f"Ошибка при повторной генерации изображения: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сгенерировать изображение: {e}")

    def __del__(self):
        self.db.close()
        logging.info("Приложение закрыто.")

    async def shutdown(self):
        """
        Асинхронный метод для завершения работы приложения.
        """
        try:
            await self.telegram_client.disconnect()
            logging.info("Telegram клиент отключен.")
        except Exception as e:
            logging.error(f"Ошибка при отключении Telegram клиента: {e}")
        finally:
            await self.telegram_client.disconnect()
            logging.info("Telegram клиент отключен.")

    def on_close(self):
        """
        Обрабатывает событие закрытия окна.
        """
        # Запускаем асинхронное завершение работы
        self.loop.run_until_complete(self.shutdown())
        self.root.destroy()

