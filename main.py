import logging
import warnings
from os import environ
from telegram.ext import (
    Application,
    ChatJoinRequestHandler,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.warnings import PTBUserWarning

from handlers import *

TOKEN = environ["TOKEN"]
ENDPOINT = environ["ENDPOINT"]
PORT = int(environ.get("PORT", "8443"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
warnings.filterwarnings("error", category=PTBUserWarning)


def registerHandlers(app: Application):
    """Helper for registering handlers."""
    joinReqHandler = ChatJoinRequestHandler(join_handler)
    answerHelp = CommandHandler(["help", "start", "start"], answer_help)
    acceptReject = CallbackQueryHandler(process_cbq)
    setRoute = CommandHandler("route", set_route)
    checkRouting = CommandHandler("check", check_routing)
    resetRouting = CommandHandler("reset", reset_routing)
    newMember = MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member)

    app.add_handlers(
        [
            joinReqHandler,
            newMember,
            acceptReject,
            answerHelp,
            setRoute,
            checkRouting,
            resetRouting,
        ]
    )
    print("Handlers successfully registered")


if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    registerHandlers(app)
    print("Setting webhook now. Ready to work.")

    # blocking here
    app.run_webhook(
        listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{ENDPOINT}/{TOKEN}"
    )
