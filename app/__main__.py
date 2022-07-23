import logging
import warnings
from sys import argv, stdout
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=stdout,
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
    """
    NB: Call with --polling to run as a long-polling application
    """

    from os import path
    import uvloop

    TOKEN = environ["TOKEN"]
    ENDPOINT = environ["ENDPOINT"]
    PORT = int(environ.get("PORT", "8443"))
    private_key_path = "./private.key"
    certificate_path = "./cert.pem"

    uvloop.install()
    app = Application.builder().token(TOKEN).build()
    registerHandlers(app)

    if "polling" in argv[1] if len(argv) >= 2 else False:
        print("Running in long-poll mode. Good luck.")
        app.run_polling(drop_pending_updates=True)

    elif path.exists(certificate_path) and path.exists(private_key_path):
        print(
            f"Starting webserver & webhook on port {PORT} with a self-signed certificate. Requests to the bot *will be* decoded by the application."
        )
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=f"bot{TOKEN}",
            webhook_url=f"{ENDPOINT}/bot{TOKEN}",
            key=private_key_path[2:],
            cert=certificate_path[2:],
        )
    else:
        print(
            "Starting webserver & webhook on port {PORT} *without* an SSL certificate. HTTPS requests will need to be decoded and encoded by the server!"
        )
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=f"bot{TOKEN}",
            webhook_url=f"{ENDPOINT}/bot{TOKEN}",
        )
