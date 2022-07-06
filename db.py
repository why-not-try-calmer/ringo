from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from os import environ

client = AsyncIOMotorClient(environ["MONGO_CONN_STRING"])
db: AsyncIOMotorDatabase = client["alert-me"]
collection: AsyncIOMotorCollection = db["routes"]


async def fetch_destination(chat_id: int) -> int | None:
    doc = await collection.find_one({"chat_id": chat_id})
    if not doc or not "destination" in doc:
        return None
    else:
        return int(doc["destination"])


async def reset(chat_id: int):
    await collection.delete_one({"chat_id": chat_id})


async def upsert_destination(chat_id: int, destination: int):
    await collection.find_one_and_update(
        {"chat_id": chat_id}, {"$set": {"destination": destination}}, upsert=True
    )


async def add_pending(chat_id: int, user_id: int, message_id: int):
    await collection.find_one_and_update(
        {"chat_id": chat_id},
        {"$set": {f"pending_{user_id}": message_id}},
        upsert=True,
    )


async def remove_pending(chat_id: int, users_ids: list[int]) -> list[int] | None:
    async def remove() -> list[int] | None:
        if doc := await collection.find_one({"chat_id": chat_id}):
            messages_ids = [
                int(v)
                for k, v in doc.items()
                if k in [f"pending_{uid}" for uid in users_ids]
            ]
            await collection.find_one_and_update(
                {"chat_id": chat_id},
                {"$unset": [f"pending_{uid}" for uid in users_ids]},
                upsert=True,
            )
            return messages_ids

    async with await client.start_session() as session:
        async with session.start_transaction():
            return await remove()
