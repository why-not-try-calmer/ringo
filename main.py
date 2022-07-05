import os
from telegram.ext import Application, ChatJoinRequestHandler, MessageHandler, CommandHandler, ContextTypes, filters
from telegram import Update
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

TOKEN = os.environ['TOKEN']
ENDPOINT = os.environ['ENDPOINT']
PORT = int(os.environ.get('PORT', '8443'))

client = AsyncIOMotorClient(
    os.environ['MONGO_CONN_STRING'])
db: AsyncIOMotorDatabase = client['alert-me']
collection: AsyncIOMotorCollection = db['routes']


async def fetch_destination(chat_id: int) -> int | None:
    doc = await collection.find_one({'chat_id': chat_id})
    if not doc or not 'destination' in doc:
        return None
    else:
        return int(doc['destination'])


async def upsert_destination(chat_id: int, destination: int):
    # FIX ME: Need proper error handling here
    await collection.find_one_and_update({'chat_id': chat_id}, {'$set': {'destination': destination}}, upsert=True)


async def notify_rejoin_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user, linkable_name = request.from_user, request.chat.username
    chat_id = update.message.chat.id
    report = ''

    if destination := await fetch_destination(chat_id):
        report = f"User {user} has just asked to join your chat @{linkable_name}, you might want to accept them."
        await context.bot.send_message(destination, report)
    else:
        report = f"A new user with name {user.full_name} just joined, but I couldn't find any chat to notify."
        await context.bot.send_message(chat_id, report)


async def check_routing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reply = ''
    if destination := await fetch_destination(chat_id):
        if destination == chat_id:
            reply = f"I am already routing requests from a chat to this monitoring chat. Use '/route' in the chat receiving join requests to change the destination."
        else:
            reply = f"I am already routing join requests to a monitoring. Use '/route' here to change the destination."
    else:
        reply = "I am not routing any join requests. Use '/route' in a chat receiving join requests to add a monitoring chat."
    await context.bot.send_message(chat_id, reply)


async def confirm_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_members = [
        u.id for u in update.message.new_chat_members if update.message.new_chat_members or []]
    if not new_members or not context.bot.id in new_members:
        return

    chat_id = update.message.chat_id
    report = ''
    if destination := await fetch_destination(chat_id):
        if destination == chat_id:
            report = f"Thanks for adding me to this monitoring chat. If that's not done already, add me to the chat whose join requests you want me to monitor. They will be notified here ({destination})"
        else:
            report = f"Thanks for adding me to this group chat. If that's not done already, add me to the monitoring chat. Join requests made here will be notified to the monitoring chat."
    else:
        print(f'Unhandled: {update.message}')
        return
    await context.bot.send_message(chat_id, report)


async def set_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    received = update.message.text
    chat_id = update.message.chat_id
    arg = received.split(' ')[1]
    reply = ''
    try:
        destination = int(arg)
        await upsert_destination(chat_id, destination)
        reply = f"Okay, will try to route join requests made in this chat to {destination} from now on."
    except ValueError:
        reply = f"This value is not a correct chat_id: {arg}"
    except Exception:
        reply = "Unable to change destination for this chat. Please try again later."
    finally:
        await context.bot.send_message(chat_id, reply)


async def answer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    reply = "This simple bot lets you define 'routes' of the shape 'origin:destination' such that the bot will post join requests from users from 'origin' to 'destination'.\n\nThe bot must be a member of BOTH. Also be aware that this is a 1-1 relation -- the bot routes each origin to EXACTLY ONE destination."
    await context.bot.send_message(chat_id, reply)


def registerHandlers(app: Application):
    rejoinHandler = ChatJoinRequestHandler(notify_rejoin_request)
    answerHelp = CommandHandler(['help', 'start', 'start'], answer_command)
    setRoute = CommandHandler('route', set_route)
    checkRouting = CommandHandler('check', check_routing)
    botAdded = MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS, confirm_bot)
    app.add_handlers([rejoinHandler, answerHelp,
                     setRoute, checkRouting, botAdded])
    print('Handlers successfully registered')


if __name__ == '__main__':
    application = Application.builder().token(TOKEN).build()
    registerHandlers(application)
    print('Setting webhook now. Ready to work.')
    application.run_webhook(
        listen='0.0.0.0',
        port=PORT,
        url_path=TOKEN,
        webhook_url=f'{ENDPOINT}/{TOKEN}'
    )
