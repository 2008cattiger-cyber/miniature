import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logger():
    # Создание директории для логов
    os.makedirs("logs", exist_ok=True)

    # Формат логов
    log_format = "[%(asctime)s] [%(levelname)s] %(message)s"

    # Ежедневная ротация логов, хранится 7 дней
    handler = TimedRotatingFileHandler(
        filename="logs/bot.log",
        when="midnight",       # новый файл каждый день
        interval=1,
        backupCount=7,         # сколько дней хранить
        encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(log_format))

    # Основной логгер проекта
    logger = logging.getLogger("bot")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    # Отключаем дублирование логов
    logger.propagate = False

    return logger


# Глобальный логгер, который импортируется в main.py
logger = setup_logger()
