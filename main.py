import telebot
import webbrowser
from telebot import types
from telebot.apihelper import ApiTelegramException
from works import my_works
from subscription import is_subscribed

from config import BOT_TOKEN, CHANNEL_ID


bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands = ['старт', 'start'])
def main(user):
    photo = open("media/welcome/fistphoto.jpg", "rb")
    bot.send_photo(user.chat.id, photo)

    button = types.InlineKeyboardMarkup()
    button.add(types.InlineKeyboardButton("Обо мне📜", callback_data = "about_me"))
    button.add(types.InlineKeyboardButton("Бесплатные мастер-классы🎁", callback_data = "check"))
    button.add(types.InlineKeyboardButton("Мои работы🧸", callback_data= "my_job"))

    text = "Приветствую на канале по созданию миниатюры!"
    bot.send_message(user.chat.id, text, reply_markup = button)



@bot.callback_query_handler(func = lambda call: call.data == 'about_me' or call.data == 'check' or call.data == "my_job" )
def processing(callback):

    if callback.data == "about_me":
        photo = open("media/welcome/Photo.jpg", "rb")
        bot.send_photo(callback.message.chat.id, photo)
        text = "Меня зовут Наталья. Мне 45 лет, я живу в Воронеже с мужем и тремя сыновьями. По образованию я лингвист-преподаватель, изучала немецкий и испанский языки и зарубежную литературу. После окончания университета работала в немецкой компании, а также преподавала немецкий язык. После рождения детей я полностью переключилась на рукоделие.\nНесколько лет я шила  косметички, сумочки и кошельки, создавала декор  для дома в разных техниках, делала на заказ работы в стиле пэчворк, книги ручной работы. Много лет я занимаюсь реставрацией, с 2009 года увлеклась созданием коллекционной игрушки, мои работы живут у коллекционеров в Японии, США, Великобритании, Австралии, Сингапуре, Франции, Германии и в других странах.  Один мой персонаж был назначен директором небольшого передвижного музея, также в музеях нашей страны есть работы, в реставрации которых я принимала участие. Мне посчастливилось сделать для мультипликатора игрушку-копию героя популярного кукольного мультипликационного фильма, утраченную во время пожара.\nЯ люблю создавать уникальные вещи для своего дома, у меня есть работы в технике декупаж, я люблю шить, вязать, вышиваю, увлекаюсь скрапбукингом (делаю книги и блокноты ручной работы), мне очень нравится пэчворк и квилтинг, несколько раз в год я выбираю что-то в этой технике для себя, на заказ или в подарок близким. У меня дома есть несколько предметов мебели, которые я отреставрировала или декорировала своими руками. Последние несколько лет мы с семьей строим дачу, и я очень много работала с деревом. Все эти увлечения и навыки очень пригодились мне в создании миниатюры.\nСейчас я посвящаю ей почти все свободное от семьи время, это наполняет меня энергией, дарит хорошее настроение и оптимизм. Особенно меня вдохновляют работы японских мастеров миниатюры в разных техниках, у них я с удовольствием учусь и готова делиться своими знаниями с теми, кто хочет погрузиться в удивительный мир утонченной красоты и гармонии, мир смелых идей, мир неограниченной фантазии.\nЯ публикую свои миниатюрные работы и мастер-классы в своем [проекте](https://vk.com/nrminiatures)"

        bot.send_message(callback.message.chat.id, text, parse_mode='Markdown')

    elif callback.data == "my_job":
        categories = list(my_works.keys())

        markup = types.InlineKeyboardMarkup()

        for i in range(0, len(categories), 2):
            row = []
            btn1 = types.InlineKeyboardButton(
                text=categories[i],
                callback_data=f"cat_{categories[i]}"
            )
            row.append(btn1)
            if i + 1 < len(categories):
                btn2 = types.InlineKeyboardButton(
                    text=categories[i + 1],
                    callback_data=f"cat_{categories[i + 1]}"
                )
                row.append(btn2)
            markup.add(*row)

        bot.send_message(
            callback.message.chat.id,
            "Выберите категорию:",
            reply_markup=markup
        )

    elif callback.data == "check":
        text1 = "Чтобы получить доступ к материалам, подпишитесь на мой телеграм-канал"

        button = types.InlineKeyboardMarkup()
        button.add(types.InlineKeyboardButton("Мой канал💬", url = "https://t.me/dollminiature"))
        button.add(types.InlineKeyboardButton("Готово, я подписан(-а)✅", callback_data="check_subscription"))

        bot.send_message(callback.message.chat.id, text1, parse_mode='Markdown', reply_markup = button)


@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def check(callback1):
    user_id = callback1.from_user.id
    if callback1.data == "check_subscription":
        if is_subscribed(bot, CHANNEL_ID, user_id):
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton(
                text="Мастер-класс🔗",
                url="https://disk.yandex.ru/i/5SeUgQ1cjjok0Q"
            )
            markup.add(btn)
            bot.send_message(
                callback1.message.chat.id,
                "Спасибо за подписку!🤩",
                reply_markup=markup,
                parse_mode='Markdown'
            )

        else:
            bot.send_message(callback1.message.chat.id, 'Вас нет среди подписчиков нашего канала, пожалуйста, подпишитесь😢')


@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def send_category_album(call):
    category_name = call.data[4:]

    if category_name not in my_works:
        bot.answer_callback_query(call.id, "Категория не найдена.")
        return

    works = my_works[category_name]
    photo_paths = [work["photo"] for work in works]

    if not photo_paths:
        bot.send_message(call.message.chat.id, "В этой категории пока нет работ.")
        return

    media_group = []
    for path in photo_paths:
        try:
            media_group.append(telebot.types.InputMediaPhoto(open(path, 'rb')))
        except FileNotFoundError:
            continue

    if not media_group:
        bot.send_message(call.message.chat.id, "Фото не найдены.")
        return

    bot.send_media_group(call.message.chat.id, media_group)

    bot.send_message(call.message.chat.id, f"🖼️ Категория: *{category_name}*", parse_mode='Markdown')

bot.polling(none_stop=True)
