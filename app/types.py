from dataclasses import asdict, dataclass, fields
from datetime import datetime
from itertools import pairwise
from functools import reduce
from sqlite3 import Date
from typing import TypeAlias
from telegram.helpers import escape_markdown

ChatId: TypeAlias = int | str
UserId: TypeAlias = int | str
MessageId = TypeAlias = int | str


@dataclass
class Settings:
    chat_id: ChatId | None = None
    chat_url: str | None = None
    mode: str | None = None
    helper_chat_id: ChatId | None = None
    verification_msg: str | None = None

    def __init__(self, settings: dict | str, chat_id: ChatId | None = None):
        fs = {f.name for f in fields(Settings)}
        verification_msg = ""

        if isinstance(settings, str):
            settings_list = []

            # Handling the special case of 'verification_msg' first
            if "verification_msg" in settings:
                _settings, msg = settings.split("\n")
                settings_list = list(
                    filter(lambda w: w != "verification_msg", _settings.split(" "))
                )
                verification_msg = msg

            s = settings_list or settings.split(" ")

            # Ensuring list into dict
            if len(s) == 1 or not s[1]:
                return

            if len(s) % 2 != 0:
                s = s[1:]

            # Ensuring dict
            settings = dict(pairwise(s))

        for k, v in settings.items():
            if k in fs:
                setattr(self, k, v if isinstance(v, str) else str(v))

        if verification_msg:
            self.verification_msg = verification_msg

        if chat_id:
            self.chat_id = chat_id

    def __str__(self) -> str:
        d = asdict(self)
        reducer = (
            lambda acc, item: acc
            + f"{escape_markdown(item[0])}: {escape_markdown(item[1])}\n"
            if item[1] and item[1] != "None"
            else acc
        )
        return reduce(reducer, d.items(), "")

    def __len__(self) -> int:
        return len(vars(self))


@dataclass
class Log:
    text: str
    chat_id: ChatId
    user_id: UserId
    username: str
    at: Date

    def __init__(self, text: str, chat_id: ChatId, user_id: UserId, username: str):
        self.text = text
        self.chat_id = chat_id
        self.user_id = user_id
        self.username = username
        self.at = datetime.now()
