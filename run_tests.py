#!/usr/bin/env python3
"""Convenience test runner: the same suite as the documented command

    python3 -m unittest discover -s tests -v

Kept so the tests can be started without remembering the discover flags:

    python3 run_tests.py

Exits 0 when every test passes and 1 otherwise, so it is safe to use in CI.
The test file is loaded by path (no __init__.py needed).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEST_FILE = HERE / "tests" / "test_agent_config_lint.py"


def load_suite() -> unittest.TestSuite:
    if not TEST_FILE.is_file():
        raise SystemExit(f"test file not found: {TEST_FILE}")
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location("test_agent_config_lint", TEST_FILE)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise SystemExit(f"cannot load {TEST_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["test_agent_config_lint"] = module
    spec.loader.exec_module(module)
    return unittest.defaultTestLoader.loadTestsFromModule(module)


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(load_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
