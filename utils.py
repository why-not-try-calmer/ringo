from typing import Callable
from dataclasses import dataclass
from functools import wraps, reduce
from itertools import pairwise
from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup


@dataclass
class Settings:
    chat_id: int | None = None
    chat_url: str | None = ""
    mode: str | None = ""
    helper_chat_id: int | None = None

    def __init__(self, settings: dict | str):

        if isinstance(settings, str):
            splitted = settings.split(" ")[1:]
            if len(splitted) % 2 != 0:
                return
            settings = dict(pairwise(settings))

        for k, v in settings.items():
            if k in self.__annotations__.keys():
                setattr(self, k, v)

    def __getitem__(self, k: str):
        if k in self.__annotations__.keys():
            return getattr(self, k)

    def __dict__(self):
        return vars(self)


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


def agree_btn(text: str, chat_id: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(text=text, callback_data=f"self-confirm:{chat_id}")
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


if __name__ == "__main__":
    s = Settings("/set mode auto helper_chat_id 123 chat_url abcd")
    print(s)
