import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from works import my_works
from subscription import is_subscribed
from config import BOT_TOKEN, CHANNEL_ID

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------------------
# 🔧 УТИЛИТЫ
# ---------------------------

def send_photo(chat_id, path, caption=None, markup=None):
    """Безопасная отправка фото"""
    try:
        with open(path, "rb") as photo:
            bot.send_photo(chat_id, photo, caption=caption, reply_markup=markup, parse_mode="Markdown")
    except FileNotFoundError:
        bot.send_message(chat_id, f"❌ Фото не найдено: {path}")


def create_buttons(*rows):
    """Создаёт InlineKeyboardMarkup из списков кнопок"""
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.add(*row)
    return markup


# ---------------------------
# 🏁 КОМАНДА /start
# ---------------------------

@bot.message_handler(commands=['старт', 'start'])
def main(message):
    send_photo(message.chat.id, "media/welcome/fistphoto.jpg")

    markup = create_buttons(
        [types.InlineKeyboardButton("Обо мне📜", callback_data="about_me")],
        [types.InlineKeyboardButton("Бесплатные мастер-классы🎁", callback_data="check")],
        [types.InlineKeyboardButton("Мои работы🧸", callback_data="my_job")]
    )

    bot.send_message(message.chat.id, "Приветствую на канале по созданию миниатюры!", reply_markup=markup)


# ---------------------------
# ℹ️ ОБО МНЕ
# ---------------------------

def send_about_info(chat_id):
    send_photo(chat_id, "media/welcome/Photo.jpg")

    text = (
        "Меня зовут Наталья. Мне 45 лет... \n"
        "Я публикую свои миниатюрные работы и мастер-классы "
        "в своём [проекте](https://vk.com/nrminiatures)"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")


# ---------------------------
# 🧸 МОИ РАБОТЫ (категории)
# ---------------------------

def send_categories(chat_id):
    categories = list(my_works.keys())

    markup = types.InlineKeyboardMarkup()
    for i in range(0, len(categories), 2):
        row = [
            types.InlineKeyboardButton(categories[i], callback_data=f"cat_{categories[i]}")
        ]
        if i + 1 < len(categories):
            row.append(types.InlineKeyboardButton(categories[i+1], callback_data=f"cat_{categories[i+1]}"))
        markup.add(*row)

    bot.send_message(chat_id, "Выберите категорию:", reply_markup=markup)


# ---------------------------
# 🎁 ПРОВЕРКА ПОДПИСКИ
# ---------------------------

def send_subscription_check(chat_id):
    markup = create_buttons(
        [types.InlineKeyboardButton("Мой канал💬", url="https://t.me/dollminiature")],
        [types.InlineKeyboardButton("Готово, я подписан(-а)✅", callback_data="check_subscription")]
    )
    bot.send_message(chat_id, "Чтобы получить доступ к материалам, подпишитесь:", reply_markup=markup)


# ---------------------------
# 📸 ОТПРАВКА КАТЕГОРИИ РАБОТ
# ---------------------------

def send_category_album(chat_id, category):
    works = my_works.get(category, [])

    if not works:
        bot.send_message(chat_id, "В этой категории пока нет работ.")
        return

    media = []
    for item in works:
        try:
            with open(item["photo"], "rb") as f:
                media.append(types.InputMediaPhoto(f.read()))
        except FileNotFoundError:
            continue

    if media:
        bot.send_media_group(chat_id, media)
        bot.send_message(chat_id, f"🖼️ Категория: *{category}*", parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "Фото не найдены.")


# ---------------------------
# 📌 ОБРАБОТКА CALLBACKS
# ---------------------------

@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    try:
        data = call.data

        if data == "about_me":
            send_about_info(call.message.chat.id)

        elif data == "my_job":
            send_categories(call.message.chat.id)

        elif data == "check":
            send_subscription_check(call.message.chat.id)

        elif data == "check_subscription":
            user_id = call.from_user.id
            if is_subscribed(bot, CHANNEL_ID, user_id):
                markup = create_buttons([
                    types.InlineKeyboardButton("Мастер-класс🔗", url="https://disk.yandex.ru/i/5SeUgQ1cjjok0Q")
                ])
                bot.send_message(call.message.chat.id, "Спасибо за подписку!🤩", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, "Вы не подписаны, пожалуйста подпишитесь 😢")

        elif data.startswith("cat_"):
            send_category_album(call.message.chat.id, data[4:])

    except ApiTelegramException as error:
        bot.send_message(call.message.chat.id, f"Ошибка Telegram API:\n{error}")


# ---------------------------
# ▶️ ЗАПУСК БОТА
# ---------------------------

if __name__ == "__main__":
    bot.polling(none_stop=True)
