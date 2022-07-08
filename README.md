# About

This bot provides a simple click-based verification workflow for your Telegram users. It presupposes that you have enabled the options `Only members can send messages` as well as `Use chat join requests` options (only the latter is strictly necessary with it goes hand in hand with the former). 

You can see it in action [here](https://t.me/PopOS_en).

The bot operates in either one of these two modes:

__Manual mode__
1. The user registers a "join request" against your chat by clicking the "request to join" button.
2. You admins accept / reject the request from any chat of their convenience provided it's where the bot forwards the join request.

__Auto mode__
1. The user registers a "join request" against your chat by clicking the "request to join" button. (same as before)
2. The bot opens a new private chat with the user. From there the user can confirm by using the button provided there. Your admins don't have anything to do.

...