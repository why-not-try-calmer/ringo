from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown, mention_markdown
from asyncio import gather

from db import add_pending, fetch_destination, remove_pending, upsert_destination, reset


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


def admins_ids_mkup(admins: list[ChatMember]) -> str:
    return ", ".join(
        [
            mention_markdown(
                admin.user.id, admin.user.username or admin.user.first_name
            )
            for admin in admins
        ]
    )


def accept_or_reject_btns(
    user_id: int, user_name: str, chat_id: int
) -> InlineKeyboardMarkup:
    accept = InlineKeyboardButton(
        text="Accept", callback_data=f"accept:{user_id}:{user_name}:{chat_id}"
    )
    reject = InlineKeyboardButton(
        text="Reject", callback_data=f"reject:{user_id}:{user_name}:{chat_id}"
    )
    keyboard = InlineKeyboardMarkup([[accept, reject]])
    return keyboard


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
        request.from_user.username or request.from_user.first_name,
        request.chat.id,
        request.chat.username,
    )
    alert = ""
    admins, destination = await gather(
        context.bot.get_chat_administrators(chat_id), fetch_destination(chat_id)
    )

    if admins:
        alert += admins_ids_mkup(admins) + "\n"

    async def closure_send(destination: int, body: str):
        text = alert + body
        response = await context.bot.send_message(
            destination,
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=accept_or_reject_btns(user_id, user_name, chat_id),
        )
        await add_pending(chat_id, user_id, response.message_id)

    if destination:
        body = f"{mention_markdown(user_id, user_name)} has just asked to join your chat {mention_markdown(chat_id, chat_name)}, you might want to accept them."
        await closure_send(destination, body)
    else:
        body = f"{mention_markdown(user_id, user_name)} just joined, but I couldn't find any chat to notify."
        await closure_send(chat_id, body)


async def process_cbq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    (verdict, user_id_str, user_name, chat_id_str) = update.callback_query.data.split(
        ":"
    )
    confirmation_chat_id, admin_name = (
        update.callback_query.message.chat.id,
        update.callback_query.message.from_user.username
        or update.callback_query.message.from_user.first_name,
    )
    if verdict == "accept":
        await gather(
            context.bot.approve_chat_join_request(chat_id_str, int(user_id_str)),
            context.bot.send_message(
                confirmation_chat_id,
                f"User {escape_markdown(user_name)} accepted to {chat_id_str} by {escape_markdown(admin_name)}",
            ),
        )
    else:
        await gather(
            context.bot.decline_chat_join_request(chat_id_str, int(user_id_str)),
            context.bot.send_message(
                confirmation_chat_id,
                f"User {escape_markdown(user_name)} denied access to {chat_id_str}",
            ),
        )


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
            await gather(
                *[context.bot.delete_message(chat_id, mid) for mid in messages_ids]
            )
