import telebot
from telebot import types
import traceback

from works import my_works
from subscription import is_subscribed
from config import BOT_TOKEN, CHANNEL_ID, ADMIN_ID
from logger import logger
from texts import BUTTONS, MESSAGES, TITLES


bot = telebot.TeleBot(BOT_TOKEN)


# ========================================================================
#                      УВЕДОМЛЕНИЯ ОБ ОШИБКАХ
# ========================================================================

def notify_user_error(chat_id):
    """
    Сообщаем пользователю, что что-то пошло не так,
    но без технических подробностей.
    """
    try:
        bot.send_message(
            chat_id,
            "⚠️  К сожалению, этот функционал временно недоступен. Мы уже работаем над исправлением."
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
            bot.send_photo(
                chat_id,
                photo,
                caption=caption,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        logger.info(f"Одиночное фото отправлено: {path} → chat({chat_id})")

    except FileNotFoundError:
        logger.error(f"Фото не найдено: {path}")

    except Exception as e:
        logger.error(f"Ошибка при отправке фото {path}: {e}")


def create_buttons(*rows):
    """
    Создаёт InlineKeyboardMarkup из нескольких строк кнопок.
    rows: список списков кнопок.
    """
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.add(*row)
    return markup


# ========================================================================
#                           КОМАНДА /start
# ========================================================================

@bot.message_handler(commands=['старт', 'start'])
def on_start(message):
    user = message.from_user
    logger.info(f"/start от пользователя {user.id} @{user.username}")

    send_photo(message.chat.id, "media/welcome/fistphoto.jpg")

    markup = create_buttons(
        [types.InlineKeyboardButton(BUTTONS["ABOUT_ME"], callback_data="about_me")],
        [types.InlineKeyboardButton(BUTTONS["FREE_MASTER"], callback_data="check")],
        [types.InlineKeyboardButton(BUTTONS["MY_WORKS"], callback_data="my_job")]
    )

    bot.send_message(message.chat.id, MESSAGES["START"], reply_markup=markup)


# ========================================================================
#                     ОБО МНЕ
# ========================================================================

def send_about_info(chat_id):
    logger.info(f"Пользователь {chat_id} открыл 'Обо мне'")
    send_photo(chat_id, "media/welcome/Photo.jpg")
    bot.send_message(chat_id, MESSAGES["ABOUT_ME"], parse_mode="Markdown")


# ========================================================================
#                     КАТЕГОРИИ РАБОТ
# ========================================================================

def send_categories(chat_id):
    logger.info(f"Пользователь {chat_id} открыл список категорий")

    categories = list(my_works.keys())
    markup = types.InlineKeyboardMarkup()

    for i in range(0, len(categories), 2):
        row = [types.InlineKeyboardButton(categories[i], callback_data=f"cat_{categories[i]}")]
        if i + 1 < len(categories):
            row.append(types.InlineKeyboardButton(categories[i + 1], callback_data=f"cat_{categories[i + 1]}"))
        markup.add(*row)

    bot.send_message(chat_id, TITLES["CHOOSE_CATEGORY"], reply_markup=markup)


# ========================================================================
#                     ПРОВЕРКА ПОДПИСКИ
# ========================================================================

def send_subscription_check(chat_id):
    logger.info(f"Пользователь {chat_id} открыл раздел проверки подписки")

    markup = create_buttons(
        [types.InlineKeyboardButton(BUTTONS["CHANNEL"], url="https://t.me/dollminiature")],
        [types.InlineKeyboardButton(BUTTONS["CHECK_SUB"], callback_data="check_subscription")]
    )

    bot.send_message(chat_id, MESSAGES["SUBSCRIBE"], reply_markup=markup)


# ========================================================================
#                     ОТПРАВКА ГРУППЫ ФОТО (АЛЬБОМ)
# ========================================================================

def send_category_album(chat_id, category):
    """
    Отправляет все фото выбранной категории в виде альбома.
    Если тут что-то ломается — ошибка улетит наверх (raise),
    и её поймает общий try/except в callbacks().
    """
    logger.info(f"Пользователь {chat_id} открыл категорию '{category}'")

    works = my_works.get(category, [])
    if not works:
        logger.warning(f"Категория '{category}' пустая")
        return

    media = []
    open_files = []

    try:
        for item in works:
            path = item.get("photo")

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

        bot.send_media_group(chat_id, media)

        bot.send_message(
            chat_id,
            TITLES["CATEGORY_HEADER"].format(name=category),
            parse_mode="Markdown"
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
        if data == "about_me":
            send_about_info(call.message.chat.id)

        elif data == "my_job":
            send_categories(call.message.chat.id)

        elif data == "check":
            send_subscription_check(call.message.chat.id)

        elif data == "check_subscription":
            if is_subscribed(bot, CHANNEL_ID, user.id):
                logger.info(f"Подписка подтверждена: {user.id}")

                markup = create_buttons([
                    types.InlineKeyboardButton(
                        BUTTONS["MASTERCLASS_LINK"],
                        url="https://disk.yandex.ru/i/5SeUgQ1cjjok0Q"
                    )
                ])
                bot.send_message(call.message.chat.id, MESSAGES["THANKS_FOR_SUB"], reply_markup=markup)
            else:
                logger.warning(f"Пользователь {user.id} НЕ подписан на канал")

        elif data.startswith("cat_"):
            category = data[4:]
            send_category_album(call.message.chat.id, category)

    except Exception as e:
        # 1. Сообщаем пользователю
        notify_user_error(call.message.chat.id)

        # 2. Пишем в лог-файл
        logger.exception(f"Ошибка в callback '{data}' для пользователя {user.id}: {e}")

        # 3. Шлём админу подробный отчёт
        full_error = traceback.format_exc()
        notify_admin_error(user, data, full_error)


# ========================================================================
#                          ЗАПУСК БОТА
# ========================================================================

if __name__ == "__main__":
    logger.info("Бот запущен ✔")
    bot.polling(none_stop=True)
