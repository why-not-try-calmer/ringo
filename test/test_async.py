import pytest
from typing import Any, Coroutine
from asyncio import as_completed, gather, get_event_loop_policy

from app.db import background_task, fetch_chat_ids, fetch_settings


@pytest.fixture(scope="session")
def event_loop():
    policy = get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


async def mark_excepted_coroutines(marker: Any, coroutine: Coroutine) -> Any | None:
    try:
        await coroutine
    except Exception:
        return marker


@pytest.mark.asyncio
async def test_collect_failed():
    async def test(n):
        if n % 2 == 0:
            raise Exception()

    failures = [
        await t
        for t in as_completed(
            [mark_excepted_coroutines(n, test(n)) for n, _ in enumerate([1, 2, 3, 4])]
        )
    ]
    failed = [f for f in failures if f is not None]
    assert len(failed) == 2


@pytest.mark.asyncio
async def test_settings():
    chats_ids = await fetch_chat_ids()
    settings = await gather(*[fetch_settings(cid) for cid in chats_ids])
    assert len(settings) == len(chats_ids)


@pytest.mark.asyncio
async def test_run_background_task():
    result = await background_task(None)
    assert result
