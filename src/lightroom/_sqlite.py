"""SQLite read fast-path for the Lightroom catalog (.lrcat).

Lightroom's catalog is plain SQLite. We treat it as **strictly read-only** —
the schema is undocumented and Lightroom holds locks while running. Writes
always go through the bridge plugin.

Strategy:

- Open the catalog ``immutable=1`` via SQLite URI so we never even try to
  acquire a lock. This works even while Lightroom has the file open.
- If that fails (e.g. some FS configurations), fall back to copying the
  ``.lrcat`` to a temp location and opening the copy.

Schema notes (community-documented, may shift between LR versions):

    Adobe_images           — core photo records (id_local, captureTime,
                             rating, colorLabels, fileFormat, orientation,
                             rootFile -> AgLibraryFile.id_local)
    AgLibraryFile          — file row (id_local, idx_filename, baseName,
                             extension, folder -> AgLibraryFolder.id_local)
    AgLibraryFolder        — folders (id_local, pathFromRoot,
                             rootFolder -> AgLibraryRootFolder.id_local)
    AgLibraryRootFolder    — drive roots (id_local, absolutePath, name)
    AgLibraryKeyword       — keyword tree
    AgLibraryKeywordImage  — many-to-many (image, tag)
    AgLibraryCollection    — user collections
    AgLibraryCollectionImage  — collection membership
    AgLibraryIPTC          — IPTC fields (caption, copyright, ...)
    AgHarvestedExifMetadata — EXIF (camera model, lens, ISO, focal length, ...)
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------- known LR id_local mappings for ratings / color labels ----------

COLOR_LABEL_NAMES = {
    "": None,
    "red": "red",
    "yellow": "yellow",
    "green": "green",
    "blue": "blue",
    "purple": "purple",
}


# ---------- low-level connection helper ----------


@contextmanager
def open_catalog(catalog_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a catalog read-only. Falls back to a tempfile copy if needed.

    Use this as a context manager::

        with open_catalog(path) as conn:
            cur = conn.execute("SELECT count(*) FROM Adobe_images")
    """
    path = Path(catalog_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"catalog not found: {path}")

    uri = f"file:{path}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as exc:
        logger.debug("immutable open failed (%s); falling back to copy", exc)
        with tempfile.TemporaryDirectory(prefix="lr-py-") as td:
            copy = Path(td) / path.name
            shutil.copy2(path, copy)
            conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
            try:
                conn.row_factory = sqlite3.Row
                yield conn
            finally:
                conn.close()
            return

    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


# ---------- public read API ----------


@dataclass(slots=True)
class CatalogStats:
    photos: int
    folders: int
    keywords: int
    collections: int
    smart_collections: int


@dataclass(slots=True)
class CatalogSummary:
    path: Path
    sqlite_user_version: int | None
    photos: int
    earliest_capture: str | None
    latest_capture: str | None


@dataclass(slots=True)
class PhotoRow:
    uuid: str  # Adobe_images.id_global
    id_local: int
    filename: str | None
    capture_time: str | None
    rating: int | None
    color_label: str | None
    file_format: str | None
    folder_path: str | None
    camera: str | None
    lens: str | None


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return None if row is None else row[0]


def get_catalog_summary(catalog_path: str | Path) -> CatalogSummary:
    """High-level snapshot of a catalog: photo count, capture-time bounds."""
    with open_catalog(catalog_path) as conn:
        version = _scalar(conn, "PRAGMA user_version")
        photos = _scalar(conn, "SELECT COUNT(*) FROM Adobe_images") or 0
        earliest = _scalar(
            conn,
            "SELECT MIN(captureTime) FROM Adobe_images WHERE captureTime IS NOT NULL",
        )
        latest = _scalar(
            conn,
            "SELECT MAX(captureTime) FROM Adobe_images WHERE captureTime IS NOT NULL",
        )
    return CatalogSummary(
        path=Path(catalog_path).resolve(),
        sqlite_user_version=int(version) if version is not None else None,
        photos=int(photos),
        earliest_capture=earliest,
        latest_capture=latest,
    )


