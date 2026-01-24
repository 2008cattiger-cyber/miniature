import telebot
from telebot import types
import traceback

from works import get_categories, list_category_photos, CATEGORY_TITLES
from masterclasses import load_masterclasses
from subscription import is_subscribed
from config import BOT_TOKEN, CHANNEL_ID, ADMIN_ID
from logger import logger, add_telegram_error_handler
from texts import BUTTONS, MESSAGES, TITLES
from voting import register_voting_handlers


bot = telebot.TeleBot(BOT_TOKEN)
add_telegram_error_handler(logger, bot, ADMIN_ID)
tracked_messages = {}
register_voting_handlers(bot, logger, ADMIN_ID, CHANNEL_ID)
PAGE_SIZE = 10
# Покупка мастер-класса временно отключена.
# Чтобы включить, раскомментируй BUY_VIDEO_PATH/BUY_USERNAME и блоки ниже (см. ответ).
# BUY_VIDEO_PATH = "media/buy/video.mp4"
# BUY_USERNAME = "nr_miniatures"


def log_event(event, user=None, **fields):
    payload = {"event": event, **fields}
    if user is not None:
        payload["user_id"] = user.id
        payload["username"] = user.username
    logger.info(event, extra=payload)


# ========================================================================
#                      УВЕДОМЛЕНИЯ ОБ ОШИБКАХ
# ========================================================================

def notify_user_error(chat_id, markup=None):
    """
    Сообщаем пользователю, что что-то пошло не так,
    но без технических подробностей.
    """
    try:
        send_tracked_message(
            chat_id,
            "⚠️  К сожалению, этот функционал временно недоступен. Мы уже работаем над исправлением.",
            reply_markup=markup
        )
    except Exception:
        # Даже если тут что-то упадёт — пользователя уже не спасаем
        pass


def notify_admin_error(user, action, exception_text):
    """
    Отправляем админу подробный отчёт об ошибке.
    """
    try:
        text = (
            "🔥 ОШИБКА У ПОЛЬЗОВАТЕЛЯ!\n\n"
            f"👤 Пользователь: {user.id} (@{user.username})\n"
            f"🧭 Действие: {action}\n\n"
            f"📄 Ошибка:\n{exception_text}"
        )
        bot.send_message(ADMIN_ID, text)
    except Exception:
        # Если не смогли сообщить админу — просто молча игнорируем
        pass


# ========================================================================
#                          УТИЛИТЫ
# ========================================================================

