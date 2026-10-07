"""Tiny logging setup: console + rotating file, no per-frame spam."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from config.settings import LOG_FILE

_ROOT_NAME = "handsnake"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(logging.INFO)
    root.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    root.addHandler(console)

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=200_000, backupCount=1, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        root.addHandler(file_handler)
    except OSError:
        pass  # read-only install: console logging is enough
    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger of the application logger."""
    _configure()
    return logging.getLogger(f"{_ROOT_NAME}.{name}" if name else _ROOT_NAME)
