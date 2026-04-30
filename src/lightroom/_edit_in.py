"""Edit-In sub-client: Topaz-style external-tool round-trip.

For ops the SDK can't reach (pixel-level edits, AI compute the SDK doesn't
expose), export selected photos to a temp dir, run an external tool on the
files, then re-import the results as stacked siblings of the originals.

Split: the Lua plugin handles export + reimport (catalog APIs); Python runs
the external command via ``subprocess`` between the two.

**Status (v0.3.0, verified against LR Classic 15.3):**

- :meth:`export` — ✅ exports selected photos to a target dir.
- :meth:`import_as_stack` — ✅ uses the canonical
  ``catalog:withWriteAccessDo(name, fn, {timeout=N})`` two-arg form.
- :meth:`run` — ✅ full export → external-cmd → reimport-as-stack round-trip.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ._core import ClientCore

logger = logging.getLogger(__name__)


class EditInAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def export(
        self,
        out_dir: str | Path,
        *,
        photo_uuids: Iterable[str] | None = None,
        format: str = "TIFF",
        quality: int = 95,
        color_space: str = "AdobeRGB",
    ) -> list[dict]:
        """Export selected photos to ``out_dir``.

        ``format`` is one of ``TIFF``, ``JPEG``, ``PSD``, ``DNG``, ``ORIGINAL``.
        Returns a list of ``{"uuid": str, "path": str}`` (or ``{"uuid", "error"}``
        if a particular photo failed to render).
        """
        result = await self._core.call(
            "edit_in.export",
            {
                "uuids": list(photo_uuids or []),
                "out_dir": str(Path(out_dir).expanduser().resolve()),
                "format": format,
                "quality": quality,
                "color_space": color_space,
            },
        )
        return list(result.get("exported") or [])

    async def import_as_stack(self, pairs: list[dict[str, str]]) -> dict:
        """Re-import processed files and stack each on top of its source photo.

        ``pairs`` is a list of ``{"src_uuid": "...", "result_path": "..."}``.
        Returns ``{"imported": [{"src_uuid", "new_uuid"}, ...], "errors": [...]}``.

        Uses the canonical ``catalog:withWriteAccessDo`` two-arg form per
        Adobe's SDK reference and Automaat/lightroom-mcp / lightroom-alt-text
        precedent. Verified against LR Classic 15.3 in v0.3.0.
        """
        if not pairs:
            raise ValueError("pairs must be a non-empty list")
        return await self._core.call(
            "edit_in.import_as_stack",
            {"pairs": pairs},
        )

    async def run(
        self,
        external_command: list[str],
        *,
        photo_uuids: Iterable[str] | None = None,
        format: str = "TIFF",
        out_dir: str | Path | None = None,
        cleanup_exports: bool = True,
    ) -> dict:
        """Full Topaz-style round-trip in one call.

        1. Tell LR to export selected photos to a temp directory.
        2. Run ``external_command`` on each exported file. The literal string
           ``{input}`` in the command list is replaced with the input file path
           and ``{output}`` with the output file path (defaults to a sibling
           with ``.processed`` before the extension if not present in the cmd).
        3. Re-import each result as a stacked sibling of the source photo.

        Returns ``{"exported": N, "processed": N, "imported": N, "errors": [...]}``.
        """
        cleanup = False
        if out_dir is None:
            out_dir_path = Path(tempfile.mkdtemp(prefix="lr-edit-in-"))
            cleanup = cleanup_exports
        else:
            out_dir_path = Path(out_dir).expanduser().resolve()
            out_dir_path.mkdir(parents=True, exist_ok=True)

        try:
            exported = await self.export(
                out_dir_path,
                photo_uuids=photo_uuids,
                format=format,
            )
            ok_exports = [e for e in exported if "path" in e]
            errors: list[dict[str, Any]] = [e for e in exported if "error" in e]

            pairs: list[dict[str, str]] = []
            for e in ok_exports:
                in_path = Path(e["path"])
                out_path = in_path.with_stem(in_path.stem + "-edited")

                cmd = [
                    arg.replace("{input}", str(in_path)).replace("{output}", str(out_path))
                    for arg in external_command
                ]
                # If the command didn't reference {output} we still want a
                # distinct result file. Default behaviour: assume the tool
                # writes back to the input file (in-place edit) and use that.
                if not any("{output}" in arg for arg in external_command):
                    out_path = in_path

                logger.info("running: %s", " ".join(cmd))
                proc = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    errors.append(
                        {
                            "uuid": e["uuid"],
                            "error": f"external command exit={proc.returncode}: {proc.stderr.strip()}",
                        }
                    )
                    continue
                pairs.append({"src_uuid": e["uuid"], "result_path": str(out_path)})

            imported_result = (
                await self.import_as_stack(pairs) if pairs else {"imported": [], "errors": []}
            )
            errors.extend(imported_result.get("errors") or [])

            return {
                "exported": len(ok_exports),
                "processed": len(pairs),
                "imported": len(imported_result.get("imported") or []),
                "errors": errors,
                "out_dir": str(out_dir_path),
            }
        finally:
            if cleanup and out_dir_path.exists():
                shutil.rmtree(out_dir_path, ignore_errors=True)
