from dataclasses import asdict, dataclass, fields
from itertools import pairwise
from functools import reduce
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

        if isinstance(settings, str):
            s = settings.strip("\n").split(" ")

            if len(s) == 1 or not s[1]:
                return

            if len(s) % 2 != 0:
                s = s[1:]
            settings = dict(pairwise(s))

        for k, v in settings.items():
            if k in fs:
                setattr(self, k, v if isinstance(v, str) else str(v))

        if chat_id:
            self.chat_id = chat_id

    def __str__(self) -> str:
        d = asdict(self)
        reducer = (
            lambda acc, item: acc
            + f"{escape_markdown(item[0])}: {escape_markdown(item[1])}\n"
            if item[1]
            else acc
        )
        return reduce(reducer, d.items(), "")