def get_catalog_stats(catalog_path: str | Path) -> CatalogStats:
    """Counts that are cheap regardless of catalog size."""
    with open_catalog(catalog_path) as conn:
        photos = int(_scalar(conn, "SELECT COUNT(*) FROM Adobe_images") or 0)
        folders = (
            int(_scalar(conn, "SELECT COUNT(*) FROM AgLibraryFolder") or 0)
            if _table_exists(conn, "AgLibraryFolder")
            else 0
        )
        keywords = (
            int(_scalar(conn, "SELECT COUNT(*) FROM AgLibraryKeyword") or 0)
            if _table_exists(conn, "AgLibraryKeyword")
            else 0
        )
        collections = 0
        smart_collections = 0
        if _table_exists(conn, "AgLibraryCollection"):
            collections = int(
                _scalar(
                    conn,
                    "SELECT COUNT(*) FROM AgLibraryCollection "
                    "WHERE creationId NOT LIKE '%smart%' OR creationId IS NULL",
                )
                or 0
            )
            smart_collections = int(
                _scalar(
                    conn,
                    "SELECT COUNT(*) FROM AgLibraryCollection WHERE creationId LIKE '%smart%'",
                )
                or 0
            )
    return CatalogStats(
        photos=photos,
        folders=folders,
        keywords=keywords,
        collections=collections,
        smart_collections=smart_collections,
    )


def list_photos(
    catalog_path: str | Path,
    *,
    rating_gte: int | None = None,
    rating_lte: int | None = None,
    camera: str | None = None,
    lens: str | None = None,
    keyword: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int | None = None,
) -> list[PhotoRow]:
    """Filter Adobe_images via SQL; return uniform :class:`PhotoRow`s.

    All filters are AND-ed. ``since`` / ``until`` accept any string SQLite
    will compare lexicographically with ``Adobe_images.captureTime`` (LR
    stores capture time as ISO-ish ``YYYY-MM-DDTHH:MM:SS``).
    """
    where: list[str] = []
    params: list[Any] = []

    if rating_gte is not None:
        where.append("img.rating >= ?")
        params.append(rating_gte)
    if rating_lte is not None:
        where.append("img.rating <= ?")
        params.append(rating_lte)
    if since is not None:
        where.append("img.captureTime >= ?")
        params.append(since)
    if until is not None:
        where.append("img.captureTime <= ?")
        params.append(until)
    if camera is not None:
        where.append(
            "EXISTS (SELECT 1 FROM AgHarvestedExifMetadata e "
            "JOIN AgInternedExifCameraModel m ON m.id_local = e.cameraModelRef "
            "WHERE e.image = img.id_local AND m.value LIKE ?)"
        )
        params.append(f"%{camera}%")
    if lens is not None:
        where.append(
            "EXISTS (SELECT 1 FROM AgHarvestedExifMetadata e "
            "JOIN AgInternedExifLens l ON l.id_local = e.lensRef "
            "WHERE e.image = img.id_local AND l.value LIKE ?)"
        )
        params.append(f"%{lens}%")
    if keyword is not None:
        where.append(
            "EXISTS (SELECT 1 FROM AgLibraryKeywordImage ki "
            "JOIN AgLibraryKeyword k ON k.id_local = ki.tag "
            "WHERE ki.image = img.id_local AND k.lc_name = ?)"
        )
        params.append(keyword.lower())

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    sql = f"""
        SELECT
          img.id_local         AS id_local,
          img.id_global        AS uuid,
          img.captureTime      AS capture_time,
          img.rating           AS rating,
          img.colorLabels      AS color_label,
          img.fileFormat       AS file_format,
          file.idx_filename    AS filename,
          folder.pathFromRoot  AS folder_path
        FROM Adobe_images img
        LEFT JOIN AgLibraryFile   file   ON file.id_local   = img.rootFile
        LEFT JOIN AgLibraryFolder folder ON folder.id_local = file.folder
        {where_sql}
        ORDER BY img.captureTime DESC
        {limit_sql}
    """

    out: list[PhotoRow] = []
    with open_catalog(catalog_path) as conn:
        try:
            cur = conn.execute(sql, params)
        except sqlite3.OperationalError as exc:
            # Some EXIF tables may not exist on very old / very new catalogs;
            # retry without those joins by stripping camera/lens filters.
            logger.warning("photo query failed (%s); retrying without camera/lens filters", exc)
            return list_photos(
                catalog_path,
                rating_gte=rating_gte,
                rating_lte=rating_lte,
                camera=None,
                lens=None,
                keyword=keyword,
                since=since,
                until=until,
                limit=limit,
            )
        camera_by_id, lens_by_id = _exif_lookup(conn, [r["id_local"] for r in cur.fetchall()])
        # Re-run because we consumed cur above:
        cur = conn.execute(sql, params)
        for row in cur:
            out.append(
                PhotoRow(
                    uuid=row["uuid"],
                    id_local=row["id_local"],
                    filename=row["filename"],
                    capture_time=row["capture_time"],
                    rating=row["rating"],
                    color_label=row["color_label"] or None,
                    file_format=row["file_format"],
                    folder_path=row["folder_path"],
                    camera=camera_by_id.get(row["id_local"]),
                    lens=lens_by_id.get(row["id_local"]),
                )
            )
    return out


