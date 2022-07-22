from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pymongo.collection import ReturnDocument
from pymongo.results import DeleteResult, UpdateResult, InsertOneResult
from os import environ
from datetime import datetime, timedelta
from asyncio import sleep

from app.types import (
    AsDict,
    ChatId,
    ServiceLog,
    MessageId,
    ServiceLog,
    Settings,
    UserId,
)

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
    for doc in await cursor.to_list(length=None):
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


async def deprecate_not_verified() -> DeleteResult | None:
    global busy
    await sleep(60)

    if busy:
        return

    now = datetime.now()
    h6 = timedelta(hours=6)
    d6 = timedelta(days=6)

    # Removing old 'wants_to_join' OPs
    busy = True
    wanted_to_join = (
        lambda item: (now - item["at"] >= h6) and item["operation"] == "wants_to_join"
    )
    was_deleted = (
        lambda item: (now - item["at"] >= d6) and item["operation"] == "deletion"
    )
    docs = logs.find(
        {
            "at": {"$exists": True},
            "user_id": {"$exists": True},
            "operation": {"$exists": True},
        }
    )

    to_log_removal: set[UserId] = set()
    to_remove: set[UserId] = set()

    for u in await docs.to_list(length=None):
        uid = u["user_id"]
        if wanted_to_join(u):
            to_log_removal.add(uid)
            to_remove.add(uid)
        if was_deleted(u):
            to_remove.add(uid)

    res: DeleteResult = await logs.delete_many(
        {"user_id": {"$in": list(to_log_removal.union(to_remove))}}
    )
    if res.deleted_count > 0:
        await log(
            ServiceLog(
                "deletion",
                f"Deleted {res.deleted_count} out of {len(to_log_removal)} user logs pending for deletion.",
            )
        )
    busy = False
