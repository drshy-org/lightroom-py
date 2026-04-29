"""Shared dataclasses and type aliases.

Kept intentionally small in Phase 0; expand as sub-clients grow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CatalogInfo:
    path: Path
    lightroom_version: str | None = None
    photo_count: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Photo:
    uuid: str
    filename: str | None = None
    rating: int | None = None
    color_label: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BridgeStatus:
    running: bool
    port: int | None
    plugin_version: str | None
    last_seen_seconds_ago: float | None
