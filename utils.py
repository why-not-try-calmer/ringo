from typing import Callable
from functools import wraps
from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup


def parseArgs(received: str, chat_id: int) -> int | None:
    parsed = received.split(" ")
    l = len(parsed)
    if l == 1 or not parsed[1]:
        return chat_id
    elif l == 2:
        try:
            return int(parsed[1])
        except ValueError:
            return None
    else:
        return None


def mention_markdown(user_id: int, username: str) -> str:
    return f"[{username}](tg://user?id={user_id})"


def admins_ids_mkup(admins: list[ChatMember]) -> str:
    return ", ".join(
        [
            mention_markdown(
                admin.user.id, admin.user.username or admin.user.first_name
            )
            for admin in admins
        ]
    )


def agree_btn(url: str) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(text="I agree, let me in", url=url)
    return InlineKeyboardMarkup([[button]])


def accept_or_reject_btns(
    user_id: int, user_name: str, chat_id: int
) -> InlineKeyboardMarkup:
    accept = InlineKeyboardButton(
        text="Accept", callback_data=f"accept:{chat_id}:{user_id}:{user_name}"
    )
    reject = InlineKeyboardButton(
        text="Reject", callback_data=f"reject:{chat_id}:{user_id}:{user_name}"
    )
    keyboard = InlineKeyboardMarkup([[accept, reject]])
    return keyboard


def withAuth(f: Callable):
    @wraps(f)
    async def inner(*args, **kwargs):
        update, context = args
        chat_id = (
            update.callback_query.message.chat.id
            if hasattr(update, "callback_query") and update.callback_query
            else update.message.chat_id
        )
        user_id = (
            update.callback_query.from_user.id
            if hasattr(update, "callback_query") and update.callback_query
            else update.message.from_user.id
        )

        if chat_id == user_id:
            # Private message, which means the bot vouches for the user
            return await f(*args, **kwargs)

        admins = await context.bot.get_chat_administrators(chat_id)
        if user_id in [admin.user.id for admin in admins]:
            return await f(*args, **kwargs)
        else:
            await context.bot.send_message(chat_id, "Only admins can use this command!")

    return inner
