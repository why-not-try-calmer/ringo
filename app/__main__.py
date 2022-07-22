import logging
import warnings
import sys
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO,
    stream=sys.stdout
)
warnings.filterwarnings("error", category=PTBUserWarning)

from app.handlers import (
    admin_op,
    replying_to_bot,
    wants_to_join,
    processing_cbq,
    answering_help,
    setting_bot,
    resetting,
    has_joined,
    strings,
)


def registerHandlers(app: Application):
    joinReqHandler = ChatJoinRequestHandler(wants_to_join)
    acceptReject = CallbackQueryHandler(processing_cbq)
    answerHelp = CommandHandler(["help", "start"], answering_help)
    setBot = CommandHandler("set", setting_bot)
    reset = CommandHandler("reset", resetting)
    newMember = MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, has_joined)
    replyToBot = MessageHandler(filters.REPLY, replying_to_bot)
    adminOp = CommandHandler("admin", admin_op)

    app.add_handlers(
        [
            joinReqHandler,
            newMember,
            acceptReject,
            answerHelp,
            setBot,
            reset,
            replyToBot,
            adminOp,
        ]
    )
    print("Handlers successfully registered")


if __name__ == "__main__":
    TOKEN = environ["TOKEN"]
    ENDPOINT = environ["ENDPOINT"]
    PORT = int(environ.get("PORT", "8443"))
    DEPLOYMENT = strings["config"]["deployment"]

    from asyncio import set_event_loop_policy
    from uvloop import EventLoopPolicy

    set_event_loop_policy(EventLoopPolicy())

    app = Application.builder().token(TOKEN).build()
    registerHandlers(app)

    print(f"Setting webhook now. Listening to {PORT} and ready to work.")
    from os import path

    if DEPLOYMENT == "polling":
        print("Running in long-poll mode. Good luck.")
        app.run_polling(drop_pending_updates=True)

    elif path.exists("./cert.pem") and path.exists("./private.key"):
        print(
            "Starting webhook with a self-signed certificate. Requests to the bot will be decoded by the application."
        )
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{ENDPOINT}/{TOKEN}",
            key="private.key",
            cert="cert.pem",
        )
    else:
        print(
            "Starting webhook without an SSL certificate; your HTTPS requests will need to be decoded and encoded by the server!"
        )
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{ENDPOINT}/{TOKEN}",
        )
