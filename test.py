MAP = '-1001170621048:-1001555963467,-1001533119579:-226151044'
ROUTES = {int(k): int(v) for [k, v] in [item.split(
    ':') for item in MAP.split(',')]}
chat_id = -226151044
origin, destination = [(k, v)
                       for k, v in ROUTES.items() if chat_id in [k, v]][0]

print(origin, destination)
