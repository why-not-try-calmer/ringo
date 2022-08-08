from os import environ
from typing import Optional
from telegram.ext import ContextTypes
from pymongo.collection import ReturnDocument
from pymongo.results import DeleteResult, UpdateResult, InsertOneResult
from datetime import datetime, timedelta
from asyncio import as_completed, gather, sleep

from app import chats, logs
from app.types import (
    AsDict,
    ChatId,
    Questionnaire,
    Operation,
    ServiceLog,
    MessageId,
    ServiceLog,
    Settings,
    User,
    UserId,
)
from app.utils import mark_successful_coroutines


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


async def upsert_questionnaire(
    chat_id: ChatId, conversation: Questionnaire
) -> UpdateResult:
    return await chats.find_one_and_update(
        {"chat_id": chat_id}, {"$set": {"conversation": conversation._asdict()}}
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


async def remove_pending(chat_id: ChatId, user_id: UserId) -> int:
    doc = await chats.find_one_and_update(
        {"chat_id": chat_id}, {"$unset": {f"pending_{user_id}": ""}}
    )
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
    t0 = now - timedelta(days=7)

    return await logs.delete_many(
        {"operation": {"$ne": operation}}, {"at": {"$lt": t0}}
    )


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
        await mark_as_banned(user)
        await context.bot.approve_chat_join_request(user.chat_id, user.user_id)
        banned = await context.bot.ban_chat_member(user.chat_id, user.user_id)
        return banned, user

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


busy = False


async def log(contents: AsDict) -> InsertOneResult:
    return await logs.insert_one(contents.as_dict())


async def mark_notified(user: User) -> User | None:
    if _ := await logs.update_many(
        {"user_id": user.user_id, "chat_id": user.chat_id}, {"$set": {"notified": True}}
    ):
        return user


async def background_task(context: ContextTypes.DEFAULT_TYPE | None) -> None | int:
    # Setup
    global busy

    if context:
        await sleep(60)

    if busy:
        return

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

    # Preparing query
    try:
        busy = True
        to_remove: list[User] = []
        to_notify: list[User] = []
        to_ban: list[User] = []
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

            if u["operation"] == is_banned:
                continue

            if tried_20min_ago_and_not_alerted(u):
                to_notify.append(User(u["user_id"], u["chat_id"]))

            if tried_6h_ago_and_got_alert(u):

                if u["chat_id"] in banners and not is_banned in u:
                    to_ban.append(User(u["user_id"], u["chat_id"]))
                else:
                    to_remove.append(User(u["user_id"], u["chat_id"]))

        # Only for testing purposes
        if not context:
            busy = False
            return len(to_remove) + len(to_notify)

        # Removing & notifying
        deleted: DeleteResult = await logs.delete_many(
            {
                "user_id": {"$in": [u.user_id for u in to_remove]},
                "chat_id": {"$in": [u.chat_id for u in to_remove]},
            }
        )
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
