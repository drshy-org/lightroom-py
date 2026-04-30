"""Example: cull a shoot.

Find photos imported in a date range, rate the ones with the right keywords,
add a "Picks" collection. Idiomatic agent-driven flow.

Run with:
    python docs/examples/cull_workflow.py /path/to/Catalog.lrcat
"""

from __future__ import annotations

import asyncio
import sys

from lightroom import LightroomClient


async def main(catalog_path: str) -> None:
    async with LightroomClient.connect() as lr:
        # Activate this catalog for the session.
        info = await lr.catalog.open(catalog_path)
        print(f"opened {info.path} ({info.photo_count} photos)")

        # Pull recent imports from this morning.
        recent = await lr.photos.list(since="2026-04-29T00:00:00", limit=200)
        print(f"\n{len(recent)} photos to cull")

        if not recent:
            return

        # Rate top 10 as 5-star (in real life: do this from a real preview).
        keepers = [p.uuid for p in recent[:10]]
        await lr.metadata.set_rating(5, photo_uuids=keepers)
        await lr.metadata.add_keywords(["Wedding|2026", "Portrait"], photo_uuids=keepers)
        print(f"rated {len(keepers)} keepers as 5-star + tagged with hierarchical keyword")

        # Make a collection for them.
        await lr.collections.create("Picks 2026-04-29", parent=None)
        await lr.collections.add("Picks 2026-04-29", keepers)
        print("added to collection")

        # Apply a develop preset to all keepers.
        await lr.develop.apply_preset(
            "Pop", folder="Adaptive: Subject", photo_uuids=keepers
        )
        print("applied 'Pop' develop preset")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
