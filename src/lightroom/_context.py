"""Per-profile context: which catalog is currently active.

Stored as JSON in ``~/.lightroom/profiles/<profile>/context.json`` so multiple
processes (CLI invocations, the bridge, the agent) all see the same active
catalog path.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .paths import context_file, profile_dir

logger = logging.getLogger(__name__)


def load_active_catalog() -> Path | None:
    """Return the active catalog path, or None if not set."""
    f = context_file()
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("could not read context file %s: %s", f, exc)
        return None
    raw = data.get("catalog_path")
    return Path(raw).expanduser() if raw else None


def save_active_catalog(path: str | Path) -> Path:
    """Persist the active catalog path; return its resolved Path."""
    resolved = Path(path).expanduser().resolve()
    profile_dir().mkdir(parents=True, exist_ok=True)
    f = context_file()
    payload = {"catalog_path": str(resolved)}
    if f.exists():
        try:
            existing = json.loads(f.read_text())
            existing.update(payload)
            payload = existing
        except (OSError, json.JSONDecodeError):
            pass
    f.write_text(json.dumps(payload, indent=2))
    return resolved


def clear_active_catalog() -> None:
    f = context_file()
    if not f.exists():
        return
    try:
        data = json.loads(f.read_text())
        data.pop("catalog_path", None)
        f.write_text(json.dumps(data, indent=2))
    except (OSError, json.JSONDecodeError):
        f.unlink(missing_ok=True)
