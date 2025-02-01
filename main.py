# main.py
from aiogram import Bot, Dispatcher
import logging
from handlers import router  # Импортируем роутер из handlers.py
from config import BOT_TOKEN  # Импортируем токен из config.py

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,  # Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s"  # Формат логов
)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)  # Используем токен из config.py
dp = Dispatcher()
dp.include_router(router)  # Подключаем роутер

if __name__ == "__main__":
    """
    Основной скрипт для запуска бота.
    """
    try:
        logging.info("Бот запущен...")
        dp.run_polling(bot)  # Запуск бота с использованием aiogram
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
    finally:
        logging.info("Бот остановлен.")