def send_photo(chat_id, path, caption=None, markup=None):
    """
    Отправляет ОДНО фото.
    - Любые ошибки логируются
    - Пользователь про техническую ошибку не узнаёт
    """
    try:
        with open(path, "rb") as photo:
            message = bot.send_photo(
                chat_id,
                photo,
                caption=caption,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        logger.info(f"Одиночное фото отправлено: {path} -> chat({chat_id})")
        logger.info(
            "media_sent",
            extra={"event": "media_sent", "chat_id": chat_id, "path": path, "type": "photo"},
        )
        return message

    except FileNotFoundError:
        logger.error(f"Фото не найдено: {path}")

    except Exception as e:
        logger.error(f"Ошибка при отправке фото {path}: {e}")
    return None


def create_buttons(*rows):
    """
    Создаёт InlineKeyboardMarkup из нескольких строк кнопок.
    rows: список списков кнопок.
    """
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.add(*row)
    return markup


def safe_delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass


def track_message(chat_id, message):
    if message is None:
        return
    tracked_messages.setdefault(chat_id, []).append(message.message_id)


def clear_tracked_messages(chat_id):
    for message_id in tracked_messages.get(chat_id, []):
        safe_delete_message(chat_id, message_id)
    tracked_messages[chat_id] = []


def send_tracked_message(chat_id, text, **kwargs):
    message = bot.send_message(chat_id, text, **kwargs)
    track_message(chat_id, message)
    return message


# ========================================================================
#                           КОМАНДА /start
# ========================================================================

def send_main_menu(chat_id):
    track_message(chat_id, send_photo(chat_id, "media/welcome/fistphoto.jpg"))

    markup = create_buttons(
        [types.InlineKeyboardButton(BUTTONS["ABOUT_ME"], callback_data="about_me")],
        [types.InlineKeyboardButton(BUTTONS["FREE_MASTER"], callback_data="check")],
        # [types.InlineKeyboardButton(BUTTONS["BUY_MASTER"], callback_data="buy_master")],
        [types.InlineKeyboardButton(BUTTONS["MY_WORKS"], callback_data="my_job")]
    )

    send_tracked_message(chat_id, MESSAGES["START"], reply_markup=markup)


@bot.message_handler(commands=['старт', 'start'])
def on_start(message):
    user = message.from_user
    log_event("command", user, command="start", chat_id=message.chat.id)

    clear_tracked_messages(message.chat.id)
    send_main_menu(message.chat.id)


# ========================================================================
#                     ОБО МНЕ
# ========================================================================

def send_about_info(chat_id):
    logger.info(f"Пользователь {chat_id} открыл 'Обо мне'")
    track_message(chat_id, send_photo(chat_id, "media/welcome/Photo.jpg"))
    markup = create_buttons(
        [types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_main")]
    )
    send_tracked_message(chat_id, MESSAGES["ABOUT_ME"], parse_mode="Markdown", reply_markup=markup)


# ========================================================================
#                     КАТЕГОРИИ РАБОТ
# ========================================================================

def send_categories(chat_id):
    logger.info(f"Пользователь {chat_id} открыл список категорий")

    categories = get_categories()
    markup = types.InlineKeyboardMarkup()

    for i in range(0, len(categories), 2):
        left_key, left_title = categories[i]
        row = [types.InlineKeyboardButton(left_title, callback_data=f"cat:{left_key}:0")]
        if i + 1 < len(categories):
            right_key, right_title = categories[i + 1]
            row.append(types.InlineKeyboardButton(right_title, callback_data=f"cat:{right_key}:0"))
        markup.add(*row)

    markup.add(types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_main"))

    send_tracked_message(chat_id, TITLES["CHOOSE_CATEGORY"], reply_markup=markup)


# ========================================================================
#                     ПРОВЕРКА ПОДПИСКИ
# ========================================================================

def send_subscription_check(chat_id):
    logger.info(f"Пользователь {chat_id} открыл раздел проверки подписки")

    markup = create_buttons(
        [types.InlineKeyboardButton(BUTTONS["CHANNEL"], url="https://t.me/dollminiature")],
        [types.InlineKeyboardButton(BUTTONS["CHECK_SUB"], callback_data="check_subscription")],
        [types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_main")]
    )

    send_tracked_message(chat_id, MESSAGES["SUBSCRIBE"], reply_markup=markup)


# ========================================================================
#                     ПОКУПКА МАСТЕР-КЛАССА (ОТКЛЮЧЕНО)
# ========================================================================
#
# def send_buy_info(chat_id):
#     logger.info(f"Пользователь {chat_id} открыл раздел покупки")
#     markup = create_buttons(
#         [types.InlineKeyboardButton(BUTTONS["BUY_CONTACT"], url=f"https://t.me/{BUY_USERNAME}")],
#         [types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_main")]
#     )
#     try:
#         with open(BUY_VIDEO_PATH, "rb") as video:
#             message = bot.send_video(
#                 chat_id,
#                 video,
#                 caption=MESSAGES["BUY_MASTER"],
#                 reply_markup=markup
#             )
#         track_message(chat_id, message)
#         logger.info(
#             "media_sent",
#             extra={"event": "media_sent", "chat_id": chat_id, "path": BUY_VIDEO_PATH, "type": "video"},
#         )
#     except FileNotFoundError:
#         logger.error(f"Видео не найдено: {BUY_VIDEO_PATH}")
#         send_tracked_message(chat_id, MESSAGES["BUY_MASTER"], reply_markup=markup)
#     except Exception as e:
#         logger.error(f"Ошибка при отправке видео {BUY_VIDEO_PATH}: {e}")
#         send_tracked_message(chat_id, MESSAGES["BUY_MASTER"], reply_markup=markup)


# ========================================================================
#                     ОТПРАВКА ГРУППЫ ФОТО (АЛЬБОМ)
# ========================================================================

def send_category_album(chat_id, category, page=0):
    """
    Отправляет все фото выбранной категории в виде альбома.
    Если тут что-то ломается — ошибка улетит наверх (raise),
    и её поймает общий try/except в callbacks().
    """
    logger.info(f"Пользователь {chat_id} открыл категорию '{category}'")

    works = list_category_photos(category)
    if not works:
        logger.warning(f"Категория '{category}' пустая или не найдена")
        return

    total_pages = (len(works) + PAGE_SIZE - 1) // PAGE_SIZE
    if total_pages <= 0:
        return
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    works = works[start:end]

    media = []
    open_files = []

    try:
        for path_obj in works:
            path = str(path_obj)

            try:
                f = open(path, "rb")
                open_files.append(f)
                media.append(types.InputMediaPhoto(f))
                logger.info(f"Добавлено фото в альбом: {path}")
            except FileNotFoundError:
                logger.error(f"Файл не найден: {path}")
            except Exception as e:
                logger.error(f"Ошибка при чтении файла {path}: {e}")

        if not media:
            logger.warning(f"В категории '{category}' нет доступных фото")
            return

        messages = bot.send_media_group(chat_id, media)
        for message in messages:
            track_message(chat_id, message)
        logger.info(
            "media_group_sent",
            extra={
                "event": "media_group_sent",
                "chat_id": chat_id,
                "category": category,
                "count": len(messages),
            },
        )

        display_name = CATEGORY_TITLES.get(category, category)
        nav_row = []
        if page > 0:
            nav_row.append(
                types.InlineKeyboardButton(
                    "⬅️ Предыдущие",
                    callback_data=f"cat:{category}:{page - 1}"
                )
            )
        if page < total_pages - 1:
            nav_row.append(
                types.InlineKeyboardButton(
                    "Следующие ➡️",
                    callback_data=f"cat:{category}:{page + 1}"
                )
            )

        buttons = []
        if nav_row:
            buttons.append(nav_row)
        buttons.append([types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_categories")])

        send_tracked_message(
            chat_id,
            TITLES["CATEGORY_HEADER"].format(name=display_name),
            parse_mode="Markdown",
            reply_markup=create_buttons(*buttons)
        )

    except Exception as e:
        logger.error(f"Ошибка при отправке альбома категории '{category}': {e}")
        raise   # <– ключевое: проброс ошибки наверх

    finally:
        for f in open_files:
            try:
                f.close()
            except Exception:
                pass


# ========================================================================
#                        ОБРАБОТЧИК CALLBACK
# ========================================================================

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    """
    Обрабатывает ВСЕ нажатия кнопок.
    При любой непойманной ошибке:
      - пользователь увидит мягкое сообщение
      - админ получит отчёт
      - логгер запишет traceback
    """

    user = call.from_user
    data = call.data

    logger.info(f"Callback '{data}' от пользователя {user.id} @{user.username}")

    try:
        if data.startswith("vote:") or data.startswith("vote_confirm:"):
            return
        clear_tracked_messages(call.message.chat.id)
        safe_delete_message(call.message.chat.id, call.message.message_id)

        if data == "about_me":
            send_about_info(call.message.chat.id)

        elif data == "my_job":
            send_categories(call.message.chat.id)

        elif data == "check":
            send_subscription_check(call.message.chat.id)

        # elif data == "buy_master":
        #     send_buy_info(call.message.chat.id)

        elif data == "check_subscription":
            if is_subscribed(bot, CHANNEL_ID, user.id):
                logger.info(f"Подписка подтверждена: {user.id}")
                log_event(
                    "subscription_checked",
                    user,
                    chat_id=call.message.chat.id,
                    subscribed=True,
                )

                masterclasses = load_masterclasses()
                buttons = []
                if masterclasses:
                    for item in masterclasses:
                        buttons.append([
                            types.InlineKeyboardButton(item["title"], url=item["url"])
                        ])
                else:
                    buttons.append([
                        types.InlineKeyboardButton(
                            BUTTONS["MASTERCLASS_LINK"],
                            url="https://disk.yandex.ru/i/5SeUgQ1cjjok0Q"
                        )
                    ])
                buttons.append([types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_subscribe")])
                markup = create_buttons(*buttons)
                send_tracked_message(call.message.chat.id, MESSAGES["THANKS_FOR_SUB"], reply_markup=markup)
            else:
                logger.warning(f"Пользователь {user.id} НЕ подписан на канал")
                log_event(
                    "subscription_checked",
                    user,
                    chat_id=call.message.chat.id,
                    subscribed=False,
                )
                markup = create_buttons(
                    [types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_subscribe")]
                )
                send_tracked_message(call.message.chat.id, MESSAGES["NOT_SUBSCRIBED"], reply_markup=markup)

        elif data == "back_main":
            send_main_menu(call.message.chat.id)

        elif data == "back_categories":
            send_categories(call.message.chat.id)

        elif data == "back_subscribe":
            send_subscription_check(call.message.chat.id)

        elif data.startswith("cat:"):
            parts = data.split(":", 2)
            if len(parts) < 3:
                return
            category = parts[1]
            try:
                page = int(parts[2])
            except Exception:
                page = 0
            send_category_album(call.message.chat.id, category, page)

        elif data.startswith("cat_"):
            category = data[4:]
            send_category_album(call.message.chat.id, category, 0)

    except Exception as e:
        # 1. Сообщаем пользователю
        fallback_markup = None
        if data.startswith("cat:") or data.startswith("cat_"):
            fallback_markup = create_buttons(
                [types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_categories")]
            )
        else:
            fallback_markup = create_buttons(
                [types.InlineKeyboardButton(BUTTONS["BACK"], callback_data="back_main")]
            )
        notify_user_error(call.message.chat.id, markup=fallback_markup)

        # 2. Пишем в лог-файл
        logger.exception(
            f"Ошибка в callback '{data}' для пользователя {user.id}: {e}",
            extra={"event": "callback_error", "user_id": user.id, "username": user.username},
        )

        # 3. Логируем traceback (алерт админам уходит через handler логгера)


# ========================================================================
#                          ЗАПУСК БОТА
# ========================================================================

if __name__ == "__main__":
    logger.info("Бот запущен ✔")
    bot.polling(none_stop=True)






