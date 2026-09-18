"""Tests for the scheduler service."""

from __future__ import annotations

import unittest
from datetime import datetime

from src.services.orders import next_attempt_at, should_retry


class SchedulerTests(unittest.TestCase):
    def test_rejects_expired_token(self) -> None:
        self.assertFalse(should_retry(attempt=1, status=401))

    def test_retries_server_error(self) -> None:
        self.assertTrue(should_retry(attempt=1, status=503))

    def test_backoff_doubles(self) -> None:
        now = datetime(2024, 1, 1, 12, 0, 0)
        first = next_attempt_at(now, 1)
        second = next_attempt_at(now, 2)
        self.assertEqual((second - first).total_seconds(), 2)


if __name__ == "__main__":
    unittest.main()
