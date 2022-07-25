from os import environ
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from toml import loads

client = AsyncIOMotorClient(environ["MONGO_CONN_STRING"])
db: AsyncIOMotorDatabase = client["alert-me"]
chats: AsyncIOMotorCollection = db["chats"]
logs: AsyncIOMotorCollection = db["logs"]

strings = ""
with open("strings.toml", "r") as f:
    r = f.read()
    strings = loads(r)
