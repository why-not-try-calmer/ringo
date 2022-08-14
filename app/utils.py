from asyncio import as_completed
from collections import namedtuple
from datetime import datetime
from typing import Any, Callable, Coroutine, Iterable
from functools import wraps
from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup

from app.types import (
    ChatId,
    UserId,
)


def average_nb_secs(datetimes: list[datetime]) -> None | int:
    if datetimes:
        now = datetime.now()
        deltas = [(now - d).total_seconds() for d in datetimes]
        return int(sum(deltas) / len(deltas))


def mention_markdown(user_id: UserId, username: str) -> str:
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


def agree_btn(text: str, chat_id: ChatId, chat_url: str) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(
        text=text, callback_data=f"self-confirm§{chat_id}§{chat_url}"
    )
    return InlineKeyboardMarkup([[button]])


def accept_or_reject_btns(
    user_id: UserId, user_name: str, chat_id: ChatId, chat_url: str
) -> InlineKeyboardMarkup:
    accept = InlineKeyboardButton(
        text="Accept",
        callback_data=f"accept§{chat_id}§{chat_url}§{user_id}§{user_name}",
    )
    reject = InlineKeyboardButton(
        text="Reject",
        callback_data=f"reject§{chat_id}§{chat_url}§{user_id}§{user_name}",
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
            await context.bot.send_message(
                chat_id,
                "Only admins can use this command!",
                disable_web_page_preview=True,
            )

    return inner


async def mark_excepted_coroutines(marker: Any, coroutine: Coroutine) -> Any | None:
    try:
        await coroutine
    except Exception:
        return marker


async def mark_successful_coroutines(marker: Any, coroutine: Coroutine) -> Any | None:
    try:
        await coroutine
        return marker
    except Exception:
        return


async def run_coroutines_masked(coroutines: Iterable[Coroutine]) -> None:
    for task in as_completed(coroutines):
        try:
            await task
        except Exception:
            return None
