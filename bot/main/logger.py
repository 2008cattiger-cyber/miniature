import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logger():
    # Создаём папку
    os.makedirs("logs", exist_ok=True)

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")

    # Логи сохраняются в файл: logs/bot.log
    file_handler = TimedRotatingFileHandler(
        filename="logs/bot.log",
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logger = logging.getLogger("bot")
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # Отключаем всплытие логов в корневой логгер
    logger.propagate = False

    return logger


logger = setup_logger()
