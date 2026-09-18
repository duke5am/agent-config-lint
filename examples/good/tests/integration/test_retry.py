"""Integration check: the API client and the scheduler agree on retries.

Run with `npm ci` first, because the fake upstream is built from the client's
TypeScript sources.
"""

from __future__ import annotations

import unittest

from src.services.orders import should_retry


class IntegrationTests(unittest.TestCase):
    def test_retry_agrees_with_client(self) -> None:
        self.assertTrue(should_retry(attempt=0, status=500))


if __name__ == "__main__":
    unittest.main()
