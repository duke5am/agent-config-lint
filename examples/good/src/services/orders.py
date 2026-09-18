"""Scheduler service: decides when a queued order is retried."""

from __future__ import annotations

from datetime import datetime, timedelta

MAX_ATTEMPTS = 5


def next_attempt_at(now: datetime, attempt: int) -> datetime:
    """Return the time of the next retry, with an exponential backoff."""
    delay_seconds = 2 ** attempt
    return now + timedelta(seconds=delay_seconds)


def should_retry(attempt: int, status: int) -> bool:
    """Return True when a failed order should be queued again."""
    if attempt >= MAX_ATTEMPTS:
        return False
    return status >= 500 or status == 429
