"""CLI entry point — dispatches to ``lightroom.cli.*`` subcommand modules."""

from __future__ import annotations

import logging

import click

from . import __version__
from ._logging import configure as _configure_logging
from .cli import (
    ai,
    bridge,
    catalog,
    collections,
    develop,
    doctor,
    edit_in,
    library,
    metadata,
    photos,
    skill,
)
from .cli import (
    setup as setup_cmd,
)

logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="lightroom")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable debug logging.",
)
def cli(verbose: bool) -> None:
    """lightroom — automate Adobe Lightroom Classic from Python and the CLI.

    Run ``lightroom doctor`` to verify the bridge is installed and working.
    """
    _configure_logging("DEBUG" if verbose else None)


cli.add_command(setup_cmd.setup)
cli.add_command(doctor.doctor)
cli.add_command(bridge.bridge)
cli.add_command(catalog.catalog)
cli.add_command(photos.photos)
cli.add_command(metadata.metadata)
cli.add_command(develop.develop)
cli.add_command(collections.collections)
cli.add_command(library.library)
cli.add_command(ai.ai)
cli.add_command(edit_in.edit_in)
cli.add_command(skill.skill)


def main() -> None:  # pragma: no cover
    cli(standalone_mode=True)


if __name__ == "__main__":  # pragma: no cover
    main()
