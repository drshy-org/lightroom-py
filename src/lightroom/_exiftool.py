"""ExifTool/XMP fast-path for batch metadata writes.

Why: writing keywords + IPTC on 5,000 photos via the bridge plugin one-at-a-time
is painfully slow. ExifTool can update XMP sidecars (or in-place for JPEG/TIFF/
PSD/DNG) in seconds, then we ask the bridge plugin to call ``photo:readMetadata()``
on those photos so the catalog picks up the changes.

This module wraps a single ``exiftool -stay_open`` process so we don't pay the
per-invocation startup cost. ``pyexiftool`` would do the same; we keep a small
in-tree implementation to avoid a hard dep (it's an extra: ``pip install
"lightroom-py[exiftool]"`` pulls pyexiftool, which we delegate to when present).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExifToolNotFoundError(RuntimeError):
    """ExifTool is not installed or not on PATH."""


def find_exiftool(extra_paths: list[Path] | None = None) -> Path:
    """Locate the ExifTool binary; raises if not found."""
    candidates: list[str | None] = [
        shutil.which("exiftool"),
        "/opt/homebrew/bin/exiftool",
        "/usr/local/bin/exiftool",
        "/usr/bin/exiftool",
        r"C:\Program Files\exiftool\exiftool.exe",
    ]
    if extra_paths:
        prefix: list[str | None] = [str(p) for p in extra_paths]
        candidates = prefix + candidates
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    raise ExifToolNotFoundError(
        "ExifTool not found on PATH. Install from https://exiftool.org/ or `brew install exiftool`."
    )


class ExifTool:
    """Persistent ExifTool process wrapper.

    Use as a context manager::

        with ExifTool() as et:
            et.write_tags(photo_path, {"Keywords": ["wedding", "bride"]})
            et.write_tags_batch({path1: {...}, path2: {...}})
    """

    def __init__(self, exiftool_path: str | Path | None = None) -> None:
        self.exiftool_path = Path(exiftool_path) if exiftool_path else find_exiftool()
        self._proc: subprocess.Popen[str] | None = None
        self._sentinel = "{ready}"

    def __enter__(self) -> ExifTool:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            [
                str(self.exiftool_path),
                "-stay_open",
                "True",
                "-@",
                "-",
                "-common_args",
                "-charset",
                "filename=utf8",
                "-G",
                "-j",
                "-sort",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env={**os.environ, "LANG": "en_US.UTF-8"},
        )

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            assert self._proc.stdin is not None
            self._proc.stdin.write("-stay_open\nFalse\n")
            self._proc.stdin.flush()
            self._proc.wait(timeout=5)
        except (BrokenPipeError, subprocess.TimeoutExpired):
            self._proc.kill()
        finally:
            self._proc = None

    def _execute(self, args: list[str]) -> str:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("ExifTool process not running")
        stdin = "\n".join(args + ["-execute"]) + "\n"
        self._proc.stdin.write(stdin)
        self._proc.stdin.flush()

        out_lines: list[str] = []
        for line in self._proc.stdout:
            line = line.rstrip("\r\n")
            if line.endswith(self._sentinel):
                break
            out_lines.append(line)
        return "\n".join(out_lines)

    def read_tags(self, path: str | Path) -> dict[str, Any]:
        """Read all metadata from a file as a dict."""
        out = self._execute([str(path)])
        if not out.strip():
            return {}
        try:
            return json.loads(out)[0]
        except (json.JSONDecodeError, IndexError):
            return {}

    def write_tags(self, path: str | Path, tags: dict[str, Any]) -> None:
        """Write the given tags to one file. Existing values are overwritten."""
        args = self._format_tags(tags) + ["-overwrite_original", str(path)]
        self._execute(args)

    def write_tags_batch(self, by_path: dict[str | Path, dict[str, Any]]) -> int:
        """Apply different tag dicts to many files in one batched call.

        Returns the number of files attempted.
        """
        if not by_path:
            return 0
        # Each (path, tags) is one -execute cycle. ExifTool doesn't support
        # interleaving different tag values for different paths in one cycle,
        # so we batch by tag-dict identity to amortize when callers pass the
        # same dict for many files.
        groups: dict[tuple[tuple[str, str], ...], list[Path]] = {}
        for path, tags in by_path.items():
            key = tuple(sorted((k, _stringify(v)) for k, v in tags.items()))
            groups.setdefault(key, []).append(Path(path))

        count = 0
        for key, paths in groups.items():
            tags = {k: _restringify(v) for k, v in key}
            args = self._format_tags(tags) + ["-overwrite_original"]
            args += [str(p) for p in paths]
            self._execute(args)
            count += len(paths)
        return count

    @staticmethod
    def _format_tags(tags: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for k, v in tags.items():
            if isinstance(v, list):
                # First clear, then add each value (so list semantics match).
                out.append(f"-{k}=")
                for item in v:
                    out.append(f"-{k}+={item}")
            elif v is None:
                out.append(f"-{k}=")
            else:
                out.append(f"-{k}={v}")
        return out


def _stringify(v: Any) -> str:
    if isinstance(v, list):
        return "\x00".join(str(x) for x in v)
    return f"|{v}"


def _restringify(s: str) -> Any:
    if s.startswith("|"):
        return s[1:]
    return s.split("\x00")
