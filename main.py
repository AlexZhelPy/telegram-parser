import tkinter as tk
from gui import TelegramParserApp

if __name__ == "__main__":
    root = tk.Tk()
    app = TelegramParserApp(root)
    root.mainloop()  # Запускаем основной цикл Tkinter