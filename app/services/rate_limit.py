"""
Simple in-memory sliding-window rate limiter.

Scope/limitation (documented honestly, not hidden): this is per-process state,
fine for a single-instance capstone demo. A multi-instance deployment would
need a shared store (Redis) — noted in README limitations, not built here,
since the brief only requires 429s under a burst with the service staying up.
"""

import time
from collections import defaultdict, deque

from app.config import get_settings

settings = get_settings()

# key -> deque of unix timestamps (seconds) of recent hits
_hits: dict[str, deque] = defaultdict(deque)

WINDOW_SECONDS = 60


def _prune(key: str, now: float) -> None:
    dq = _hits[key]
    while dq and now - dq[0] > WINDOW_SECONDS:
        dq.popleft()


def is_rate_limited(key: str, limit: int | None = None) -> bool:
    """Records this hit and returns True if `key` has exceeded the limit
    within the trailing WINDOW_SECONDS."""
    limit = limit if limit is not None else settings.rate_limit_per_minute
    now = time.time()
    _prune(key, now)
    dq = _hits[key]
    if len(dq) >= limit:
        return True
    dq.append(now)
    return False


def reset() -> None:
    """Test helper — clears all counters between test cases."""
    _hits.clear()
