"""Example: send selected photos through ImageMagick auto-level, restack.

Requires `magick` (ImageMagick) on PATH. Run with:
    python docs/examples/edit_in_imagemagick.py
"""

from __future__ import annotations

import asyncio

from lightroom import LightroomClient


async def main() -> None:
    async with LightroomClient.connect() as lr:
        # Use whatever's currently selected in LR.
        result = await lr.edit_in.run(
            ["magick", "{input}", "-auto-level", "{output}"],
            photo_uuids=None,  # None = active selection
            format="TIFF",
        )
        print(f"exported: {result['exported']}")
        print(f"processed: {result['processed']}")
        print(f"imported: {result['imported']}")
        if result["errors"]:
            print("\nerrors:")
            for e in result["errors"]:
                print(f"  - {e}")


if __name__ == "__main__":
    asyncio.run(main())
