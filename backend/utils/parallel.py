import asyncio


async def gather_cancel_on_error(*coroutines):
    """Do not let sibling AI calls survive a failed/cancelled game stage."""
    tasks = [asyncio.create_task(coroutine) for coroutine in coroutines]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
