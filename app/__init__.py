import logging
import warnings
from os import environ
from sys import stdout

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from telegram.warnings import PTBUserWarning
from toml import loads

from app.types import DialogManager

""" Logging """
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=stdout,
)
warnings.filterwarnings("error", category=PTBUserWarning)

""" Database """
client = AsyncIOMotorClient(environ["MONGO_CONN_STRING"])
db: AsyncIOMotorDatabase = client["alert-me"]
chats: AsyncIOMotorCollection = db["chats"]
logs: AsyncIOMotorCollection = db["logs"]
clean_up_db = True if environ.get("CLEAN_UP_DB", False) == "true" else False

""" Setup strings """
strings = ""
with open("strings.toml", "r") as f:
    r = f.read()
    strings = loads(r)

""" Conversation manager handling 1-1 conversations """
dialog_manager = DialogManager()
