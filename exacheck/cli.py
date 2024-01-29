# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Command line interface for the ExaCheck application.
"""

from pathlib import Path
from json import dumps

import click

from .__version__ import __version__
from .exacheck import ExaCheck
from .settings.settings import Settings


@click.group()
@click.help_option("-h", "--help")
@click.version_option(
    version=__version__,
    prog_name="ExaBGP ExaCheck Command Line Interface",
)
def cli() -> None:
    """
    ExaCheck - ExaBGP Health Checker

    Command line interface for the ExaCheck application.

    For full usage instructions see https://exacheck.net.
    """


@cli.command()
@click.help_option("-h", "--help")
@click.option(
    "-f",
    "--file",
    "file",
    help="The configuration file to load from",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    required=True,
    envvar="EXACHECK_CONFIG",
    default=Path("/etc/exabgp/exacheck.yaml"),
    show_default=True,
)
@click.option(
    "-v",
    "--verbose",
    "verbosity",
    help="Set output verbosity level - specify multiple times for further debugging",
    envvar="EXACHECK_VERBOSITY",
    count=True,
    default=1,
)
def run(
    file: Path,
    verbosity: int,
) -> None:
    """
    Run ExaCheck
    """
    # Create ExaCheck object
    exacheck = ExaCheck(
        file=file,
        verbosity=verbosity,
    )

    # Run ExaCheck
    exacheck.run()


@cli.command()
@click.help_option("-h", "--help")
def schema() -> None:
    """
    Dump JSON schema for ExaCheck configuration file to STDOUT
    """
    # Dump schema
    print(dumps(Settings.model_json_schema(), indent=4))


@cli.command()
@click.help_option("-h", "--help")
@click.option(
    "-f",
    "--file",
    "file",
    help="The configuration file to load from",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    required=True,
    envvar="EXACHECK_CONFIG",
    default=Path("/etc/exabgp/exacheck.yaml"),
    show_default=True,
)
@click.option(
    "-v",
    "--verbose",
    "verbosity",
    help="Set output verbosity level - specify multiple times for further debugging",
    envvar="EXACHECK_VERBOSITY",
    count=True,
    default=3,
)
def test(
    file: Path,
    verbosity: int,
) -> None:
    """
    Test ExaCheck configuration file
    """
    # Create ExaCheck object which will load the configuration file
    try:
        ExaCheck(
            file=file,
            verbosity=verbosity,
            dry_run=True,
        )
    except SystemExit as exc:  # NOSONAR
        raise click.Abort() from exc


if __name__ == "__main__":
    cli(obj={})  # pylint: disable=no-value-for-parameter
