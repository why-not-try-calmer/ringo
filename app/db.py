from os import environ
from typing import Optional
from telegram.ext import ContextTypes
from pymongo.collection import ReturnDocument
from pymongo.results import DeleteResult, UpdateResult, InsertOneResult
from datetime import datetime, timedelta
from asyncio import as_completed, gather, sleep

from app import chats, logs
from app.types import (
    ChatId,
    Log,
    Questionnaire,
    Operation,
    ServiceLog,
    MessageId,
    ServiceLog,
    Settings,
    Status,
    User,
    UserId,
    UserLog,
    UserWithName,
)
from app.utils import mark_successful_coroutines, run_coroutines_masked


""" Settings """


async def fetch_settings(chat_id: ChatId) -> Settings | None:
    if doc := await chats.find_one({"chat_id": chat_id}):
        return Settings(doc)


async def reset(chat_id: ChatId) -> DeleteResult:
    return await chats.delete_one({"chat_id": chat_id})


async def upsert_settings(settings: Settings) -> Settings | None:
    if updated := await chats.find_one_and_update(
        {"chat_id": settings.chat_id},
        {"$set": settings.as_dict()},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    ):
        return Settings(updated)


async def upsert_questionnaire(chat_id: ChatId, q: Questionnaire) -> UpdateResult:
    return await chats.find_one_and_update(
        {"chat_id": chat_id}, {"$set": {"questionnaire": q._asdict()}}, upsert=True
    )


""" Chats """


async def fetch_chat_ids() -> list[ChatId]:
    cursor = chats.find()
    users_id = []
    async for doc in cursor:
        if "chat_id" in doc and ("changelog" not in doc or doc["changelog"] != "off"):
            users_id.append(doc["chat_id"])
    return users_id


async def remove_chats(chats_ids: list[ChatId]) -> DeleteResult:
    return await chats.delete_many({"chat_id": {"$in": chats_ids}})


async def add_pending(
    chat_id: ChatId, user_id: UserId, message_id: MessageId
) -> UpdateResult:

    user_key = f"pending_{user_id}"
    payload = {"message_id": message_id, "at": datetime.now()}
    return await chats.find_one_and_update(
        {"chat_id": chat_id}, {"$set": {user_key: payload}}
    )


async def remove_pending(chat_id: ChatId, user_id: UserId) -> None | int:
    doc = await chats.find_one_and_update(
        {"chat_id": chat_id}, {"$unset": {f"pending_{user_id}": ""}}
    )
    if f"pending_{user_id}" in doc:
        return doc[f"pending_{user_id}"]["message_id"]


async def get_banners() -> list[ChatId]:
    banners = []
    cursor = chats.find(
        {"chat_id": {"$exists": True}, "ban_not_joining": {"$exists": True}}
    )
    async for doc in cursor:
        if doc["ban_not_joining"] is True:
            banners.append(doc["chat_id"])
    return banners


async def get_status(chat_id: ChatId) -> None | Status:
    def extract(d: dict) -> UserWithName:
        user_id = d["user_id"]
        user_name = d["username"]
        at = d["at"]
        return UserWithName(user_id=user_id, user_name=user_name, at=at)

    cursor = logs.find(
        {
            "at": {"$exists": True},
            "user_id": {"$exists": True},
            "username": {"$exists": True},
            "chat_id": {"$exists": True},
            "operation": {"$exists": True},
        }
    )

    notified: list[UserWithName] = []
    pending: list[UserWithName] = []
    prebanned: list[UserWithName] = []
    is_banned: Operation = "is_banned"
    wants_to_join: Operation = "wants_to_join"

    async for doc in cursor:
        user = extract(doc)

        if doc["operation"] == is_banned:
            prebanned.append(user)

        elif "notified" in doc:
            notified.append(user)

        elif doc["operation"] == wants_to_join:
            pending.append(user)

    operation: Operation = "background_task"
    cursor = logs.find({"operation": operation})

    ats = sorted([doc["at"] async for doc in cursor if "at" in doc])
    work_summary = f"Chat has operated since {ats[0]} and has run {len(ats)} background tasks since, with the latest at: {ats[-1]}"

    if notified + pending + prebanned + ats:
        return Status(
            chat_id,
            pending,
            notified,
            prebanned,
            work_summary,
        )


