[![Test](https://github.com/why-not-try-calmer/ringo/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/why-not-try-calmer/ringo/actions/workflows/test.yml)
[![Publish](https://github.com/why-not-try-calmer/ringo/actions/workflows/publish.yml/badge.svg?branch=master)](https://github.com/why-not-try-calmer/ringo/actions/workflows/publish.yml)

## Overview

This bot provides a simple click-based verification workflow for your Telegram users. It requires that you have enabled the options `Only members can send messages` as well as `Use chat join requests`; only the latter is strictly necessary but goes hand in hand with the former. 

You can see [the bot](https://t.me/alert_me_and_my_chat_bot) in action [here](https://t.me/PopOS_en).

If you like the bot, feel free to use it in your own chats, fork this repository or even pay a coffee or a beer to the developer. At any rate please mind the LICENSE. 

## How it works

There are two modes of operation:

__Manual mode__
1. The user registers a "join request" against your chat by clicking the "request to join" button.
2. You admins accept / reject the request from any chat of their convenience provided it's where the bot forwards the join request.

__Auto mode__
1. The user registers a "join request" against your chat by clicking the "request to join" button. (same as before)
2. The bot opens a new private chat with the user. From there the user can confirm by using the button provided there. Your admins don't have anything to do.

## Commands

The bot uses exactly two commands in addition to `/help` (which aliases to `/start`):

- `/set <key1 val1 key2 val2 ...>`: configure the bot to your liking. Here is the list of possibles keys (the values are always text strings):
    - `chat_id`: the chat_id of the chat where the bot should listen for join requests (you cannot manually set this value)
    - `chat_url`: the full url (https://t.me/...) of the chat where the bot should listen for join requests (you can and __should__ set this value)
    - `mode <auto | manual>`: see the previous section for explanations
    - `helper_chat_id_`: chat_id of the chat to which the both should forward join requests notifications (only used in __manual__ mode)  
    - `verification_msg`: the message the bot should send to users trying to verify after landing a join requests. Naturall it's not convenient to set a long verification message in this way, so for that key it might be preferable to use a line break, as in:
    ```
    /set mode auto verification_message
    Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem. 
    ```
    - `active <on | off>`: _off_ pauses the bot for this chat, _on_ makes it active
    - `changelog < on | off>`: _off_ lets you opt-out of changelog notification messages
- `/reset` (no parameter): resets the bot to its default settings relative to chat(s) you manage.

## Tests

Run test with `python -m pytest -s --asyncio-mode=strict -v`

## Deploy

Since I don't plan on investing heavy resources on deployment it's better if users deploy their own copy of this bot. The easiest way is to use Docker / Podman. Create a new directoy, cd to it and then:

1. Clone this repository: `git clone https://github.com/why-not-try-calmer/ringo.git .`
2. Cd to it and there create your own SSL certificate (for encoding/decoding HTTPS requests to/from Telegram): `openssl req -newkey rsa:2048 -sha256 -nodes -keyout private.key -x509 -days 3650 -out cert.pem`. Follow the interactive instructions.
3. Build the image: `docker build . -t ringo` (use `docker` if you are able to use `podman`)
4. Deploy: `docker run -p <HOST_PORT>:8443 --env-file .env localhost/ringo`

The last command assumes that you are using an .env file to pass secrets to the bot. This is required if you don't set ENVARs containing the needed secret by some other means. The bot expects the following ENVARs (random examples):

```
ADMIN=userid_of_admin       <- the chat the operator is going to use to administrate the bot
ENDPOINT=https://some.ur.l  <- the webhook's url
MONGO_CONN_STRING=mongodb+srv://myapp:mypass@myhost/?retryWrites=true&w=majority  <- the Mongo db connection string
TOKEN=123344:DFKDFK54KFKkdslkelg1 <- your Telegram token
```
Notice that Telegram as per their [official documentation](https://core.telegram.org/bots/api#setwebhook) requires you to use any of 443, 80, 88 or 8443 as your HOST_PORT.

If you want to have the bot listen to a custom port, there is the option to add a `PORT` envar. Then command (4) above will read instead:

4. Deploy: `docker run -p <HOST_PORT>:<CUSTOM_CONTAINER_PORT> --env-file .env localhost/ringo`

Finally to start the bot run `python -m app` if you want to register a webhook hook and receive updates with the built-in server. Otherwise start with `python -m app --polling`.