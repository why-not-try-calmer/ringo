from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from telegram.ext import ContextTypes
from pymongo.collection import ReturnDocument
from pymongo.results import DeleteResult, UpdateResult, InsertOneResult
from os import environ
from datetime import datetime, timedelta
from asyncio import gather, sleep

from app.types import (
    AsDict,
    ChatId,
    ServiceLog,
    MessageId,
    ServiceLog,
    Settings,
    UserId,
)
from app.utils import mark_successful_coroutines

client = AsyncIOMotorClient(environ["MONGO_CONN_STRING"])
db: AsyncIOMotorDatabase = client["alert-me"]
chats: AsyncIOMotorCollection = db["chats"]
logs: AsyncIOMotorCollection = db["logs"]

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
        {"chat_id": chat_id},
        {"$set": {user_key: payload}},
        upsert=True,
    )


async def remove_pending(chat_id: ChatId, user_id: UserId) -> int:
    doc = await chats.find_one_and_update(
        {"chat_id": chat_id}, {"$unset": {f"pending_{user_id}": ""}}, upsert=True
    )
    return doc[f"pending_{user_id}"]["message_id"]


""" Logs """

busy = False


async def log(contents: AsDict) -> InsertOneResult:
    return await logs.insert_one(contents.as_dict())


async def mark_notified(user_id: UserId) -> bool | None:
    res = await logs.find_one_and_update(
        {"user_id": user_id}, {"$set": {"notified": True}}
    )
    if res.modified_count > 0:
        return True


async def background_task(context: ContextTypes.DEFAULT_TYPE | None) -> None | str:

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

    # Action
    try:
        busy = True
        cursor = logs.find(
            {
                "at": {"$exists": True},
                "user_id": {"$exists": True},
                "operation": {"$exists": True},
            }
        )

        user_docs_to_remove = []
        to_notify = []

        async for u in cursor:

            if tried_6h_ago_and_got_alert(u):
                user_docs_to_remove.append(u)

            if tried_20min_ago_and_not_alerted(u):
                to_notify.append(u)

        if not context:
            busy = False
            res = f"Users to remove: {len(user_docs_to_remove)}, to notify: {len(to_notify)}"
            return res

        # Notifying & removing
        deleted: DeleteResult = await logs.delete_many(
            {"user_id": {"$in": list(user_docs_to_remove)}}
        )
        successful_ids = await gather(
            *[
                mark_successful_coroutines(
                    uid,
                    context.bot.send_message(
                        uid,
                        "Hey, some 20 minutes ago I tried handle your request to join our group, perhaps you've missed it? How about scrolling up a bit? :)",
                    ),
                )
                for uid in to_notify
            ]
        )
        confirmed = await gather(*[mark_notified(uid) for uid in successful_ids])

        # Logging
        elapsed_time = datetime.now() - now
        await log(
            ServiceLog(
                "background_task",
                f"Job completed within {elapsed_time}, with {len(successful_ids)} notified users found late on joining, {len(confirmed)} logs edited and {deleted.deleted_count} deleted.",
            )
        )
    except Exception as error:
        print(error)
    finally:
        busy = False
