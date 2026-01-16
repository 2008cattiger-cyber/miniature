import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler

_STANDARD_LOG_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_ATTRS and not key.startswith("_")
        }
        if extras:
            payload["extra"] = extras
        return json.dumps(payload, ensure_ascii=False)


class TelegramErrorHandler(logging.Handler):
    def __init__(self, bot, admin_id):
        super().__init__(level=logging.ERROR)
        self._bot = bot
        self._admin_id = admin_id

    def emit(self, record):
        if not self._admin_id:
            return
        try:
            message = record.getMessage()
            user_id = getattr(record, "user_id", None)
            username = getattr(record, "username", None)
            location = f"{record.module}:{record.lineno} {record.funcName}"
            user_line = ""
            if user_id is not None or username:
                user_label = f"{user_id}" if user_id is not None else "-"
                username_label = f"@{username}" if username else "-"
                user_line = f"\nПользователь: {user_label} {username_label}"
            text = f"Ошибка: {message}{user_line}\n{location}"
            if record.exc_info:
                text += f"\n\n{self.formatException(record.exc_info)}"
            self._bot.send_message(self._admin_id, text)
        except Exception:
            pass


def setup_logger():
    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    formatter = JsonFormatter()

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    # Логи сохраняются в файл: <log_dir>/bot.jsonl
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "bot.jsonl"),
        when="midnight",
        interval=1,
        backupCount=7,

        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    error_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "errors.jsonl"),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    logger = logging.getLogger("bot")
    logger.setLevel(log_level)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    # Отключаем всплытие логов в корневой логгер
    logger.propagate = False

    return logger


logger = setup_logger()


def add_telegram_error_handler(logger_instance, bot, admin_id):
    handler = TelegramErrorHandler(bot, admin_id)
    handler.setFormatter(JsonFormatter())
    logger_instance.addHandler(handler)
