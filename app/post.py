from typing import Any, Coroutine
from asyncio import sleep

from app.db import deprecate_not_verified


async def mark_excepted_coroutines(marker: Any, coroutine: Coroutine) -> Any | None:
    try:
        await coroutine
    except Exception:
        return marker


async def run_deprecate_not_verified():
    print(
        "Spawned task for cleaning up database. Running once every 6 minutes. Next run in 6 minutes."
    )
    while True:
        await sleep(60 * 10)
        await deprecate_not_verified()
