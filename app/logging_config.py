"""Application-wide logging setup."""

from __future__ import annotations

import logging

LOGGER_NAME = "checkin-bot"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root logging format/level once and return the app logger."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        level=level,
    )
    return logging.getLogger(LOGGER_NAME)


def get_logger() -> logging.Logger:
    """Return the shared application logger (call `setup_logging()` first)."""
    return logging.getLogger(LOGGER_NAME)
