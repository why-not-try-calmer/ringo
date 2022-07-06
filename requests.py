from telegram.helpers import escape_markdown
from aiohttp import ClientSession
from asyncio import gather
from os import environ

TOKEN = environ["TOKEN"]
base_url = f"https://api.telegram.org/bot{TOKEN}"


def admins_ids_mkup(ids: list[tuple[str, str]]) -> str:
    return ", ".join(
        [
            f"@[{escape_markdown(first_name)}](tg://user?id={i})"
            for (i, first_name) in ids
        ]
    )


async def get_chat_admins_ids(
    chat_id: int, bot_id: int
) -> list[tuple[str, str]] | None:
    async with ClientSession() as session:
        async with session.get(
            url=f"{base_url}/getChatAdministrators", data={"chat_id": chat_id}
        ) as response:
            decoded_response = await response.json()
            if "result" in decoded_response:
                admins = (
                    (
                        u["user"]["id"],
                        u["user"]["username"]
                        if "username" in u["user"]
                        else u["user"]["first_name"],
                    )
                    for u in decoded_response["result"]
                )
                return [
                    (user_id, user_name)
                    for user_id, user_name in admins
                    if user_id != str(bot_id)
                ]


async def remove_messages_by_id(chat_id: int, messages_ids: list[int]):
    async def deleteOne(session: ClientSession, chat_id: int, message_id: int):
        await session.get(
            url=f"{base_url}/deleteMessage",
            data={"chat_id": chat_id, "message_id": message_id},
        )

    async with ClientSession() as session:
        await gather(
            *[deleteOne(session, chat_id, message_id) for message_id in messages_ids]
        )
