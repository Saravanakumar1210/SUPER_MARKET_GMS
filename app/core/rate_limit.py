import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status


_BUCKETS: dict[str, deque[float]] = defaultdict(deque)

# How many requests to process between eviction sweeps.
# A sweep removes bucket keys that have no timestamps in the last window,
# preventing unbounded memory growth from unique IPs.
_REQUESTS_BETWEEN_EVICTIONS = 500
_request_counter = 0


def clear_rate_limits(*, namespace: str | None = None) -> int:
    """Clear in-memory rate-limit buckets. Returns number of keys removed."""
    if namespace is None:
        n = len(_BUCKETS)
        _BUCKETS.clear()
        return n
    prefix = f"{namespace}:"
    keys = [k for k in list(_BUCKETS) if k.startswith(prefix)]
    for key in keys:
        del _BUCKETS[key]
    return len(keys)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _evict_stale_buckets(max_window: int) -> None:
    """Remove bucket entries whose sliding window has fully expired."""
    now = time.monotonic()
    stale_keys = [k for k, v in _BUCKETS.items() if not v or now - v[-1] >= max_window]
    for key in stale_keys:
        del _BUCKETS[key]


def rate_limit(
    *,
    namespace: str,
    limit: int,
    window_seconds: int,
    key_func: Callable[[Request], str] | None = None,
):
    async def dependency(request: Request) -> None:
        global _request_counter
        _request_counter += 1
        if _request_counter >= _REQUESTS_BETWEEN_EVICTIONS:
            _request_counter = 0
            _evict_stale_buckets(window_seconds)

        now = time.monotonic()
        key_part = key_func(request) if key_func else _client_ip(request)
        bucket_key = f"{namespace}:{key_part}"
        bucket = _BUCKETS[bucket_key]

        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()

        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again shortly.",
            )

        bucket.append(now)

    return dependency
