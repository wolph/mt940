"""Shared pytest configuration for the mt940 test suite."""

import logging

import pytest

# Each ``-v`` lowers the root logger threshold one step. ``-vvv`` enables the
# parser's DEBUG output, which becomes very verbose very quickly.
LOG_LEVELS: dict[int, int] = {
    0: logging.ERROR,
    1: logging.WARNING,
    2: logging.INFO,
    3: logging.DEBUG,
}


def pytest_configure(config: pytest.Config) -> None:
    verbosity = int(config.getoption('verbose') or 0)
    logging.basicConfig(level=LOG_LEVELS.get(verbosity, logging.DEBUG))