""" Logs """


async def check_if_banned(chat_id: ChatId, user_ids: list[UserId]) -> list[UserId]:
    cursor = logs.find(
        {"user_id": {"$in": user_ids}, "chat_id": chat_id, "operation": "is_banned"}
    )
    user_ids = []
    async for doc in cursor:
        user_ids.append(doc["user_id"])
    return user_ids


async def remove_old_logs(now: Optional[datetime] = None) -> DeleteResult:
    if not now:
        now = datetime.now()

    operation: Operation = "background_task"
    t0 = now - timedelta(days=30)
    return await logs.delete_many({"operation": {"$ne": operation}, "at": {"$lt": t0}})


async def mark_as_banned(user: User) -> UpdateResult:
    op: Operation = "is_banned"
    return await logs.find_one_and_update(
        {"user_id": user.user_id, "chat_id": user.chat_id}, {"$set": {"operation": op}}
    )


async def preban(
    context: ContextTypes.DEFAULT_TYPE | None, users: list[User]
) -> tuple[list[User], list[User]] | None:
    if not context:
        return

    async def accept_then_ban(user: User) -> tuple[bool, User]:
        try:
            await context.bot.approve_chat_join_request(user.chat_id, user.user_id)
            await context.bot.ban_chat_member(user.chat_id, user.user_id)
            await mark_as_banned(user)
            return banned, user
        except Exception:
            return False, user

    failed_to_ban_but_invited = []
    successfully_banned = []

    for task in as_completed([accept_then_ban(u) for u in users]):
        banned, user = await task
        if banned:
            successfully_banned.append(user)
        else:
            failed_to_ban_but_invited.append(user)

    return failed_to_ban_but_invited, successfully_banned


async def get_users_at(chat_id: ChatId, user_ids: list[UserId]) -> list[datetime]:
    cursor = logs.find(
        {
            "chat_id": chat_id,
            "user_id": {"$in": user_ids},
            "at": {"$exists": True},
            "has_joined": {"$exists": False},
            "joined_at": {"$exists": False},
        }
    )
    datetimes = []
    async for user_doc in cursor:
        datetimes.append(user_doc["at"])
    return datetimes


async def log(to_log: Log) -> InsertOneResult | UpdateResult:
    match to_log:
        case ServiceLog():
            return await logs.insert_one(to_log.as_dict())
        case UserLog():
            return await logs.find_one_and_update(
                {"user_id": to_log.user_id, "chat_id": to_log.chat_id},
                {"$set": to_log.as_dict()},
                upsert=True,
            )


async def mark_notified(user: User) -> User | None:
    if _ := await logs.find_one_and_update(
        {"user_id": user.user_id, "chat_id": user.chat_id}, {"$set": {"notified": True}}
    ):
        return user


busy = False


