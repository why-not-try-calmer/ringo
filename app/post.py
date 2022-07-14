from typing import Any, Coroutine
from asyncio import sleep

from app.db import deprecate_not_verified


async def mark_excepted_coroutines(marker: Any, coroutine: Coroutine) -> Any | None:
    try:
        await coroutine
    except Exception:
        return marker
