import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from telebot import types


DEFAULT_DURATION_SECONDS = 7 * 24 * 60 * 60
_DRAFTS = {}


def _db_path():
    env_path = os.getenv("VOTES_DB_PATH")
    if env_path:
        return Path(env_path)
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root.parent / "data" / "votes.db"


def _get_conn():
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_db():
    conn = _get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS polls (
                poll_id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                end_at INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                closed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS options (
                poll_id TEXT NOT NULL,
                option_idx INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                PRIMARY KEY (poll_id, option_idx)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                name TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                poll_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                option_idx INTEGER NOT NULL,
                PRIMARY KEY (poll_id, user_id, option_idx)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS confirmations (
                poll_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                confirmed_at INTEGER NOT NULL,
                PRIMARY KEY (poll_id, user_id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _poll_row_to_dict(row):
    if not row:
        return None
    return {
        "poll_id": row["poll_id"],
        "question": row["question"],
        "created_at": row["created_at"],
        "end_at": row["end_at"],
        "chat_id": row["chat_id"],
        "message_id": row["message_id"],
        "closed": bool(row["closed"]),
    }


def _fetch_polls(channel_id=None):
    conn = _get_conn()
    try:
        if channel_id is None:
            rows = conn.execute(
                """
                SELECT poll_id, question, created_at, end_at, chat_id, message_id, closed
                FROM polls
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT poll_id, question, created_at, end_at, chat_id, message_id, closed
                FROM polls
                WHERE chat_id = ?
                """,
                (channel_id,),
            ).fetchall()
        return [_poll_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def _get_poll_base(poll_id):
    conn = _get_conn()
    try:
        row = conn.execute(
            """
            SELECT poll_id, question, created_at, end_at, chat_id, message_id, closed
            FROM polls
            WHERE poll_id = ?
            """,
            (poll_id,),
        ).fetchone()
        return _poll_row_to_dict(row)
    finally:
        conn.close()


def _get_poll(poll_id):
    conn = _get_conn()
    try:
        row = conn.execute(
            """
            SELECT poll_id, question, created_at, end_at, chat_id, message_id, closed
            FROM polls
            WHERE poll_id = ?
            """,
            (poll_id,),
        ).fetchone()
        poll = _poll_row_to_dict(row)
        if not poll:
            return None

        option_rows = conn.execute(
            """
            SELECT option_text
            FROM options
            WHERE poll_id = ?
            ORDER BY option_idx
            """,
            (poll_id,),
        ).fetchall()
        poll["options"] = [row["option_text"] for row in option_rows]

        votes_rows = conn.execute(
            """
            SELECT user_id, option_idx
            FROM votes
            WHERE poll_id = ?
            """,
            (poll_id,),
        ).fetchall()
        votes = {}
        for row in votes_rows:
            votes.setdefault(row["user_id"], []).append(row["option_idx"])
        poll["votes"] = votes

        confirmed_rows = conn.execute(
            """
            SELECT user_id
            FROM confirmations
            WHERE poll_id = ?
            """,
            (poll_id,),
        ).fetchall()
        confirmed = {row["user_id"]: True for row in confirmed_rows}
        poll["confirmed"] = confirmed

        user_ids = set(votes.keys()) | set(confirmed.keys())
        users = {}
        if user_ids:
            placeholders = ",".join("?" * len(user_ids))
            user_rows = conn.execute(
                f"""
                SELECT user_id, username, name
                FROM users
                WHERE user_id IN ({placeholders})
                """,
                list(user_ids),
            ).fetchall()

            users = {
                row["user_id"]: {"username": row["username"], "name": row["name"]}
                for row in user_rows
            }
        poll["users"] = users
        return poll
    finally:
        conn.close()


def _get_option_count(poll_id):
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(1) AS count FROM options WHERE poll_id = ?",
            (poll_id,),
        ).fetchone()
        return int(row["count"] or 0)
    finally:
        conn.close()


def _create_poll(poll_id, question, options, end_at, chat_id, message_id):
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO polls (poll_id, question, created_at, end_at, chat_id, message_id, closed)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (poll_id, question, _now_ts(), end_at, chat_id, message_id),
        )
        conn.executemany(
            """
            INSERT INTO options (poll_id, option_idx, option_text)
            VALUES (?, ?, ?)
            """,
            [(poll_id, idx, option) for idx, option in enumerate(options)],
        )
        conn.commit()
    finally:
        conn.close()


def _set_poll_closed(poll_id, closed=True):
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE polls SET closed = ? WHERE poll_id = ?",
            (1 if closed else 0, poll_id),
        )
        conn.commit()
    finally:
        conn.close()


def _is_confirmed(poll_id, user_id):
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM confirmations WHERE poll_id = ? AND user_id = ?",
            (poll_id, user_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _confirm_vote(poll_id, user_id, selections, user_info):
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO users (user_id, username, name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                name = excluded.name
            """,
            (user_id, user_info.get("username"), user_info.get("name")),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO confirmations (poll_id, user_id, confirmed_at)
            VALUES (?, ?, ?)
            """,
            (poll_id, user_id, _now_ts()),
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO votes (poll_id, user_id, option_idx)
            VALUES (?, ?, ?)
            """,
            [(poll_id, user_id, option_idx) for option_idx in selections],
        )
        conn.commit()
    finally:
        conn.close()


def _get_draft_selections(poll_id, user_id):
    return set(_DRAFTS.get(poll_id, {}).get(user_id, []))


def _set_draft_selections(poll_id, user_id, selections):
    poll_drafts = _DRAFTS.setdefault(poll_id, {})
    poll_drafts[user_id] = sorted(selections)


def _clear_draft_selections(poll_id, user_id):
    poll_drafts = _DRAFTS.get(poll_id)
    if not poll_drafts:
        return
    poll_drafts.pop(user_id, None)
    if not poll_drafts:
        _DRAFTS.pop(poll_id, None)


_init_db()


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


def _extract_channel_override(text):
    if not text:
        return None
    parts = text.split()
    if len(parts) < 3:
        return None
    if parts[0].lstrip("/").lower() != "vote":
        return None
    if parts[1].lower() != "channel":
        return None
    try:
        return int(parts[2])
    except Exception:
        return None


def _strip_channel_prefix(text):
    parts = text.split(" ", 3)
    if len(parts) < 3:
        return text
    if parts[1].lower() != "channel":
        return text
    try:
        int(parts[2])
    except Exception:
        return text
    if len(parts) == 3:
        return parts[0]
    return f"{parts[0]} {parts[3]}"


def _format_end_time(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_end_date(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


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
            selected = opt_idx
            if isinstance(opt_idx, list):
                selected = idx in opt_idx
            else:
                selected = opt_idx == idx
            if selected:
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
    def log_event(event, user=None, **fields):
        payload = {"event": event, **fields}
        if user is not None:
            payload["user_id"] = user.id
            payload["username"] = user.username
        logger.info(event, extra=payload)

    @bot.message_handler(commands=["help"])
    def handle_help(message):
        user = message.from_user
        if not _is_admin(user.id, admin_id):
            return

        help_text = (
            "Доступные команды:\n"
            "/start\n"
            "/vote Вопрос | Вариант 1 | Вариант 2\n"
            "/vote channel CHANNEL_ID Вопрос | Вариант 1 | Вариант 2\n"
            "/vote_results\n"
            "/vote_results POLL_ID\n"
            "/vote_results channel CHANNEL_ID\n"
            "/vote_participants\n"
            "/vote_participants POLL_ID\n"
            "/vote_participants channel CHANNEL_ID\n"
            "/vote_close POLL_ID\n"
            "/vote_close channel CHANNEL_ID\n"
        )
        bot.send_message(message.chat.id, help_text)

    @bot.message_handler(commands=["vote"])
    def handle_vote_command(message):
        user = message.from_user
        if not _is_admin(user.id, admin_id):
            return

        log_event("command", user, command="vote", chat_id=message.chat.id)

        channel_override = _extract_channel_override(message.text)
        parse_text = _strip_channel_prefix(message.text) if channel_override else message.text

        question, options = _parse_vote_command(parse_text)
        if not question:
            bot.send_message(
                message.chat.id,
                "Usage: /vote Question | Option 1 | Option 2\n"
                "Optional: /vote channel -1001234567890 Question | Option 1 | Option 2"
            )
            return

        target_chat_id = message.chat.id
        if channel_override:
            target_chat_id = channel_override
        elif message.chat.type == "private":
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
            "Выберите, затем нажмите кнопку Подтвердить ?.",
            "",
            "Кончается: " + _format_end_date(end_at),
        ]
        text = "\n".join(text_lines)

        markup.add(
            types.InlineKeyboardButton(
                "Подтвердить ?",
                callback_data=f"vote_confirm:{poll_id}"
            )
        )

        message_out = bot.send_message(target_chat_id, text, reply_markup=markup)

        _create_poll(
            poll_id,
            question,
            options,
            end_at,
            target_chat_id,
            message_out.message_id,
        )
        log_event(
            "poll_created",
            user,
            poll_id=poll_id,
            chat_id=target_chat_id,
            options_count=len(options),
        )
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

        log_event("command", user, command="vote_results", chat_id=message.chat.id)

        parts = (message.text or "").split()
        poll_id = parts[1] if len(parts) > 1 else None
        channel_id_override = None
        if len(parts) > 2 and parts[1].lower() == "channel":
            try:
                channel_id_override = int(parts[2])
            except Exception:
                channel_id_override = None

        polls = _fetch_polls(channel_id_override if channel_id_override is not None else None)
        if not polls:
            if channel_id_override is not None:
                bot.send_message(message.chat.id, "No polls found for that channel.")
            else:
                bot.send_message(message.chat.id, "No polls found.")
            return

        if not poll_id:
            poll_id = max(polls, key=lambda p: p.get("created_at", 0))["poll_id"]
        elif poll_id and poll_id.lower() == "channel" and channel_id_override is not None:
            poll_id = max(polls, key=lambda p: p.get("created_at", 0))["poll_id"]

        poll = _get_poll(poll_id)
        if not poll:
            bot.send_message(message.chat.id, f"Poll not found: {poll_id}")
            return
        if channel_id_override is not None and poll.get("chat_id") != channel_id_override:
            bot.send_message(message.chat.id, "Poll not found for that channel.")
            return

        results_text = _build_results_text(poll)
        bot.send_message(message.chat.id, results_text)

    @bot.message_handler(commands=["vote_participants"])
    def handle_vote_participants(message):
        user = message.from_user
        if not _is_admin(user.id, admin_id):
            return

        log_event("command", user, command="vote_participants", chat_id=message.chat.id)

        parts = (message.text or "").split()
        poll_id = parts[1] if len(parts) > 1 else None
        channel_id_override = None
        if len(parts) > 2 and parts[1].lower() == "channel":
            try:
                channel_id_override = int(parts[2])
            except Exception:
                channel_id_override = None

        polls = _fetch_polls(channel_id_override if channel_id_override is not None else None)
        if not polls:
            if channel_id_override is not None:
                bot.send_message(message.chat.id, "No polls found for that channel.")
            else:
                bot.send_message(message.chat.id, "No polls found.")
            return

        if not poll_id:
            poll_id = max(polls, key=lambda p: p.get("created_at", 0))["poll_id"]
        elif poll_id and poll_id.lower() == "channel" and channel_id_override is not None:
            poll_id = max(polls, key=lambda p: p.get("created_at", 0))["poll_id"]

        poll = _get_poll(poll_id)
        if not poll:
            bot.send_message(message.chat.id, f"Poll not found: {poll_id}")
            return
        if channel_id_override is not None and poll.get("chat_id") != channel_id_override:
            bot.send_message(message.chat.id, "Poll not found for that channel.")
            return

        users = poll.get("users", {})
        confirmed = poll.get("confirmed", {})
        confirmed_users = [
            _format_user(info, user_id)
            for user_id, info in users.items()
            if confirmed.get(user_id)
        ]
        if not confirmed_users:
            bot.send_message(message.chat.id, "No participants yet.")
            return

        text = "Участники:\n" + "\n".join(sorted(confirmed_users))
        bot.send_message(message.chat.id, text)

    @bot.message_handler(commands=["vote_close"])
    def handle_vote_close(message):
        user = message.from_user
        if not _is_admin(user.id, admin_id):
            return

        log_event("command", user, command="vote_close", chat_id=message.chat.id)

        parts = (message.text or "").split()
        if len(parts) < 2:
            bot.send_message(
                message.chat.id,
                "Usage: /vote_close POLL_ID\n"
                "Optional: /vote_close channel -1001234567890"
            )
            return

        poll_id = parts[1]
        channel_id_override = None
        if poll_id.lower() == "channel" and len(parts) >= 3:
            try:
                channel_id_override = int(parts[2])
            except Exception:
                channel_id_override = None
            poll_id = None

        if poll_id is None:
            candidates = _fetch_polls(channel_id_override)
            if not candidates:
                bot.send_message(message.chat.id, "No polls found for that channel.")
                return
            poll = max(candidates, key=lambda p: p.get("created_at", 0))
            poll_id = poll["poll_id"]
        else:
            poll = _get_poll_base(poll_id)
        if not poll:
            bot.send_message(message.chat.id, f"Poll not found: {poll_id}")
            return

        _set_poll_closed(poll_id, True)
        poll = _get_poll(poll_id)
        results_text = _build_results_text(poll)
        bot.send_message(message.chat.id, results_text)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("vote:") or call.data.startswith("vote_confirm:"))
    def handle_vote_callback(call):
        if call.data.startswith("vote_confirm:"):
            try:
                _, poll_id = call.data.split(":", 1)
            except Exception:
                bot.answer_callback_query(call.id, "Invalid vote data.")
                return

            poll = _get_poll_base(poll_id)
            if not poll:
                bot.answer_callback_query(call.id, "Poll not found.")
                return

            if poll.get("closed") or _now_ts() >= poll["end_at"]:
                if not poll.get("closed"):
                    _set_poll_closed(poll_id, True)
                bot.answer_callback_query(call.id, "Poll is closed.")
                return

            user = call.from_user
            user_id = str(user.id)
            if _is_confirmed(poll_id, user_id):
                bot.answer_callback_query(call.id, "Вы уже проголосовали.")
                return

            selections = _get_draft_selections(poll_id, user_id)
            if not selections:
                bot.answer_callback_query(call.id, "Выберите хотя бы один вариант.")
                return

            _confirm_vote(
                poll_id,
                user_id,
                sorted(set(selections)),
                {
                    "username": user.username,
                    "name": " ".join(filter(None, [user.first_name, user.last_name])).strip(),
                },
            )
            log_event(
                "vote_confirmed",
                user,
                poll_id=poll_id,
                chat_id=poll.get("chat_id") if poll else None,
                selections=sorted(selections),
            )
            _clear_draft_selections(poll_id, user_id)
            bot.answer_callback_query(call.id, "Ваш голос учтен.")
            logger.info(f"Vote confirmed in poll {poll_id} from {user_id} -> {sorted(selections)}")
            return

        try:
            _, poll_id, option_idx = call.data.split(":", 2)
            option_idx = int(option_idx)
        except Exception:
            bot.answer_callback_query(call.id, "Invalid vote data.")
            return

        poll = _get_poll_base(poll_id)
        if not poll:
            bot.answer_callback_query(call.id, "Poll not found.")
            return

        if poll.get("closed") or _now_ts() >= poll["end_at"]:
            if not poll.get("closed"):
                _set_poll_closed(poll_id, True)
            bot.answer_callback_query(call.id, "Poll is closed.")
            return

        if option_idx < 0 or option_idx >= _get_option_count(poll_id):
            bot.answer_callback_query(call.id, "Invalid option.")
            return

        user = call.from_user
        user_id = str(user.id)
        if _is_confirmed(poll_id, user_id):
            bot.answer_callback_query(call.id, "Вы уже проголосовали.")
            return

        selections = _get_draft_selections(poll_id, user_id)
        if option_idx in selections:
            selections.remove(option_idx)
            action_text = "Убрано из выбора."
        else:
            selections.add(option_idx)
            action_text = "Добавлено в выбор."
        _set_draft_selections(poll_id, user_id, selections)

        log_event(
            "vote_draft_updated",
            user,
            poll_id=poll_id,
            chat_id=poll.get("chat_id") if poll else None,
            selections=sorted(selections),
        )
        bot.answer_callback_query(call.id, action_text)
        logger.info(f"Selection update in poll {poll_id} from {user_id} -> {sorted(selections)}")
