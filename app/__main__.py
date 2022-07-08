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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
warnings.filterwarnings("error", category=PTBUserWarning)

from app.handlers import (
    wants_to_join,
    processing_cbq,
    answering_help,
    setting_bot,
    resetting,
    has_joined,
)


def registerHandlers(app: Application):
    joinReqHandler = ChatJoinRequestHandler(wants_to_join)
    acceptReject = CallbackQueryHandler(processing_cbq)
    answerHelp = CommandHandler(["help", "start", "start"], answering_help)
    setBot = CommandHandler("set", setting_bot)
    reset = CommandHandler("reset", resetting)
    newMember = MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, has_joined)

    app.add_handlers(
        [
            joinReqHandler,
            newMember,
            acceptReject,
            answerHelp,
            setBot,
            reset,
        ]
    )
    print("Handlers successfully registered")


if __name__ == "__main__":
    TOKEN = environ["TOKEN"]
    ENDPOINT = environ["ENDPOINT"]
    PORT = int(environ.get("PORT", "8443"))

    app = Application.builder().token(TOKEN).build()
    registerHandlers(app)
    print("Setting webhook now. Ready to work.")

    app.run_webhook(
        listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{ENDPOINT}/{TOKEN}"
    )
