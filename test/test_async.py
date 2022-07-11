import pytest
from asyncio import as_completed
from app.utils import mark_excepted_coroutines


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
