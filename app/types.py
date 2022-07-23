from datetime import date, datetime
from itertools import pairwise
from functools import reduce
from typing import Literal, Optional, TypeAlias
from telegram.helpers import escape_markdown

ChatId: TypeAlias = int | str
UserId: TypeAlias = int | str
MessageId: TypeAlias = int | str


class AsDict:
    def as_dict(self) -> dict:
        return vars(self)


class Settings(AsDict):
    chat_id: Optional[ChatId] = None
    chat_url: Optional[str] = None
    mode: Optional[str] = None
    helper_chat_id: Optional[ChatId] = None
    verification_msg: Optional[str] = None
    changelog: Optional[str] = None
    active: Optional[str] = None

    def __init__(self, settings: dict | str, chat_id: Optional[int | str] = None):
        clean_string_array = []

        if isinstance(settings, str):
            line_broken = settings.split("\n", maxsplit=1)

            if len(line_broken) == 2:
                clean_string_array = line_broken[0].split(" ")[1:] + [line_broken[1]]
            else:
                clean_string_array = line_broken[0].split(" ")[1:]

        d = (
            settings
            if isinstance(settings, dict)
            else dict(pairwise(clean_string_array))
        )

        for k, v in d.items():
            if k in {
                "helper_chat_id",
                "chat_id",
                "chat_url",
                "verification_msg",
                "mode",
                "changelog",
                "active",
            } and not (v == "None" or v is None):
                setattr(self, k, v if isinstance(v, str) else str(v))

        if chat_id:
            self.chat_id = chat_id

    def render(self, with_alert: bool = True) -> str:
        d = self.as_dict()

        if with_alert:

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
            reducer = (
                lambda acc, item: acc
                + f"{escape_markdown(item[0])}: {escape_markdown(item[1])}\n"
            )
            return reduce(reducer, d.items(), "")

    def __len__(self) -> int:
        return len(self.as_dict())


Operation = Literal[
    "wants_to_join", "has_verified", "replying_to_bot", "deletion", "background_task"
]


class UserLog(AsDict):
    operation: Operation
    message: Optional[str]
    chat_id: ChatId
    user_id: UserId
    username: str
    at: date
    joined_at: Optional[datetime]

    def __init__(
        self,
        operation: Operation,
        chat_id: ChatId,
        user_id: UserId,
        username: str,
        message: Optional[str] = None,
    ):
        self.operation = operation
        self.chat_id = chat_id
        self.user_id = user_id
        self.username = username

        now = datetime.now()

        if operation == "has_joined":
            self.joined_at = now
        else:
            self.at = now

        if message:
            self.message = message


class ServiceLog(AsDict):
    operation: Operation
    message: str
    at: datetime

    def __init__(self, operation: Operation, message):
        now = datetime.now()
        self.operation = operation
        self.message = message
        self.at = now
