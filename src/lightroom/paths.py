"""Filesystem paths and per-profile config directories.

Mirrors notebooklm-py's ``NOTEBOOKLM_HOME`` / ``NOTEBOOKLM_PROFILE`` conventions
with ``LIGHTROOM_HOME`` / ``LIGHTROOM_PROFILE``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_HOME = Path.home() / ".lightroom"
DEFAULT_PROFILE = "default"


def lightroom_home() -> Path:
    """Root config directory; honours ``$LIGHTROOM_HOME``."""
    raw = os.environ.get("LIGHTROOM_HOME")
    return Path(raw).expanduser() if raw else DEFAULT_HOME


def active_profile() -> str:
    return os.environ.get("LIGHTROOM_PROFILE", DEFAULT_PROFILE)


def profile_dir(profile: str | None = None) -> Path:
    return lightroom_home() / "profiles" / (profile or active_profile())


def context_file(profile: str | None = None) -> Path:
    """Per-profile context file: stores the currently-open catalog path, etc."""
    return profile_dir(profile) / "context.json"


def lr_modules_dir() -> Path:
    """User-installed Lightroom plugin / Modules directory for the current OS.

    macOS:   ~/Library/Application Support/Adobe/Lightroom/Modules
    Windows: %APPDATA%/Adobe/Lightroom/Modules
    Linux:   not supported (LR Classic does not ship for Linux)
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Adobe" / "Lightroom" / "Modules"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "Adobe" / "Lightroom" / "Modules"
    raise RuntimeError(
        "Lightroom Classic is not supported on this OS; "
        "lightroom-py runs only on macOS and Windows."
    )


def ensure_dirs() -> None:
    """Create lightroom-py's config dirs if missing."""
    profile_dir().mkdir(parents=True, exist_ok=True)
