"""Startup readiness flags shared by lifespan, health, and auth/cart gates."""

from __future__ import annotations

import asyncio

from fastapi import HTTPException

_db_ready = asyncio.Event()
_warmup_done = False
_warmup_error: str | None = None


def mark_db_ready() -> None:
    """Schema/pool warmup finished — auth and cart may proceed."""
    _db_ready.set()


def mark_warmup_complete(*, error: str | None = None) -> None:
    global _warmup_done, _warmup_error
    if error:
        _warmup_done = False
        _warmup_error = error
        return
    _warmup_done = True
    _warmup_error = None
    _db_ready.set()


def reset_warmup_state_for_tests() -> None:
    """Used by offline tests so each session starts clean."""
    global _warmup_done, _warmup_error
    _warmup_done = False
    _warmup_error = None
    _db_ready.clear()


def warmup_payload() -> dict:
    if _warmup_done:
        status = "ready"
    elif _warmup_error:
        status = "error"
    else:
        status = "pending"
    return {
        "warmup": status,
        "warmup_error": _warmup_error,
        "db_ready": _db_ready.is_set(),
    }


async def wait_until_db_ready(timeout: float = 25.0) -> None:
    """Block auth/cart until schema warmup succeeds (or time out with 503)."""
    if _db_ready.is_set():
        return
    try:
        await asyncio.wait_for(_db_ready.wait(), timeout=timeout)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=503,
            detail="Store is still starting up. Please try again in a moment.",
            headers={"Retry-After": "2"},
        ) from exc
