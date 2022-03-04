import asyncio


async def gather_with_concurrency(n, *tasks, return_exceptions=False):
    """Gather tasks with a concurrency limit"""
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task

    return await asyncio.gather(
        *(sem_task(task) for task in tasks), return_exceptions=return_exceptions
    )
