from telebot.apihelper import ApiTelegramException

def is_subscribed(bot, chat_id, user_id):
    try:
        response = bot.get_chat_member(chat_id, user_id)
        return response.status not in ('left', 'kicked')
    except ApiTelegramException as e:
        if e.result_json['error_code'] == 400:
            return False
        raise