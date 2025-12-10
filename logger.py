import logging
import os
from logging.handlers import TimedRotatingFileHandler
from telebot import TeleBot
from config import ADMIN_ID
from config import BOT_TOKEN

bot = TeleBot(BOT_TOKEN)

class TelegramErrorHandler(logging.Handler):
    """Отправляет ошибки админу в Telegram."""
    def emit(self, record):
        try:
            log_entry = self.format(record)
            bot.send_message(ADMIN_ID, f"🔥 Ошибка:\n{log_entry}")
        except Exception:
            pass


def setup_logger():
    os.makedirs("logs", exist_ok=True)

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")

    file_handler = TimedRotatingFileHandler(
        filename="logs/bot.log",
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # новый обработчик — отправка ошибок админу
    tg_handler = TelegramErrorHandler()
    tg_handler.setLevel(logging.ERROR)
    tg_handler.setFormatter(formatter)

    logger = logging.getLogger("bot")
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(tg_handler)

    logger.propagate = False
    return logger


logger = setup_logger()