async def background_task(context: ContextTypes.DEFAULT_TYPE | None) -> None | int:
    """
    Run a background task at most every minute on the chat_id corresponding to the calling handler.
    The logic is:
    - if a user has not joined within the next 20 minutes after landing a join request, they get notified
    - if a user has been notified and does not join within the next 5h40, they get banned if the chat declares a ban_not_joining setting or
        if it doesn't, they get declined and removed from the database.
    - all database logs older than 30 days get removed unless they bear the 'background_task' label.
    """

    # Setup
    global busy

    if context:
        await sleep(60)
    if busy:
        return busy

    now = datetime.now()
    h6 = timedelta(hours=6)
    min20 = timedelta(minutes=20)

    due = lambda item, delt: now - item["at"] >= delt
    tried_6h_ago_and_got_alert = (
        lambda item: due(item, h6)
        and item["operation"] == "wants_to_join"
        and "notified" in item
    )
    tried_20min_ago_and_not_alerted = (
        lambda item: due(item, min20)
        and item["operation"] == "wants_to_join"
        and not "notified" in item
    )
    hh = lambda uid, cid: str(uid) + "_" + str(cid)

    # Preparing query
    try:
        busy = True
        to_deny_and_remove: list[User] = []
        to_notify: list[User] = []
        to_ban: list[User] = []
        banned: set[str] = set()
        banners = await get_banners()
        is_banned: Operation = "is_banned"
        cursor = logs.find(
            {
                "at": {"$exists": True},
                "user_id": {"$exists": True},
                "chat_id": {"$exists": True},
                "operation": {"$exists": True},
            }
        )

        # Collecting results

        async for u in cursor:

            uid = u["user_id"]
            cid = u["chat_id"]

            if u["operation"] == is_banned:
                banned.add(hh(uid, cid))

            if tried_20min_ago_and_not_alerted(u):
                to_notify.append(User(u["user_id"], u["chat_id"]))

            if tried_6h_ago_and_got_alert(u):

                if u["chat_id"] in banners:
                    if not hh(uid, cid) in banned:
                        to_ban.append(User(u["user_id"], u["chat_id"]))
                else:
                    to_deny_and_remove.append(User(u["user_id"], u["chat_id"]))

        # Only for testing purposes
        if not context:
            busy = False
            return len(to_deny_and_remove) + len(to_notify)

        # Removing, declining and  notifying
        deleted: DeleteResult = await logs.delete_many(
            {
                "user_id": {"$in": [u.user_id for u in to_deny_and_remove]},
                "chat_id": {"$in": [u.chat_id for u in to_deny_and_remove]},
            }
        )
        # Declining pending join requests with exceptions masked
        # as there is no way to determine with certainty if the target join request was taken back or not
        await run_coroutines_masked(
            [
                context.bot.decline_chat_join_request(user.chat_id, user.user_id)
                for user in to_deny_and_remove
            ]
        )

        # Notifying & marking success
        successfully_notified = await gather(
            *[
                mark_successful_coroutines(
                    user,
                    context.bot.send_message(
                        user.user_id,
                        "Hey, some 20 minutes ago I tried handle your request to join our group, perhaps you've missed it? How about scrolling up a bit? :)",
                    ),
                )
                for user in to_notify
            ]
        )
        confirmed_notified = await gather(
            *[mark_notified(user) for user in successfully_notified]
        )

        # Banning & notifying
        banning_report_failed = ""
        banning_report_success = ""

        if to_ban:
            await context.bot.send_message(
                environ["ADMIN"], f"Banning these users: {str(to_ban)}"
            )

        if mb_banned := await preban(context, to_ban):
            failed_to_ban, confirmed_banned = mb_banned
            banning_report_failed += "\n".join(
                [
                    f" Failed to banned: {u.user_id} from {u.chat_id}."
                    for u in failed_to_ban
                ]
            )
            banning_report_success += "\n".join(
                [
                    f" Successfully banned: {u.user_id} from {u.chat_id}."
                    for u in confirmed_banned
                ]
            )

        # Logging
        elapsed_time = datetime.now() - now
        await log(
            ServiceLog(
                "background_task",
                f"Job completed within {elapsed_time}, with {len(successfully_notified)} notified users found late on joining, {len(confirmed_notified)} logs edited and {deleted.deleted_count} deleted."
                + banning_report_failed
                + banning_report_success,
            )
        )

        # Removing old entries
        await remove_old_logs()

    except Exception as error:
        if context:
            await context.bot.send_message(environ["ADMIN"], str(error))
        else:
            print(error)
    finally:
        busy = False
