from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatType
from asyncio import create_task, gather
from toml import loads
from os import environ

from app.types import ChatId, UserLog, Settings
from app.utils import (
    accept_or_reject_btns,
    admins_ids_mkup,
    agree_btn,
    mention_markdown,
    withAuth,
)
from app.utils import mark_excepted_coroutines
from app.db import (
    add_pending,
    background_task,
    fetch_chat_ids,
    log,
    remove_chats,
    remove_pending,
    fetch_settings,
    upsert_settings,
    reset,
)

strings = ""
with open("strings.toml", "r") as f:
    r = f.read()
    strings = loads(r)


async def answering_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reply = strings["commands"]["help"]
    await context.bot.send_message(
        chat_id, reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


@withAuth
async def setting_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    received = update.message.text
    chat_id = update.message.chat_id
    s = received.split(" ")
    reply = ""

    if len(s) == 1 or s[1] == "":
        # Get
        if fetched := await fetch_settings(chat_id):
            reply = strings["settings"]["settings"] + fetched.render(with_alert=True)
        else:
            reply = strings["settings"]["none_found"]
    elif settings := Settings(received, chat_id):
        # Set
        if updated := await upsert_settings(settings):
            reply = strings["settings"]["updated"] + updated.render(with_alert=True)
        else:
            reply = strings["settings"]["failed_to_update"]
    else:
        # No parse
        reply = strings["settings"]["failed_to_parse"]
    await context.bot.send_message(
        chat_id, reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


@withAuth
async def resetting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    reply = strings["settings"]["reset"]
    await gather(
        reset(chat_id),
        context.bot.send_message(chat_id, reply, disable_web_page_preview=True),
    )


async def wants_to_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cleaning up just in case
    create_task(background_task(context))

    request = update.chat_join_request
    user_id, user_name, chat_id, chat_name = (
        request.from_user.id,
        request.from_user.username or request.from_user.first_name,
        request.chat.id,
        request.chat.username,
    )

    admins, settings = await gather(
        context.bot.get_chat_administrators(chat_id), fetch_settings(chat_id)
    )
    alert = admins_ids_mkup(admins) if admins else ""

    # Missing settings
    if not settings:
        return await context.bot.send_message(
            chat_id, strings["settings"]["missing"], disable_web_page_preview=True
        )

    # Inactive
    if hasattr(settings, "active") and settings.active == "off":
        return

    # Auto mode
    if hasattr(settings, "mode") and settings.mode == "auto":
        await gather(
            context.bot.send_message(
                user_id,
                settings.verification_msg
                if settings.verification_msg and len(settings.verification_msg) >= 10
                else strings["wants_to_join"]["verification_msg"],
                disable_web_page_preview=True,
                reply_markup=agree_btn(
                    strings["wants_to_join"]["ok"],
                    chat_id,
                    strings["chat"]["url"]
                    if not settings.chat_url
                    else settings.chat_url,
                ),
            ),
            log(UserLog("wants_to_join", chat_id, user_id, user_name)),
        )
        return

    # Manual mode
    async def closure_send(destination: ChatId, text: str):
        response = await context.bot.send_message(
            destination,
            text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
            reply_markup=accept_or_reject_btns(
                user_id,
                user_name,
                chat_id,
                strings["chat"]["url"] if not settings.chat_url else settings.chat_url,
            ),
        )
        await add_pending(chat_id, user_id, response.message_id)

    if hasattr(settings, "helper_chat_id") and settings.helper_chat_id:
        body = f"{mention_markdown(user_id, user_name)} has just asked to join your chat {mention_markdown(chat_id, chat_name)}, you might want to accept them."
        await closure_send(settings.helper_chat_id, alert + "\n" + body)
    else:
        body = f"{mention_markdown(user_id, user_name)} just joined, but I couldn't find any chat to notify."
        await closure_send(chat_id, alert + "\n" + body)


async def replying_to_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (hasattr(update, "message") or hasattr(update.message, "reply_to_message")):
        print(f"Unable to make use of this update: {update}")
        return

    if (
        update.message.reply_to_message.from_user.id == context.bot.id
        and update.message.reply_to_message.chat.type == ChatType.PRIVATE
    ):
        user_id, user_name, text = (
            update.message.from_user.id,
            update.message.from_user.username or update.message.from_user.first_name,
            update.message.text,
        )

        await gather(
            log(UserLog("replying_to_bot", user_id, user_id, user_name, text)),
            context.bot.send_message(user_id, b"\xF0\x9F\x91\x8C".decode("utf-8")),
        )


@withAuth
async def processing_cbq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Exiting on wrong data payload
    if not hasattr(update.callback_query, "data") or not update.callback_query.data:
        await gather(
            context.bot.answer_callback_query(update.callback_query.id),
            context.bot.send_message(
                update.callback_query.message.chat.id,
                "Wrong 'data' payload, unable to process.",
                disable_web_page_preview=True,
            ),
        )
        return

    # 'Parsing'
    splitted = update.callback_query.data.split("§")
    operation, chat_id_str, chat_url = splitted[0], splitted[1], splitted[2]

    # Auto mode
    if operation == "self-confirm":
        await gather(
            context.bot.send_message(
                update.callback_query.from_user.id,
                f"Thanks, you are welcome to join {chat_url}. {strings['has_joined']['post_join']}",
                disable_web_page_preview=True,
            ),
            context.bot.answer_callback_query(update.callback_query.id),
        )
        await gather(
            context.bot.approve_chat_join_request(
                chat_id_str, update.callback_query.from_user.id
            ),
            log(
                UserLog(
                    "has_verified",
                    update.callback_query.from_user.id,
                    update.callback_query.from_user.id,
                    update.callback_query.from_user.username
                    or update.callback_query.from_user.first_name,
                )
            ),
        )
        return

    # Manual mode
    # Setting up verdict handling
    user_id_str, user_name = splitted[3], splitted[4]
    user_id = int(user_id_str)
    chat_id = int(chat_id_str)
    confirmation_chat_id = update.callback_query.message.chat.id
    admin_name = (
        update.callback_query.from_user.username
        or update.callback_query.from_user.first_name
    )

    # Manual mode
    # Handling verdict
    reply = ""
    if operation == "accept":
        response = await context.bot.approve_chat_join_request(chat_id, user_id)
        if response:
            reply = f"{user_name} accepted to {chat_id_str} by {admin_name}"
        else:
            reply = "User already approved"
    elif operation == "reject":
        response = await context.bot.decline_chat_join_request(chat_id, user_id)
        if response:
            reply = f"{user_name} denied access to {chat_id_str} by {admin_name}"
        else:
            reply = "User already denied."
    else:
        return

    # Manual mode
    # Confirmation and cleaning behind on accepted or rejected
    async def closure_together():
        message_id = await remove_pending(chat_id, user_id)
        await context.bot.delete_message(confirmation_chat_id, message_id)

    await gather(
        context.bot.send_message(
            confirmation_chat_id, reply, disable_web_page_preview=True
        ),
        closure_together(),
    )


async def has_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    new_members = [
        (u.id, u.username or u.first_name, u.language_code)
        for u in update.message.new_chat_members
        if update.message.new_chat_members or []
    ]
    if not new_members:
        return

    if context.bot.id in [uid for uid, _, _ in new_members]:
        # The newcomer is the bot itself
        report = ""
        if settings := await fetch_settings(chat_id):
            if getattr(settings, "helper_chat_id"):
                report = (
                    f"{strings['has_joined']['destination']} {settings.helper_chat_id}"
                )
            else:
                report = strings["has_joined"]["not_destination"]
            if settings.helper_chat_id:
                await context.bot.send_message(
                    settings.helper_chat_id, report, disable_web_page_preview=True
                )
    else:
        # Genuinely new users
        greet = (
            lambda lang: "welcome"
            if not lang in strings["welcome"]
            else strings["welcome"][lang]
        )
        greetings = (
            ", ".join(
                [
                    f"{greet(lang)} {mention_markdown(uid, name)}"
                    for uid, name, lang in new_members
                ]
            )
            + "!"
        )
        await context.bot.send_message(
            chat_id,
            greetings.capitalize(),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )


async def admin_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, admin_id = update.message.chat.id, update.message.from_user.id

    if environ["ADMIN"] != str(admin_id):
        return await context.bot.send_message(chat_id, strings["admin"]["error"])

    # Get all chats_ids
    _, msg = update.message.text.split(" ", maxsplit=1)
    chat_ids = await fetch_chat_ids()

    # Broadcast, removing chats_ids that didn't accept the message
    failures = await gather(
        *[
            mark_excepted_coroutines(cid, context.bot.send_message(cid, msg))
            for cid in chat_ids
        ]
    )
    await remove_chats([f for f in failures if f is not None])
