"""
In-process pub/sub broker for the real-time dashboard. A dashboard tab opens
an SSE connection and gets an asyncio.Queue; the submission endpoint pushes
onto every queue subscribed to that widget_id.

Same documented limitation as services/rate_limit.py: this is per-process
state. Fine for a single-instance capstone demo; a multi-instance deployment
would need a shared pub/sub (Redis Streams, etc.) instead.
"""

import asyncio
from collections import defaultdict

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)


def subscribe(widget_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[widget_id].add(queue)
    return queue


def unsubscribe(widget_id: str, queue: asyncio.Queue) -> None:
    _subscribers[widget_id].discard(queue)
    if not _subscribers[widget_id]:
        _subscribers.pop(widget_id, None)


async def publish(widget_id: str, event: dict) -> None:
    for queue in list(_subscribers.get(widget_id, ())):
        await queue.put(event)


def subscriber_count(widget_id: str) -> int:
    return len(_subscribers.get(widget_id, ()))


def reset() -> None:
    """Test helper — clears all subscribers between test cases."""
    _subscribers.clear()
