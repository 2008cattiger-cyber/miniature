import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

from works import my_works
from subscription import is_subscribed
from config import BOT_TOKEN, CHANNEL_ID

from logger import logger
from texts import BUTTONS, MESSAGES, TITLES


bot = telebot.TeleBot(BOT_TOKEN)


# ---------------------------------------------------------
# УТИЛИТЫ
# ---------------------------------------------------------

def send_photo(chat_id, path, caption=None, markup=None):
    """Отправляет фото и логирует ошибки, не показывая их пользователю."""
    try:
        with open(path, "rb") as photo:
            bot.send_photo(
                chat_id,
                photo,
                caption=caption,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        logger.info(f"Отправлено фото '{path}' пользователю {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки фото '{path}': {e}")


def create_buttons(*rows):
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.add(*row)
    return markup


# ---------------------------------------------------------
# /start
# ---------------------------------------------------------

@bot.message_handler(commands=['старт', 'start'])
def on_start(message):
    user = message.from_user
    logger.info(f"/start от {user.id} (@{user.username})")

    # Фото приветствия
    send_photo(message.chat.id, "media/welcome/fistphoto.jpg")

    # Кнопки
    markup = create_buttons(
        [types.InlineKeyboardButton(BUTTONS["ABOUT_ME"], callback_data="about_me")],
        [types.InlineKeyboardButton(BUTTONS["FREE_MASTER"], callback_data="check")],
        [types.InlineKeyboardButton(BUTTONS["MY_WORKS"], callback_data="my_job")]
    )

    bot.send_message(message.chat.id, MESSAGES["START"], reply_markup=markup)


# ---------------------------------------------------------
# ОБО МНЕ
# ---------------------------------------------------------

def send_about_info(chat_id):
    logger.info(f"Раздел 'Обо мне' открыт пользователем {chat_id}")

    send_photo(chat_id, "media/welcome/Photo.jpg")
    bot.send_message(chat_id, MESSAGES["ABOUT_ME"], parse_mode="Markdown")


# ---------------------------------------------------------
# КАТЕГОРИИ
# ---------------------------------------------------------

def send_categories(chat_id):
    logger.info(f"Пользователь {chat_id} открыл список категорий работ")

    categories = list(my_works.keys())
    markup = types.InlineKeyboardMarkup()

    for i in range(0, len(categories), 2):
        row = [
            types.InlineKeyboardButton(categories[i], callback_data=f"cat_{categories[i]}")
        ]
        if i + 1 < len(categories):
            row.append(
                types.InlineKeyboardButton(categories[i+1], callback_data=f"cat_{categories[i+1]}")
            )
        markup.add(*row)

    bot.send_message(chat_id, TITLES["CHOOSE_CATEGORY"], reply_markup=markup)


# ---------------------------------------------------------
# ПРОВЕРКА ПОДПИСКИ
# ---------------------------------------------------------

def send_subscription_check(chat_id):
    logger.info(f"Пользователь {chat_id} запросил проверку подписки")

    markup = create_buttons(
        [types.InlineKeyboardButton(BUTTONS["CHANNEL"], url="https://t.me/dollminiature")],
        [types.InlineKeyboardButton(BUTTONS["CHECK_SUB"], callback_data="check_subscription")]
    )

    bot.send_message(chat_id, MESSAGES["SUBSCRIBE"], reply_markup=markup)


# ---------------------------------------------------------
# КАТЕГОРИЯ РАБОТ
# ---------------------------------------------------------

def send_category_album(chat_id, category):
    logger.info(f"Пользователь {chat_id} открыл категорию '{category}'")

    works = my_works.get(category, [])

    if not works:
        logger.warning(f"Категория '{category}' пуста")
        return

    media = []
    for item in works:
        try:
            with open(item["photo"], "rb") as f:
                media.append(types.InputMediaPhoto(f.read()))
        except FileNotFoundError:
            logger.error(f"Файл отсутствует: {item['photo']}")

    if media:
        bot.send_media_group(chat_id, media)
        bot.send_message(
            chat_id,
            TITLES["CATEGORY_HEADER"].format(name=category),
            parse_mode="Markdown"
        )


# ---------------------------------------------------------
# CALLBACK HANDLER
# ---------------------------------------------------------

@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    user = call.from_user
    data = call.data

    logger.info(f"Callback '{data}' от {user.id} (@{user.username})")

    try:
        if data == "about_me":
            send_about_info(call.message.chat.id)

        elif data == "my_job":
            send_categories(call.message.chat.id)

        elif data == "check":
            send_subscription_check(call.message.chat.id)

        elif data == "check_subscription":
            if is_subscribed(bot, CHANNEL_ID, user.id):
                logger.info(f"Подписка подтверждена пользователем {user.id}")

                markup = create_buttons([
                    types.InlineKeyboardButton(
                        BUTTONS["MASTERCLASS_LINK"],
                        url="https://disk.yandex.ru/i/5SeUgQ1cjjok0Q"
                    )
                ])

                bot.send_message(
                    call.message.chat.id,
                    MESSAGES["THANKS_FOR_SUB"],
                    reply_markup=markup
                )
            else:
                logger.warning(f"Пользователь {user.id} НЕ подписан")

        elif data.startswith("cat_"):
            category = data[4:]
            send_category_album(call.message.chat.id, category)

    except Exception as e:
        logger.exception(f"Ошибка при обработке callback '{data}': {e}")
        # пользователю ничего не показываем


# ---------------------------------------------------------
# ЗАПУСК БОТА
# ---------------------------------------------------------

if __name__ == "__main__":
    logger.info("Бот запущен")
    bot.polling(none_stop=True)
