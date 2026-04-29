"""Tests for the SQLite read fast-path against a synthetic .lrcat."""

from __future__ import annotations

from pathlib import Path

import pytest

from lightroom._sqlite import (
    count_photos,
    get_catalog_stats,
    get_catalog_summary,
    list_photos,
)


def test_summary(synthetic_lrcat: Path) -> None:
    s = get_catalog_summary(synthetic_lrcat)
    assert s.photos == 5
    assert s.earliest_capture == "2026-04-01T10:00:00"
    assert s.latest_capture == "2026-05-02T08:00:00"
    assert s.sqlite_user_version == 1100200


def test_stats(synthetic_lrcat: Path) -> None:
    s = get_catalog_stats(synthetic_lrcat)
    assert s.photos == 5
    assert s.folders == 2
    assert s.keywords == 3
    assert s.collections == 2
    assert s.smart_collections == 1


def test_list_unfiltered(synthetic_lrcat: Path) -> None:
    rows = list_photos(synthetic_lrcat)
    assert len(rows) == 5
    # Should be ordered by captureTime DESC.
    assert rows[0].uuid == "uuid-005"
    assert rows[-1].uuid == "uuid-001"
    assert rows[0].camera == "Sony ILCE-7M4"
    assert rows[0].lens == "Sony FE 50mm f/1.8"


def test_list_rating_filter(synthetic_lrcat: Path) -> None:
    rows = list_photos(synthetic_lrcat, rating_gte=4)
    assert {r.uuid for r in rows} == {"uuid-001", "uuid-002"}

    rows = list_photos(synthetic_lrcat, rating_lte=2)
    assert {r.uuid for r in rows} == {"uuid-004", "uuid-005"}

    rows = list_photos(synthetic_lrcat, rating_gte=3, rating_lte=4)
    assert {r.uuid for r in rows} == {"uuid-002", "uuid-003"}


def test_list_camera_filter(synthetic_lrcat: Path) -> None:
    sony = list_photos(synthetic_lrcat, camera="Sony")
    assert {r.uuid for r in sony} == {"uuid-001", "uuid-002", "uuid-005"}

    nikon = list_photos(synthetic_lrcat, camera="Nikon")
    assert {r.uuid for r in nikon} == {"uuid-003", "uuid-004"}


def test_list_lens_filter(synthetic_lrcat: Path) -> None:
    rows = list_photos(synthetic_lrcat, lens="50mm")
    assert {r.uuid for r in rows} == {"uuid-001", "uuid-002", "uuid-005"}


def test_list_keyword_filter(synthetic_lrcat: Path) -> None:
    wedding = list_photos(synthetic_lrcat, keyword="wedding")
    assert {r.uuid for r in wedding} == {"uuid-001", "uuid-002"}

    landscape = list_photos(synthetic_lrcat, keyword="landscape")
    assert {r.uuid for r in landscape} == {"uuid-004", "uuid-005"}

    case_insensitive = list_photos(synthetic_lrcat, keyword="WEDDING")
    assert len(case_insensitive) == 2


def test_list_date_range(synthetic_lrcat: Path) -> None:
    april = list_photos(synthetic_lrcat, since="2026-04-01", until="2026-04-30T23:59:59")
    assert {r.uuid for r in april} == {"uuid-001", "uuid-002", "uuid-003"}


def test_list_limit(synthetic_lrcat: Path) -> None:
    rows = list_photos(synthetic_lrcat, limit=2)
    assert len(rows) == 2


def test_count_matches_list(synthetic_lrcat: Path) -> None:
    assert count_photos(synthetic_lrcat, rating_gte=4) == 2
    assert count_photos(synthetic_lrcat, camera="Sony", rating_gte=3) == 2


def test_missing_catalog_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        get_catalog_summary(tmp_path / "no-such.lrcat")


def test_wal_aware_open(synthetic_lrcat: Path) -> None:
    """When a non-empty ``.lrcat-wal`` exists, ``open_catalog`` must read the
    trio so it sees uncheckpointed changes — not silently miss them via
    ``immutable=1``.

    Reproduces the real bug we hit against Lightroom 15.3: 8 default smart
    collections were sitting in the WAL and our stats query returned 0.

    Lightroom keeps the catalog connection open while running, so the WAL
    persists on disk. Python's ``sqlite3`` runs a passive checkpoint on
    ``close()`` regardless of ``wal_autocheckpoint=0``, so we must hold the
    writer connection alive for the duration of the assertion.
    """
    import sqlite3

    # Switch to WAL mode (one-time setup).
    setup = sqlite3.connect(synthetic_lrcat)
    setup.execute("PRAGMA journal_mode=WAL")
    setup.commit()
    setup.close()

    # Open + write + leave open — mirrors Lightroom holding the catalog.
    writer = sqlite3.connect(synthetic_lrcat)
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute(
        "INSERT INTO AgLibraryCollection VALUES (?, ?, ?)",
        (99, None, "Late-arrival collection"),
    )
    writer.commit()
    try:
        wal = synthetic_lrcat.with_name(synthetic_lrcat.name + "-wal")
        assert wal.exists() and wal.stat().st_size > 0, (
            f"test setup: WAL should hold the row (size={wal.stat().st_size if wal.exists() else 'N/A'})"
        )

        # Sanity-check the bug: with the WAL persisted, ``immutable=1`` against
        # the main file alone misses the row. Our open_catalog must NOT do that.
        immutable = sqlite3.connect(f"file:{synthetic_lrcat}?mode=ro&immutable=1", uri=True)
        bare_count = immutable.execute("SELECT COUNT(*) FROM AgLibraryCollection").fetchone()[0]
        immutable.close()
        assert bare_count < 4, "test scaffolding: WAL row leaked into main file"

        # Now the real assertion — get_catalog_stats goes through open_catalog,
        # which must see the WAL row.
        s = get_catalog_stats(synthetic_lrcat)
        # Baseline: 2 collections (Picks/Rejects), 1 smart. + WAL row 'Late-arrival'
        # has creationId=NULL so it counts as regular => 3 collections, 1 smart.
        assert s.collections == 3, f"expected 3 (incl. WAL row), got {s.collections}"
        assert s.smart_collections == 1
    finally:
        writer.close()
