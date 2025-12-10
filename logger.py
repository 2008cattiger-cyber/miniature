import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logger():
    # создаём папку logs, если её нет
    os.makedirs("logs", exist_ok=True)

    # формат логов
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")

    # файл логов с ротацией (новый файл каждый день)
    file_handler = TimedRotatingFileHandler(
        filename="logs/bot.log",
        when="midnight",      # новый файл каждый день
        interval=1,
        backupCount=7,        # хранить 7 дней
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # создаём логгер
    logger = logging.getLogger("bot")
    logger.setLevel(logging.INFO)

    # добавляем запись в файл
    logger.addHandler(file_handler)

    # отключаем распространение в корневой логгер
    logger.propagate = False

    return logger


logger = setup_logger()