def count_photos(
    catalog_path: str | Path,
    **filters: Any,
) -> int:
    """Count photos matching the same filters as :func:`list_photos`."""
    # Reuse list_photos for filter parity but only fetch ids.
    rows = list_photos(catalog_path, **filters)
    return len(rows)


def resolve_paths(catalog_path: str | Path, uuids: list[str]) -> dict[str, Path]:
    """Resolve photo UUIDs (Adobe_images.id_global) to absolute file paths.

    Returns a dict mapping UUID -> Path. UUIDs that don't resolve are omitted.
    """
    if not uuids:
        return {}
    placeholders = ",".join("?" * len(uuids))
    sql = f"""
        SELECT
          img.id_global       AS uuid,
          root.absolutePath   AS root_path,
          folder.pathFromRoot AS folder_path,
          file.idx_filename   AS filename
        FROM Adobe_images img
        JOIN AgLibraryFile        file   ON file.id_local   = img.rootFile
        JOIN AgLibraryFolder      folder ON folder.id_local = file.folder
        JOIN AgLibraryRootFolder  root   ON root.id_local   = folder.rootFolder
        WHERE img.id_global IN ({placeholders})
    """
    out: dict[str, Path] = {}
    with open_catalog(catalog_path) as conn:
        cur = conn.execute(sql, uuids)
        for row in cur:
            root = (row["root_path"] or "").rstrip("/")
            folder = (row["folder_path"] or "").lstrip("/")
            filename = row["filename"] or ""
            if not (root and filename):
                continue
            out[row["uuid"]] = Path(root) / folder / filename
    return out


def _exif_lookup(
    conn: sqlite3.Connection, image_ids: list[int]
) -> tuple[dict[int, str], dict[int, str]]:
    """Bulk-lookup camera + lens strings for a list of image id_locals."""
    if not image_ids:
        return {}, {}
    if not _table_exists(conn, "AgHarvestedExifMetadata"):
        return {}, {}

    placeholders = ",".join("?" * len(image_ids))
    cam: dict[int, str] = {}
    lens: dict[int, str] = {}

    try:
        cur = conn.execute(
            f"""
            SELECT e.image, m.value
              FROM AgHarvestedExifMetadata e
              JOIN AgInternedExifCameraModel m ON m.id_local = e.cameraModelRef
             WHERE e.image IN ({placeholders})
            """,
            image_ids,
        )
        for row in cur:
            cam[int(row[0])] = row[1]
    except sqlite3.OperationalError:
        pass

    try:
        cur = conn.execute(
            f"""
            SELECT e.image, l.value
              FROM AgHarvestedExifMetadata e
              JOIN AgInternedExifLens l ON l.id_local = e.lensRef
             WHERE e.image IN ({placeholders})
            """,
            image_ids,
        )
        for row in cur:
            lens[int(row[0])] = row[1]
    except sqlite3.OperationalError:
        pass

    return cam, lens
