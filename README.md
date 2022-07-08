# About

This bot provides a simple click-based verification workflow for your Telegram users. It presupposes that you have enabled the options `Only members can send messages` as well as `Use chat join requests` options (only the latter is strictly necessary with it goes hand in hand with the former). 

You can see it in action [here](https://t.me/PopOS_en).

This bot manages user verification for your chat(s). With _/mode auto_, it will open a private chat with users requesting to join your chat. With _/mode manual_, it will notifiy this or another chat of pending join requests. Use _/route_ to have the current chat be the one receiving requests and _/route chatid_ to forward them to another chat.

Use _/check_ to view the settings, _/reset_ to reset them.

To recap:

__Manual mode__
1. The user registers a "join request" against your chat by clicking the "request to join" button.
2. You admins accept / reject the request from any chat of their convenience provided it's where the bot forwards the join request.

__Auto mode__
1. The user registers a "join request" against your chat by clicking the "request to join" button. (same as before)
2. The bot opens a new private chat with the user. From there the user can confirm by using the button provided there. Your admins don't have anything to do.

with `/reset` and `/check` to reset and check settings, and `/mode` and `/route` to change mode, respectively forward join requests notifications to a different chat.
