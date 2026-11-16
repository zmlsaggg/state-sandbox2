"""Request-scoped streaming: no work survives the HTTP invocation."""
import asyncio
import os
from typing import AsyncGenerator

from fastapi.responses import StreamingResponse
from routers.schemas import HeartbeatEvent, StateErrorEvent

# Leave time for cancellation/rollback before the platform's 300s hard limit.
STREAM_TIMEOUT_SECONDS = int(os.getenv("STREAM_TIMEOUT_SECONDS", "280"))


async def with_heartbeat(stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    deadline = asyncio.get_running_loop().time() + STREAM_TIMEOUT_SECONDS
    task = None
    try:
        task = asyncio.create_task(stream.__anext__())
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                yield StateErrorEvent(message="Generation timed out. Please try again.").json_line()
                return
            done, _ = await asyncio.wait([task], timeout=min(2, remaining))
            if not done:
                yield HeartbeatEvent().json_line()
                continue
            try:
                item = task.result()
            except StopAsyncIteration:
                return
            yield item
            task = asyncio.create_task(stream.__anext__())
    finally:
        if task is not None:
            task.cancel()
            # Await cancellation so DB cleanup finishes before request teardown.
            await asyncio.gather(task, return_exceptions=True)
        await stream.aclose()


def event_stream_response(stream: AsyncGenerator[str, None]) -> StreamingResponse:
    return StreamingResponse(
        with_heartbeat(stream),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
