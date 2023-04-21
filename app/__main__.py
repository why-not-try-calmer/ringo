from os import environ
from sys import argv

from telegram import Message
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.ext.filters import MessageFilter

from app import dialog_manager
from app.handlers import (
    admin_op,
    answering_help,
    expected_dialog,
    getting_status,
    has_joined,
    processing_cbq,
    replying_to_bot,
    resetting,
    setting_bot,
    wants_to_join,
)


class Dialog(MessageFilter):
    """Custom filter"""

    def filter(self, message: Message) -> bool:
        return hasattr(message, "text") and message.from_user.id in dialog_manager


def registerHandlers(app: Application):
    expectedDialogHandler = MessageHandler(Dialog(), expected_dialog)
    joinReqHandler = ChatJoinRequestHandler(wants_to_join)
    acceptReject = CallbackQueryHandler(processing_cbq)
    answerHelp = CommandHandler(["help", "start"], answering_help)
    setBot = CommandHandler("set", setting_bot)
    reset = CommandHandler("reset", resetting)
    status = CommandHandler("status", getting_status)
    newMember = MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, has_joined)
    replyToBot = MessageHandler(filters.REPLY, replying_to_bot)
    adminOp = CommandHandler("admin", admin_op)

    app.add_handlers(
        [
            expectedDialogHandler,
            adminOp,
            acceptReject,
            setBot,
            reset,
            status,
            newMember,
            joinReqHandler,
            answerHelp,
            replyToBot,
        ]
    )
    print("Handlers successfully registered")


if __name__ == "__main__":
    """
    Run the program with `--polling` to run as a long-polling application
    """

    from os import path

    import uvloop

    TOKEN = environ["TOKEN"]
    HOST = environ["HOST"]
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
            url_path=f"/{ENDPOINT}/bot{TOKEN}",
            webhook_url=f"{HOST}/{ENDPOINT}/bot{TOKEN}",
            key=private_key_path[2:],
            cert=certificate_path[2:],
        )
    else:
        print(
            f"Starting webserver & webhook ({ENDPOINT}/bot<TOKEN>) on port {PORT} *without* an SSL certificate. HTTPS requests will need to be decoded and encoded by the server!"
        )
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=f"{ENDPOINT}/bot{TOKEN}",
            webhook_url=f"{HOST}{ENDPOINT}/bot{TOKEN}",
        )
