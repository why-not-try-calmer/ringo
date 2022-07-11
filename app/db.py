from dataclasses import asdict
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pymongo.collection import ReturnDocument
from os import environ
from datetime import datetime

from app.types import ChatId, Log, MessageId, Settings, UserId

client = AsyncIOMotorClient(environ["MONGO_CONN_STRING"])
db: AsyncIOMotorDatabase = client["alert-me"]
chats: AsyncIOMotorCollection = db["chats"]
logs: AsyncIOMotorCollection = db["logs"]


async def fetch_settings(chat_id: ChatId) -> Settings | None:
    if doc := await chats.find_one({"chat_id": chat_id}):
        print("Found settings: ", Settings(doc).as_dict_no_none())
        return Settings(doc)


async def reset(chat_id: ChatId):
    await chats.delete_one({"chat_id": chat_id})


async def upsert_settings(settings: Settings) -> Settings | None:
    print("Trying to update: ", settings.as_dict_no_none())
    if updated := await chats.find_one_and_update(
        {"chat_id": settings.chat_id},
        {"$set": settings.as_dict_no_none()},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    ):
        return Settings(updated)


async def add_pending(chat_id: ChatId, user_id: UserId, message_id: MessageId):
    user_key = f"pending_{user_id}"
    payload = {"message_id": message_id, "at": datetime.now()}
    await chats.find_one_and_update(
        {"chat_id": chat_id},
        {"$set": {user_key: payload}},
        upsert=True,
    )


async def remove_pending(chat_id: ChatId, user_id: UserId) -> int:
    doc = await chats.find_one_and_update(
        {"chat_id": chat_id}, {"$unset": {f"pending_{user_id}": ""}}, upsert=True
    )
    return doc[f"pending_{user_id}"]["message_id"]


async def log(contents: Log):
    await logs.insert(asdict(contents))
