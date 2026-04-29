"""Logging setup. Library code uses ``logging.getLogger(__name__)``; the CLI
configures a Rich handler when run interactively."""

from __future__ import annotations

import logging
import os


def configure(level: str | int | None = None) -> None:
    """Configure root logging for CLI use.

    Called from the CLI entry point. Library users should not call this.
    """
    if level is None:
        level = os.environ.get("LIGHTROOM_LOG_LEVEL", "WARNING")
    if isinstance(level, str):
        level = level.upper()

    try:
        from rich.logging import RichHandler

        handler: logging.Handler = RichHandler(
            rich_tracebacks=True,
            show_time=False,
            show_path=False,
            markup=False,
        )
        fmt = "%(message)s"
    except ImportError:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s %(name)s — %(message)s"

    logging.basicConfig(level=level, format=fmt, handlers=[handler], force=True)
