from dataclasses import asdict, dataclass, fields
from itertools import pairwise
from functools import reduce
from typing import TypeAlias

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

    def __init__(self, settings: dict | str):
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
                setattr(self, k, v)

    def __str__(self) -> str:
        d = asdict(self)
        reducer = lambda acc, item: acc + f"{item[0]}: {item[1]}\n" if item[1] else acc
        return reduce(reducer, d.items(), "")
