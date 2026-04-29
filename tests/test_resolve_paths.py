"""Tests for SQLite UUID -> filesystem path resolution."""

from __future__ import annotations

from pathlib import Path

from lightroom._sqlite import resolve_paths


def test_resolve_known_uuids(synthetic_lrcat: Path) -> None:
    paths = resolve_paths(synthetic_lrcat, ["uuid-001", "uuid-003"])
    assert set(paths) == {"uuid-001", "uuid-003"}
    p1 = paths["uuid-001"]
    assert p1.name == "DSC_0001.NEF"
    assert "Photos" in str(p1)


def test_resolve_unknown_uuids_omitted(synthetic_lrcat: Path) -> None:
    paths = resolve_paths(synthetic_lrcat, ["uuid-001", "no-such"])
    assert set(paths) == {"uuid-001"}


def test_resolve_empty(synthetic_lrcat: Path) -> None:
    assert resolve_paths(synthetic_lrcat, []) == {}
