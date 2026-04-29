"""Pytest fixtures shared across the suite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def _build_lrcat(path: Path) -> None:
    """Create a minimal Lightroom-shaped catalog with a few rows.

    Mirrors the subset of the real schema that ``lightroom._sqlite`` reads.
    Anything outside that subset is omitted on purpose to keep the fixture small.
    """
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.executescript(
        """
        PRAGMA user_version = 1100200;

        CREATE TABLE Adobe_images (
            id_local      INTEGER PRIMARY KEY,
            id_global     TEXT,
            captureTime   TEXT,
            rating        INTEGER,
            colorLabels   TEXT,
            fileFormat    TEXT,
            orientation   TEXT,
            rootFile      INTEGER
        );

        CREATE TABLE AgLibraryFile (
            id_local      INTEGER PRIMARY KEY,
            idx_filename  TEXT,
            baseName      TEXT,
            extension     TEXT,
            folder        INTEGER
        );

        CREATE TABLE AgLibraryFolder (
            id_local      INTEGER PRIMARY KEY,
            pathFromRoot  TEXT,
            rootFolder    INTEGER
        );

        CREATE TABLE AgLibraryRootFolder (
            id_local      INTEGER PRIMARY KEY,
            absolutePath  TEXT,
            name          TEXT
        );

        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY,
            name     TEXT,
            lc_name  TEXT
        );

        CREATE TABLE AgLibraryKeywordImage (
            tag   INTEGER,
            image INTEGER
        );

        CREATE TABLE AgLibraryCollection (
            id_local   INTEGER PRIMARY KEY,
            name       TEXT,
            creationId TEXT
        );

        CREATE TABLE AgInternedExifCameraModel (
            id_local INTEGER PRIMARY KEY,
            value    TEXT
        );

        CREATE TABLE AgInternedExifLens (
            id_local INTEGER PRIMARY KEY,
            value    TEXT
        );

        CREATE TABLE AgHarvestedExifMetadata (
            image           INTEGER PRIMARY KEY,
            cameraModelRef  INTEGER,
            lensRef         INTEGER
        );
        """
    )

    cur.executemany(
        "INSERT INTO AgLibraryRootFolder VALUES (?, ?, ?)",
        [(1, "/Volumes/Photos/", "Photos")],
    )
    cur.executemany(
        "INSERT INTO AgLibraryFolder VALUES (?, ?, ?)",
        [(10, "2026/04/", 1), (11, "2026/05/", 1)],
    )
    cur.executemany(
        "INSERT INTO AgLibraryFile VALUES (?, ?, ?, ?, ?)",
        [
            (100, "DSC_0001.NEF", "DSC_0001", "NEF", 10),
            (101, "DSC_0002.NEF", "DSC_0002", "NEF", 10),
            (102, "DSC_0003.NEF", "DSC_0003", "NEF", 11),
            (103, "DSC_0004.NEF", "DSC_0004", "NEF", 11),
            (104, "DSC_0005.NEF", "DSC_0005", "NEF", 11),
        ],
    )
    cur.executemany(
        "INSERT INTO AgInternedExifCameraModel VALUES (?, ?)",
        [(1, "Sony ILCE-7M4"), (2, "Nikon Z 6")],
    )
    cur.executemany(
        "INSERT INTO AgInternedExifLens VALUES (?, ?)",
        [(1, "Sony FE 50mm f/1.8"), (2, "NIKKOR Z 24-70mm f/4 S")],
    )
    cur.executemany(
        "INSERT INTO Adobe_images "
        "(id_local, id_global, captureTime, rating, colorLabels, fileFormat, "
        " orientation, rootFile) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "uuid-001", "2026-04-01T10:00:00", 5, "red", "RAW", "1", 100),
            (2, "uuid-002", "2026-04-02T11:00:00", 4, "", "RAW", "1", 101),
            (3, "uuid-003", "2026-04-03T12:00:00", 3, "yellow", "RAW", "1", 102),
            (4, "uuid-004", "2026-05-01T09:00:00", 2, "", "RAW", "1", 103),
            (5, "uuid-005", "2026-05-02T08:00:00", 0, "", "RAW", "1", 104),
        ],
    )
    cur.executemany(
        "INSERT INTO AgHarvestedExifMetadata VALUES (?, ?, ?)",
        [(1, 1, 1), (2, 1, 1), (3, 2, 2), (4, 2, 2), (5, 1, 1)],
    )
    cur.executemany(
        "INSERT INTO AgLibraryKeyword VALUES (?, ?, ?)",
        [(1, "Wedding", "wedding"), (2, "Bride", "bride"), (3, "Landscape", "landscape")],
    )
    cur.executemany(
        "INSERT INTO AgLibraryKeywordImage VALUES (?, ?)",
        [(1, 1), (2, 1), (1, 2), (3, 4), (3, 5)],
    )
    cur.executemany(
        "INSERT INTO AgLibraryCollection VALUES (?, ?, ?)",
        [
            (1, "Picks", None),
            (2, "Rejects", None),
            (3, "5-star", "com.adobe.ag.library.smart_collection"),
        ],
    )

    conn.commit()
    conn.close()


@pytest.fixture
def synthetic_lrcat(tmp_path: Path) -> Path:
    """Build and return the path to a freshly-baked tiny .lrcat."""
    p = tmp_path / "Test.lrcat"
    _build_lrcat(p)
    return p


@pytest.fixture
def lightroom_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate ~/.lightroom for the duration of a test."""
    home = tmp_path / "lr-home"
    monkeypatch.setenv("LIGHTROOM_HOME", str(home))
    return home
