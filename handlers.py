from telegram import Update
from telegram.ext import ContextTypes
from asyncio import gather

from db import add_pending, fetch_destination, remove_pending, upsert_destination, reset
from requests import admins_ids_mkup, get_chat_admins_ids, remove_messages_by_id


def parseArgs(received: str, chat_id: int) -> int | None:
    parsed = received.split(" ")
    l = len(parsed)
    if l == 1 or not parsed[1]:
        return chat_id
    elif l == 2:
        try:
            return int(parsed[1])
        except ValueError:
            return None
    else:
        return None


async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        if destination := await fetch_destination(chat_id):
            if destination == chat_id:
                report = f"Thanks for adding me to this monitoring chat. If that's not done already, add me to the chat whose join requests you want me to monitor. They will be notified here ({destination})"
            else:
                report = f"Thanks for adding me to this group chat. If that's not done already, add me to the monitoring chat. Join requests made here will be notified to the monitoring chat."
            await context.bot.send_message(chat_id, report)
        else:
            print(f"Unhandled: {update.message}")
    else:
        # Possibly a user who's made a join requests before
        # so let's clean it up
        if messages_ids := await remove_pending(chat_id, new_members):
            await remove_messages_by_id(chat_id, messages_ids)


async def answer_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reply = "This simple bot lets you define 'routes' of the shape 'origin:destination' such that the bot will post join requests from users from 'origin' to 'destination'.\n\nThe bot must be a member of BOTH. Also be aware that this is a 1-1 relation -- the bot routes each origin to EXACTLY ONE destination."
    await context.bot.send_message(chat_id, reply)


async def set_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    received = update.message.text
    chat_id = update.message.chat_id
    reply = ""
    destination = parseArgs(received, chat_id)

    if destination:
        await upsert_destination(chat_id, destination)
        reply = f"Okay, will try to route join requests made in this chat to {destination} from now on."
    else:
        reply = f"This input does not feature a correct chat_id: {received}"
    await context.bot.send_message(chat_id, reply)


async def check_routing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reply = ""
    if destination := await fetch_destination(chat_id):
        if destination == chat_id:
            reply = f"I am already routing requests from a chat to this monitoring chat. Use /route with an optional <chat_id> argument from the chat receiving join requests to change the destination."
        else:
            reply = f"I am already routing join requests to a monitoring chat. Use /route with an optional <chat_id> argument from here to change the destination."
    else:
        reply = "I am not routing any join requests. Use /route with an optional <chat_id> argument in a chat receiving join requests to add a monitoring chat. Without argument, the monitoring chat = the chat where /route is issued."
    await context.bot.send_message(chat_id, reply)


async def reset_routing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reply = "All routing from this chat have been disabled. Use /route with an optional <chat_id> argument to start over."
    await reset(chat_id)
    await context.bot.send_message(chat_id, reply)


async def join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user_id, user_name, chat_id, chat_name = (
        request.from_user.id,
        request.from_user.username,
        request.chat.id,
        request.chat.username,
    )
    report = ""
    print(f"Received join request from {user_name} in chat {chat_id}.")

    admins, destination = await gather(
        get_chat_admins_ids(chat_id), fetch_destination(chat_id)
    )

    if admins:
        report += admins_ids_mkup(admins) + "\n"
    if destination:
        report += f"User @{user_name} has just asked to join your chat @{chat_name}, you might want to accept them."
        response = await context.bot.send_message(
            destination, report, parse_mode="Markdown"
        )
        await add_pending(chat_id, user_id, response.message_id)
    else:
        report += f"A new user with name @{user_name} just joined, but I couldn't find any chat to notify."
        response = await context.bot.send_message(
            chat_id, report, parse_mode="Markdown"
        )
        await add_pending(chat_id, user_id, response.message_id)
