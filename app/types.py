from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from itertools import pairwise
from functools import reduce
from typing import Optional, TypeAlias
from telegram.helpers import escape_markdown

ChatId: TypeAlias = int | str
UserId: TypeAlias = int | str
MessageId: TypeAlias = int | str


@dataclass
class Settings:
    chat_id: Optional[ChatId] = None
    chat_url: Optional[str] = None
    mode: Optional[str] = None
    helper_chat_id: Optional[ChatId] = None
    verification_msg: Optional[str] = None

    def __init__(self, settings: dict | str, chat_id: Optional[ChatId] = None):
        fs = {f.name for f in fields(Settings)}
        settings_list = []
        verification_msg = ""

        if isinstance(settings, str):
            settings_list = []

            # Handling the special case of 'verification_msg' first
            if "verification_msg" in settings:
                _settings, msg = settings.split("\n", maxsplit=1)
                settings_list = list(
                    filter(
                        lambda w: not w in ["verification_msg", "/set"],
                        _settings.split(" "),
                    )
                )
                verification_msg = msg

            s = settings_list or settings.split(" ")

            # Ensuring list into dict
            if len(s) == 1 or not s[1]:
                return

            # Ensuring dict
            settings = dict(pairwise(s))

        for k, v in settings.items():
            if k in fs:
                setattr(self, k, v if isinstance(v, str) else str(v))

        if verification_msg:
            self.verification_msg = verification_msg

        if chat_id:
            self.chat_id = chat_id

    def as_dict_no_none(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v and v is not None}

    def render(self, with_alert: bool) -> str:
        if with_alert:
            d = asdict(self)

            def reducer(acc, item) -> str:
                k, v = (
                    item[0],
                    str(item[1]) if not isinstance(item[1], str) else item[1],
                )

                if k in ["chat_url", "verification_msg"] and (not v or v == "None"):
                    return (
                        acc
                        + "\n"
                        + b"\xE2\x9A\xA0".decode("utf-8")
                        + f"Missing an important value here ({escape_markdown(k)})! The bot won't be able to operate properly without it!\n\n"
                    )
                return acc + f"{escape_markdown(k)}: {escape_markdown(v)}\n"

            return reduce(reducer, d.items(), "")

        else:
            d = self.as_dict_no_none()
            reducer = (
                lambda acc, item: acc
                + f"{escape_markdown(item[0])}: {escape_markdown(item[1])}\n"
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
    at: date

    def __init__(self, text: str, chat_id: ChatId, user_id: UserId, username: str):
        self.text = text
        self.chat_id = chat_id
        self.user_id = user_id
        self.username = username
        self.at = datetime.now()
