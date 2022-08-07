from collections import namedtuple
from datetime import date, datetime
from itertools import pairwise
from functools import reduce
from typing import (
    Any,
    Callable,
    Iterator,
    Literal,
    NamedTuple,
    Optional,
    OrderedDict,
    TypeAlias,
)
from asyncio import create_task, get_running_loop

from telegram.helpers import escape_markdown

ChatId: TypeAlias = int | str
UserId: TypeAlias = int | str
MessageId: TypeAlias = int | str


class AsDict:
    def as_dict(self) -> dict:
        return vars(self)


Settings_keys = {
    "helper_chat_id",
    "chat_id",
    "chat_url",
    "verification_msg",
    "mode",
    "changelog",
    "active",
    "show_join_time",
    "ban_not_joining",
}

Settings_boolean_keys = {
    "changelog",
    "active",
    "show_join_time",
    "ban_not_joining",
}

Mode = Literal["auto", "manual", "questionnaire"]
Questionnaire = namedtuple("Questionnaire", ["intro", "questions", "outro"])


def parse_to_questionnaire(text: str) -> Questionnaire | None:
    splitted = text.split("\n")

    if len(splitted) >= 3:
        return Questionnaire(splitted[0], splitted[1:-1], splitted[-1])


def render_questionnaire(q: Questionnaire) -> str:
    vals = q._asdict().values()
    return "\n".join(vals)


class Settings(AsDict):
    chat_id: Optional[ChatId] = None
    chat_url: Optional[str] = None
    mode: Optional[Mode] = None
    helper_chat_id: Optional[ChatId] = None
    verification_msg: Optional[str] = None
    changelog: Optional[bool] = None
    active: Optional[bool] = None
    show_join_time: Optional[bool] = None
    ban_not_joining: Optional[bool] = None
    conversation: Optional[Questionnaire] = None

    def __init__(self, settings: dict | str, chat_id: Optional[int | str] = None):
        # Receives dict from MongoDB, str from Telegram
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
            if k in Settings_keys and not (v == "None" or v is None):
                value: bool | str = ""
                if k in Settings_boolean_keys:
                    match v:
                        case "True" | "true" | "on" | "enabled":
                            value = True
                        case "False" | "false" | "off" | "disabled":
                            value = False
                        case _:
                            value = v

                elif k == "conversation" and isinstance(v, dict):
                    self.questionnaire = Questionnaire(**v)

                else:
                    value = v
                setattr(self, k, value)

        if chat_id:
            self.chat_id = chat_id

    @property
    def unassigned(self) -> list[str]:
        key_vals = vars(self)
        nones = [k for k, v in key_vals.items() if v is None]
        missing = [k for k in Settings_keys if not k in key_vals.keys()]
        return nones + missing

    def render(self, with_alert: bool = True) -> str:
        d = self.as_dict()

        def pretty_bool_str(v: Any) -> str:
            if isinstance(v, bool):
                return "on" if v is True else "off"
            return str(v)

        if with_alert:

            def reducer(acc, item) -> str:
                k, v = item[0], item[1]

                if k in ["chat_url", "verification_msg"] and (not v or v == "None"):
                    return (
                        acc
                        + "\n"
                        + b"\xE2\x9A\xA0".decode("utf-8")
                        + f"Missing an important value here ({escape_markdown(k)})! The bot won't be able to operate properly without it!\n\n"
                    )
                return (
                    acc
                    + f"{escape_markdown(k)}: {escape_markdown(pretty_bool_str(v))}\n"
                )

            return reduce(reducer, d.items(), "")

        else:
            reducer = (
                lambda acc, item: acc
                + f"{escape_markdown(item[0])}: {escape_markdown(pretty_bool_str(item[1]))}\n"
            )
            return reduce(reducer, d.items(), "")

    def __len__(self) -> int:
        return len(self.as_dict())


Operation = Literal[
    "wants_to_join",
    "has_verified",
    "replying_to_bot",
    "deletion",
    "background_task",
    "is_banned",
]


class UserLog(AsDict):
    operation: Operation
    message: Optional[str]
    chat_id: ChatId
    user_id: UserId
    username: str
    at: date
    joined_at: Optional[datetime]
    banned_at: Optional[datetime]

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

        match operation:
            case "has_joined":
                self.joined_at = now
            case "is_banned":
                self.is_banned = now
            case _:
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


User = namedtuple("User", ["user_id", "chat_id"])


"""" Conversation handler to replace the garbage ConversationHandler from the library"""


class Dialog:
    """
    Holds a 1-1 conversation between the bot and users
    """

    user_id: UserId
    for_chat_id: ChatId

    intro: str
    questions: list[str]
    outro: str

    answers: list[str]
    it: Iterator[str]
    extract_state: Callable
    has_started: bool

    def __init__(
        self,
        user_id: UserId,
        chat_id: ChatId,
        q: Questionnaire,
        extract_answers: Callable,
    ):
        self.user_id = user_id
        self.for_chat_id = chat_id

        self.intro = q.intro
        self.questions = q.questions
        self.outro = q.outro

        self.answers = []
        self.it = iter(self.questions)
        self._extract_answers = extract_answers
        self.has_started = False

    def _next_q(self, answer: Optional[str] = None) -> str | None:
        try:
            if answer:
                self.answers.append(answer)
            return next(self.it)

        except StopIteration:
            return None

    @property
    def done(self) -> bool:
        return len(self.answers) == len(self.questions)

    def start(self):
        self.has_started = True

    def start_over(self):
        self.it = iter(self.questions)
        self.answers = []

    def extract_answers(self):
        try:
            loop = get_running_loop()
            if loop.is_running:
                create_task(self._extract_answers(self.answers))
            else:
                self._extract_answers(self.answers)

        except RuntimeError:
            self._extract_answers(self.answers)

    def take_reply(self, answer: Optional[str] = None) -> None | str:
        # Dialog has not begun yet
        if not self.has_started:
            self.start()
            return self.intro

        # Dialog has begun, continue
        reply = self._next_q(answer)

        # Peeks if self is done
        if self.done:
            # Schedules callback
            self.extract_answers()
            return self.outro

        if reply:
            return reply


class DialogManager(OrderedDict):
    """
    Holds all the 1-1 conversations between the bot and users.
    We are intentionnally not allowing a single user
    to have two validation conversations at the same time.
    """

    max_size: int

    def __init__(self, max_size=100):
        super().__init__()
        self.max_size = max_size

    def __setitem__(self, user_id: UserId, convo: Dialog):
        while len(self) > self.max_size:
            self.popitem(last=False)

        super().__setitem__(user_id, convo)
        self.move_to_end(user_id)

    def __getitem__(self, user_id: UserId) -> None | Dialog:
        return super().get(user_id)

    def add(
        self,
        user_id: UserId,
        chat_id: ChatId,
        convo: Questionnaire,
        extract_state: Callable,
    ):
        instance = Dialog(user_id, chat_id, convo, extract_state)
        self.__setitem__(user_id, instance)

    def remove(self, user_id: UserId):
        if user_id in self:
            self.__delitem__(user_id)

    def cancel(self, user_id: UserId):
        if dialog := self[user_id]:
            dialog.start_over()
