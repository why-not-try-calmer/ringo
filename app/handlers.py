from asyncio import create_task, gather
from os import environ

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from app import dialog_manager, strings
from app.db import (
    add_pending,
    background_task,
    check_if_banned,
    fetch_chat_ids,
    fetch_settings,
    get_status,
    get_users_at,
    log,
    remove_chats,
    remove_pending,
    reset,
    upsert_questionnaire,
    upsert_settings,
)
from app.types import (
    ChatData,
    ChatId,
    ChatJoinRequestData,
    Dialog,
    Mode,
    Questionnaire,
    Reply,
    Settings,
    UserId,
    UserLog,
)
from app.utils import (
    accept_or_reject_btns,
    admins_ids_mkup,
    agree_btn,
    appropriate_emoji,
    average_nb_secs,
    fmt_delta,
    mark_excepted_coroutines,
    mention_markdown,
    slice_on_n,
    withAuth,
)


async def answering_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_data = ChatData.from_update(update)
    if not chat_data:
        return
    reply = strings["commands"]["help"]
    await context.bot.send_message(
        chat_data.chat_id,
        reply,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


@withAuth
async def setting_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_data = ChatData.from_update(update)
    if not chat_data:
        return
    s = chat_data.message_text.split(" ")
    reply = ""

    if len(s) == 1 or s[1] == "":
        # Get
        if fetched := await fetch_settings(chat_data.chat_id):
            reply = strings["settings"]["settings"] + fetched.render(with_alert=True)
        else:
            reply = strings["settings"]["none_found"]
    elif settings := Settings(chat_data.message_text, chat_data.chat_id):
        # Set
        if updated := await upsert_settings(settings):
            questionnaire: Mode = "questionnaire"

            # Setting up context for receiving Questionnaire settings
            if settings.mode == questionnaire:

                async def extractor_closure(
                    answers: list[str] | str,
                ):
                    # Closure to extract the results of the questionnaire
                    rep = ""

                    if q := Questionnaire.parse(answers):
                        await upsert_questionnaire(chat_data.chat_id, q)
                        rep = "Thanks, the questionnaire reads:\n" + q.render()

                    else:
                        rep = "Failed to parse your message into a valid questionnaire. Please start over."

                    await context.bot.send_message(chat_data.chat_id, rep)

                # Setting up state to detect the reply
                dialog_manager.add(
                    chat_data.user_id,
                    Reply(
                        chat_data.user_id,
                        chat_data.chat_id,
                        extractor_closure,
                    ),
                )
                reply = "Please *reply* to this message with an intro, questions, and an outro, separating each parts with a single linebreak. Example:\n_Intro_. This is my intro.\n_Q1_. This is a question.\n_Q2_.This is another question.\n_Outro_. This is the outro."
            else:
                reply = strings["settings"]["updated"] + updated.render(with_alert=True)
        else:
            reply = strings["settings"]["failed_to_update"]
    else:
        # No parse
        reply = strings["settings"]["failed_to_parse"]
    await context.bot.send_message(
        chat_data.chat_id,
        reply,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


@withAuth
async def resetting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_data = ChatData.from_update(update)
    if not chat_data:
        return

    reply = strings["settings"]["reset"]
    await gather(
        reset(chat_data.chat_id),
        context.bot.send_message(
            chat_data.chat_id, reply, disable_web_page_preview=True
        ),
    )


async def wants_to_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = ChatJoinRequestData.from_update(update)
    if not req:
        return
    admins, settings = await gather(
        context.bot.get_chat_administrators(req.chat_id), fetch_settings(req.chat_id)
    )
    alert = admins_ids_mkup(admins) if admins else ""
    # Missing settings
    if not settings:
        return await context.bot.send_message(
            req.chat_id, strings["settings"]["missing"], disable_web_page_preview=True
        )
    # Paused
    if hasattr(settings, "paused") and settings.paused:
        return
    if hasattr(settings, "mode"):
        match settings.mode:
            case "auto":
                await gather(
                    context.bot.send_message(
                        req.user_chat_id,
                        settings.verification_msg
                        if settings.verification_msg
                        and len(settings.verification_msg) >= 10
                        else strings["wants_to_join"]["verification_msg"],
                        disable_web_page_preview=True,
                        reply_markup=agree_btn(
                            text=strings["wants_to_join"]["ok"],
                            from_chat_id=req.user_chat_id,
                            target_chat_id=req.chat_id,
                            target_chat_url=strings["chat"]["url"]
                            if not settings.chat_url
                            else settings.chat_url,
                        ),
                    ),
                    log(
                        UserLog(
                            "wants_to_join",
                            req.chat_id,
                            req.from_user_id,
                            req.from_user_name,
                        )
                    ),
                )

            case "manual":

                async def closure_send(destination: ChatId, text: str):
                    response = await context.bot.send_message(
                        destination,
                        text,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                        reply_markup=accept_or_reject_btns(
                            req.from_user_id,
                            req.from_user_name,
                            req.chat_id,
                            strings["chat"]["url"]
                            if not settings.chat_url
                            else settings.chat_url,
                        ),
                    )
                    await add_pending(
                        req.chat_id, req.from_user_id, response.message_id
                    )

                if hasattr(settings, "helper_chat_id") and settings.helper_chat_id:
                    body = f"{mention_markdown(req.from_user_id, req.from_user_name)} has just asked to join your chat {mention_markdown(req.chat_id, req.chat_name)}, you might want to accept them."
                    await closure_send(settings.helper_chat_id, alert + "\n" + body)
                else:
                    body = f"{mention_markdown(req.from_user_id, req.from_user_name)} just joined, but I couldn't find any chat to notify."
                    await closure_send(req.chat_id, alert + "\n" + body)

            case "questionnaire":
                if q := settings.questionnaire:
                    questions = q.questions

                    async def extractor_closure(answers: list[str]) -> None:
                        q_a = "\n".join(
                            [
                                f"Question: {escape_markdown(q)} => Answer: {escape_markdown(a)}"
                                for q, a in zip(questions, answers)
                            ]
                        )
                        reply = f"@{mention_markdown(req.from_user_id, req.from_user_name)} has just requested to join this chat. Their answers to the questionnaire are as follows:\n{escape_markdown(q_a)}"
                        keyboard = accept_or_reject_btns(
                            req.from_user_id, req.from_user_name, req.chat_id, ""
                        )

                        await context.bot.send_message(
                            req.chat_id,
                            reply,
                            reply_markup=keyboard,
                            parse_mode=ParseMode.MARKDOWN,
                        )

                    dialog = Dialog(req.from_user_id, req.chat_id, q, extractor_closure)
                    dialog.start()
                    reply = dialog.take_reply()
                    dialog_manager.add(req.from_user_id, dialog)

                    await context.bot.send_message(
                        req.user_chat_id, dialog.intro + ("\n" + reply) if reply else ""
                    )

            case _:
                pass


tasks = set()


async def replying_to_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Taking advantage of the fact that even with privacy mode off
    # the bot will be handed over all replies
    t = create_task(background_task(context))
    tasks.add(t)
    t.add_done_callback(tasks.discard)

    if not (hasattr(update, "message") and hasattr(update.message, "reply_to_message")):
        print(
            f"Unable to make use of this update: {update}. Running background task instead"
        )
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
    operation, from_user_chat_id, target_chat_id_str, target_chat_url = (
        splitted[0],
        splitted[1],
        splitted[2],
    )

    # Auto mode
    if operation == "self-confirm":
        await gather(
            context.bot.answer_callback_query(update.callback_query.id),
            context.bot.send_message(
                from_user_chat_id,
                f"Thanks, you are welcome to join {target_chat_url}. {strings['has_joined']['post_join']}",
                disable_web_page_preview=True,
            ),
            context.bot.approve_chat_join_request(
                target_chat_id_str, update.callback_query.from_user.id
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

    # Manual or questionnaire mode
    # Setting up verdict handling
    user_id_str, user_name = splitted[3], splitted[4]
    user_id = int(user_id_str)
    chat_id = int(target_chat_id_str)
    confirmation_chat_id = update.callback_query.message.chat.id
    admin_name = (
        update.callback_query.from_user.username
        or update.callback_query.from_user.first_name
    )

    # Manual mode
    # Handling verdict
    reply = ""

    match operation:
        case "accept":
            response = await context.bot.approve_chat_join_request(chat_id, user_id)
            if response:
                reply = f"{user_name} accepted to {target_chat_id_str} by {admin_name}"
            else:
                reply = "User already approved"

        case "reject":
            response = await context.bot.decline_chat_join_request(chat_id, user_id)
            if response:
                reply = (
                    f"{user_name} denied access to {target_chat_id_str} by {admin_name}"
                )
            else:
                reply = "User already denied."
        case _:
            return

    # Manual mode
    # Confirmation and cleaning behind on accepted or rejected
    async def closure_together():
        if message_id := await remove_pending(chat_id, user_id):
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
    new_members_ids: list[UserId] = [uid for uid, _, _ in new_members]

    # Termination if not a new user after all
    if not new_members:
        return

    # Setting up for handling event
    settings, banned = await gather(
        fetch_settings(chat_id), check_if_banned(chat_id, new_members_ids)
    )

    if context.bot.id in new_members_ids:
        # The newcomer is the bot itself
        report = ""

        if settings and getattr(settings, "helper_chat_id"):
            report = f"{strings['has_joined']['destination']} {settings.helper_chat_id}"
        else:
            report = strings["has_joined"]["not_destination"]

        await context.bot.send_message(
            settings.helper_chat_id
            if settings and settings.helper_chat_id
            else chat_id,
            report,
            disable_web_page_preview=True,
        )
    else:
        # Genuinely new users
        # First checking if we are "pre-banning"
        banned = await check_if_banned(chat_id, new_members_ids)
        not_banned = [
            (uid, uname, ulang)
            for uid, uname, ulang in new_members
            if uid not in banned
        ]

        if banned:
            banned_uid_names = [
                (uid, uname) for uid, uname, _ in new_members if uid in banned
            ]
            report = (
                "".join([mention_markdown(uid, name) for uid, name in banned_uid_names])
                + " were banned during verification!"
            )
            await context.bot.send_message(
                chat_id, report, parse_mode=ParseMode.MARKDOWN
            )

        if not not_banned:
            return

        greet = (
            lambda lang: "welcome"
            if not lang in strings["welcome"]
            else strings["welcome"][lang]
        )
        greetings = (
            ", ".join(
                [
                    f"{greet(lang)} {mention_markdown(uid, name)}"
                    for uid, name, lang in not_banned
                ]
            )
            + "! "
            + appropriate_emoji()
        ).capitalize()

        if settings and hasattr(settings, "show_join_time") and settings.show_join_time:
            datetimes = await get_users_at(chat_id, new_members_ids)
            if average_join_time := average_nb_secs(datetimes):
                if average_join_time < 12:
                    greetings += (
                        f" It took you {average_join_time} seconds for joining. Did you actually _read_ the conditions? "
                        + "\U0001F609"
                    )
                elif average_join_time > 10800:
                    greetings += (
                        f" It took you {fmt_delta(average_join_time)} for joining. "
                        + "\U0001F62A"
                    )

        await context.bot.send_message(
            chat_id,
            greetings,
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


async def expected_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if "/cancel" in text:
        dialog_manager.cancel(user_id)
        user_id = update.message.from_user.id
        reply = "Okay, starting over"
        return await context.bot.send_message(user_id, reply)

    if dialog := dialog_manager[user_id]:
        match dialog:
            case Dialog():
                if reply := dialog.take_reply(text):
                    await context.bot.send_message(user_id, reply)
                elif dialog.done:
                    dialog_manager.remove(user_id)

            case Reply():
                await dialog.extractor(text)
                dialog_manager.remove(user_id)


@withAuth
async def getting_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    reply = ""

    if status := await get_status(chat_id):
        reply += status.render()
    else:
        reply += "No pending, banned or notified users for this chat!"

    sliced = slice_on_n(reply)
    t = len(sliced)

    for i, s in enumerate(sliced):
        e = f"({i+1}/{t}) {s}"
        await context.bot.send_message(chat_id, e)
