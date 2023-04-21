from asyncio import as_completed, gather, get_event_loop_policy
from typing import Any, Coroutine

import pytest

from app.db import background_task, fetch_chat_ids, fetch_settings, get_status


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
    print(f"test_run_background: Found {result} to remove or notify.")
    assert result is not None


@pytest.mark.asyncio
async def test_status():
    if status := await get_status(-1001607431141):
        text = status.render()
        print(text)
        assert len(text) > 0
    else:
        assert False
