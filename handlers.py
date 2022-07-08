from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from asyncio import gather
from utils import (
    accept_or_reject_btns,
    admins_ids_mkup,
    agree_btn,
    mention_markdown,
    parseArgs,
    withAuth,
)
from toml import loads

from db import (
    add_pending,
    fetch_settings,
    get_mode,
    remove_pending,
    set_mode,
    upsert_destination,
    reset,
)

strings = ""
with open("./strings.toml", "r") as f:
    r = f.read()
    strings = loads(r)


async def answering_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reply = strings["commands"]["help"]
    await context.bot.send_message(chat_id, reply)


@withAuth
async def setting_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    received = update.message.text
    chat_id = update.message.chat_id

    reply = ""
    if destination := parseArgs(received, chat_id):
        await upsert_destination(chat_id, destination)
        reply = f"Okay, will try to route join requests made in this chat to {destination} from now on."
    else:
        reply = f"This input does not feature a correct chat_id: {received}"
    await context.bot.send_message(chat_id, reply)


async def checking_routing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reply = ""
    settings = await fetch_settings(chat_id)
    if settings:
        if "destination" in settings and int(settings["destination"]) == chat_id:
            reply = strings["checking_routing"]["destination"]
        else:
            reply = strings["checking_routing"]["not_destination"]
    else:
        reply = strings["checking_routing"]["not_routing"]
    await context.bot.send_message(chat_id, reply)


@withAuth
async def resetting_routing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    reply = strings["resetting_routing"]["disabled"]
    await reset(chat_id)
    await context.bot.send_message(chat_id, reply)


@withAuth
async def setting_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    parsed = update.message.text.split(" ")
    l = len(parsed)
    if l == 1 or not parsed[1]:
        mode = await get_mode(chat_id)
        await context.bot.send_message(
            chat_id,
            f"The current mode is set to: {mode}. Available options: _auto_ | _manual_",
            parse_mode=ParseMode.MARKDOWN,
        )
    elif l == 2:
        mode = parsed[1]
        await gather(
            set_mode(chat_id, mode),
            context.bot.send_message(chat_id, f"Mode changed to: {mode}"),
        )
    else:
        await context.bot.send_message(
            chat_id, f"Unable to parse the following input: {update.message.text}"
        )


async def wants_to_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    if not settings:
        return

    if "mode" in settings and settings["mode"] == "auto":
        await context.bot.send_message(
            user_id,
            strings["wants_to_join"]["agreement"],
            reply_markup=agree_btn(strings["my_chat"]["url"]),
        )
        return

    async def closure_send(destination: int, text: str):
        response = await context.bot.send_message(
            destination,
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=accept_or_reject_btns(user_id, user_name, chat_id),
        )
        await add_pending(chat_id, user_id, response.message_id)

    if "destination" in settings:
        body = f"{mention_markdown(user_id, user_name)} has just asked to join your chat {mention_markdown(chat_id, chat_name)}, you might want to accept them."
        await closure_send(int(settings["destination"]), alert + "\n" + body)
    else:
        body = f"{mention_markdown(user_id, user_name)} just joined, but I couldn't find any chat to notify."
        await closure_send(chat_id, alert + "\n" + body)


@withAuth
async def processing_cbq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Exiting on wrong data payload
    if not hasattr(update.callback_query, "data") or not update.callback_query.data:
        await gather(
            context.bot.answer_callback_query(update.callback_query.id),
            context.bot.send_message(
                update.callback_query.message.chat.id,
                "Wrong 'data' payload, unable to process.",
            ),
        )
        return

    # 'Parsing'
    splitted = update.callback_query.data.split(":")
    operation, chat_id_str = splitted[0], splitted[1]

    # Branch for handling confirmation in auto mode
    if operation == "self-confirm":
        await gather(
            context.bot.approve_chat_join_request(
                chat_id_str, update.callback_query.from_user.id
            ),
            context.bot.answer_callback_query(update.callback_query.id),
        )
        return

    # Manual mode continues...
    # Setting up verdict handling
    user_id_str, user_name = splitted[2], splitted[3]
    user_id = int(user_id_str)
    chat_id = int(chat_id_str)
    confirmation_chat_id = update.callback_query.message.chat.id
    admin_name = (
        update.callback_query.from_user.username
        or update.callback_query.from_user.first_name
    )

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

    # Confirmation and cleaning behind on accepted or rejected
    async def closure_together():
        message_id = await remove_pending(chat_id, user_id)
        await context.bot.delete_message(confirmation_chat_id, message_id)

    tasks = [context.bot.send_message(confirmation_chat_id, reply), closure_together()]
    await gather(*tasks)


async def has_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    new_members = [
        u.id
        for u in update.message.new_chat_members
        if update.message.new_chat_members or []
    ]
    if not new_members:
        return

    if context.bot.id in new_members:
        # The newcomer is the bot itself
        report = ""
        if settings := await fetch_settings(chat_id):
            if int(settings["destination"]) == chat_id:
                report = strings["has_joined"]["destination"] + settings["destination"]
            else:
                report = strings["has_joined"]["not_destination"]
            await context.bot.send_message(int(settings["destination"]), report)
    else:
        print(f"A user joined!")
