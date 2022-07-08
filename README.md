[![Python application](https://github.com/why-not-try-calmer/notify-join/actions/workflows/python-app.yml/badge.svg)](https://github.com/why-not-try-calmer/notify-join/actions/workflows/python-app.yml)

## Overview

This bot provides a simple click-based verification workflow for your Telegram users. It requires that you have enabled the options `Only members can send messages` as well as `Use chat join requests`; only the latter is strictly necessary but goes hand in hand with the former. 

You can see the bot in action [here](https://t.me/PopOS_en).

There are two modes of operation:

__Manual mode__
1. The user registers a "join request" against your chat by clicking the "request to join" button.
2. You admins accept / reject the request from any chat of their convenience provided it's where the bot forwards the join request.

__Auto mode__
1. The user registers a "join request" against your chat by clicking the "request to join" button. (same as before)
2. The bot opens a new private chat with the user. From there the user can confirm by using the button provided there. Your admins don't have anything to do.

## Commands

The bot uses exactly two commands:

- `/set` <key1 val1 key2 val2 ...>: configure the bot to your liking. Here is the list of possibles keys (the values are always text strings):
    - _chat_id_: the chat_id of the chat where the bot should listen for join requests (you cannot manually set this value)
    - _chat_url_: the full url (`https://t.me/...`) of the chat where the bot should listen for join requests (you can and __should__ set this value)
    - _mode_: `auto | manual`: see the previous section for explanations
    - _help_chat_id_: chat_id of the chat to which the both should forward join requests notifications (only used in __manual__ mode)  
    - _verification\_msg_: the message the bot should send to users trying to verify after landing a join requests 
- `/reset` (no parameter): resets the bot to its default settings relative to chat(s) you manage.