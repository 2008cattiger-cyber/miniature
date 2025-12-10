import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# Файл my_works.py содержит структуру вида:
# {
#     "basket": [
#         {"photo": "media/works/basket/photo1.jpg"},
#         {"photo": "media/works/basket/photo2.jpg"}
#     ],
#     ...
# }
from works import my_works

# Функция для проверки подписки пользователя на канал
from subscription import is_subscribed

# Настройки: токен бота и ID канала, на который должна быть подписка
from config import BOT_TOKEN, CHANNEL_ID

# Наш логгер — все ошибки и события записываются в файл logs/bot.log
from logger import logger

# Все текстовые константы: кнопки, сообщения, заголовки
from texts import BUTTONS, MESSAGES, TITLES


# Создаём объект бота
bot = telebot.TeleBot(BOT_TOKEN)


# ========================================================================
#                          УТИЛИТЫ
# ========================================================================

def send_photo(chat_id, path, caption=None, markup=None):
    """
    Отправляет ОДНО фото.
    - Любые ошибки логируются
    - Пользователь НЕ узнаёт об ошибках
    - Файл открывается через 'with' (автоматически закрывается)
    """

    try:
        # Открываем фото в режиме чтения байтов
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
    """
    Обрабатывает команду /start.
    Показывает приветственное фото + 3 кнопки меню.
    """

    user = message.from_user
    logger.info(f"/start от пользователя {user.id} @{user.username}")

    # Отправляем приветственное фото
    send_photo(message.chat.id, "media/welcome/fistphoto.jpg")

    # Создаём кнопки меню
    markup = create_buttons(
        [types.InlineKeyboardButton(BUTTONS["ABOUT_ME"], callback_data="about_me")],
        [types.InlineKeyboardButton(BUTTONS["FREE_MASTER"], callback_data="check")],
        [types.InlineKeyboardButton(BUTTONS["MY_WORKS"], callback_data="my_job")]
    )

    # Текст приветствия
    bot.send_message(message.chat.id, MESSAGES["START"], reply_markup=markup)


# ========================================================================
#                     ОБО МНЕ
# ========================================================================

def send_about_info(chat_id):
    """
    Отправляет фото и биографию автора.
    """

    logger.info(f"Пользователь {chat_id} открыл 'Обо мне'")

    send_photo(chat_id, "media/welcome/Photo.jpg")
    bot.send_message(chat_id, MESSAGES["ABOUT_ME"], parse_mode="Markdown")


# ========================================================================
#                     КАТЕГОРИИ РАБОТ
# ========================================================================

def send_categories(chat_id):
    """
    Отправляет список категорий, находящихся в словаре my_works.
    Каждая категория — кнопка.
    """

    logger.info(f"Пользователь {chat_id} открыл список категорий")

    categories = list(my_works.keys())
    markup = types.InlineKeyboardMarkup()

    # Делаем кнопки в 2 колонки
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
    """
    Предлагает пользователю проверить подписку.
    """

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
    Важно: telebot требует ОТКРЫТЫЕ файлы (не байтовые строки).
    """

    logger.info(f"Пользователь {chat_id} открыл категорию '{category}'")

    works = my_works.get(category, [])

    if not works:
        logger.warning(f"Категория '{category}' пустая")
        return

    media = []        # список объектов InputMediaPhoto
    open_files = []   # список файлов, чтобы закрыть их после отправки

    try:
        for item in works:
            path = item.get("photo")

            try:
                # Открываем файл (потом закроем вручную)
                f = open(path, "rb")
                open_files.append(f)

                # Добавляем фото в альбом
                media.append(types.InputMediaPhoto(f))
                logger.info(f"Добавлено фото в альбом: {path}")

            except FileNotFoundError:
                logger.error(f"Файл не найден: {path}")

            except Exception as e:
                logger.error(f"Ошибка при чтении файла {path}: {e}")

        if not media:
            logger.warning(f"В категории '{category}' нет доступных фото")
            return

        # Отправляем альбом
        bot.send_media_group(chat_id, media)

        # Отправляем заголовок категории
        bot.send_message(
            chat_id,
            TITLES["CATEGORY_HEADER"].format(name=category),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка при отправке альбома категории '{category}': {e}")

    finally:
        # ВАЖНО! Закрываем все файлы после отправки
        for f in open_files:
            try:
                f.close()
            except:
                pass


# ========================================================================
#                        ОБРАБОТЧИК CALLBACK
# ========================================================================

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    """
    Обрабатывает ВСЕ нажатия кнопок.
    Мы различаем кнопки по call.data.
    """

    user = call.from_user
    data = call.data

    logger.info(f"Callback '{data}' от пользователя {user.id} @{user.username}")

    try:
        # Кнопка "Обо мне"
        if data == "about_me":
            send_about_info(call.message.chat.id)

        # Кнопка "Мои работы"
        elif data == "my_job":
            send_categories(call.message.chat.id)

        # Кнопка "Бесплатные материалы"
        elif data == "check":
            send_subscription_check(call.message.chat.id)

        # Проверяем подписку
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
                # Пользователю не показываем сообщение — только логируем

        # Фото категории
        elif data.startswith("cat_"):
            category = data[4:]  # убираем префикс "cat_"
            send_category_album(call.message.chat.id, category)

    except Exception as e:
        logger.exception(f"Ошибка в callback '{data}': {e}")
        # Пользователь не увидит ошибку — только лог


# ========================================================================
#                          ЗАПУСК БОТА
# ========================================================================

if __name__ == "__main__":
    logger.info("Бот запущен ✔")
    bot.polling(none_stop=True)

