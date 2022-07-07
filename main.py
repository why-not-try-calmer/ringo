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
    joinReqHandler = ChatJoinRequestHandler(wants_to_join)
    acceptReject = CallbackQueryHandler(processing_cbq)
    answerHelp = CommandHandler(["help", "start", "start"], answering_help)
    setRoute = CommandHandler("route", setting_route)
    checkRouting = CommandHandler("check", checking_routing)
    resetRouting = CommandHandler("reset", resetting_routing)
    setApprovalMode = CommandHandler("mode", setting_mode)
    newMember = MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, has_joined)

    app.add_handlers(
        [
            joinReqHandler,
            newMember,
            acceptReject,
            answerHelp,
            setRoute,
            checkRouting,
            resetRouting,
            setApprovalMode,
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
