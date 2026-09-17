"""Logging configuration, applied once at application startup."""

import logging
import sys

from core.config import settings

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"


def setup_logging() -> None:
    """Configure root logging from settings.log_level."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # httpx logs every request at INFO, which is noise at our level.
    logging.getLogger("httpx").setLevel(logging.WARNING)
