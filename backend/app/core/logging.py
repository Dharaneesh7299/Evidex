"""Logging utilities. Keep logs free of document content."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "info") -> None:
    """Configure root logging once for the backend."""

    log_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root = logging.getLogger()
    # Replace handlers to avoid duplicate output in reload scenarios.
    root.handlers = [handler]
    root.setLevel(log_level)
    # Reduce noise from third-party libs.
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
