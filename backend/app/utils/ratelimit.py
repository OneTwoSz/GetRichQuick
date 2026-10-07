"""
In-memory sliding-window rate limiting.

Free and dependency-free, which suits a single server process (the Render
free plan runs one). Counters live in this process only: with several
workers or instances, move them to Redis so limits are shared.
"""
import math
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

_hits: Dict[str, Deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _prune(q: Deque[float], window: float, now: float):
    while q and q[0] <= now - window:
        q.popleft()


def check(key: str, limit: int, window_seconds: float, *, record: bool = True) -> None:
    """Raise 429 when `key` already has `limit` hits inside the window;
    otherwise record this hit (unless record=False)."""
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        _prune(q, window_seconds, now)
        if len(q) >= limit:
            retry = max(1, math.ceil(q[0] + window_seconds - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {math.ceil(retry / 60)} minute(s).",
                headers={"Retry-After": str(retry)},
            )
        if record:
            q.append(now)


def record(key: str) -> None:
    with _lock:
        _hits[key].append(time.monotonic())


def clear(key: str) -> None:
    with _lock:
        _hits.pop(key, None)


def reset_all() -> None:
    """Tests only."""
    with _lock:
        _hits.clear()


def client_ip(request: Request) -> str:
    # uvicorn runs with --proxy-headers on hosted deploys, so this is the
    # real client address behind Render's proxy.
    return request.client.host if request.client else "unknown"
