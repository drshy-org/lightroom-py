"""Edit-In sub-client: Topaz-style external-tool round-trip.

For ops the SDK can't reach (pixel-level edits, AI compute the SDK doesn't
expose), export the selection as TIFF/JPEG, run an external tool on the file,
then re-import the result as a stacked sibling.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ._core import ClientCore

logger = logging.getLogger(__name__)


class EditInAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def run(
        self,
        external_command: list[str],
        *,
        photo_uuids: list[str] | None = None,
        export_format: str = "tiff",
        reimport_as_stack: bool = True,
    ) -> list[Path]:
        """Export → run command on each file → reimport as stack."""
        del external_command, photo_uuids, export_format, reimport_as_stack
        raise NotImplementedError
