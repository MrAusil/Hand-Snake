"""Small, dependency-free helper functions."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def clamp(value: float, low: float, high: float) -> float:
    """Return ``value`` limited to the inclusive range ``[low, high]``."""
    return max(low, min(high, value))


def format_score(value: int) -> str:
    """Format a score as a zero-padded, six digit string."""
    return f"{int(value):06d}"


def read_json(path: Path, default: Any = None) -> Any:
    """Read JSON from ``path``; return ``default`` on any read/parse error."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def write_json_atomic(path: Path, data: Any) -> bool:
    """Write JSON atomically (temp file + rename). Returns True on success."""
    tmp_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
        os.replace(tmp_name, path)
        return True
    except (OSError, TypeError, ValueError):
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass
        return False
