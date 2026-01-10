import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from telebot import types


DATA_PATH = Path(__file__).resolve().parents[1] / "votes.json"
DEFAULT_DURATION_SECONDS = 7 * 24 * 60 * 60


def _load_state():
    if not DATA_PATH.exists():
        return {"polls": {}}
    try:
        with DATA_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"polls": {}}


def _save_state(state):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True, ensure_ascii=True)


def _now_ts():
    return int(time.time())


def _is_admin(user_id, admin_id):
    try:
        return int(user_id) == int(admin_id)
    except Exception:
        return False


def _parse_vote_command(text):
    if not text:
        return None, None
    parts = text.split(" ", 1)
    if len(parts) < 2:
        return None, None
    payload = parts[1].strip()
    items = [item.strip() for item in payload.split("|") if item.strip()]
    if len(items) < 3:
        return None, None
    question = items[0]
    options = items[1:]
    return question, options


def _format_end_time(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_user(info, user_id):
    username = info.get("username")
    name = info.get("name")
    if username:
        return f"@{username} ({user_id})"
    if name:
        return f"{name} ({user_id})"
    return str(user_id)


def _build_results_text(poll):
    lines = []
    lines.append(f"Poll ID: {poll['poll_id']}")
    lines.append(f"Question: {poll['question']}")
    lines.append(f"Ends at: {_format_end_time(poll['end_at'])}")
    lines.append("")
    votes = poll.get("votes", {})
    users = poll.get("users", {})
    for idx, option in enumerate(poll["options"]):
        voters = []
        for user_id, opt_idx in votes.items():
            if opt_idx == idx:
                info = users.get(user_id, {})
                voters.append(_format_user(info, user_id))
        lines.append(f"{idx + 1}. {option} - {len(voters)} vote(s)")
        for voter in voters:
            lines.append(f"- {voter}")
        if not voters:
            lines.append("- (no votes)")
        lines.append("")
    return "\n".join(lines).strip()


def register_voting_handlers(bot, logger, admin_id, channel_id):
    @bot.message_handler(commands=["vote"])
    def handle_vote_command(message):
        user = message.from_user
        if not _is_admin(user.id, admin_id):
            return

        question, options = _parse_vote_command(message.text)
        if not question:
            bot.send_message(
                message.chat.id,
                "Usage: /vote Question | Option 1 | Option 2"
            )
            return

        target_chat_id = message.chat.id
        if message.chat.type == "private":
            try:
                target_chat_id = int(channel_id)
            except Exception:
                bot.send_message(message.chat.id, "CHANNEL_ID is not set.")
                return

        poll_id = uuid.uuid4().hex[:8]
        end_at = _now_ts() + DEFAULT_DURATION_SECONDS

        markup = types.InlineKeyboardMarkup()
        for idx, option in enumerate(options):
            markup.add(
                types.InlineKeyboardButton(
                    option,
                    callback_data=f"vote:{poll_id}:{idx}"
                )
            )

        text_lines = [
            question,
            "",
            "Options:",
        ]
        for idx, option in enumerate(options):
            text_lines.append(f"{idx + 1}. {option}")
        text_lines.append("")
        text_lines.append(f"Ends at: {_format_end_time(end_at)}")
        text = "\n".join(text_lines)

        message_out = bot.send_message(target_chat_id, text, reply_markup=markup)

        state = _load_state()
        state["polls"][poll_id] = {
            "poll_id": poll_id,
            "question": question,
            "options": options,
            "created_at": _now_ts(),
            "end_at": end_at,
            "chat_id": target_chat_id,
            "message_id": message_out.message_id,
            "votes": {},
            "users": {},
            "closed": False,
        }
        _save_state(state)
        logger.info(f"Created poll {poll_id} in chat {target_chat_id}")
        if message.chat.id != target_chat_id:
            bot.send_message(
                message.chat.id,
                f"Poll created in channel. Poll ID: {poll_id}"
            )

    @bot.message_handler(commands=["vote_results"])
    def handle_vote_results(message):
        user = message.from_user
        if not _is_admin(user.id, admin_id):
            return

        parts = (message.text or "").split()
        poll_id = parts[1] if len(parts) > 1 else None

        state = _load_state()
        polls = state.get("polls", {})
        if not polls:
            bot.send_message(message.chat.id, "No polls found.")
            return

        if not poll_id:
            poll_id = max(polls.values(), key=lambda p: p.get("created_at", 0))["poll_id"]

        poll = polls.get(poll_id)
        if not poll:
            bot.send_message(message.chat.id, f"Poll not found: {poll_id}")
            return

        results_text = _build_results_text(poll)
        bot.send_message(message.chat.id, results_text)

    @bot.message_handler(commands=["vote_close"])
    def handle_vote_close(message):
        user = message.from_user
        if not _is_admin(user.id, admin_id):
            return

        parts = (message.text or "").split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Usage: /vote_close POLL_ID")
            return

        poll_id = parts[1]
        state = _load_state()
        poll = state.get("polls", {}).get(poll_id)
        if not poll:
            bot.send_message(message.chat.id, f"Poll not found: {poll_id}")
            return

        poll["closed"] = True
        state["polls"][poll_id] = poll
        _save_state(state)

        results_text = _build_results_text(poll)
        bot.send_message(message.chat.id, results_text)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("vote:"))
    def handle_vote_callback(call):
        try:
            _, poll_id, option_idx = call.data.split(":", 2)
            option_idx = int(option_idx)
        except Exception:
            bot.answer_callback_query(call.id, "Invalid vote data.")
            return

        state = _load_state()
        poll = state.get("polls", {}).get(poll_id)
        if not poll:
            bot.answer_callback_query(call.id, "Poll not found.")
            return

        if poll.get("closed") or _now_ts() >= poll["end_at"]:
            poll["closed"] = True
            state["polls"][poll_id] = poll
            _save_state(state)
            bot.answer_callback_query(call.id, "Poll is closed.")
            return

        if option_idx < 0 or option_idx >= len(poll["options"]):
            bot.answer_callback_query(call.id, "Invalid option.")
            return

        user = call.from_user
        user_id = str(user.id)
        poll.setdefault("votes", {})[user_id] = option_idx
        poll.setdefault("users", {})[user_id] = {
            "username": user.username,
            "name": " ".join(filter(None, [user.first_name, user.last_name])).strip(),
        }
        state["polls"][poll_id] = poll
        _save_state(state)

        bot.answer_callback_query(call.id, "Vote recorded.")
        logger.info(f"Vote in poll {poll_id} from {user_id} -> {option_idx}")
